# Studio

A small home-built music studio for the Mac Mini that Claude drives directly, made for making covers
and songs in plain words. Claude writes the band into a plain-text song file. The studio renders it
with free instruments, plays it in a browser window with a slider for each track, records your voice
over it, cleans up the recording, and can take a finished song (like one of our Lyria tracks) and
split the singing off so a new band can go underneath it. Everything runs on this machine. The plan
it follows is in `../music-videos/docs/studio-plan.md`.

## The studio window

    python3 server.py        # then open http://localhost:8765

Pick a song on the left. You can play it, click the timeline to jump, and move each track's slider,
mute it or solo it. **Save mix** writes the slider positions into the song file. **Record** (or the R
key) records your voice from the playhead. Wear headphones so the music stays out of the microphone.
Each take is cleaned up (rumble, background noise, harsh "s" sounds, even volume, a little echo) and
added to the song as a voice called take-1, take-2 and so on, which you can remove with the cross.
**Import a song** splits a finished song into its singing and its music, estimates the tempo, first
beat and chords, and writes a starter song file with the singing as a voice and the original music
muted underneath for comparison.

The window reloads by itself whenever a song file changes, so when Claude edits a song, you hear the
new version without doing anything.

## Rendering without the window

    python3 bandmaker.py songs/first-light.toml           # render the mix, MIDI and one file per instrument
    python3 bandmaker.py songs/first-light.toml --check   # only check the song file

The output goes to `out/<song name>/` (the mix as WAV and MP3, the MIDI, and `stems/`). `out` and
`instruments` are links to the Samsung drive. Recorded takes live in `out/<song>/takes/`, and the
untouched recording is kept next to each cleaned one.

## Needs

FluidSynth and ffmpeg (from Homebrew), plus the free GeneralUser GS sound library in
`instruments/GeneralUser-GS.sf2` (from github.com/mrbumpy409/GeneralUser-GS). Importing needs the
splitter's own Python on the Samsung drive (`studio/splitter-env`, with Demucs and librosa,
installed with uv on Python 3.12).

## Honest limits

- Free instruments sound decent, but not like a polished commercial record.
- There's no pitch correction yet.
- The importer's chords are estimates, and the splitter can mistake a lead instrument for singing.
- Recording lines takes up using the browser's own timing. If a take sits a little early or late,
  change its `start` in the song file.

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

**Voices** (`[voices.name]`) are audio files laid into the song: `file`, `start` (seconds into the
song; a negative value trims the file's head), `volume` (0 to 2, where 0 keeps the voice muted as a
reference) and `pan`. A song-level `offset` delays the band so bar one lands on an imported song's
first beat.

**Rhythms** are sixteenth-note grids that repeat across the section: `x` is a hit, `X` is loud,
`o` is soft, `-` holds, and `.` is a rest, so `"x---x---x---x---"` is four on the floor. **Drums** give
one grid per piece (kick, snare, hat, open hat, crash, ride, clap, rim, toms, shaker, tambourine,
and so on). `first = {...}` plays only in the section's first bar, and `fill = {...}` replaces the
last bar.

The same song file always renders the same audio, because the human feel is seeded.
