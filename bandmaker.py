"""
Author: Claude Opus 5.5 Medium
Date: 19-October-2026
PURPOSE: The band maker's command line. Give it a song file and it checks it, prints a short summary
(sections, bars, length) and renders the mix, the MIDI and one audio file per instrument into
out/<song name>/ on the Samsung drive. "--check" only validates, which is handy after an edit.
Wires together band/song.py (reading), band/parts.py (notes) and band/render.py (audio).
SRP/DRY check: Pass - argument handling and the summary only; all real work is in the band package.
"""

import argparse
import sys
from pathlib import Path

from band.render import render
from band.song import SongError, load_song


def summary(song) -> str:
    lines = [f"{song.title}: {song.tempo:g} beats a minute, {song.meter} beats a bar, "
             f"{song.total_bars()} bars, about {song.seconds():.0f} seconds"]
    for name in song.order:
        s = song.sections[name]
        playing = ", ".join(s.parts) or "silence"
        lines.append(f"  {name:<12} {s.bars:>2} bars  {playing}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Render a song file into audio.")
    ap.add_argument("song", type=Path, help="path to a .toml song file")
    ap.add_argument("--check", action="store_true", help="only check the song file")
    ap.add_argument("--no-stems", action="store_true", help="skip the per-instrument files")
    args = ap.parse_args()

    try:
        song = load_song(args.song)
        print(summary(song))
        if args.check:
            # Building the notes is what catches bad grids, chords and melodies.
            from band.parts import build_track
            for t in song.tracks.values():
                build_track(song, t)
            print("song file looks good")
            return
        folder = render(song, args.song.stem, stems=not args.no_stems)
    except SongError as e:
        sys.exit(f"Song file problem: {e}")
    print(f"rendered to {folder}")


if __name__ == "__main__":
    main()
