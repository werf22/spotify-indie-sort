"""Derive conservative DJ-search tags from existing metadata and features.

No audio is decoded here. Every generated value is explicitly marked as an
inference, includes confidence, and can later be superseded by audio analysis.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone

from musicdb import connect, record_source_run

SOURCE = "derived:semantic-v1"
SUBGENRE_SOURCE = "taxonomy:subgenre-v1"
MOOD_TAXONOMY_SOURCE = "taxonomy:mood-v1"

# Free-form providers often file affective descriptors under "genre". Keep a
# controlled exact-match vocabulary so words such as "haunting" or "serene"
# become searchable moods without turning arbitrary social tags into moods.
MOOD_TERMS = {
    "aggressive", "angry", "anxious", "atmospheric", "beautiful", "bittersweet",
    "blissful", "calm", "celebratory", "chill", "chilled", "contemplative",
    "dark", "dramatic", "dreamy", "emotional", "energetic", "epic", "eerie",
    "ethereal", "euphoric", "ecstatic", "gentle", "happy", "haunting",
    "hopeful", "hypnotic", "inspiring", "intimate", "joyful", "magical",
    "meditative", "melancholic", "melancholy", "mellow", "moody", "mysterious",
    "nostalgic", "ominous", "optimistic", "passionate", "peaceful", "playful",
    "powerful", "reflective", "relaxed", "relaxing", "ritual", "romantic",
    "sad", "scary", "sensual", "sentimental", "serene", "sinister", "somber",
    "soothing", "soulful", "spiritual", "sunny", "tense", "tender",
    "triumphant", "uplifting", "warm", "wistful",
}

BROAD_GENRES = {
    "ambient", "blues", "classical", "country", "dance", "electronic",
    "electronica", "experimental", "folk", "funk", "hip hop", "hip-hop",
    "jazz", "latin", "metal", "new age", "pop", "punk", "r&b", "reggae",
    "rock", "soul", "soundtrack", "traditional", "world",
}

# The labels describe kick-pattern families, not time signatures. Breakbeat
# music is commonly still in 4/4, but does not put a kick on all four beats.
STEADY_TERMS = {
    "house", "techno", "trance", "disco", "eurodance", "hardstyle",
    "hi-nrg", "italo-disco", "dance-pop", "psytrance", "psy-trance",
}
BROKEN_TERMS = {
    "broken beat", "breakbeat", "breaks", "progressive breaks", "breakcore",
    "drum and bass", "drum & bass", "drum n bass", "dnb", "jungle",
    "uk garage", "2-step", "two-step", "future garage", "speed garage",
    "dubstep", "halftime", "half-time", "trip hop", "trip-hop", "hip hop",
    "hip-hop", "glitch hop", "footwork", "juke", "grime", "drill",
}
BEATLESS_TERMS = {
    "ambient", "dark ambient", "drone", "soundscape", "field recording",
    "meditation", "sleep", "neoclassical", "neo-classical", "modern classical",
    "contemporary classical", "piano", "spoken word", "new age",
}

SOURCE_WEIGHT = {
    "onetagger:beatport": 0.94,
    "onetagger:traxsource": 0.92,
    "onetagger:junodownload": 0.90,
    "onetagger:bandcamp": 0.88,
    "onetagger:discogs": 0.86,
    "last.fm:track": 0.75,
    "spotify:artist-genre": 0.72,
    "deezer": 0.70,
    "musicbrainz": 0.68,
    "last.fm:artist": 0.55,
    "spotify:playlist-inference": 0.42,
}

FEATURE_PRIORITY = {
    "reccobeats": 100,
    "spotify_legacy_dataset": 95,
    "acousticbrainz": 80,
    "onetagger": 72,
    "freqblog": 65,
    "deezer": 55,
    "spotify:playlist-inference": 20,
}


def contains_term(tag: str, term: str) -> bool:
    return tag == term or term in tag


def evidence_score(source: str, confidence: float | None) -> float:
    reported = confidence if confidence is not None else 0.75
    return min(1.0, SOURCE_WEIGHT.get(source, 0.60) * min(1.0, max(0.0, reported)))


def preferred_features(db):
    fields = ("energy", "valence", "danceability", "acousticness", "instrumentalness")
    out: dict[str, dict[str, float]] = defaultdict(dict)
    rank: dict[tuple[str, str], int] = {}
    for row in db.execute(
        "SELECT spotify_id,source,energy,valence,danceability,acousticness,instrumentalness FROM audio_features"
    ):
        priority = FEATURE_PRIORITY.get(row["source"], 40)
        for field in fields:
            value = row[field]
            key = (row["spotify_id"], field)
            if value is not None and priority > rank.get(key, -1):
                out[row["spotify_id"]][field] = float(value)
                rank[key] = priority
    return out


def mood_rows(sid: str, f: dict[str, float]):
    e, v = f.get("energy"), f.get("valence")
    d, a, i = f.get("danceability"), f.get("acousticness"), f.get("instrumentalness")
    if e is None or v is None:
        return []
    moods: dict[str, float] = {}
    if e >= 0.68: moods["energetic"] = 0.68
    if e <= 0.34: moods["calm"] = 0.64
    if v >= 0.70: moods["joyful"] = 0.62
    if v >= 0.62 and e >= 0.50: moods["uplifting"] = 0.66
    if v >= 0.72 and e >= 0.72 and (d or 0) >= 0.55: moods["euphoric"] = 0.64
    if v <= 0.34 and e >= 0.62: moods["tense"] = 0.62
    if v <= 0.28: moods["dark"] = 0.57
    if v <= 0.36 and e <= 0.56: moods["melancholic"] = 0.62
    if v <= 0.25 and e <= 0.44: moods["somber"] = 0.58
    if v >= 0.50 and e <= 0.32: moods["peaceful"] = 0.61
    if e >= 0.84 and v <= 0.34: moods["aggressive"] = 0.56
    if d is not None and d >= 0.73 and e >= 0.65 and v >= 0.50: moods["party"] = 0.61
    if i is not None and i >= 0.55 and e <= 0.46: moods["contemplative"] = 0.55
    if i is not None and i >= 0.55 and e <= 0.52 and (a or 0) >= 0.28: moods["dreamy"] = 0.53
    if a is not None and a >= 0.58 and e <= 0.50: moods["intimate"] = 0.52
    return [(sid, tag, "mood", SOURCE, confidence) for tag, confidence in moods.items()]


def main() -> None:
    db = connect()
    now = datetime.now(timezone.utc).isoformat()
    features = preferred_features(db)
    genre_rows = defaultdict(list)
    for row in db.execute("SELECT spotify_id,tag,source,confidence FROM tags WHERE tag_type IN ('genre','style')"):
        tag = " ".join((row["tag"] or "").lower().replace("_", " ").split())
        if tag:
            genre_rows[row["spotify_id"]].append(
                (tag, row["source"], row["confidence"], evidence_score(row["source"], row["confidence"]))
            )

    attrs = []
    semantic_tags = []
    subgenres = []
    for row in db.execute("SELECT spotify_id FROM tracks"):
        sid = row["spotify_id"]
        evidence = genre_rows.get(sid, [])
        semantic_tags.extend(mood_rows(sid, features.get(sid, {})))
        for tag, source, confidence, _ in evidence:
            if tag in MOOD_TERMS:
                semantic_tags.append(
                    (sid, tag, "mood", MOOD_TAXONOMY_SOURCE, min(1.0, (confidence or 0.55) * 0.92))
                )

        steady = [(t, s, score) for t, s, _, score in evidence if any(contains_term(t, x) for x in STEADY_TERMS)]
        broken = [(t, s, score) for t, s, _, score in evidence if any(contains_term(t, x) for x in BROKEN_TERMS)]
        beatless = [(t, s, score) for t, s, _, score in evidence if any(contains_term(t, x) for x in BEATLESS_TERMS)]
        best_steady = max([x[2] for x in steady] or [0.0])
        best_broken = max([x[2] for x in broken] or [0.0])
        best_beatless = max([x[2] for x in beatless] or [0.0])

        pattern = "unknown"
        pattern_conf = 0.0
        if best_steady and best_broken and abs(best_steady - best_broken) < 0.16:
            pattern, pattern_conf = "mixed_or_variable", max(best_steady, best_broken) * 0.62
        elif best_steady > best_broken:
            pattern, pattern_conf = "steady_four_on_floor", best_steady
        elif best_broken:
            pattern, pattern_conf = "broken_beat", best_broken

        presence, presence_conf = "unknown", 0.0
        if pattern != "unknown":
            presence, presence_conf = "beat", max(pattern_conf, 0.55)
        elif best_beatless:
            presence, presence_conf = "beatless", best_beatless * 0.82
        else:
            f = features.get(sid, {})
            dance, energy = f.get("danceability"), f.get("energy")
            if dance is not None and energy is not None:
                if dance >= 0.48 or energy >= 0.62:
                    presence, presence_conf = "beat", 0.46
                elif dance <= 0.20 and energy <= 0.30:
                    presence, presence_conf = "beatless", 0.44

        evidence_json = json.dumps(
            {"steady": steady[:8], "broken": broken[:8], "beatless": beatless[:8]},
            ensure_ascii=False, sort_keys=True,
        )
        attrs.extend([
            (sid, "beat_presence", SOURCE, presence, None, evidence_json, presence_conf, now),
            (sid, "rhythm_pattern", SOURCE, pattern, None, evidence_json, pattern_conf, now),
        ])

        # Controlled sources already use genre vocabularies; Last.fm is admitted
        # only when the label contains a recognisable genre-family term.
        for tag, source, confidence, _ in evidence:
            if tag in BROAD_GENRES or len(tag) > 80:
                continue
            controlled = source.startswith("onetagger:") or source in {"spotify:artist-genre", "deezer", "musicbrainz"}
            genre_shaped = any(contains_term(tag, x) for x in STEADY_TERMS | BROKEN_TERMS | BROAD_GENRES)
            if controlled or genre_shaped:
                subgenres.append((sid, tag, "subgenre", SUBGENRE_SOURCE, min(1.0, (confidence or 0.65) * 0.92)))

    with db:
        db.execute(
            "DELETE FROM tags WHERE source IN (?,?,?)",
            (SOURCE, SUBGENRE_SOURCE, MOOD_TAXONOMY_SOURCE),
        )
        db.execute("DELETE FROM track_attributes WHERE source=?", (SOURCE,))
        db.executemany("INSERT OR REPLACE INTO tags VALUES(?,?,?,?,?)", semantic_tags)
        db.executemany("INSERT OR REPLACE INTO tags VALUES(?,?,?,?,?)", subgenres)
        db.executemany(
            """INSERT OR REPLACE INTO track_attributes
               (spotify_id,attribute,source,value_text,value_num,value_json,confidence,updated_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            attrs,
        )
    record_source_run(
        db, SOURCE, now, len(attrs) // 2,
        f"mood_tags={len(semantic_tags)},subgenre_tags={len(subgenres)},metadata_only=true",
    )
    print(
        f"Semantic derivation: tracks={len(attrs)//2:,}, mood_tags={len(semantic_tags):,}, "
        f"subgenre_tags={len(subgenres):,}"
    )


if __name__ == "__main__":
    main()
