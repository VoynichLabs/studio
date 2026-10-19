"""
Author: Claude Opus 5.5 Medium
Date: 19-October-2026
PURPOSE: Writes standard MIDI files (type 1) from the band maker's note lists, with no outside
library. Each track gets its own channel, instrument, volume, pan, reverb and chorus settings; drums
go on the General MIDI drum channel. A silent tail is added at the end so reverb rings out instead
of being cut off when the instrument player reaches the end of the file. Used by band/render.py.
SRP/DRY check: Pass - the only code that knows the MIDI byte format.
"""

import struct

from .parts import TPB

DRUM_CHANNEL = 9
TAIL_SECONDS = 2.5


def _vlq(n: int) -> bytes:
    """MIDI variable-length number: seven bits per byte, high bit set on all but the last."""
    out = [n & 0x7F]
    n >>= 7
    while n:
        out.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(out))


def _chunk(kind: bytes, body: bytes) -> bytes:
    return kind + struct.pack(">I", len(body)) + body


def _track_bytes(timed: list, end_tick: int) -> bytes:
    """timed: [(tick, order, raw_event_bytes)] -> one MTrk body with delta times."""
    body, now = bytearray(), 0
    for tick, _, data in sorted(timed, key=lambda e: (e[0], e[1])):
        body += _vlq(tick - now) + data
        now = tick
    body += _vlq(max(0, end_tick - now)) + b"\xff\x2f\x00"   # end of track
    return bytes(body)


def channels_for(tracks) -> dict:
    """Give each track a channel, skipping the drum channel for pitched instruments."""
    free = [c for c in range(16) if c != DRUM_CHANNEL]
    out = {}
    for t in tracks:
        if t.drums:
            out[t.name] = DRUM_CHANNEL
        else:
            if not free:
                raise ValueError("too many pitched tracks (fifteen is the limit)")
            out[t.name] = free.pop(0)
    return out


def write_midi(path, song, track_events: dict, only=None):
    """track_events: track name -> [(tick, length, pitch, velocity)]. `only` limits to some tracks
    (used for single-instrument stems) while keeping every track's channel the same."""
    channels = channels_for(song.tracks.values())
    last = max((t + d for evs in track_events.values() for t, d, _, _ in evs), default=0)
    end_tick = last + int(TAIL_SECONDS * song.tempo / 60 * TPB)

    usec_per_beat = int(60_000_000 / song.tempo)
    tempo_track = [
        (0, 0, b"\xff\x51\x03" + usec_per_beat.to_bytes(3, "big")),
        (0, 0, b"\xff\x58\x04" + bytes([song.meter, 2, 24, 8])),   # meter / quarter note
    ]
    chunks = [_track_bytes(tempo_track, end_tick)]

    for t in song.tracks.values():
        if only is not None and t.name not in only:
            continue
        ch = channels[t.name]
        name = t.name.encode()
        setup = [
            (0, 0, b"\xff\x03" + _vlq(len(name)) + name),
            (0, 1, bytes([0xC0 | ch, t.program])),
            (0, 2, bytes([0xB0 | ch, 7, round(t.volume * 127)])),
            (0, 2, bytes([0xB0 | ch, 10, round((t.pan + 1) * 63.5)])),
            (0, 2, bytes([0xB0 | ch, 91, round(t.reverb * 127)])),
            (0, 2, bytes([0xB0 | ch, 93, round(t.chorus * 127)])),
        ]
        notes = []
        for tick, length, pitch, vel in track_events.get(t.name, []):
            if not 0 <= pitch <= 127:
                continue  # an octave setting pushed a note off the keyboard; skip it quietly
            # Order 3 (off) sorts before 4 (on) at the same tick so repeated notes re-strike.
            notes.append((tick + 1, 4, bytes([0x90 | ch, pitch, vel])))
            notes.append((tick + 1 + max(1, length), 3, bytes([0x80 | ch, pitch, 0])))
        chunks.append(_track_bytes(setup + notes, end_tick))

    header = _chunk(b"MThd", struct.pack(">HHH", 1, len(chunks), TPB))
    with open(path, "wb") as f:
        f.write(header + b"".join(_chunk(b"MTrk", c) for c in chunks))
