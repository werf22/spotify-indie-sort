#!/usr/bin/env python3
"""Turn the partial signals into ONE interpreted answer per question.

WHAT: Mood, Genre, Style, Beat Type, Energy, Vocal, Danceability — a single
value each, instead of the contradictory lists the raw view shows
("calm, joyful, peaceful, sad, sad").

HOW IT DECIDES: every tag carries a source and a confidence, and the sources
form a real trust order, visible in the data itself:

    audio-full:consensus-v2            0.95   our own stages agreeing
    audio-full:essentia-supervised-v2  0.83   our supervised model
    audio-full:*                       ~0.8   our other stages
    theaudiodb / lastfm / discogs      0.75   external providers
    derived:* / freqblog:tag:*         0.66   heuristics over other numbers

So the rule is: OUR OWN AUDIO ANALYSIS OUTRANKS ANYTHING SCRAPED, and within a
tier the higher confidence wins. That ordering is the whole opinion in this
file — everything else is mechanical.

WHY NOT A VOTE: counting tags would let a provider that emits ten near-synonyms
outvote one high-confidence measurement of the actual audio. Rank first, count
never.

HOW TO TWEAK: SOURCE_RANK is the trust order; BEAT_TYPE_LABELS renames the
rhythm classes; ENERGY_BANDS sets the thresholds. Nothing else needs touching.
"""

from __future__ import annotations

# Lower number = more trusted. Matched by prefix, longest match wins.
SOURCE_RANK: list[tuple[str, int]] = [
    ("audio-full:consensus", 0),
    ("audio-full:essentia-supervised", 1),
    ("audio-full:", 2),
    ("onetagger:", 3),
    ("discogs", 3),
    ("musicbrainz", 4),
    ("lastfm", 4),
    ("theaudiodb", 4),
    ("spotify", 5),
    ("freqblog:tag:", 6),
    ("derived:", 7),
]

BEAT_TYPE_LABELS = {
    "steady_four_on_floor": "Four on the floor",
    "broken_beat": "Broken beat",
    "mixed_or_variable": "Mixed / variable",
    "beatless": "Beatless",
    "unknown": "",
}

# (upper bound, label) — first match wins.
ENERGY_BANDS = [(0.33, "Low"), (0.66, "Medium"), (1.01, "High")]

# Which tag_type feeds which interpreted column, in order of preference.
DERIVED_FROM_TAGS = {
    "Mood":         ["mood", "mood_candidate"],
    "Genre":        ["genre", "genre_audio_candidate"],
    "Style":        ["style", "subgenre", "audio_style_candidate"],
    "Vocal":        ["voice", "voice_candidate", "vocal_character"],
    "Instrument":   ["instrument", "instrument_candidate"],
}

DERIVED_COLUMNS = (list(DERIVED_FROM_TAGS)
                   + ["Beat Type", "Energy", "Danceability", "BPM", "Key"])


def source_rank(source: str) -> int:
    """Trust tier of a tag's source; unknown sources sort last."""
    best, best_len = 9, -1
    for prefix, rank in SOURCE_RANK:
        if source and source.startswith(prefix) and len(prefix) > best_len:
            best, best_len = rank, len(prefix)
    return best


def is_english(tag: str) -> bool:
    """Reject tags carrying non-English letters.

    Owner rule: tags are English, always, and are never translated. The library
    holds 113,319 that are not — almost all from Deezer, which localises genre
    names, so "elektronická" and "tanečná" sit alongside the English "electronic"
    and "dance" meaning exactly the same thing. Judging by LETTERS, not by bytes,
    keeps legitimate English tags that merely contain a symbol, such as
    "33 1/3 rpm" written with a fraction glyph.
    """
    # Compare the character AS IT IS. Normalising to NFD first was the bug in
    # the first version: it decomposes "á" into "a" + a combining accent, so the
    # ASCII test then passed and every Slovak tag was let through.
    for ch in tag or "":
        if ch.isalpha() and not ("a" <= ch <= "z" or "A" <= ch <= "Z"):
            return False
    return True


def best_tag(candidates: list[dict]) -> str:
    """Pick one tag: most trusted source first, then highest confidence."""
    candidates = [c for c in candidates if is_english((c.get("tag") or ""))]
    if not candidates:
        return ""
    ranked = sorted(candidates,
                    key=lambda c: (source_rank(c.get("source") or ""),
                                   -float(c.get("confidence") or 0)))
    return (ranked[0].get("tag") or "").strip()


def band(value, bands=ENERGY_BANDS) -> str:
    if value is None:
        return ""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    if v > 1.0:          # some providers report 0-100
        v = v / 100.0
    for upper, label in bands:
        if v < upper:
            return label
    return bands[-1][1]


def beat_type(row: dict) -> str:
    """The rhythm class, named for a human.

    Prefers the model's own classification; falls back to the two scores only
    when it is missing or unknown, because a score comparison is a weaker
    statement than the classifier's own verdict.
    """
    pattern = (row.get("rhythm_rhythm_pattern") or "").strip()
    if pattern and pattern != "unknown":
        return BEAT_TYPE_LABELS.get(pattern, pattern.replace("_", " ").capitalize())
    four = row.get("rhythm_four_on_floor_score")
    broken = row.get("rhythm_broken_beat_score")
    if four is None or broken is None:
        return BEAT_TYPE_LABELS.get(pattern, "")
    try:
        four, broken = float(four), float(broken)
    except (TypeError, ValueError):
        return ""
    if max(four, broken) < 0.25:
        return "Beatless"
    return "Four on the floor" if four >= broken else "Broken beat"


def interpret(row: dict, tags: dict[str, list[dict]]) -> dict:
    """Add the interpreted columns to one row.

    `tags` maps tag_type -> [{tag, source, confidence}, ...] for this track.
    """
    out: dict[str, object] = {}
    for column, types in DERIVED_FROM_TAGS.items():
        # POOL every listed type, then rank once. Taking the first type that has
        # anything was wrong: our own analysis writes mood mostly to
        # `mood_candidate` (410k rows) and only 84k to `mood`, so a single weak
        # provider tag in `mood` hid every measurement we made ourselves. The
        # source decides, never which bucket the tag happened to land in.
        pooled: list[dict] = []
        for tag_type in types:
            pooled.extend(tags.get(tag_type) or [])
        out[column] = best_tag(pooled)

    out["Beat Type"] = beat_type(row)

    # Energy and danceability: prefer our own analysis, fall back to the
    # provider's number, and always show the band rather than a bare float.
    energy = row.get("energy")
    out["Energy"] = band(energy)
    dance = row.get("danceability")
    out["Danceability"] = band(dance)

    # BPM: our own beat tracker is the measurement; a provider's is hearsay.
    bpm = row.get("rhythm_bpm") or row.get("bpm_analysis") or row.get("bpm_freqblog")
    try:
        out["BPM"] = round(float(bpm)) if bpm else ""
    except (TypeError, ValueError):
        out["BPM"] = ""

    out["Key"] = (row.get("key_freqblog") or "").strip()
    return out
