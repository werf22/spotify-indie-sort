"""Quality-aware nearest-track search for DJ preparation."""
from __future__ import annotations

import argparse
import math
import re
import zlib
from collections import defaultdict

import numpy as np

from musicdb import connect

FIELDS = {
    "energy": 1.30,
    "danceability": 1.05,
    "valence": 0.80,
    "acousticness": 0.50,
    "instrumentalness": 0.75,
    "speechiness": 0.35,
    "liveness": 0.20,
    "loudness": 0.45,
}
TAG_WEIGHTS = {
    "subgenre": 2.80,
    "genre": 1.80,
    "mood": 1.20,
    "instrument": 0.80,
    "voice": 0.50,
}
EMBEDDING_WEIGHTS = {"clap": 2.60, "maest": 1.55}
DEFAULT_SOURCE_WEIGHT = {
    ("deezer", "bpm"): 0.90,
    ("soundnet", "bpm"): 0.80,
    ("soundnet", "key"): 0.75,
}
KEY_TO_CAMELOT = {
    "abm": "1A", "g#m": "1A", "b": "1B",
    "ebm": "2A", "d#m": "2A", "f#": "2B", "gb": "2B",
    "bbm": "3A", "a#m": "3A", "db": "3B", "c#": "3B",
    "fm": "4A", "ab": "4B", "g#": "4B",
    "cm": "5A", "eb": "5B", "d#": "5B",
    "gm": "6A", "bb": "6B", "a#": "6B",
    "dm": "7A", "f": "7B",
    "am": "8A", "c": "8B",
    "em": "9A", "g": "9B",
    "bm": "10A", "d": "10B",
    "f#m": "11A", "gbm": "11A", "a": "11B",
    "c#m": "12A", "dbm": "12A", "e": "12B",
}


def spotify_id(value: str) -> str | None:
    match = re.search(r"(?:track[:/])([A-Za-z0-9]{22})", value)
    return match.group(1) if match else (value if re.fullmatch(r"[A-Za-z0-9]{22}", value) else None)


def artists(value: str | None) -> set[str]:
    return {part.strip().casefold() for part in (value or "").split(",") if part.strip()}


def normalized_title(value: str | None) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").casefold()))


def same_recording(a, b) -> bool:
    if a["isrc"] and b["isrc"] and a["isrc"] == b["isrc"]:
        return True
    return normalized_title(a["title"]) == normalized_title(b["title"]) and bool(
        artists(a["artist_names"]) & artists(b["artist_names"])
    )


def recording_key(row) -> tuple:
    if row["isrc"]:
        return ("isrc", row["isrc"])
    return ("metadata", normalized_title(row["title"]), tuple(sorted(artists(row["artist_names"]))))


def bpm_distance(a: float, b: float) -> float:
    return min(1.0, min(abs(a - b), abs(a * 2 - b), abs(a - b * 2)) / 25.0)


def canonical_key(value: str | None) -> str:
    text = (value or "").lower().replace("-major", "").replace(" major", "")
    text = text.replace("-minor", "m").replace(" minor", "m").replace("♯", "#").replace("♭", "b")
    return text.replace(" ", "")


def harmonic_distance(a: str | None, b: str | None) -> float:
    ca, cb = KEY_TO_CAMELOT.get(canonical_key(a)), KEY_TO_CAMELOT.get(canonical_key(b))
    if not ca or not cb:
        return 0.0 if canonical_key(a) == canonical_key(b) else 1.0
    na, la, nb, lb = int(ca[:-1]), ca[-1], int(cb[:-1]), cb[-1]
    if ca == cb:
        return 0.0
    if na == nb and la != lb:  # relative major/minor
        return 0.18
    if la == lb and ((na - nb) % 12 in {1, 11}):
        return 0.25
    return 1.0


def weighted_jaccard(a: dict[str, float], b: dict[str, float], idf: dict[str, float]) -> float:
    keys = set(a) | set(b)
    if not keys:
        return 0.0
    union = sum(max(a.get(k, 0.0), b.get(k, 0.0)) * idf.get(k, 1.0) for k in keys)
    overlap = sum(min(a.get(k, 0.0), b.get(k, 0.0)) * idf.get(k, 1.0) for k in keys)
    return overlap / union if union else 0.0


