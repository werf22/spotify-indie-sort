#!/usr/bin/env python3
"""Build a diverse, sensual Spotify playlist around one reference track.

The ranking is deliberately local and free: it combines the user's own playlist
context, accumulated genre/mood tags, and audio-feature distance.  Spotify is
only contacted with --create, after the dry-run has been inspected.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from spotify_client import SpotifyClient


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "music.db"
SEED_ID = "5mPD9BQWOOglxSOV9S9htW"

FEATURE_PRIORITY = {
    "reccobeats": 0,
    "spotify_legacy_dataset": 1,
    "freqblog": 2,
    "onetagger": 3,
    "acousticbrainz": 4,
    "deezer": 5,
}

MOOD_WEIGHTS = {
    "sensual": 11.0,
    "seductive": 9.0,
    "sultry": 9.0,
    "sexy": 7.0,
    "intimate": 5.0,
    "romantic": 4.5,
    "hypnotic": 3.5,
    "nocturnal": 3.0,
    "ethereal": 2.7,
    "dreamy": 2.6,
    "mysterious": 2.4,
    "lush": 2.2,
    "tender": 2.0,
    "yearning": 1.8,
    "warm": 1.5,
    "dark": 1.2,
}

GENRE_WEIGHTS = {
    "trip hop": 5.0,
    "downtempo": 4.2,
    "organic downtempo": 4.0,
    "world bass": 3.7,
    "alternative r&b": 3.6,
    "neo soul": 3.5,
    "neo-soul": 3.5,
    "folktronica": 3.3,
    "ambient pop": 3.0,
    "dream pop": 2.8,
    "electronica": 2.2,
    "chillout": 2.2,
    "soul": 2.0,
    "organic house": 1.8,
    "deep house": 1.2,
}

NEGATIVE_TERMS = {
    "hardstyle": 9.0,
    "hardcore": 8.0,
    "gabber": 9.0,
    "metal": 7.0,
    "punk": 5.5,
    "drill": 5.0,
    "big room": 5.0,
    "psytrance": 4.0,
    "aggressive": 4.0,
    "workout": 3.0,
    "children": 8.0,
    "comedy": 8.0,
}

TARGET = {
    "bpm": 135.941,
    "energy": 0.382,
    "danceability": 0.778,
    "valence": 0.369,
    "acousticness": 0.217,
    "instrumentalness": 0.189,
    "speechiness": 0.0814,
    "liveness": 0.108,
    "loudness": -12.247,
}


def normalized(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode()
    value = value.casefold()
    value = re.sub(r"\b(remaster(?:ed)?|radio|album|single|original|extended|edit|version|mix)\b", " ", value)
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def split_terms(value: str | None) -> set[str]:
    if not value:
        return set()
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return {str(x).strip().casefold() for x in parsed if str(x).strip()}
    except (json.JSONDecodeError, TypeError):
        pass
    return {x.strip().casefold() for x in value.split("|") if x.strip()}


def similarity(value: float | None, target: float, scale: float) -> float:
    if value is None:
        return 0.25
    return math.exp(-((value - target) / scale) ** 2)


def tempo_similarity(value: float | None) -> float:
    if not value or value <= 0:
        return 0.25
    variants = (value, value * 2, value / 2)
    delta = min(abs(x - TARGET["bpm"]) for x in variants)
    return math.exp(-((delta / 18.0) ** 2))


def best_features(conn: sqlite3.Connection) -> dict[str, dict[str, float | str | None]]:
    result: dict[str, dict[str, float | str | None]] = {}
    sources: dict[str, dict[str, int]] = defaultdict(dict)
    fields = (
        "bpm", "key", "mode", "danceability", "energy", "valence", "acousticness",
        "instrumentalness", "speechiness", "liveness", "loudness",
    )
    rows = conn.execute(
        "SELECT spotify_id,source,bpm,key,mode,danceability,energy,valence,"
        "acousticness,instrumentalness,speechiness,liveness,loudness FROM audio_features"
    )
    for row in rows:
        sid, source = row[0], row[1]
        priority = FEATURE_PRIORITY.get(source, 8)
        target = result.setdefault(sid, {})
        for field, value in zip(fields, row[2:]):
            if value is not None and priority < sources[sid].get(field, 99):
                target[field] = value
                sources[sid][field] = priority
    return result


def load_tags(conn: sqlite3.Connection) -> dict[str, set[str]]:
    tags: dict[str, set[str]] = defaultdict(set)
    for sid, tag in conn.execute("SELECT spotify_id,lower(tag) FROM tags"):
        tags[sid].add(tag.strip())
    return tags


def rank_tracks(conn: sqlite3.Connection) -> list[dict]:
    features = best_features(conn)
    tags = load_tags(conn)
    seed_artists = {"siren & seer", "saqi", "diamonde"}
    ranked: list[dict] = []

    rows = conn.execute(
        "SELECT spotify_id,uri,title,artist_names,isrc,genres,library_sources,popularity "
        "FROM tracks WHERE length(spotify_id)=22"
    )
    for sid, uri, title, artist_names, isrc, genres_raw, sources_raw, popularity in rows:
        track_tags = tags.get(sid, set()) | split_terms(genres_raw)
        sources_text = (sources_raw or "").casefold()
        artists = {x.strip().casefold() for x in artist_names.split(",") if x.strip()}
        f = features.get(sid, {})

        sensual_source = any(x in sources_text for x in ("sensual", "sexy", "tantra"))
        positive_tags = sum(MOOD_WEIGHTS.get(x, 0) + GENRE_WEIGHTS.get(x, 0) for x in track_tags)
        artist_overlap = bool(artists & seed_artists)
        eligible = sid == SEED_ID or sensual_source or positive_tags >= 2.0 or artist_overlap
        if not eligible:
            continue

        score = 0.0
        reasons: list[str] = []
        if sensual_source:
            score += 9.0
            reasons.append("sensual-playlist")
            if "deep sensual" in sources_text or "tantra" in sources_text:
                score += 1.5
        if "sensual" in track_tags:
            reasons.append("sensual-tag")

        score += min(16.0, positive_tags)
        score -= sum(weight for term, weight in NEGATIVE_TERMS.items() if term in track_tags)

        if artist_overlap:
            score += 10.0 + 2.0 * len(artists & seed_artists)
            reasons.append("seed-artist")

        audio_score = (
            2.2 * tempo_similarity(f.get("bpm"))
            + 2.0 * similarity(f.get("energy"), TARGET["energy"], 0.22)
            + 2.2 * similarity(f.get("danceability"), TARGET["danceability"], 0.19)
            + 1.5 * similarity(f.get("valence"), TARGET["valence"], 0.24)
            + 0.8 * similarity(f.get("acousticness"), TARGET["acousticness"], 0.38)
            + 0.8 * similarity(f.get("instrumentalness"), TARGET["instrumentalness"], 0.38)
            + 0.5 * similarity(f.get("speechiness"), TARGET["speechiness"], 0.15)
            + 0.3 * similarity(f.get("liveness"), TARGET["liveness"], 0.20)
            + 0.5 * similarity(f.get("loudness"), TARGET["loudness"], 7.0)
        )
        score += audio_score

        energy = f.get("energy")
        valence = f.get("valence")
        speechiness = f.get("speechiness")
        if energy is not None and energy > 0.72:
            score -= (energy - 0.72) * 14
        if valence is not None and valence > 0.78:
            score -= (valence - 0.78) * 9
        if speechiness is not None and speechiness > 0.30:
            score -= (speechiness - 0.30) * 10
        score += min(0.7, (popularity or 0) / 100.0 * 0.7)

        ranked.append(
            {
                "id": sid,
                "uri": uri or f"spotify:track:{sid}",
                "title": title,
                "artists": artist_names,
                "artist_set": artists,
                "primary_artist": normalized(artist_names.split(",")[0]),
                "isrc": (isrc or "").upper(),
                "tags": track_tags,
                "score": score,
                "reasons": reasons,
                **{k: f.get(k) for k in TARGET},
            }
        )

    ranked.sort(key=lambda x: (x["id"] != SEED_ID, -x["score"], x["title"]))
    return ranked


def diversify(ranked: list[dict], limit: int) -> list[dict]:
    chosen: list[dict] = []
    seen_isrc: set[str] = set()
    seen_recording: set[tuple[str, str]] = set()
    primary_counts: Counter[str] = Counter()
    artist_combo_counts: Counter[str] = Counter()

    # First pass keeps the list broad. A second pass relaxes only the artist cap.
    for artist_cap in (3, 5, 8):
        for track in ranked:
            if track in chosen:
                continue
            recording = (normalized(track["title"]), normalized(track["artists"]))
            combo = normalized(track["artists"])
            if track["isrc"] and track["isrc"] in seen_isrc:
                continue
            if recording in seen_recording:
                continue
            if primary_counts[track["primary_artist"]] >= artist_cap:
                continue
            if artist_combo_counts[combo] >= 2 and track["id"] != SEED_ID:
                continue
            chosen.append(track)
            if track["isrc"]:
                seen_isrc.add(track["isrc"])
            seen_recording.add(recording)
            primary_counts[track["primary_artist"]] += 1
            artist_combo_counts[combo] += 1
            if len(chosen) == limit:
                return chosen
    return chosen


def print_preview(chosen: list[dict], preview: int) -> None:
    print(f"Selected: {len(chosen)} tracks")
    for i, t in enumerate(chosen[:preview], 1):
        feature_text = (
            f"bpm={t.get('bpm')!s:<7} e={t.get('energy')!s:<5} "
            f"d={t.get('danceability')!s:<5} v={t.get('valence')!s:<5}"
        )
        relevant = sorted((t["tags"] & (set(MOOD_WEIGHTS) | set(GENRE_WEIGHTS))))[:6]
        print(
            f"{i:3}. {t['score']:5.1f}  {t['title']} — {t['artists']}  "
            f"[{feature_text}; {', '.join(relevant)}]"
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--preview", type=int, default=50)
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--name", default="Made of Gold — Sensual 200")
    args = parser.parse_args()
    if args.limit < 1 or args.limit > 500:
        raise SystemExit("--limit must be between 1 and 500")

    conn = sqlite3.connect(DB_PATH)
    chosen = diversify(rank_tracks(conn), args.limit)
    conn.close()
    if len(chosen) != args.limit:
        raise SystemExit(f"Only {len(chosen)} sufficiently diverse tracks were found")
    print_preview(chosen, args.preview)

    if not args.create:
        print("DRY RUN: Spotify was not changed.")
        return

    client = SpotifyClient()
    me = client.current_user()
    playlist = client.create_playlist(
        me["id"],
        args.name,
        "200 sensual, intimate and hypnotic tracks selected around Made of Gold "
        "by Siren & Seer, SaQi & Diamonde using my personal DJ music database.",
        public=False,
    )
    client.add_tracks(playlist["id"], [track["uri"] for track in chosen])
    payload = client.request("GET", f"/playlists/{playlist['id']}").json()
    actual = payload.get("tracks", {}).get("total")
    if actual != args.limit:
        raise RuntimeError(f"Spotify verification failed: expected {args.limit}, got {actual}")
    print(f"CREATED: {actual} tracks -> {playlist['external_urls']['spotify']}")


if __name__ == "__main__":
    main()
