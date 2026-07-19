"""Stratified FreqBlog validation on underground and control tracks."""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import re
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from dotenv import load_dotenv

from enrich_freqblog import ensure_status_schema, post_bulk, save_success
from musicdb import connect

ROOT = Path(__file__).resolve().parent
VERSION_WORDS = re.compile(r"\b(remix|mix|mixed|edit|radio|extended|original|reinterpretation|version)\b", re.I)
UNDERGROUND = ("afro house", "afro tech", "organic house", "tribal house", "downtempo", "ethnotronica")
CONTROL = ("indie", "alternative", "post-punk", "dream pop", "shoegaze")


def norm(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    return " ".join("".join(c.lower() if c.isalnum() else " " for c in text).split())


def first_artist(value: str | None) -> str:
    return (value or "").split(",", 1)[0].strip()


def stable_order(row) -> str:
    return hashlib.sha1(row["spotify_id"].encode()).hexdigest()


def select_unique(rows, count: int, seen: set[tuple[str, str]], max_per_artist: int = 999) -> list:
    chosen = []
    artist_counts: Counter[str] = Counter()
    # Alternate ISRC-bearing and name-only candidates while remaining deterministic.
    ordered = sorted(rows, key=lambda r: (stable_order(r), r["spotify_id"]))
    ordered = sorted(ordered, key=lambda r: 0 if bool(r["isrc"]) == (len(chosen) % 2 == 0) else 1)
    for row in ordered:
        artist = norm(first_artist(row["artist_names"]))
        identity = (artist, norm(row["title"]))
        if identity in seen or artist_counts[artist] >= max_per_artist:
            continue
        chosen.append(row)
        seen.add(identity)
        artist_counts[artist] += 1
        if len(chosen) >= count:
            break
    return chosen


def sample_tracks(db, target: int) -> list[tuple[str, object]]:
    rows = db.execute(
        """SELECT spotify_id,title,artist_names,isrc,genres,popularity
           FROM tracks WHERE title<>'' AND artist_names<>''"""
    ).fetchall()
    tebra = [r for r in rows if "tebra" in {norm(x) for x in (r["artist_names"] or "").split(",")}]
    tebra_original = [r for r in tebra if norm(first_artist(r["artist_names"])) == "tebra" and not VERSION_WORDS.search(r["title"])]
    tebra_versions = [r for r in tebra if VERSION_WORDS.search(r["title"])]
    tebra_collabs = [r for r in tebra if norm(first_artist(r["artist_names"])) != "tebra" and not VERSION_WORDS.search(r["title"])]

    genre_by_track: dict[str, set[str]] = defaultdict(set)
    for tag in db.execute("SELECT spotify_id,tag FROM tags WHERE tag_type='genre'"):
        genre_by_track[tag["spotify_id"]].add(norm(tag["tag"]))

    underground = []
    controls = []
    tebra_ids = {r["spotify_id"] for r in tebra}
    for row in rows:
        if row["spotify_id"] in tebra_ids:
            continue
        genres = genre_by_track[row["spotify_id"]] | {norm(x) for x in (row["genres"] or "").split(",")}
        popularity = row["popularity"]
        if any(any(term in genre for genre in genres) for term in UNDERGROUND) and (popularity is None or popularity <= 15):
            underground.append(row)
        if any(any(term in genre for genre in genres) for term in CONTROL):
            controls.append(row)

    seen: set[tuple[str, str]] = set()
    groups = [
        ("tebra_original", tebra_original, 40, 999),
        ("tebra_versions", tebra_versions, 50, 999),
        ("tebra_collabs", tebra_collabs, 30, 999),
        ("underground_other", underground, 60, 2),
        ("indie_control", controls, 20, 2),
    ]
    result = []
    for name, pool, count, max_artist in groups:
        result.extend((name, row) for row in select_unique(pool, count, seen, max_artist))
    if len(result) < target:
        remainder = select_unique(underground + controls + tebra, target - len(result), seen, 3)
        result.extend(("underground_extra", row) for row in remainder)
    return result[:target]


def payload(row) -> dict:
    item = {"track": row["title"][:200], "artist": first_artist(row["artist_names"])[:200]}
    if row["isrc"]:
        item["isrc"] = row["isrc"][:15]
    return item


def lookup_batches(api_key: str, items: list[tuple[str, object]]) -> tuple[dict[str, dict], int]:
    results: dict[str, dict] = {}
    used = 0
    for start in range(0, len(items), 50):
        batch = items[start : start + 50]
        response, _ = post_bulk(api_key, [payload(row) for _, row in batch], timeout=120)
        used += int(response.get("requests_used") or 0)
        api_results = response.get("results") or []
        if len(api_results) != len(batch):
            raise RuntimeError(f"batch result mismatch: {len(api_results)} vs {len(batch)}")
        for (_, row), result in zip(batch, api_results):
            results[row["spotify_id"]] = result
    return results, used


def decode_onetagger_key(value: str | None) -> str | None:
    if not value:
        return None
    try:
        data = json.loads(base64.b64decode(value).decode())
        return data.get("key")
    except Exception:
        return value


def canonical_key(value: str | None) -> str | None:
    if not value:
        return None
    value = value.replace("-Major", "").replace("-Minor", "m").replace("♯", "#").replace("♭", "b")
    enharmonic = {"Db": "C#", "Eb": "D#", "Gb": "F#", "Ab": "G#", "Bb": "A#"}
    minor = value.endswith("m")
    root = value[:-1] if minor else value
    return enharmonic.get(root, root) + ("m" if minor else "")


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=200)
    parser.add_argument("--retry", type=int, default=50, help="maximum queued tracks to retry once")
    parser.add_argument("--retry-wait", type=int, default=20)
    args = parser.parse_args()
    api_key = (os.getenv("FREQBLOG_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit("FREQBLOG_API_KEY is missing")
    db = connect()
    ensure_status_schema(db)
    sampled = sample_tracks(db, args.size)
    if len(sampled) < args.size:
        raise SystemExit(f"only selected {len(sampled)} of {args.size} requested tracks")

    initial, used = lookup_batches(api_key, sampled)
    queued_items = [item for item in sampled if (initial[item[1]["spotify_id"]].get("backfill_status") in {"queued", "processing"})]
    retried: dict[str, dict] = {}
    if queued_items and args.retry:
        time.sleep(args.retry_wait)
        retried, retry_used = lookup_batches(api_key, queued_items[: args.retry])
        used += retry_used

    final_results = dict(initial)
    final_results.update(retried)
    timestamp = datetime.now(timezone.utc).isoformat()
    details = []
    fields = ["bpm", "key", "camelot", "energy", "danceability", "valence", "acousticness",
              "instrumentalness", "liveness", "speechiness", "loudness_db", "mood", "genre",
              "release_date", "duration_ms", "isrc"]
    onetagger = {
        r["spotify_id"]: r for r in db.execute(
            "SELECT spotify_id,key,energy FROM audio_features WHERE source='onetagger'"
        )
    }
    field_counts = Counter()
    group_counts = Counter()
    found_by_group = Counter()
    identity_ok = suspicious = 0
    key_agree = key_compared = 0
    energy_deltas = []

    for group, row in sampled:
        result = final_results[row["spotify_id"]]
        data = result.get("result") if result.get("found") else None
        group_counts[group] += 1
        status = "found" if data else (result.get("backfill_status") or "not_found")
        title_similarity = artist_similarity = None
        missing = fields[:]
        if data:
            found_by_group[group] += 1
            for field in fields:
                if data.get(field) is not None:
                    field_counts[field] += 1
            missing = [f for f in fields if data.get(f) is None]
            title_similarity = SequenceMatcher(None, norm(row["title"]), norm(data.get("track_name"))).ratio()
            artist_similarity = SequenceMatcher(None, norm(first_artist(row["artist_names"])), norm(data.get("artist_name"))).ratio()
            good_identity = title_similarity >= 0.82 and artist_similarity >= 0.55
            identity_ok += good_identity
            suspicious += not good_identity
            save_success(db, row, data, timestamp)
            old = onetagger.get(row["spotify_id"])
            if old:
                old_key = canonical_key(decode_onetagger_key(old["key"]))
                new_key = canonical_key(data.get("key"))
                if old_key and new_key:
                    key_compared += 1
                    key_agree += old_key == new_key
                if old["energy"] is not None and data.get("energy") is not None:
                    old_energy = float(old["energy"])
                    old_energy = old_energy / 10.0 if old_energy > 1 else old_energy
                    energy_deltas.append(abs(old_energy - float(data["energy"])))
        details.append({
            "group": group, "spotify_id": row["spotify_id"], "title": row["title"],
            "artist": row["artist_names"], "input_isrc": row["isrc"] or "", "status": status,
            "matched_title": data.get("track_name") if data else "",
            "matched_artist": data.get("artist_name") if data else "",
            "title_similarity": round(title_similarity, 3) if title_similarity is not None else "",
            "artist_similarity": round(artist_similarity, 3) if artist_similarity is not None else "",
            "bpm": data.get("bpm") if data else "", "key": data.get("key") if data else "",
            "camelot": data.get("camelot") if data else "", "energy": data.get("energy") if data else "",
            "danceability": data.get("danceability") if data else "", "valence": data.get("valence") if data else "",
            "mood": data.get("mood") if data else "", "genre": data.get("genre") if data else "",
            "feature_source": data.get("feature_source") if data else "", "missing_fields": ",".join(missing),
        })

    found = sum(found_by_group.values())
    output_dir = ROOT / "data"
    json_path = output_dir / "freqblog_validation.json"
    csv_path = output_dir / "freqblog_validation.csv"
    report_path = output_dir / "freqblog_validation.md"
    json_path.write_text(json.dumps({"created_at": timestamp, "quota_requests": used, "details": details}, ensure_ascii=False, indent=2))
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=details[0].keys())
        writer.writeheader(); writer.writerows(details)

    lines = [
        "# FreqBlog validation", "", f"Tested: **{len(sampled)}**", f"Quota requests used: **{used}**",
        f"Found after one retry: **{found}/{len(sampled)} ({found/len(sampled):.1%})**",
        f"Identity checks passed: **{identity_ok}/{found}**; suspicious: **{suspicious}**", "",
        "## Coverage among found tracks", "",
    ]
    for field in fields:
        lines.append(f"- {field}: {field_counts[field]}/{found} ({field_counts[field]/found:.1%})" if found else f"- {field}: 0")
    lines.extend(["", "## By group", ""])
    for group in group_counts:
        lines.append(f"- {group}: {found_by_group[group]}/{group_counts[group]} ({found_by_group[group]/group_counts[group]:.1%})")
    lines.extend(["", "## Existing OneTagger comparison", ""])
    lines.append(f"- Key agreement: {key_agree}/{key_compared} ({key_agree/key_compared:.1%})" if key_compared else "- Key agreement: no overlap")
    lines.append(f"- Energy mean absolute difference: {sum(energy_deltas)/len(energy_deltas):.3f}" if energy_deltas else "- Energy: no overlap")
    report_path.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nDetails: {csv_path}\nRaw: {json_path}\nReport: {report_path}")


if __name__ == "__main__":
    main()
