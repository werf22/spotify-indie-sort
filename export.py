"""
Bulk-exports the user's Spotify library: playlists they own + Liked Songs.
Input: spotify_client.SpotifyClient (needs data/token.json seeded).
Output: data/library_export.json — deduped list of tracks with artist genres
attached, plus which playlist(s)/Liked Songs each track came from.
"""

from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

from spotify_client import SpotifyClient

DATA_DIR = Path(__file__).resolve().parent / "data"
OUT_PATH = DATA_DIR / "library_export.json"
EXCLUDED_PATH = DATA_DIR / "excluded_playlists.json"

# Playlists that are technical artifacts, not music you'd want sorted — e.g.
# leftovers from the 2026-07-09 Traktor-to-Spotify track-matching job
# (missing_tracks_traktor_2026-07-09.csv). Add more patterns here if future
# runs turn up other non-taste playlists; keep patterns narrow and specific
# (a broad "temp" match once caught "Downtempo" and "Temple Step Project" —
# checked with a dry scan before relying on this).
EXCLUDED_NAME_PATTERNS = [r"missing track"]


def log(msg: str) -> None:
    print(f"[export] {msg}", flush=True)


def track_from_item(item: dict, source: str) -> dict | None:
    track = item.get("track")
    if not track or not track.get("id"):
        return None  # local files / removed tracks have no id
    return {
        "id": track["id"],
        "uri": track["uri"],
        "name": track["name"],
        "album": (track.get("album") or {}).get("name", ""),
        "artists": [
            {"id": a["id"], "name": a["name"]} for a in track.get("artists", [])
        ],
        "sources": [source],
    }


def main() -> None:
    client = SpotifyClient()
    me = client.current_user()
    log(f"authenticated as {me['id']} ({me.get('display_name')})")

    log("scanning all playlists for ones you own (this pages through everything)...")
    owned = []
    seen_playlists = 0
    t0 = time.time()
    for pl in client.my_owned_playlists(me["id"]):
        owned.append(pl)
        seen_playlists += 1
        if seen_playlists % 100 == 0:
            log(f"  ...scanned {seen_playlists} playlists, {len(owned)} owned so far")
    log(f"done scanning: {seen_playlists} total playlists, {len(owned)} owned by you ({time.time()-t0:.0f}s)")

    pattern = re.compile("|".join(EXCLUDED_NAME_PATTERNS), re.I)
    excluded = [pl for pl in owned if pattern.search(pl["name"])]
    owned = [pl for pl in owned if not pattern.search(pl["name"])]
    if excluded:
        excluded_tracks = sum(pl.get("tracks", {}).get("total", 0) for pl in excluded)
        log(f"excluding {len(excluded)} non-music utility playlists ({excluded_tracks} track-slots):")
        for pl in excluded:
            log(f"  SKIP '{pl['name']}' ({pl.get('tracks', {}).get('total', 0)} tracks)")
        DATA_DIR.mkdir(exist_ok=True)
        EXCLUDED_PATH.write_text(
            json.dumps(
                [{"name": pl["name"], "tracks": pl.get("tracks", {}).get("total", 0)} for pl in excluded],
                indent=2,
                ensure_ascii=False,
            )
        )

    tracks: dict[str, dict] = {}

    for idx, pl in enumerate(owned, 1):
        name = pl["name"]
        count = pl.get("tracks", {}).get("total", 0)
        log(f"[{idx}/{len(owned)}] '{name}' ({count} tracks)")
        for item in client.playlist_tracks(pl["id"]):
            t = track_from_item(item, name)
            if not t:
                continue
            if t["id"] in tracks:
                tracks[t["id"]]["sources"].append(name)
            else:
                tracks[t["id"]] = t

    log("fetching Liked Songs...")
    liked_count = 0
    for item in client.liked_songs():
        t = track_from_item(item, "Liked Songs")
        if not t:
            continue
        liked_count += 1
        if t["id"] in tracks:
            tracks[t["id"]]["sources"].append("Liked Songs")
        else:
            tracks[t["id"]] = t
        if liked_count % 500 == 0:
            log(f"  ...{liked_count} liked songs so far")
    log(f"liked songs: {liked_count}")

    log(f"unique tracks after dedup: {len(tracks)}")

    artist_ids = sorted({a["id"] for t in tracks.values() for a in t["artists"]})
    log(f"fetching genres for {len(artist_ids)} unique artists...")
    genres = client.several_artists_genres(artist_ids)
    for t in tracks.values():
        t["genres"] = sorted({g for a in t["artists"] for g in genres.get(a["id"], [])})

    DATA_DIR.mkdir(exist_ok=True)
    OUT_PATH.write_text(json.dumps(list(tracks.values()), indent=2, ensure_ascii=False))
    log(f"wrote {OUT_PATH} ({len(tracks)} tracks, {len(owned)} owned playlists scanned)")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 - top-level script, must not die silently
        log(f"FAILED: {e!r}")
        sys.exit(1)
