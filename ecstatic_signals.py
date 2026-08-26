#!/usr/bin/env python3
"""Which tags in this library mean "oriental", "sensual", "playful", "driving".

WHY A FILE OF ITS OWN: the words a DJ uses are not the words the taggers use.
Nothing in this database is labelled "sexy middle-eastern banger" — that feeling
is spread across an instrument (tabla), a label (Desert Trax), an artist genre
(turkish) and a mood (sensual). Each signal alone is weak and noisy; together
they point at the right records. Keeping the mapping here means the next set —
a different theme, a different night — is a change to THIS file only.

HOW TO TWEAK: every line is (tag_type, tag, weight, source_prefix_or_None).
Raise a weight to make that marker matter more. A source prefix of None accepts
the tag from any tagger. Weights are summed per track and then squashed to 0..1,
so adding more markers of the same idea makes the signal more robust, not louder.

ARTIST_LEVEL_SOURCES are damped: "this artist is Turkish" says much less about
one record than "this record has a tabla in it".
"""

# Taggers that describe the ARTIST, not the track. Counted, but at a discount.
ARTIST_LEVEL_SOURCES = ("last.fm:artist", "spotify:artist-genre", "theaudiodb")
ARTIST_LEVEL_DAMPING = 0.45

SIGNALS = {
    # ---- oriental / middle-eastern flavour -------------------------------
    "orient": [
        ("instrument_candidate", "tabla",            1.00, None),
        ("label",                "desert trax",      0.95, None),
        ("label",                "alt orient",       0.90, None),
        ("genre",                "oriental",         0.90, None),
        ("genre",                "middle eastern",   0.90, None),
        ("genre",                "arabic",           0.85, None),
        ("genre",                "arab",             0.85, None),
        ("genre",                "turkish",          0.80, None),
        ("subgenre",             "turkish pop",      0.80, None),
        ("genre",                "persian",          0.80, None),
        ("genre",                "egypt",            0.75, None),
        ("genre",                "morocco",          0.75, None),
        ("genre",                "balkan",           0.70, None),
        ("genre",                "gypsy",            0.65, None),
        ("audio_style_candidate", "gypsy jazz",      0.55, None),
        ("voice_candidate",      "chanting",         0.45, None),
        ("instrument_candidate", "gongs",            0.35, None),
        ("instrument_candidate", "singing bowls",    0.30, None),
        ("voice_candidate",      "wordless vocals",  0.30, None),
        ("instrument_candidate", "accordion",        0.28, None),
        ("instrument_candidate", "flute",            0.25, None),
        ("genre",                "world music",      0.35, None),
        ("subgenre",             "world music",      0.35, None),
        ("genre",                "world",            0.30, None),
        ("instrument_candidate", "violin",           0.18, None),
    ],
    # ---- the scene this music lives in -----------------------------------
    # KEPT SEPARATE FROM "orient" ON PURPOSE. Organic/afro/tribal house is the
    # context that turns a tabla from "a raga" into "a dancefloor record", but
    # there are 13,000 afro-house tracks here and only a few hundred genuinely
    # oriental ones. Mixed into one number, the common signal swallowed the rare
    # one and the ranking filled up with Latin party records.
    "scene": [
        ("subgenre",             "organic house",    1.00, None),
        ("genre",                "organic house",    1.00, None),
        ("subgenre",             "tribal house",     0.90, None),
        ("genre",                "tribal house",     0.90, None),
        ("subgenre",             "afro house",       0.70, None),
        ("genre",                "afro house",       0.70, None),
        ("subgenre",             "melodic house",    0.55, None),
        ("genre",                "melodic house",    0.55, None),
        ("subgenre",             "downtempo",        0.45, None),
        ("instrument_candidate", "djembe",           0.40, None),
        ("instrument_candidate", "bongos",           0.40, None),
        ("instrument_candidate", "congas",           0.50, None),
        ("instrument_candidate", "field recordings", 0.30, None),
    ],
    # ---- sexy / sensual ---------------------------------------------------
    "sensual": [
        ("mood",           "sensual",        1.00, None),
        ("mood_candidate", "sensual",        0.90, None),
        ("genre",          "sexy",           0.85, None),
        ("subgenre",       "sexy",           0.85, None),
        ("mood_candidate", "sexy",           0.85, None),
        ("mood",           "intimate",       0.55, None),
        ("mood_candidate", "intimate",       0.50, None),
        ("mood",           "romantic",       0.40, None),
        ("mood_candidate", "romantic",       0.38, None),
        ("voice_candidate", "soulful vocals", 0.35, None),
        ("mood",           "deep",           0.28, None),
        ("mood_candidate", "love",           0.25, None),
        ("voice_candidate", "female vocals", 0.20, None),
        ("mood_candidate", "tender",         0.20, None),
    ],
    # ---- playful / funny --------------------------------------------------
    "playful": [
        ("mood",           "quirky",       1.00, None),
        ("mood",           "funny",        0.90, None),
        ("mood_candidate", "funny",        0.70, None),
        ("genre",          "funny",        0.70, None),
        ("mood",           "party",        0.40, None),
        ("mood_candidate", "party",        0.35, None),
        ("mood",           "joyful",       0.35, None),
        ("mood",           "happy",        0.28, None),
        ("mood_candidate", "happy",        0.22, None),
        ("mood_candidate", "playful",      0.90, None),
        ("mood",           "playful",      1.00, None),
    ],
    # ---- driving / danceable ---------------------------------------------
    "driving": [
        ("danceability_band", "very-danceable", 1.00, None),
        ("danceability_band", "danceable",      0.55, None),
        ("rhythm",         "four-on-the-floor", 0.75, None),
        ("mood_candidate", "propulsive",        0.65, None),
        ("mood_candidate", "rolling",           0.55, None),
        ("mood",           "energetic",         0.50, None),
        ("mood_candidate", "energetic",         0.45, None),
        ("mood_candidate", "building",          0.30, None),
        ("mood_candidate", "hypnotic",          0.35, None),
        ("mood_candidate", "primal",            0.35, None),
        ("mood",           "party",             0.30, None),
    ],
    # ---- what would RUIN this night (subtracted) --------------------------
    "wrong": [
        ("rhythm",         "beatless",      1.00, None),
        ("danceability_band", "not-danceable", 1.00, None),
        ("mood",           "sad",           0.60, None),
        ("mood_candidate", "sad",           0.45, None),
        ("mood",           "aggressive",    0.55, None),
        ("mood_candidate", "angry",         0.55, None),
        ("mood",           "somber",        0.50, None),
        ("mood",           "melancholic",   0.40, None),
        ("mood_candidate", "corporate",     0.45, None),
        ("mood_candidate", "advertising",   0.45, None),
        ("mood_candidate", "background",    0.35, None),
        ("mood",           "relaxing",      0.30, None),
        ("subgenre",       "drum and bass", 0.50, None),
        ("subgenre",       "hardstyle",     0.80, None),
        ("subgenre",       "metal",         0.90, None),
    ],
}


