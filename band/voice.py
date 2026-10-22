"""
Author: Claude Opus 5.5 Medium
Date: 22-October-2026
PURPOSE: Saves and cleans the Boss's recorded takes. The studio window sends raw microphone samples
plus the song time where the take started. This module writes them as a WAV on the Samsung drive,
then makes a cleaned copy with ffmpeg: rumble cut, background-noise removal, softened "s" sounds,
even volume, a touch of echo, and a steady level. It then adds the take to the song file as a voice
so the next render includes it. Used by server.py.
SRP/DRY check: Pass - take saving and cleanup only; song file writes go through band/edit.py.
"""

import array
import wave
from pathlib import Path

from . import edit
from .render import OUT, SAMPLE_RATE, _ffmpeg

# Order matters: cut rumble first so the noise reducer and compressor don't chase it.
CLEANUP = ",".join([
    "highpass=f=80",
    "afftdn=nf=-28",                       # learns and removes steady background hiss/hum
    "deesser=i=0.4",
    "acompressor=threshold=-20dB:ratio=3:attack=5:release=120:makeup=2",
    "aecho=0.8:0.55:70|140:0.12|0.06",     # a small room, not a cave
    "loudnorm=I=-18:TP=-2:LRA=7",
])


def next_take_name(song) -> str:
    n = 1
    while f"take-{n}" in song.voices:
        n += 1
    return f"take-{n}"


def save_take(song, song_name: str, samples: bytes, rate: int, start: float) -> str:
    """samples: little-endian 32-bit float mono. Returns the new voice's name."""
    takes = OUT / song_name / "takes"
    takes.mkdir(parents=True, exist_ok=True)
    name = next_take_name(song)
    floats = array.array("f")
    floats.frombytes(samples)
    pcm = array.array("h", (max(-32767, min(32767, int(x * 32767))) for x in floats))
    raw = takes / f"{name}-raw.wav"
    with wave.open(str(raw), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm.tobytes())
    clean = takes / f"{name}.wav"
    _ffmpeg("-i", str(raw), "-af", CLEANUP, "-ar", str(SAMPLE_RATE), "-ac", "1", str(clean))
    edit.add_table(song.path, f"voices.{name}",
                   {"file": str(clean), "start": round(start, 3), "volume": 1.0},
                   comment=f"Recorded in the studio window; the untouched recording is {raw.name}.")
    return name
