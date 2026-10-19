"""
Author: Claude Opus 5.5 Medium
Date: 19-October-2026
PURPOSE: Reads a song file (TOML) into a checked Song object. The song file is the studio's control
surface: Claude writes and edits it directly. This module resolves "like" sections (a chorus that
copies another chorus and changes one thing), checks every name and value, and reports problems in
plain words with the section and track they came from. Used by bandmaker.py; feeds band/parts.py.
SRP/DRY check: Pass - parsing and validation only; turning parts into notes lives in parts.py.
"""

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import instruments

SECTION_KEYS = {"bars", "chords", "like"}


class SongError(ValueError):
    """A mistake in the song file, worded for a person to read."""


@dataclass
class Track:
    name: str
    instrument: str
    drums: bool
    program: int          # GM program, or kit number for drums
    volume: float = 0.8   # 0..1 channel volume
    pan: float = 0.0      # -1 left .. 1 right
    reverb: float = 0.25  # 0..1 reverb send
    chorus: float = 0.0   # 0..1 chorus send
    octave: int = 4
    velocity: int = 90


@dataclass
class Section:
    name: str
    bars: int
    chords: str
    parts: dict = field(default_factory=dict)  # track name -> options dict


@dataclass
class Song:
    title: str
    tempo: float
    meter: int            # beats per bar
    swing: float
    seed: int
    tracks: dict          # name -> Track (insertion order = mixer order)
    sections: dict        # name -> Section (resolved, no "like" left)
    order: list           # section names in play order

    @property
    def steps_per_bar(self) -> int:
        return self.meter * 4  # the grid is in sixteenth notes

    def total_bars(self) -> int:
        return sum(self.sections[s].bars for s in self.order)

    def seconds(self) -> float:
        return self.total_bars() * self.meter * 60.0 / self.tempo


def _num(value, what, lo, hi):
    if not isinstance(value, (int, float)) or not lo <= value <= hi:
        raise SongError(f"{what} should be a number from {lo} to {hi}, got {value!r}")
    return value


def _load_track(name, spec) -> Track:
    if not isinstance(spec, dict) or "instrument" not in spec:
        raise SongError(f"track '{name}' needs an instrument, like instrument = \"piano\"")
    inst = spec["instrument"]
    kit = instruments.kit_for(inst)
    try:
        program = kit if kit is not None else instruments.program_for(inst)
    except ValueError as e:
        raise SongError(f"track '{name}': {e}") from None
    t = Track(name, inst, kit is not None, program)
    for key, lo, hi in (("volume", 0, 1), ("pan", -1, 1), ("reverb", 0, 1), ("chorus", 0, 1),
                        ("octave", 0, 8), ("velocity", 1, 127)):
        if key in spec:
            setattr(t, key, _num(spec[key], f"track '{name}' {key}", lo, hi))
    unknown = set(spec) - {"instrument", "volume", "pan", "reverb", "chorus", "octave", "velocity"}
    if unknown:
        raise SongError(f"track '{name}': unknown setting(s) {', '.join(sorted(unknown))}")
    return t


def _resolve_section(name, raw, tracks, seen=()):
    """Return (bars, chords, parts) for a section, following its "like" chain."""
    if name not in raw:
        raise SongError(f"section '{name}' is used but never written")
    if name in seen:
        raise SongError(f"sections copy each other in a loop: {' -> '.join(seen + (name,))}")
    spec = raw[name]
    if "like" in spec:
        bars, chords, parts = _resolve_section(spec["like"], raw, tracks, seen + (name,))
        parts = {k: dict(v) for k, v in parts.items()}
    else:
        bars, chords, parts = None, "", {}
    chords = spec.get("chords", chords)
    bars = spec.get("bars", bars)
    for key, value in spec.items():
        if key in SECTION_KEYS:
            continue
        if key not in tracks:
            raise SongError(f"section '{name}' has a part for '{key}', but there is no track by that name")
        if value == "off":
            parts.pop(key, None)
        elif isinstance(value, dict):
            # A copied section only changes what it mentions; everything else carries over.
            parts[key] = {**parts.get(key, {}), **value}
        else:
            raise SongError(f"section '{name}', track '{key}': expected settings or \"off\"")
    if bars is None:
        # Default length: one pass through the chord chart.
        bars = max(1, len([b for b in chords.split("|") if b.strip()])) if chords else 4
    if not isinstance(bars, int) or bars < 1:
        raise SongError(f"section '{name}': bars should be a whole number above zero")
    return bars, chords, parts


def load_song(path) -> Song:
    path = Path(path)
    try:
        data = tomllib.loads(path.read_text())
    except tomllib.TOMLDecodeError as e:
        raise SongError(f"{path.name} isn't readable as a song file: {e}") from None

    tracks = {n: _load_track(n, s) for n, s in data.get("tracks", {}).items()}
    if not tracks:
        raise SongError("the song has no tracks")
    raw_sections = data.get("sections", {})
    order = data.get("order") or list(raw_sections)
    sections = {}
    for name in dict.fromkeys(order):
        bars, chords, parts = _resolve_section(name, raw_sections, tracks)
        sections[name] = Section(name, bars, chords, parts)

    meter = data.get("meter", 4)
    if meter not in (2, 3, 4, 5, 6, 7):
        raise SongError("meter (beats per bar) should be between 2 and 7")
    return Song(
        title=data.get("title", path.stem),
        tempo=_num(data.get("tempo", 100), "tempo", 30, 260),
        meter=meter,
        swing=_num(data.get("swing", 0.0), "swing", 0, 1),
        seed=int(data.get("seed", 1)),
        tracks=tracks,
        sections=sections,
        order=list(order),
    )