def embedding_family(model: str) -> str | None:
    lowered = model.casefold()
    if "clap" in lowered:
        return "clap"
    if "maest" in lowered:
        return "maest"
    return None


def load_embeddings(db, seed_id: str) -> dict[str, dict[str, np.ndarray]]:
    """Load only model versions present for the seed, preferring newest per family."""
    selected = {}
    for row in db.execute(
        "SELECT model,updated_at FROM audio_embeddings WHERE spotify_id=? ORDER BY updated_at DESC",
        (seed_id,),
    ):
        family = embedding_family(row["model"])
        if family and family not in selected:
            selected[family] = row["model"]
    output = {family: {} for family in selected}
    for family, model in selected.items():
        for row in db.execute(
            "SELECT spotify_id,dimensions,dtype,vector FROM audio_embeddings WHERE model=?",
            (model,),
        ):
            if row["dtype"] != "float16+zlib":
                continue
            vector = np.frombuffer(zlib.decompress(row["vector"]), dtype=np.float16).astype(np.float32)
            if len(vector) != int(row["dimensions"]):
                continue
            norm = float(np.linalg.norm(vector))
            if norm > 1e-8:
                output[family][row["spotify_id"]] = vector / norm
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("seed", help="Spotify track ID/URL, or title search")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--exclude-same-artist", action="store_true")
    args = parser.parse_args()
    db = connect()
    sid = spotify_id(args.seed)
    if not sid:
        row = db.execute(
            "SELECT spotify_id FROM track_search WHERE track_search MATCH ? ORDER BY rank LIMIT 1",
            (args.seed,),
        ).fetchone()
        sid = row["spotify_id"] if row else None
    tracks = {r["spotify_id"]: r for r in db.execute(
        "SELECT spotify_id,title,artist_names,isrc,release_date,duration_ms FROM tracks"
    )}
    if not sid or sid not in tracks:
        raise SystemExit("Seed track was not found")

    policies = {(r["source"], r["field"]): float(r["similarity_weight"])
                for r in db.execute("SELECT * FROM source_field_policy")}
    best: dict[str, dict[str, tuple[object, str, float]]] = defaultdict(dict)
    columns = ["bpm", "key", *FIELDS]
    for row in db.execute("SELECT spotify_id,source,bpm,key,energy,danceability,valence,acousticness,instrumentalness,speechiness,liveness,loudness FROM audio_features"):
        for field in columns:
            value = row[field]
            if value is None:
                continue
            quality = policies.get((row["source"], field), DEFAULT_SOURCE_WEIGHT.get((row["source"], field), 0.40))
            old = best[row["spotify_id"]].get(field)
            if not old or quality > old[2]:
                best[row["spotify_id"]][field] = (value, row["source"], quality)

    tags: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    for row in db.execute("SELECT spotify_id,tag,tag_type,confidence FROM tags WHERE tag_type IN ('subgenre','genre','mood','instrument','voice')"):
        confidence = float(row["confidence"] if row["confidence"] is not None else 0.35)
        current = tags[row["spotify_id"]][row["tag_type"]].get(row["tag"], 0.0)
        tags[row["spotify_id"]][row["tag_type"]][row["tag"]] = max(current, confidence)
    document_frequency: dict[str, dict[str, int]] = defaultdict(dict)
    for tag_type in TAG_WEIGHTS:
        for row in db.execute(
            "SELECT tag,COUNT(DISTINCT spotify_id) AS n FROM tags WHERE tag_type=? GROUP BY tag",
            (tag_type,),
        ):
            document_frequency[tag_type][row["tag"]] = int(row["n"])
    tag_idf = {
        tag_type: {
            tag: 1.0 + math.log((len(tracks) + 1.0) / (count + 1.0))
            for tag, count in counts.items()
        }
        for tag_type, counts in document_frequency.items()
    }
    rhythm = defaultdict(dict)
    for row in db.execute(
        """SELECT spotify_id,attribute,value_text,confidence FROM track_attributes
           WHERE attribute IN ('beat_presence','rhythm_pattern')"""
    ):
        rhythm[row["spotify_id"]][row["attribute"]] = (
            row["value_text"], float(row["confidence"] or 0.0)
        )
    embeddings = load_embeddings(db, sid)

    seed_track, seed_features = tracks[sid], best.get(sid, {})
    scored = []
    for candidate_id, candidate_track in tracks.items():
        if candidate_id == sid or same_recording(seed_track, candidate_track) or (
            args.exclude_same_artist and artists(candidate_track["artist_names"]) & artists(seed_track["artist_names"])
        ):
            continue
        candidate_features = best.get(candidate_id, {})
        distance = weight = 0.0
        common = 0
        for field, base_weight in FIELDS.items():
            if field in seed_features and field in candidate_features:
                a, _, qa = seed_features[field]; b, _, qb = candidate_features[field]
                pair_weight = base_weight * math.sqrt(qa * qb)
                distance += pair_weight * (float(a) - float(b)) ** 2
                weight += pair_weight; common += 1
        if "bpm" in seed_features and "bpm" in candidate_features:
            a, _, qa = seed_features["bpm"]; b, _, qb = candidate_features["bpm"]
            pair_weight = 1.65 * math.sqrt(qa * qb)
            distance += pair_weight * bpm_distance(float(a), float(b)) ** 2
            weight += pair_weight; common += 1
        if "key" in seed_features and "key" in candidate_features:
            a, _, qa = seed_features["key"]; b, _, qb = candidate_features["key"]
            pair_weight = 0.55 * math.sqrt(qa * qb)
            distance += pair_weight * harmonic_distance(str(a), str(b)) ** 2
            weight += pair_weight; common += 1
        for tag_type, base_weight in TAG_WEIGHTS.items():
            a = tags[sid][tag_type]; b = tags[candidate_id][tag_type]
            if a and b:
                distance += base_weight * (1.0 - weighted_jaccard(a, b, tag_idf[tag_type])) ** 2
                weight += base_weight; common += 1
            elif a and tag_type == "genre":
                # Unknown genre must not outrank a well-tagged compatible track
                # merely by avoiding this comparison altogether.
                missing_weight = base_weight * 0.70
                distance += missing_weight * 0.75 ** 2
                weight += missing_weight
        for attribute, base_weight in (("beat_presence", 0.90), ("rhythm_pattern", 1.35)):
            seed_value = rhythm[sid].get(attribute)
            candidate_value = rhythm[candidate_id].get(attribute)
            if not seed_value or not candidate_value or "unknown" in {seed_value[0], candidate_value[0]}:
                continue
            pair_weight = base_weight * (seed_value[1] * candidate_value[1]) ** 0.5
            distance += pair_weight * (0.0 if seed_value[0] == candidate_value[0] else 1.0)
            weight += pair_weight
            common += 1
        for family, vectors in embeddings.items():
            seed_vector, candidate_vector = vectors.get(sid), vectors.get(candidate_id)
            if seed_vector is None or candidate_vector is None:
                continue
            cosine = float(np.clip(np.dot(seed_vector, candidate_vector), -1.0, 1.0))
            embedding_distance = (1.0 - cosine) * 0.5
            pair_weight = EMBEDDING_WEIGHTS[family]
            distance += pair_weight * embedding_distance ** 2
            weight += pair_weight
            common += 1
        if common >= 3 and weight:
            similarity = 100.0 * (1.0 - min(1.0, math.sqrt(distance / weight)))
            scored.append((similarity, common, candidate_track, candidate_features))

    scored.sort(key=lambda item: (-item[0], -item[1]))
    print(f"Seed: {seed_track['title']} — {seed_track['artist_names']}\n")
    displayed = set()
    index = 0
    for score, common, row, features in scored:
        identity = recording_key(row)
        if identity in displayed:
            continue
        displayed.add(identity)
        index += 1
        bpm = f"{float(features['bpm'][0]):.1f}" if "bpm" in features else "?"
        key = str(features["key"][0]) if "key" in features else "?"
        print(f"{index:>2}. {score:5.1f}%  {row['title']} — {row['artist_names']}  BPM {bpm}  key {key}  [{common} signals]")
        if index >= args.limit:
            break


if __name__ == "__main__":
    main()
