#!/usr/bin/env python3
"""Turn the classified pool + resolved fill tracks into the 10 final playlists (200 each).

INPUT:  data/halloween_ed/pool.json (account tracks), assign_all.json (bucket per pool row),
        resolved.json + halloween_ed/candidates/light_{1,2,4,5}.txt (fill tracks found on Spotify).
OUTPUT: data/halloween_ed/plan.json (the exact 10 x 200 ids) and, with `apply`, the playlists
        "ED Halloween - Dark 1" ... "Light 5" on the owner's Spotify account.

PRIORITY inside every bucket: the owner's seed playlists first, then liked / playlist evidence
(pool weight), then fill tracks chosen by Claude. No track appears in two playlists. A track
Spotify reports as unplayable in the owner's market (SK) is never used.

HOW TO TWEAK: ARTIST_CAP stops one artist flooding a playlist (seeds are exempt); TARGET is the
playlist size.   Usage:  ./.venv/bin/python halloween_final.py plan | apply | verify
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter

import requests

from halloween_build import MARKET, norm, read_candidates
from halloween_pools import WORK

TARGET = 200
ARTIST_CAP = 9
BUCKETS = [f"{m}{n}" for m in "DL" for n in range(1, 6)]
FILL_FILES = {"L1": "light_1", "L2": "light_2", "L4": "light_4", "L5": "light_5", "D5": "dark_5"}
PLAN = WORK / "plan.json"
PLAYABLE = WORK / "playable.json"


def recording_key(artist: str, title: str) -> str:
    return norm(artist.split(",")[0]) + "|" + norm(title)


def load_candidates() -> dict[str, list[dict]]:
    """bucket -> ordered candidates [{id, artist, title, src}], best first."""
    rows = json.loads((WORK / "pool.json").read_text())
    assign = json.loads((WORK / "assign_all.json").read_text())
    by_bucket: dict[str, list[dict]] = {b: [] for b in BUCKETS}
    for idx, code in assign.items():
        r = rows[int(idx)]
        by_bucket[code].append({"id": r["id"], "artist": r["artist"], "title": r["title"], "isrc": r.get("isrc"),
                                "seed": "seed" in r["why"], "w": r["w"], "src": "account"})
    for lst in by_bucket.values():
        lst.sort(key=lambda c: (not c["seed"], -c["w"], c["artist"].lower(), c["title"].lower()))
    cache = json.loads((WORK / "resolved.json").read_text())
    for bucket, name in FILL_FILES.items():
        for a, t in read_candidates(name):
            hit = cache.get(f"{a} | {t}")
            if hit:
                by_bucket[bucket].append({"id": hit["id"], "artist": ", ".join(hit["artists"]), "title": hit["name"],
                                          "isrc": hit.get("isrc"), "seed": False, "w": 0, "src": "fill"})
    return by_bucket


def check_playable(client, ids: list[str]) -> dict[str, bool]:
    """Spotify availability in MARKET for every id (cached; 25 ids per request - 50 timed out)."""
    known = json.loads(PLAYABLE.read_text()) if PLAYABLE.exists() else {}
    todo = [i for i in dict.fromkeys(ids) if i not in known]
    for s in range(0, len(todo), 25):
        batch = todo[s:s + 25]
        for attempt in range(8):                   # Spotify answers 503 now and then; the cache keeps progress
            try:
                items = client.request("GET", "/tracks", params={"ids": ",".join(batch), "market": MARKET}).json()["tracks"]
                break
            except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as exc:
                code = getattr(getattr(exc, "response", None), "status_code", None)
                if code is not None and code < 500:
                    raise
                time.sleep(4 * (attempt + 1))
        else:
            raise RuntimeError("Spotify /tracks kept returning 5xx - rerun to resume from the cache")
        for sid, item in zip(batch, items):
            known[sid] = bool(item) and item.get("is_playable", True) is not False
        PLAYABLE.write_text(json.dumps(known))
    return known


def make_plan() -> dict[str, list[dict]]:
    from spotify_client import SpotifyClient
    cands = load_candidates()
    ok = check_playable(SpotifyClient(), [c["id"] for lst in cands.values() for c in lst])
    used_id, used_rec, plan = set(), set(), {}
    for b in BUCKETS:
        chosen, per = [], Counter()
        for c in cands[b]:
            rec = recording_key(c["artist"], c["title"])
            if not ok.get(c["id"]) or c["id"] in used_id or rec in used_rec or (c["isrc"] and c["isrc"] in used_id):
                continue
            first_artist = c["artist"].split(",")[0].strip().lower()
            if not c["seed"] and per[first_artist] >= ARTIST_CAP:
                continue
            chosen.append(c)
            per[first_artist] += 1
            used_id.add(c["id"]); used_rec.add(rec)
            if c["isrc"]:
                used_id.add(c["isrc"])
            if len(chosen) == TARGET:
                break
        plan[b] = chosen
    PLAN.write_text(json.dumps(plan, ensure_ascii=False))
    return plan


def report(plan: dict) -> None:
    for b in BUCKETS:
        c = Counter(x["src"] if not x["seed"] else "seed" for x in plan[b])
        flag = "" if len(plan[b]) == TARGET else f"   <-- SHORT by {TARGET - len(plan[b])}"
        print(f"{b}: {len(plan[b]):3d}  seed {c['seed']:3d}  account {c['account']:3d}  fill {c['fill']:3d}{flag}")
    print("total tracks:", sum(len(v) for v in plan.values()))


def retry(fn, *args, **kwargs):
    """Call a Spotify helper, retrying 5xx / timeouts (Spotify returned 503 on /me during this job)."""
    for attempt in range(8):
        try:
            return fn(*args, **kwargs)
        except (requests.HTTPError, requests.ConnectionError, requests.Timeout) as exc:
            code = getattr(getattr(exc, "response", None), "status_code", None)
            if code is not None and code < 500:
                raise
            time.sleep(4 * (attempt + 1))
    raise RuntimeError(f"Spotify kept failing for {getattr(fn, '__name__', fn)}")


def write_playlist(client, pid: str, uris: list[str]) -> None:
    """Replace the playlist content: PUT the first 100 (replaces), then append the rest."""
    retry(client.request, "PUT", f"/playlists/{pid}/tracks", json={"uris": uris[:100]})
    for i in range(100, len(uris), 100):
        retry(client.request, "POST", f"/playlists/{pid}/tracks", json={"uris": uris[i:i + 100]})


def apply_plan(plan: dict) -> None:
    from spotify_client import SpotifyClient
    client = SpotifyClient()
    state = json.loads((WORK / "playlists.json").read_text()) if (WORK / "playlists.json").exists() else {}
    uid = retry(client.current_user)["id"]
    for b in BUCKETS:
        key = ("dark_" if b[0] == "D" else "light_") + b[1]
        mood = "Dark" if b[0] == "D" else "Light"
        uris = [f"spotify:track:{c['id']}" for c in plan[b]]
        if key not in state:
            pl = retry(client.create_playlist, uid, f"ED Halloween - {mood} {b[1]}",
                       f"Ecstatic Dance Halloween pool - {mood.lower()}, energy {b[1]}/5", public=False)
            state[key] = pl["id"]
            (WORK / "playlists.json").write_text(json.dumps(state, indent=1))
        for attempt in range(3):               # a failed append restarts the whole playlist, so no duplicates
            try:
                write_playlist(client, state[key], uris)
                break
            except RuntimeError:
                if attempt == 2:
                    raise
        print(f"{b}: playlist {state[key]} written with {len(uris)} tracks")


def verify() -> None:
    from spotify_client import SpotifyClient
    client = SpotifyClient()
    state = json.loads((WORK / "playlists.json").read_text())
    seen: Counter = Counter()
    for b in BUCKETS:
        key = ("dark_" if b[0] == "D" else "light_") + b[1]
        items = retry(lambda: list(client.playlist_tracks(state[key])))      # whole read retried on a 5xx
        ids = [i["track"]["id"] for i in items if i.get("track") and i["track"].get("id")]
        seen.update(ids)
        print(f"{b}: {len(ids)} tracks, {len(set(ids))} unique   https://open.spotify.com/playlist/{state[key]}")
    dup = [i for i, n in seen.items() if n > 1]
    print("total:", sum(seen.values()), "| unique across all 10:", len(seen), "| ids in more than one playlist:", len(dup))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "plan":
        report(make_plan())
    elif cmd == "apply":
        apply_plan(json.loads(PLAN.read_text()))
    elif cmd == "verify":
        verify()
    else:
        sys.exit(__doc__)
