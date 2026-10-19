"""
Author: Claude Opus 5.5 Medium
Date: 19-October-2026
PURPOSE: Turns a Song into audio on the Mac Mini. Writes MIDI (band/midi.py), plays it through the
free GeneralUser GS instruments with FluidSynth to make the full mix and one file per instrument
(stems), then uses ffmpeg to bring the mix to a steady streaming loudness and save a WAV and an MP3.
Everything stays local. Outputs go under the studio's out folder, which points at the Samsung drive.
SRP/DRY check: Pass - the only module that calls outside programs.
"""

import shutil
import subprocess
from pathlib import Path

from . import midi, parts

STUDIO = Path(__file__).resolve().parent.parent
SOUNDS = STUDIO / "instruments" / "GeneralUser-GS.sf2"
OUT = STUDIO / "out"
SAMPLE_RATE = 44100
SYNTH_GAIN = 0.5          # FluidSynth's master gain; low enough that a full band doesn't clip
LOUDNESS = "loudnorm=I=-14:TP=-1.5:LRA=11"   # typical streaming loudness target


def _need(program: str):
    if not shutil.which(program):
        raise RuntimeError(f"{program} isn't installed; the studio needs it to make audio")


def _synth(mid: Path, wav: Path, sounds: Path):
    subprocess.run(
        ["fluidsynth", "-ni", "-q", "-g", str(SYNTH_GAIN), "-r", str(SAMPLE_RATE),
         "-F", str(wav), str(sounds), str(mid)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _finish(raw: Path, wav: Path, mp3: Path):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af", LOUDNESS,
         "-ar", str(SAMPLE_RATE), str(wav)], check=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-codec:a", "libmp3lame",
         "-q:a", "2", str(mp3)], check=True)


def render(song, name: str, stems: bool = True, sounds: Path = SOUNDS) -> Path:
    """Render the whole song. Returns the folder holding mix.wav, mix.mp3, song.mid and stems/."""
    _need("fluidsynth")
    _need("ffmpeg")
    if not sounds.exists():
        raise RuntimeError(f"instrument sounds not found at {sounds} (is the Samsung drive mounted?)")
    folder = OUT / name
    folder.mkdir(parents=True, exist_ok=True)

    track_events = {t.name: parts.build_track(song, t) for t in song.tracks.values()}
    mid = folder / "song.mid"
    midi.write_midi(mid, song, track_events)
    raw = folder / "mix-raw.wav"
    _synth(mid, raw, sounds)
    _finish(raw, folder / "mix.wav", folder / "mix.mp3")
    raw.unlink()

    if stems:
        stem_dir = folder / "stems"
        if stem_dir.exists():
            shutil.rmtree(stem_dir)   # drop stems of tracks that no longer exist
        stem_dir.mkdir()
        for t in song.tracks.values():
            if not track_events[t.name]:
                continue
            smid = stem_dir / f"{t.name}.mid"
            midi.write_midi(smid, song, track_events, only={t.name})
            _synth(smid, stem_dir / f"{t.name}.wav", sounds)
            smid.unlink()
    return folder
