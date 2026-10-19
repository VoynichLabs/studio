"""
Author: Claude Opus 5.5 Medium
Date: 19-October-2026
PURPOSE: Turns each track's parts in a Song into timed notes. This is the "band": a chord chart plus
a playing style (held pad, struck chords, strummed guitar, arpeggio, bass roots, root-fifth,
octaves) or a written melody, and drum grids in sixteenth-note steps. Adds swing and a small seeded
human feel so repeats don't sound machine-stamped, and so the same song file always renders the same.
Reads band/song.py objects, uses band/theory.py and band/instruments.py, feeds band/midi.py.
SRP/DRY check: Pass - all note generation lives here; one grid reader and one chord reader serve
every style.
"""

import random
import re

from . import instruments, theory
from .song import Song, SongError

TPB = 480                 # MIDI ticks per beat (quarter note)
STEP = TPB // 4           # one sixteenth-note grid step
HIT_CHARS = {"X": 22, "x": 0, "o": -35}   # loud accent, normal, soft ghost note
GRID_CHARS = set(HIT_CHARS) | {".", "-"}

PITCHED_STYLES = {"pad", "block", "strum", "arp", "root", "root-fifth", "octave", "notes"}
PITCHED_KEYS = {"style", "rhythm", "octave", "velocity", "pattern", "notes", "strum", "gate"}
DEFAULT_RHYTHM = {
    "block": "x---x---x---x---", "strum": "x---x---x---x---", "arp": "x-x-x-x-x-x-x-x-",
    "root": "x-------x-------", "root-fifth": "x-------x-------", "octave": "x-x-x-x-x-x-x-x-",
}
DURATIONS = {"w": 4 * TPB, "h": 2 * TPB, "q": TPB, "e": TPB // 2, "s": TPB // 4}


# ---------------------------------------------------------------- shared readers

def read_grid(grid: str, total_steps: int, where: str, tile: bool = True):
    """'x---x.o.' -> [(step, length_in_steps, accent)]. The grid repeats to fill the section
    unless tile is False (then the rest is silence). '-' holds the previous hit, '.' is a rest."""
    cells = grid.replace("|", "").replace(" ", "")
    bad = set(cells) - GRID_CHARS
    if not cells or bad:
        raise SongError(f"{where}: rhythm '{grid}' may only use x X o - . and | between bars")
    seq = (cells * (total_steps // len(cells) + 1))[:total_steps] if tile else cells[:total_steps]
    hits = []
    for i, c in enumerate(seq):
        if c in HIT_CHARS:
            hits.append([i, 1, HIT_CHARS[c]])
        elif c == "-" and hits and hits[-1][0] + hits[-1][1] == i:
            hits[-1][1] += 1
    return [tuple(h) for h in hits]


def read_chords(chart: str, bars: int, steps_per_bar: int, where: str):
    """'Am | F | C G | G' -> [(start_step, end_step, Chord or None)], repeated to fill the section.
    In a bar, chords share the bar evenly; '-' holds the previous chord, '%' repeats the last bar,
    'N' is no chord. Back-to-back identical chords merge so pads don't re-strike every bar."""
    written = [b.split() for b in chart.split("|") if b.strip()] if chart.strip() else [["N"]]
    spans, last_bar = [], None
    for bar_index in range(bars):
        tokens = written[bar_index % len(written)]
        if tokens == ["%"]:
            if last_bar is None:
                raise SongError(f"{where}: '%' repeats the previous bar, but there isn't one")
            tokens = last_bar
        last_bar = tokens
        width = steps_per_bar / len(tokens)
        for k, tok in enumerate(tokens):
            start = bar_index * steps_per_bar + round(k * width)
            end = bar_index * steps_per_bar + round((k + 1) * width)
            if tok == "-" and spans:
                spans[-1][1] = end
                continue
            try:
                chord = None if tok in ("N", "-") else theory.parse_chord(tok)
            except ValueError as e:
                raise SongError(f"{where}: {e}") from None
            if spans and spans[-1][1] == start and _same(spans[-1][2], chord):
                spans[-1][1] = end
            else:
                spans.append([start, end, chord])
    return [tuple(s) for s in spans]


def _same(a, b):
    return (a is None and b is None) or (a is not None and b is not None and a.symbol == b.symbol)


def chord_at(spans, step):
    for start, end, chord in spans:
        if start <= step < end:
            return chord, end
    return None, step + 1


# ---------------------------------------------------------------- feel

class Feel:
    """Swing and a little human looseness, seeded so renders repeat exactly."""

    def __init__(self, song: Song, seed_key: str, tight: bool):
        self.swing = song.swing
        self.rng = random.Random(f"{song.seed}:{seed_key}")
        self.timing_sd = 3 if tight else 7
        self.vel_sd = 4

    def tick(self, step: int) -> int:
        base = step * STEP
        pos = step % 4
        # Full swing pushes the off-beat eighth to the triplet spot (a sixth of a beat late).
        if pos == 2:
            base += round(self.swing * TPB / 6)
        elif pos == 3:
            base += round(self.swing * TPB / 12)
        return base

    def loosen(self, tick: int, velocity: int):
        t = tick + round(max(-12, min(12, self.rng.gauss(0, self.timing_sd))))
        v = velocity + round(self.rng.gauss(0, self.vel_sd))
        return max(0, t), max(1, min(127, v))


# ---------------------------------------------------------------- melodies

_NOTE_TOKEN = re.compile(r"^([^:]+):([whqes][.t]?(?:~[whqes][.t]?)*)([!?]?)$")


def _length(code: str) -> int:
    total = 0
    for piece in code.split("~"):
        ticks = DURATIONS[piece[0]]
        if piece.endswith("."):
            ticks = ticks * 3 // 2
        elif piece.endswith("t"):
            ticks = ticks * 2 // 3
        total += ticks
    return total


def read_melody(text: str, where: str):
    """'A4:q C5:e. r:s E4,G4:h!' -> [(offset_ticks, length_ticks, [pitches], accent)].
    r is a rest, commas stack notes, ~ ties lengths, ! is loud, ? is soft, | is ignored."""
    out, at = [], 0
    for tok in text.replace("|", " ").split():
        m = _NOTE_TOKEN.match(tok)
        if not m:
            raise SongError(f"{where}: '{tok}' should look like A4:q, r:e or C4,E4:h (w h q e s, . dotted, t triplet)")
        names, code, mark = m.groups()
        length = _length(code)
        if names != "r":
            try:
                pitches = [theory.parse_pitch(n) for n in names.split(",")]
            except ValueError as e:
                raise SongError(f"{where}: {e}") from None
            out.append((at, length, pitches, 22 if mark == "!" else -30 if mark == "?" else 0))
        at += length
    if at == 0:
        raise SongError(f"{where}: the melody is empty")
    return out, at


# ---------------------------------------------------------------- builders

def _drum_events(part, track, total_steps, steps_per_bar, feel, where):
    allowed_extra = {"velocity", "first", "fill"}
    base_vel = part.get("velocity", track.velocity)
    first = part.get("first", {})
    fill = part.get("fill", {})
    if not isinstance(first, dict) or not isinstance(fill, dict):
        raise SongError(f"{where}: first and fill should be drum grids, like fill = {{ snare = \"x.x.xxxx\" }}")
    last_bar_start = total_steps - steps_per_bar
    events = []
    pieces = {k: v for k, v in part.items() if k not in allowed_extra}
    for piece in set(pieces) | set(fill) | set(first):
        try:
            note = instruments.drum_note(piece)
        except ValueError as e:
            raise SongError(f"{where}: {e}") from None
        hits = []
        if piece in pieces:
            hits = read_grid(pieces[piece], total_steps, where)
            if piece in fill:   # the fill replaces this piece's last bar
                hits = [h for h in hits if h[0] < last_bar_start]
        if piece in fill:
            hits += [(s + last_bar_start, n, a)
                     for s, n, a in read_grid(fill[piece], steps_per_bar, where, tile=False)]
        if piece in first:
            hits += read_grid(first[piece], steps_per_bar, where, tile=False)
        for step, length, accent in hits:
            tick, vel = feel.loosen(feel.tick(step), base_vel + accent)
            events.append((tick, max(STEP, length * STEP), note, vel))
    return events


def _pitched_events(part, track, section, song, feel, state, where):
    unknown = set(part) - PITCHED_KEYS
    if unknown:
        raise SongError(f"{where}: unknown setting(s) {', '.join(sorted(unknown))}")
    style = part.get("style", "notes" if "notes" in part else "block")
    if style not in PITCHED_STYLES:
        raise SongError(f"{where}: style '{style}' isn't one of {', '.join(sorted(PITCHED_STYLES))}")
    octave = part.get("octave", track.octave)
    base_vel = part.get("velocity", track.velocity)
    gate = part.get("gate", 0.95)
    spb = song.steps_per_bar
    total = section.bars * spb
    events = []

    if style == "notes":
        if "notes" not in part:
            raise SongError(f"{where}: style notes needs notes = \"...\"")
        melody, loop = read_melody(part["notes"], where)
        end_tick = total * STEP
        for rep in range(0, end_tick, loop):
            for off, length, pitches, accent in melody:
                start = rep + off
                if start >= end_tick:
                    break
                for p in pitches:
                    t, v = feel.loosen(start, base_vel + accent)
                    events.append((t, max(30, int(min(length, end_tick - start) * gate)), p, v))
        return events

    spans = read_chords(section.chords, section.bars, spb, where)
    center = (octave + 1) * 12 + 4

    if style == "pad":
        for start, end, chord in spans:
            if chord is None:
                continue
            notes = theory.voice_chord(chord, center, state.get("voicing"))
            state["voicing"] = notes
            for p in notes:
                t, v = feel.loosen(feel.tick(start), base_vel)
                events.append((t, int((end - start) * STEP * gate), p, v))
        return events

    hits = read_grid(part.get("rhythm", DEFAULT_RHYTHM[style]), total, where)
    pattern = part.get("pattern", "up")
    strum_ticks = part.get("strum", 18)
    arp_index, arp_chord = 0, None
    for n, (step, length, accent) in enumerate(hits):
        chord, chord_end = chord_at(spans, step)
        if chord is None:
            continue
        length = min(length, chord_end - step)      # never ring past a chord change
        tick = feel.tick(step)
        dur = max(30, int(length * STEP * gate))
        vel = base_vel + accent
        if style in ("block", "strum"):
            notes = theory.voice_chord(chord, center, state.get("voicing"))
            state["voicing"] = notes
            if style == "strum":
                # Down-strums on the beat, up-strums off it, like a guitarist's hand.
                down = step % 4 == 0
                order = notes if down else list(reversed(notes))
                for k, p in enumerate(order):
                    t, v = feel.loosen(tick + k * strum_ticks, vel - (0 if down else 12))
                    events.append((t, max(30, dur - k * strum_ticks), p, v))
            else:
                for p in notes:
                    t, v = feel.loosen(tick, vel)
                    events.append((t, dur, p, v))
        elif style == "arp":
            if chord is not arp_chord:
                arp_chord, arp_index = chord, 0
                state["voicing"] = theory.voice_chord(chord, center, state.get("voicing"))
            tones = state["voicing"] + [state["voicing"][0] + 12]
            if pattern == "down":
                seq = list(reversed(tones))
            elif pattern == "updown":
                seq = tones + list(reversed(tones[1:-1]))
            else:
                seq = tones
            p = seq[arp_index % len(seq)]
            arp_index += 1
            t, v = feel.loosen(tick, vel)
            events.append((t, dur, p, v))
        else:  # bass styles
            p = theory.bass_pitch(
                chord, octave,
                fifth=(style == "root-fifth" and n % 2 == 1),
                up_octave=(style == "octave" and n % 2 == 1))
            t, v = feel.loosen(tick, vel)
            events.append((t, dur, p, v))
    return events


def build_track(song: Song, track) -> list:
    """All notes for one track across the whole song: [(tick, length, pitch, velocity)]."""
    events, bar_offset, state = [], 0, {}
    for index, name in enumerate(song.order):
        section = song.sections[name]
        part = section.parts.get(track.name)
        if part is not None:
            where = f"section '{name}', track '{track.name}'"
            feel = Feel(song, f"{track.name}:{index}", tight=track.drums)
            total = section.bars * song.steps_per_bar
            if track.drums:
                local = _drum_events(part, track, total, song.steps_per_bar, feel, where)
            else:
                local = _pitched_events(part, track, section, song, feel, state, where)
            offset = bar_offset * song.steps_per_bar * STEP
            events += [(t + offset, d, p, v) for t, d, p, v in local]
        bar_offset += section.bars
    return sorted(events)
