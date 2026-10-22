"""
Author: Claude Opus 5.5 Medium
Date: 22-October-2026
PURPOSE: Turns a Song into audio on the Mac Mini. Each band track is written as MIDI (band/midi.py)
and played through the free GeneralUser GS instruments with FluidSynth into its own file (a stem).
Each voice (a recorded take, or singing split off a Lyria song) is placed at its start time with its
volume and pan. The stems are summed into the mix, which ffmpeg brings to a steady streaming loudness
and saves as WAV and MP3. info.json records the stems and the loudness gain, so the studio window can
play the stems at the same level as the finished mix. Everything stays local, and outputs go under
the studio's out folder on the Samsung drive.
SRP/DRY check: Pass - the only module that calls FluidSynth and ffmpeg for rendering.
"""

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from . import midi, parts

STUDIO = Path(__file__).resolve().parent.parent
SOUNDS = STUDIO / "instruments" / "GeneralUser-GS.sf2"
OUT = STUDIO / "out"
SAMPLE_RATE = 44100
SYNTH_GAIN = 0.5          # FluidSynth's master gain; low enough that a full band doesn't clip
TARGET_LUFS = -14         # typical streaming loudness
LOUDNESS = f"loudnorm=I={TARGET_LUFS}:TP=-1.5:LRA=11"


def _need(program: str):
    if not shutil.which(program):
        raise RuntimeError(f"{program} isn't installed; the studio needs it to make audio")


def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def _synth(mid: Path, wav: Path, sounds: Path):
    subprocess.run(
        ["fluidsynth", "-ni", "-q", "-g", str(SYNTH_GAIN), "-r", str(SAMPLE_RATE),
         "-F", str(wav), str(sounds), str(mid)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def _place(src: Path, dst: Path, start: float, volume: float = 1.0, pan: float = 0.0, mono=False):
    """Copy audio to a stereo stem that begins `start` seconds into the song."""
    chain = [f"aresample={SAMPLE_RATE}"]
    if mono:
        # Equal-power-ish pan of a mono voice: the far side drops, the near side stays full.
        left, right = min(1.0, 1 - pan), min(1.0, 1 + pan)
        chain += ["aformat=channel_layouts=mono", f"pan=stereo|c0={left:.3f}*c0|c1={right:.3f}*c0"]
    else:
        chain += ["aformat=channel_layouts=stereo"]
    if start < 0:
        chain += [f"atrim=start={-start:.4f}", "asetpts=PTS-STARTPTS"]
    elif start > 0:
        chain += [f"adelay={start * 1000:.1f}:all=1"]
    if volume != 1.0:
        chain += [f"volume={volume:.4f}"]
    _ffmpeg("-i", str(src), "-af", ",".join(chain), "-c:a", "pcm_s16le", str(dst))


def loudness(wav: Path) -> float:
    """Integrated loudness in LUFS (very low for near-silence)."""
    out = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(wav), "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    found = re.findall(r"I:\s+(-?[\d.]+|-inf) LUFS", out)
    return float(found[-1]) if found and found[-1] != "-inf" else -70.0


def render(song, name: str, sounds: Path = SOUNDS) -> Path:
    """Render every stem and the finished mix. Returns the song's output folder."""
    _need("fluidsynth")
    _need("ffmpeg")
    if song.tracks and not sounds.exists():
        raise RuntimeError(f"instrument sounds not found at {sounds} (is the Samsung drive mounted?)")
    folder = OUT / name
    stem_dir = folder / "stems"
    if stem_dir.exists():
        shutil.rmtree(stem_dir)   # drop stems of tracks that no longer exist
    stem_dir.mkdir(parents=True)

    track_events = {t.name: parts.build_track(song, t) for t in song.tracks.values()}
    if song.tracks:
        midi.write_midi(folder / "song.mid", song, track_events)
    stems = []   # [(name, kind)] in mixer order
    for t in song.tracks.values():
        if not track_events[t.name]:
            continue
        smid, raw = stem_dir / f"{t.name}.mid", stem_dir / f"{t.name}-raw.wav"
        midi.write_midi(smid, song, track_events, only={t.name})
        _synth(smid, raw, sounds)
        _place(raw, stem_dir / f"{t.name}.wav", song.offset)
        smid.unlink()
        raw.unlink()
        stems.append((t.name, "drums" if t.drums else "band"))
    muted = set()
    for v in song.voices.values():
        # A voice at volume 0 is a muted reference (like the original instrumental): its stem is
        # kept at full level so the studio window can bring it up, but it stays out of the mix.
        if v.volume == 0:
            muted.add(v.name)
        _place(v.file, stem_dir / f"{v.name}.wav", v.start, v.volume or 1.0, v.pan, mono=True)
        stems.append((v.name, "voice"))
    heard = [n for n, _ in stems if n not in muted]
    if not heard:
        raise RuntimeError("nothing plays in this song yet")

    raw_mix = folder / "mix-raw.wav"
    inputs = [arg for n in heard for arg in ("-i", str(stem_dir / f"{n}.wav"))]
    _ffmpeg(*inputs, "-filter_complex",
            f"amix=inputs={len(heard)}:normalize=0:duration=longest", str(raw_mix))
    gain_db = TARGET_LUFS - loudness(raw_mix)
    _ffmpeg("-i", str(raw_mix), "-af", LOUDNESS, "-ar", str(SAMPLE_RATE), str(folder / "mix.wav"))
    _ffmpeg("-i", str(folder / "mix.wav"), "-codec:a", "libmp3lame", "-q:a", "2", str(folder / "mix.mp3"))
    raw_mix.unlink()

    bar_seconds = song.meter * 60.0 / song.tempo
    sections, at = [], song.offset
    for name in song.order:
        sections.append({"name": name, "start": round(at, 3)})
        at += song.sections[name].bars * bar_seconds
    info = {
        "title": song.title, "sections": sections, "seconds": song.seconds(), "gain_db": round(gain_db, 2),
        "stems": [{"name": n, "kind": k, "muted": n in muted} for n, k in stems],
        "rendered": time.time(),
        "song_mtime": song.path.stat().st_mtime if song.path else None,
    }
    (folder / "info.json").write_text(json.dumps(info, indent=2))
    return folder
