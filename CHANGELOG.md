# Changelog

## 0.2.0 - 22-October-2026 (Claude Opus 5.5 Medium)
- New: the studio window (`server.py` plus `web/index.html`). It plays a song's stems together with a
  live volume, mute and solo for each track, shows a clickable section timeline, saves slider
  positions into the song file, and reloads by itself whenever a song file changes.
- New: recording. The microphone is captured on the same audio clock as playback, so takes line up.
  Takes are cleaned with ffmpeg and added to the song file as voices, and they can be removed again.
- New: importing (`band/importer.py`, `tools/analyze.py`). A finished song is split into singing and
  music with Demucs, the tempo, first beat and chords are estimated with librosa, and a starter song
  file is written.
- Song files gain `[voices.*]` (placed audio files) and a song-level `offset`. Every render now writes
  a stem for each track and voice, builds the mix from those stems, and writes `info.json`.
- Why: so the whole studio described in the plan exists in one piece, not one stage at a time.
- Tested on the original demo and on a test song made from the demo plus a computer voice. The
  importer found the demo's tempo and chords. Recording from a real microphone hasn't been tried yet.

## 0.1.0 - 19-October-2026 (Claude Opus 5.5 Medium)
- New: the band maker, stage one of the studio plan. It reads a plain-text song file (tracks,
  sections, chord charts, playing styles, drum grids, written melodies), writes MIDI with no outside
  library, and renders it through FluidSynth and the free GeneralUser GS instruments. The output is
  a loudness-matched WAV and MP3 mix plus one audio file per instrument.
- Why: so Claude can write and change one part of a song at a time, which Lyria can't do.
- New: `songs/first-light.toml`, an original demo written only to test the instruments.
