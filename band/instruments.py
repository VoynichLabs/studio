"""
Author: Claude Opus 5.5 Medium
Date: 19-October-2026
PURPOSE: Plain-word instrument names for the band maker. Maps names like "fingered bass" or
"warm pad" to General MIDI program numbers, drum piece names like "kick" or "open hat" to drum note
numbers, and drum kit names like "brush" or "808" to the kit numbers the GeneralUser GS sound
library provides. Used by band/song.py (validation) and band/parts.py (drum notes).
SRP/DRY check: Pass - the single lookup table for every sound name.
"""

# The 128 General MIDI programs in order, named in plain lowercase words.
GM_PROGRAMS = [
    "acoustic grand piano", "bright piano", "electric grand piano", "honky tonk piano",
    "electric piano", "electric piano 2", "harpsichord", "clavinet",
    "celesta", "glockenspiel", "music box", "vibraphone",
    "marimba", "xylophone", "tubular bells", "dulcimer",
    "drawbar organ", "percussive organ", "rock organ", "church organ",
    "reed organ", "accordion", "harmonica", "tango accordion",
    "nylon guitar", "steel guitar", "jazz guitar", "clean guitar",
    "muted guitar", "overdrive guitar", "distortion guitar", "guitar harmonics",
    "acoustic bass", "fingered bass", "picked bass", "fretless bass",
    "slap bass", "slap bass 2", "synth bass", "synth bass 2",
    "violin", "viola", "cello", "contrabass",
    "tremolo strings", "pizzicato strings", "harp", "timpani",
    "strings", "slow strings", "synth strings", "synth strings 2",
    "choir aahs", "voice oohs", "synth voice", "orchestra hit",
    "trumpet", "trombone", "tuba", "muted trumpet",
    "french horn", "brass section", "synth brass", "synth brass 2",
    "soprano sax", "alto sax", "tenor sax", "baritone sax",
    "oboe", "english horn", "bassoon", "clarinet",
    "piccolo", "flute", "recorder", "pan flute",
    "blown bottle", "shakuhachi", "whistle", "ocarina",
    "square lead", "saw lead", "calliope lead", "chiff lead",
    "charang lead", "voice lead", "fifths lead", "bass and lead",
    "new age pad", "warm pad", "polysynth pad", "choir pad",
    "bowed pad", "metallic pad", "halo pad", "sweep pad",
    "rain fx", "soundtrack fx", "crystal fx", "atmosphere fx",
    "brightness fx", "goblins fx", "echoes fx", "sci-fi fx",
    "sitar", "banjo", "shamisen", "koto",
    "kalimba", "bagpipe", "fiddle", "shanai",
    "tinkle bell", "agogo", "steel drums", "woodblock",
    "taiko drum", "melodic tom", "synth drum", "reverse cymbal",
    "guitar fret noise", "breath noise", "seashore", "bird tweet",
    "telephone ring", "helicopter", "applause", "gunshot",
]

# Short everyday names that point at one of the programs above.
ALIASES = {
    "piano": "acoustic grand piano", "grand piano": "acoustic grand piano",
    "rhodes": "electric piano", "wurlitzer": "electric piano 2", "organ": "drawbar organ",
    "acoustic guitar": "steel guitar", "guitar": "clean guitar", "electric guitar": "clean guitar",
    "bass": "fingered bass", "upright bass": "acoustic bass", "pad": "warm pad",
    "choir": "choir aahs", "brass": "brass section", "horns": "brass section",
    "sax": "alto sax", "lead": "saw lead", "steel drum": "steel drums", "bells": "tubular bells",
}

# Drum kits live on the drum channel; these are the GS kit numbers in GeneralUser GS.
DRUM_KITS = {
    "drums": 0, "standard": 0, "room": 8, "power": 16, "rock": 16,
    "electronic": 24, "808": 25, "tr808": 25, "jazz": 32, "brush": 40, "orchestra": 48,
}

# Drum piece name -> General MIDI drum note number.
DRUM_NOTES = {
    "kick": 36, "kick2": 35, "rim": 37, "snare": 38, "clap": 39, "snare2": 40,
    "hat": 42, "closed hat": 42, "pedal hat": 44, "open hat": 46,
    "tom low": 45, "tom mid": 47, "tom high": 50, "floor tom": 41,
    "crash": 49, "crash2": 57, "ride": 51, "ride bell": 53, "china": 52, "splash": 55,
    "tambourine": 54, "cowbell": 56, "shaker": 70, "cabasa": 69, "maracas": 70,
    "conga high": 63, "conga low": 64, "bongo high": 60, "bongo low": 61,
    "clave": 75, "woodblock": 76, "triangle": 81, "snap": 39,
}


def program_for(name: str) -> int:
    """Plain instrument name -> General MIDI program number (0-127)."""
    key = name.strip().lower()
    key = ALIASES.get(key, key)
    if key in GM_PROGRAMS:
        return GM_PROGRAMS.index(key)
    raise ValueError(f"unknown instrument '{name}'. Try one of: "
                     + ", ".join(sorted(set(ALIASES) | set(GM_PROGRAMS))))


def kit_for(name: str):
    """Drum track instrument -> kit number, or None if the name isn't a drum kit."""
    key = name.strip().lower()
    if key.startswith("drums:"):
        key = key.split(":", 1)[1].strip()
    return DRUM_KITS.get(key)


def drum_note(piece: str) -> int:
    key = piece.strip().lower().replace("_", " ").replace("-", " ")
    if key in DRUM_NOTES:
        return DRUM_NOTES[key]
    raise ValueError(f"unknown drum piece '{piece}'. Known: " + ", ".join(sorted(DRUM_NOTES)))
