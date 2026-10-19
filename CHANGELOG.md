# Changelog

## 0.1.0 - 19-October-2026 (Claude Opus 5.5 Medium)
- New: the band maker, stage one of the studio plan. It reads a plain-text song file (tracks,
  sections, chord charts, playing styles, drum grids, written melodies), writes MIDI with no outside
  library, and renders it through FluidSynth and the free GeneralUser GS instruments. The output is
  a loudness-matched WAV and MP3 mix plus one audio file per instrument.
- Why: so Claude can write and change one part of a song at a time, which Lyria can't do.
- New: `songs/first-light.toml`, an original demo written only to test the instruments.
