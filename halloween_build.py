#!/usr/bin/env python3
"""Resolve candidate lists to Spotify tracks, measure them, and build the playlists.

INPUT:  halloween_ed/candidates/<dark|light>_<1-5>.txt  ("Artist | Title" per line)
OUTPUT: data/halloween_ed/resolved.json   (cache: "artist | title" -> Spotify track or null)
        data/halloween_ed/playlists.json  (bucket -> Spotify playlist id; makes build re-runnable)
        private Spotify playlists "ED Halloween - Dark 3" etc. (only with `build`)

Usage:  ./.venv/bin/python halloween_build.py resolve dark_3 light_3
        ./.venv/bin/python halloween_build.py check dark_3
        ./.venv/bin/python halloween_build.py build dark_3 --limit 30

PACING: one search per ~1.5 s. Spotify banned this app for hours once when duplicate
workers hammered it (docs/OPERATIONS.md) - never lower SEARCH_PAUSE to "speed it up",
and never run two of these at once. The cache makes every command safely resumable.
"""
from __future__ import annotations

import json
import re
import sys
import time
import unicodedata
from pathlib import Path

import requests

from halloween_pools import WORK, bucket, fetch_features

ROOT = Path(__file__).resolve().parent
CANDIDATES = ROOT / "halloween_ed" / "candidates"
RESOLVED = WORK / "resolved.json"
PLAYLISTS = WORK / "playlists.json"
SEARCH_PAUSE = 1.5                  # seconds between searches (on top of ~0.9 s response time)
MARKET = "SK"                       # the owner's Spotify country: unavailable tracks stay out
BAD_WORDS = ("karaoke", "tribute", "cover", "instrumental", "live", "remix", "edit", "version",
             "mix", "acoustic", "sped up", "slowed", "8d", "lullaby")


