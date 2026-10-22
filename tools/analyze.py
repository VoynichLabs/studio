"""
Author: Claude Opus 5.5 Medium
Date: 22-October-2026
PURPOSE: Runs inside the splitter's own Python (on the Samsung drive, with Demucs and librosa). Splits
a finished song into its singing and everything else with Demucs, then studies the instrumental half:
the tempo, where the first beat lands, and a rough chord for each bar (matching the bar's note energy
against major and minor chord shapes). Prints one JSON object for band/importer.py to turn into a
starter song file. The chords are a starting point for Claude to correct, not a transcription.
SRP/DRY check: Pass - the only code that uses Demucs or librosa; nothing else imports them.
Usage: splitter-env/bin/python tools/analyze.py <song audio> <output folder>
"""

import json
import subprocess
import sys
from pathlib import Path

import librosa
import numpy as np

NAMES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]


def split(audio: Path, out: Path):
    """Demucs two-stem split -> (vocals.wav, no_vocals.wav)."""
    subprocess.run([sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", "htdemucs",
                    "-o", str(out), str(audio)], check=True, stdout=subprocess.DEVNULL)
    folder = out / "htdemucs" / audio.stem
    return folder / "vocals.wav", folder / "no_vocals.wav"


def chord_templates():
    shapes = []
    for root in range(12):
        for suffix, intervals in (("", (0, 4, 7)), ("m", (0, 3, 7))):
            t = np.zeros(12)
            t[[(root + i) % 12 for i in intervals]] = 1
            shapes.append((NAMES[root] + suffix, t / np.linalg.norm(t)))
    return shapes


def study(instrumental: Path):
    y, sr = librosa.load(str(instrumental), sr=22050, mono=True)
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units="time")
    tempo = float(np.atleast_1d(tempo)[0])
    beats = np.asarray(beats, dtype=float)
    # Beat trackers often lock to half or double time; keep it in a singable middle range.
    while tempo < 70:
        tempo *= 2
    while tempo > 170:
        tempo /= 2
    beat_len = 60.0 / tempo
    first = float(beats[0]) if len(beats) else 0.0
    # Step back whole beats while there's room, so a pickup before the tracked start isn't lost.
    while first - beat_len * 4 >= 0:
        first -= beat_len * 4

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    times = librosa.frames_to_time(np.arange(chroma.shape[1]), sr=sr)
    bar_len = beat_len * 4
    duration = len(y) / sr
    shapes = chord_templates()
    chords = []
    t = first
    while t + bar_len * 0.5 < duration:
        mask = (times >= t) & (times < t + bar_len)
        v = chroma[:, mask].mean(axis=1) if mask.any() else np.zeros(12)
        norm = np.linalg.norm(v)
        if norm < 1e-6:
            chords.append("N")
        else:
            name, score = max(((n, float(s @ (v / norm))) for n, s in shapes), key=lambda x: x[1])
            chords.append(name if score > 0.55 else "N")
        t += bar_len
    return {"tempo": round(tempo, 2), "first_beat": round(first, 3),
            "duration": round(duration, 2), "bar_chords": chords}


def main():
    audio, out = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    out.mkdir(parents=True, exist_ok=True)
    vocals, instrumental = split(audio, out)
    result = study(instrumental)
    result.update({"vocals": str(vocals), "instrumental": str(instrumental)})
    print(json.dumps(result))


if __name__ == "__main__":
    main()
