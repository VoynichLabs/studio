# Studio

A small home-built music studio for the Mac Mini that Claude drives directly. This is stage one of
the plan in `../music-videos/docs/studio-plan.md`: the band maker.

You write a song file (plain text, in `songs/`), and the band maker turns it into audio using free
instruments, entirely on this machine.

    python3 bandmaker.py songs/first-light.toml           # render the mix, MIDI and one file per instrument
    python3 bandmaker.py songs/first-light.toml --check   # only check the song file

The output goes to `out/<song name>/` (the mix as WAV and MP3, the MIDI, and `stems/`). `out` and
`instruments` are links to the Samsung drive.

## Needs

FluidSynth and ffmpeg (from Homebrew), plus the free GeneralUser GS sound library in
`instruments/GeneralUser-GS.sf2` (from github.com/mrbumpy409/GeneralUser-GS).

## The song file

The top of the file sets `title`, `tempo` (beats a minute), `meter` (beats a bar), `swing` (0 to 1)
and `seed`. `order` lists the sections in play order, and a section can appear more than once.

**Tracks** (`[tracks.name]`) choose an `instrument` by plain name ("fingered bass", "electric piano",
"warm pad", "steel guitar", "flute"; drums use "drums", "brush", "808", "jazz", "room" and so on),
plus `volume`, `pan`, `reverb`, `chorus`, `octave` and `velocity`.

**Sections** (`[sections.name]`) set `bars` and `chords`, like `"Am | F | C G | G"`. Chords inside a
bar share it evenly, `-` holds the previous chord, `%` repeats the last bar, and `N` means no chord.
Writing `like = "verse"` copies another section, so you only write what changes. Setting a track to
`"off"` silences it there.

Each track's **part** in a section picks a `style`:

- `pad` holds each chord.
- `block` strikes chords on a rhythm.
- `strum` is the same, but strummed like a guitar (down on the beat, up off it).
- `arp` plays chord notes one at a time, with `pattern` set to up, down or updown.
- `root`, `root-fifth` and `octave` are bass styles.
- `notes` plays a written melody: `"A4:q C5:e. r:s E4,G4:h!"`. The lengths are w h q e s, with `.`
  for dotted and `t` for triplet. `~` ties notes, `r` is a rest, commas stack notes into a chord,
  `!` plays loud and `?` plays soft.

**Rhythms** are sixteenth-note grids that repeat across the section: `x` is a hit, `X` is loud,
`o` is soft, `-` holds, and `.` is a rest, so `"x---x---x---x---"` is four on the floor. **Drums** give
one grid per piece (kick, snare, hat, open hat, crash, ride, clap, rim, toms, shaker, tambourine,
and so on). `first = {...}` plays only in the section's first bar, and `fill = {...}` replaces the
last bar.

The same song file always renders the same audio, because the human feel is seeded.
