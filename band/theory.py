"""
Author: Claude Opus 5.5 Medium
Date: 19-October-2026
PURPOSE: Music theory helpers for the band maker: turning note names like "C#4" into MIDI pitch
numbers, reading chord symbols like "F#m7/C#" into pitch classes, and choosing smooth chord voicings
so pads and keys move to the nearest inversion instead of jumping around the keyboard.
Used by band/parts.py. No outside dependencies.
SRP/DRY check: Pass - the only place note and chord names are understood.
"""

import re
from dataclasses import dataclass

NOTE_BASE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}

# Intervals in semitones above the root. Extensions above an octave (9ths) stay above 12 so the
# voicing code keeps them on top instead of folding them into the triad.
CHORD_QUALITIES = {
    "": [0, 4, 7], "maj": [0, 4, 7], "M": [0, 4, 7],
    "m": [0, 3, 7], "min": [0, 3, 7], "-": [0, 3, 7],
    "dim": [0, 3, 6], "aug": [0, 4, 8], "+": [0, 4, 8],
    "5": [0, 7], "sus2": [0, 2, 7], "sus4": [0, 5, 7], "sus": [0, 5, 7],
    "6": [0, 4, 7, 9], "m6": [0, 3, 7, 9],
    "7": [0, 4, 7, 10], "maj7": [0, 4, 7, 11], "M7": [0, 4, 7, 11],
    "m7": [0, 3, 7, 10], "-7": [0, 3, 7, 10], "m7b5": [0, 3, 6, 10], "dim7": [0, 3, 6, 9],
    "7sus4": [0, 5, 7, 10], "mmaj7": [0, 3, 7, 11],
    "9": [0, 4, 7, 10, 14], "maj9": [0, 4, 7, 11, 14], "m9": [0, 3, 7, 10, 14],
    "add9": [0, 4, 7, 14], "madd9": [0, 3, 7, 14],
}

_PITCH_RE = re.compile(r"^([A-Ga-g])([#b]?)(-?\d)$")
_CHORD_RE = re.compile(r"^([A-G])([#b]?)(.*?)(?:/([A-G])([#b]?))?$")


def pitch_class(letter: str, accidental: str) -> int:
    pc = NOTE_BASE[letter.upper()]
    if accidental == "#":
        pc += 1
    elif accidental == "b":
        pc -= 1
    return pc % 12


def parse_pitch(name: str) -> int:
    """'C4' -> 60 (middle C). Raises ValueError with a readable message."""
    m = _PITCH_RE.match(name.strip())
    if not m:
        raise ValueError(f"'{name}' is not a note name like C4, F#3 or Bb2")
    letter, acc, octave = m.groups()
    # Use the unwrapped value so Cb4 / B#3 land in the right octave.
    base = NOTE_BASE[letter.upper()] + (1 if acc == "#" else -1 if acc == "b" else 0)
    return (int(octave) + 1) * 12 + base


@dataclass(frozen=True)
class Chord:
    symbol: str
    root: int          # pitch class 0-11
    intervals: tuple   # semitones above root
    bass: int          # pitch class of the bass note (root unless slash chord)


def parse_chord(symbol: str) -> Chord:
    m = _CHORD_RE.match(symbol.strip())
    if not m:
        raise ValueError(f"'{symbol}' is not a chord symbol like Am, F#m7 or C/E")
    letter, acc, quality, bass_letter, bass_acc = m.groups()
    if quality not in CHORD_QUALITIES:
        known = ", ".join(q or "(major)" for q in CHORD_QUALITIES)
        raise ValueError(f"chord '{symbol}': unknown type '{quality}'. Known types: {known}")
    root = pitch_class(letter, acc)
    bass = pitch_class(bass_letter, bass_acc) if bass_letter else root
    return Chord(symbol, root, tuple(CHORD_QUALITIES[quality]), bass)


def _candidate_voicings(chord: Chord, center: int):
    """Every inversion of the chord, each shifted to the octave that sits closest to `center`."""
    core = [i for i in chord.intervals if i < 12]
    ext = [i for i in chord.intervals if i >= 12]
    for k in range(len(core)):
        rotated = core[k:] + [i + 12 for i in core[:k]]
        notes = [chord.root + i for i in rotated] + [chord.root + i for i in ext]
        mean = sum(notes) / len(notes)
        shift = round((center - mean) / 12) * 12
        yield [n + shift for n in notes]


def voice_chord(chord: Chord, center: int, previous=None) -> list:
    """Pick the inversion nearest the previous voicing (smooth voice leading), else nearest center."""
    best, best_cost = None, None
    for notes in _candidate_voicings(chord, center):
        mean = sum(notes) / len(notes)
        if previous:
            cost = sum(min(abs(n - p) for p in previous) for n in notes)
            # Small pull back toward the requested register so long progressions don't drift.
            cost += abs(mean - center) * 0.5
        else:
            cost = abs(mean - center)
        if best_cost is None or cost < best_cost:
            best, best_cost = notes, cost
    return sorted(best)


def bass_pitch(chord: Chord, octave: int, fifth: bool = False, up_octave: bool = False) -> int:
    pc = (chord.root + 7) % 12 if fifth else chord.bass
    pitch = (octave + 1) * 12 + pc
    return pitch + 12 if up_octave else pitch
