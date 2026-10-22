"""
Author: Claude Opus 5.5 Medium
Date: 22-October-2026
PURPOSE: Brings an existing song (usually one of our Lyria tracks) into the studio. Copies the audio
to the Samsung drive, runs tools/analyze.py in the splitter's own Python to split off the singing
and estimate tempo, first beat and chords, then writes a starter song file in songs/. That file has
the singing as a voice, the original instrumental as a muted reference voice, and a simple drums,
bass and keys band on the estimated chords, ready for Claude to rewrite in plain-word rounds with
the Boss. Used by import_song.py and the studio server.
SRP/DRY check: Pass - import orchestration only; analysis lives in tools/analyze.py, file writing in
this module's one template.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

from .render import OUT, STUDIO

# The splitter's own Python on the Samsung drive. Never .resolve() this path: the venv's python is a
# symlink to the base interpreter, and following it would lose the splitter's installed packages.
SPLITTER_PY = Path("/Volumes/Samsung 9100 SSD/studio/splitter-env/bin/python")
ANALYZE = STUDIO / "tools" / "analyze.py"
SONGS = STUDIO / "songs"


def slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "imported-song"


def _chart(chords, per_line=4):
    rows = [" | ".join(chords[i:i + per_line]) for i in range(0, len(chords), per_line)]
    return '"""\n  ' + " |\n  ".join(rows) + '\n"""'


def import_song(audio: Path, title: str = None, log=print) -> Path:
    audio = Path(audio).expanduser().resolve()
    if not audio.exists():
        raise FileNotFoundError(f"{audio} doesn't exist")
    python = SPLITTER_PY
    if not python.exists():
        raise RuntimeError("the song splitter isn't installed on the Samsung drive")
    title = title or audio.stem.replace("_", " ").replace("-", " ").strip().title()
    slug = slugify(title)
    song_file = SONGS / f"{slug}.toml"
    if song_file.exists():
        raise FileExistsError(f"songs/{slug}.toml already exists; pick another title")

    work = OUT / slug / "import"
    work.mkdir(parents=True, exist_ok=True)
    source = work / f"source{audio.suffix.lower()}"
    if audio != source:
        shutil.copy2(audio, source)

    log("splitting the singing from the music and finding the tempo and chords (a minute or two)")
    done = subprocess.run([str(python), "-I", str(ANALYZE), str(source), str(work / "split")],
                          capture_output=True, text=True)
    if done.returncode != 0:
        raise RuntimeError("the splitter failed: " + done.stderr.strip().splitlines()[-1])
    found = json.loads(done.stdout.strip().splitlines()[-1])

    chords = found["bar_chords"] or ["N"]
    text = f'''# {title} - imported {source.name} by the studio importer.
# Tempo, first beat and chords are machine estimates from the instrumental: check them by ear.
# "offset" makes bar one of the band land on the song's first beat.

title = {json.dumps(title)}
tempo = {found["tempo"]}
meter = 4
offset = {found["first_beat"]}
seed = 1
order = ["song"]

[tracks.drums]
instrument = "drums"
volume = 0.8

[tracks.bass]
instrument = "fingered bass"
octave = 2
volume = 0.8

[tracks.keys]
instrument = "electric piano"
octave = 4
volume = 0.55
reverb = 0.3

[sections.song]
bars = {len(chords)}
chords = {_chart(chords)}
keys = {{ style = "block", rhythm = "x-----x-x-----x-" }}
bass = {{ style = "root", rhythm = "x-----x-x-------" }}

[sections.song.drums]
kick = "x.......x......."
snare = "....x.......x..."
hat = "x.x.x.x.x.x.x.x."

# The singing split off the original.
[voices.vocals]
file = {json.dumps(found["vocals"])}
start = 0.0
volume = 1.0

# The original music without the singing, muted; raise it in the studio window to compare.
[voices.original]
file = {json.dumps(found["instrumental"])}
start = 0.0
volume = 0.0
'''
    song_file.write_text(text)
    log(f"wrote songs/{slug}.toml: about {found['tempo']:.0f} beats a minute, {len(chords)} bars")
    return song_file