# ---------------------------------------------------------------------------
# WHO PLAYS THIS MUSIC — domain knowledge the taggers do not have.
#
# WHY: "middle eastern" as a tag covers 61 tracks in this library. The feeling
# is really carried by a scene — Anatolian / organic / ecstatic-dance artists
# and labels — and the artist name is a far stronger signal for it than any
# mood model. Matched as a lower-case substring against artist AND title, so a
# remix ("… - Anatolian Sessions Remix") counts too.
#
# HOW TO TWEAK: add a name with a weight 0..1. 1.0 = this name alone means the
# record belongs on this night. Keep names distinctive — a short string like
# "mira" would match half the library.
ORIENT_ARTISTS = {
    "cafe de anatolia": 1.00, "anatolian sessions": 1.00, "oceanvs orientalis": 1.00,
    "mercan dede": 1.00, "omar souleyman": 1.00, "acid arab": 0.95, "zigan aldi": 0.95,
    "bora uzer": 0.95, "armen miran": 0.90, "hraach": 0.90, "sarkis mikael": 0.90,
    "be svendsen": 0.85, "bedouin": 0.85, "satori": 0.80, "acid pauli": 0.75,
    "nicola cruz": 0.75, "chancha via circuito": 0.70, "el búho": 0.70, "el buho": 0.70,
    "rodrigo gallardo": 0.70, "dengue dengue dengue": 0.70, "barbarix": 0.70,
    "kermesse": 0.70, "goldcap": 0.65, "sabo": 0.65, "amonita": 0.65, "iorie": 0.60,
    "guy mantzur": 0.50, "yamil": 0.50, "kayan": 0.60, "tal fussman": 0.45,
    "damian lazarus": 0.55, "blond:ish": 0.50, "lost desert": 0.55, "tibi dabo": 0.55,
    "sainte vie": 0.55, "nu zau": 0.50, "trikk": 0.50, "adriatique": 0.40,
    "monolink": 0.45, "kalabrese": 0.45, "dee montero": 0.40, "sabb": 0.40,
}

# Words in a TITLE that give the record away regardless of who made it.
ORIENT_TITLE_WORDS = {
    "anatolia": 0.85, "bedouin": 0.80, "sahara": 0.75, "orient": 0.80, "arabia": 0.85,
    "istanbul": 0.80, "marrakech": 0.85, "bosphorus": 0.80, "caravan": 0.65,
    "nomad": 0.60, "oasis": 0.60, "desert": 0.55, "habibi": 0.85, "yalla": 0.80,
    "derwish": 0.85, "dervish": 0.85, "sufi": 0.85, "rumi": 0.80, "harem": 0.85,
    "bazaar": 0.75, "medina": 0.70, "casbah": 0.80, "damascus": 0.85, "beirut": 0.80,
    "tabla": 0.80, "darbuka": 0.90, "oud": 0.55, "duduk": 0.90, "kanun": 0.70,
    "shisha": 0.75, "hamam": 0.75, "mystic": 0.45, "gypsy": 0.60, "balkan": 0.65,
}

# A masquerade wants flirtation and mischief, and titles say it plainly.
FLAVOUR_TITLE_WORDS = {
    "sensual": ("sensual", 0.8), "seduc": ("sensual", 0.8), "sexy": ("sensual", 0.85),
    "desire": ("sensual", 0.6), "kiss": ("sensual", 0.5), "lover": ("sensual", 0.5),
    "touch": ("sensual", 0.45), "skin": ("sensual", 0.45), "naked": ("sensual", 0.6),
    "tease": ("playful", 0.7), "funk": ("playful", 0.4), "boogie": ("playful", 0.6),
    "circus": ("playful", 0.8), "carnaval": ("playful", 0.8), "carnival": ("playful", 0.8),
    "mask": ("playful", 0.7), "masquerade": ("playful", 1.0), "fiesta": ("playful", 0.6),
    "crazy": ("playful", 0.5), "wild": ("playful", 0.45), "party": ("playful", 0.4),
    "dance": ("driving", 0.35), "groove": ("driving", 0.5), "rhythm": ("driving", 0.45),
    "drum": ("driving", 0.4), "voodoo": ("playful", 0.6), "magic": ("playful", 0.45),
}