def norm(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    text = re.sub(r"\(.*?\)|\[.*?\]", " ", text)                 # (feat. x) (Remastered 2011)
    text = re.sub(r" - .*$", "", text)                            # " - Radio Edit" style suffix
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def read_candidates(name: str) -> list[tuple[str, str]]:
    out = []
    for line in (CANDIDATES / f"{name}.txt").read_text().splitlines():
        if line.strip() and not line.startswith("#") and "|" in line:
            artist, title = (p.strip() for p in line.split("|", 1))
            out.append((artist, title))
    return out


def score(hit: dict, artist: str, title: str) -> float:
    names = [norm(a["name"]) for a in hit["artists"]]
    if norm(hit["name"]) != norm(title) or not any(norm(artist) in n or n in norm(artist) for n in names):
        return -1
    pts = 3.0
    low_hit, low_want = hit["name"].lower(), title.lower()
    for w in BAD_WORDS:                       # a live/remix/karaoke copy only if the list asked for it
        if w in low_hit and w not in low_want:
            pts -= 3
    if hit["album"].get("album_type") == "compilation":
        pts -= 1.5
    return pts + (hit.get("popularity") or 0) / 100


def search_page(client, q: str):
    """One search, retried on Spotify 5xx / timeouts (a single 503 once killed a whole run)."""
    for attempt in range(6):
        try:
            return client.request("GET", "/search", params={"q": q, "type": "track", "limit": 10, "market": MARKET})
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as exc:
            code = getattr(getattr(exc, "response", None), "status_code", None)
            if code is not None and code < 500:
                raise                                   # 4xx is a real error, not a blip
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Spotify search kept failing for {q!r}")


def search_one(client, artist: str, title: str) -> dict | None:
    for q in (f'track:"{title}" artist:"{artist}"', f"{artist} {title}"):
        r = search_page(client, q)
        time.sleep(SEARCH_PAUSE)
        ranked = sorted(((score(h, artist, title), h) for h in r.json()["tracks"]["items"]), key=lambda x: -x[0])
        if ranked and ranked[0][0] > 0:
            h = ranked[0][1]
            return {"id": h["id"], "name": h["name"], "artists": [a["name"] for a in h["artists"]],
                    "album": h["album"]["name"], "isrc": (h.get("external_ids") or {}).get("isrc")}
    return None


def cmd_resolve(names: list[str]) -> None:
    from spotify_client import SpotifyClient
    client = SpotifyClient()
    cache = json.loads(RESOLVED.read_text()) if RESOLVED.exists() else {}
    for name in names:
        todo = [(a, t) for a, t in read_candidates(name) if f"{a} | {t}" not in cache]
        for i, (a, t) in enumerate(todo, 1):
            cache[f"{a} | {t}"] = search_one(client, a, t)     # RuntimeError on a long ban: stops loudly
            RESOLVED.write_text(json.dumps(cache, ensure_ascii=False, indent=0))
        got = [cache[f"{a} | {t}"] for a, t in read_candidates(name)]
        print(f"{name}: {sum(1 for g in got if g)}/{len(got)} resolved; "
              f"misses: {[f'{a} - {t}' for (a, t), g in zip(read_candidates(name), got) if not g]}")


def resolved_for(name: str) -> list[tuple[str, str, dict]]:
    cache = json.loads(RESOLVED.read_text())
    seen, out = set(), []
    for a, t in read_candidates(name):
        hit = cache.get(f"{a} | {t}")
        key = hit and (hit["isrc"] or hit["id"])
        if hit and key not in seen:
            seen.add(key)
            out.append((a, t, hit))
    return out


def cmd_check(name: str) -> list:
    """Print measured bucket for every resolved track; return rows (fit = measured level)."""
    intended = int(name.split("_")[1])
    rows = resolved_for(name)
    feats = fetch_features([h["id"] for _, _, h in rows])
    res = []
    for a, t, h in rows:
        f = feats.get(h["id"])
        lvl, mood = bucket(f) if f else (None, None)
        res.append((a, t, h, f, lvl, mood))
        tag = "  " if lvl == intended else ("~ " if lvl and abs(lvl - intended) == 1 else "! ")
        info = f"E{f['energy']:.2f} D{f['danceability']:.2f} V{f['valence']:.2f} {f['tempo']:.0f}bpm" if f else "no features"
        print(f"{tag}L{lvl} {mood or '-':5} {a[:24]:24} {t[:34]:34} {info}")
    exact = sum(1 for r in res if r[4] == intended)
    print(f"{name}: {len(res)} tracks, {exact} measure exactly level {intended}, "
          f"{sum(1 for r in res if r[4] and abs(r[4]-intended) == 1)} within one level")
    return res


def cmd_build(name: str, limit: int) -> None:
    from spotify_client import SpotifyClient
    client = SpotifyClient()
    state = json.loads(PLAYLISTS.read_text()) if PLAYLISTS.exists() else {}
    rows = [r for r in cmd_check(name) if r[4] and abs(r[4] - int(name.split("_")[1])) <= 1][:limit]
    if name not in state:
        mood, level = name.split("_")
        pl = client.create_playlist(client.current_user()["id"], f"ED Halloween - {mood.title()} {level}",
                                    f"Ecstatic Dance Halloween pool, {mood} energy {level}/5", public=False)
        state[name] = pl["id"]
        PLAYLISTS.write_text(json.dumps(state, indent=1))
    have = {i["track"]["id"] for i in client.playlist_tracks(state[name]) if i.get("track")}
    new = [f"spotify:track:{r[2]['id']}" for r in rows if r[2]["id"] not in have]
    client.add_tracks(state[name], new)
    print(f"{name}: playlist {state[name]} - added {len(new)}, already there {len(rows) - len(new)}")


if __name__ == "__main__":
    cmd, args = (sys.argv[1] if len(sys.argv) > 1 else ""), sys.argv[2:]
    lim = int(args[args.index("--limit") + 1]) if "--limit" in args else 200
    names = [a for a in args if re.fullmatch(r"(dark|light)_[1-5]", a)]
    if cmd == "resolve":
        cmd_resolve(names)
    elif cmd == "check":
        [cmd_check(n) for n in names]
    elif cmd == "build":
        [cmd_build(n, lim) for n in names]
    else:
        sys.exit(__doc__)
