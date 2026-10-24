#!/usr/bin/env python3
"""Shared tools for the Halloween Ecstatic Dance pools (10 playlists: Dark/Light x energy 1-5).

INPUT:  the four seed playlists on Spotify (SEEDS) and, later, candidate lists in
        halloween_ed/candidates/<dark|light>_<1-5>.txt ("Artist | Title" per line).
OUTPUT: data/halloween_ed/features.json (cache: Spotify id -> ReccoBeats features)
        and data/halloween_ed/seeds.json (every seed track with its suggested bucket).

WHY MEASURE AT ALL: Spotify's own audio-features endpoint is closed to new apps, so
ReccoBeats (free, exact Spotify ids) is the independent signal. It is a plausibility
check, NOT ground truth - tempo detection halves/doubles on slow tracks.

HOW TO TWEAK: the energy cut-offs (ENERGY_CUTS) and the Dark/Light line (DARK_VALENCE)
are the only knobs. Raise a cut-off and fewer tracks land in the higher buckets.
Usage:  ./.venv/bin/python halloween_pools.py seeds
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
WORK = ROOT / "data" / "halloween_ed"
FEATURES = WORK / "features.json"
RECCO = "https://api.reccobeats.com/v1/audio-features"

# The four playlists the owner named as the core of the night.
SEEDS = {
    "dark_moody": "5bWJhkCcVEaZFf5Tndld5I",      # Temny Zmyselny Moody Vajb
    "night_traveling": "66qoJtoH2f8qaoiank1wP6",  # Night Traveling (3)
    "ritual_snake": "3lwUQ1ngIqyPkV0xVPKfrG",     # Ritual Snake to Horse 2026
    "ritual_new": "6LQPA9qcaKOPkSmWP3seW8",       # Ritual New
}

# dance-floor energy index (0..1) -> owner's scale 1..5. Index = 0.55*energy +
# 0.30*danceability + 0.15*tempo (60 BPM -> 0, 140 BPM -> 1). Upper bound of each level.
# Calibrated on ~30 known tracks (Creep/Glory Box/Teardrop = 2, Black Hole = 3, Run Away
# = 4, ARTBAT remix/Bleed It Out = 5): Spotify-style "energy" rates loud rock very high,
# so the cuts sit higher than a plain split of 0..1 would put them.
ENERGY_CUTS = (0.33, 0.55, 0.70, 0.82)   # below -> 1,2,3,4 ; above the last -> 5
DARK_VALENCE = 0.40                      # valence below this reads Dark
DARK_VALENCE_MINOR = 0.50                # ... or below this when the track is in a minor key


def dance_index(f: dict) -> float:
    bpm = f.get("tempo") or 100
    if bpm > 150:        # detectors double slow tracks (Starboy 186, Heart-Shaped Box 203)
        bpm /= 2
    tempo = min(max(bpm - 60, 0), 80) / 80
    return 0.55 * (f.get("energy") or 0) + 0.30 * (f.get("danceability") or 0) + 0.15 * tempo


def bucket(f: dict) -> tuple[int, str]:
    """(energy 1..5, 'dark'|'light') for one ReccoBeats feature record."""
    idx = dance_index(f)
    level = 1 + sum(idx >= cut for cut in ENERGY_CUTS)
    v = f.get("valence")
    v = 0.5 if v is None else v
    dark = v < DARK_VALENCE or (f.get("mode") == 0 and v < DARK_VALENCE_MINOR)
    return level, "dark" if dark else "light"


def load_features() -> dict:
    return json.loads(FEATURES.read_text()) if FEATURES.exists() else {}


def fetch_features(ids: list[str]) -> dict:
    """Features for `ids`, using the cache; ReccoBeats takes 40 ids per request."""
    WORK.mkdir(parents=True, exist_ok=True)
    cache = load_features()
    todo = [i for i in dict.fromkeys(ids) if i not in cache]
    for start in range(0, len(todo), 40):
        batch = todo[start:start + 40]
        for attempt in range(5):
            r = requests.get(RECCO, params={"ids": ",".join(batch)}, timeout=45,
                             headers={"Accept": "application/json", "User-Agent": "local-dj-music-db/1.0"})
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", "5")) + 1)
                continue
            r.raise_for_status()
            break
        else:
            raise RuntimeError(f"ReccoBeats kept returning 429 for batch at {start}")
        found = {}
        for item in r.json().get("content", []):
            sid = (item.get("href") or "").rsplit("/", 1)[-1]
            if sid:
                found[sid] = item
        for sid in batch:
            cache[sid] = found.get(sid)          # None = ReccoBeats has no data (kept, not retried)
        FEATURES.write_text(json.dumps(cache))
        time.sleep(0.4)
    return cache


def seed_rows(refresh: bool) -> list[dict]:
    """The 416 seed tracks. Re-reads Spotify only with `refresh`; otherwise the saved copy."""
    saved = WORK / "seeds.json"
    if saved.exists() and not refresh:
        return [{k: r[k] for k in ("id", "seed", "title", "artist")} for r in json.loads(saved.read_text())]
    from spotify_client import SpotifyClient       # imported late: needs .env + token
    client, rows = SpotifyClient(), []
    for name, pid in SEEDS.items():
        for item in client.playlist_tracks(pid):
            t = item.get("track") or {}
            if t.get("id"):
                rows.append({"id": t["id"], "seed": name, "title": t["name"],
                             "artist": ", ".join(a["name"] for a in t["artists"])})
    return rows


def cmd_seeds() -> None:
    rows = seed_rows(refresh="--refresh" in sys.argv)
    seen = {r["id"] for r in rows}
    feats = fetch_features([r["id"] for r in rows])
    counts, missing = {}, 0
    for r in rows:
        f = feats.get(r["id"])
        if f is None:
            r["bucket"] = None
            missing += 1
            continue
        r.update(energy=f.get("energy"), valence=f.get("valence"), tempo=f.get("tempo"),
                 danceability=f.get("danceability"), mode=f.get("mode"))
        r["level"], r["mood"] = bucket(f)
        counts[(r["mood"], r["level"])] = counts.get((r["mood"], r["level"]), 0) + 1
    (WORK / "seeds.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))
    print(f"seed rows: {len(rows)}  unique tracks: {len(seen)}  without features: {missing}")
    for mood in ("dark", "light"):
        print(mood, [counts.get((mood, lvl), 0) for lvl in range(1, 6)], "(energy 1..5)")


if __name__ == "__main__":
    {"seeds": cmd_seeds}.get(sys.argv[1] if len(sys.argv) > 1 else "", lambda: sys.exit(__doc__))()
