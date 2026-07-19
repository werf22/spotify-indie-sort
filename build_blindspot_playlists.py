#!/usr/bin/env python3
"""Create resumable Spotify playlists for true local-library blindspots."""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from index_audio_files import norm
from musicdb import connect
from spotify_client import SpotifyClient


ROOT = Path(__file__).resolve().parent
PURPOSE = "local-blindspots-2026-07-18"
DEFAULT_CHUNK = 8000
MISSING_DATA = Path("/Users/jakub/Appky Claude/dj-set-spotify/data")


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def missing_spotify_ids() -> set[str]:
    ids: set[str] = set()
    cached = MISSING_DATA / "missing_tracks_deduped_correct_spotify_cached/cached_matched_tracks.json"
    if cached.is_file():
        for item in json.loads(cached.read_text(encoding="utf-8")):
            sid = ((item.get("spotify") or {}).get("id") or "").strip()
            if len(sid) == 22:
                ids.add(sid)
    for path in (
        MISSING_DATA / "traktor_missing_spotify/spotify_playlist_state.json",
        MISSING_DATA / "traktor_missing_spotify/summary_after_rate_limit.json",
    ):
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        values = payload.get("added_uris") or (payload.get("playlist_state") or {}).get("added_uris") or []
        for uri in values:
            sid = str(uri).rsplit(":", 1)[-1]
            if len(sid) == 22:
                ids.add(sid)
    return ids


VERSION_WORDS = {
    "remaster", "remastered", "radio", "edit", "extended", "original",
    "version", "mix", "mixed", "mono", "stereo", "deluxe",
}


def canonical_title(value: str) -> str:
    words = norm(value).split()
    while words and (words[-1] in VERSION_WORDS or re.fullmatch(r"20\d\d|19\d\d", words[-1])):
        words.pop()
    return " ".join(words)


def artist_overlap(a: str, b: str) -> float:
    left, right = norm(a), norm(b)
    if not left or not right:
        return 0.0
    lset, rset = set(left.split()), set(right.split())
    token = len(lset & rset) / max(1, min(len(lset), len(rset)))
    return max(token, SequenceMatcher(None, left, right).ratio())


def select_candidates(db) -> tuple[list[dict], dict]:
    excluded_missing = missing_spotify_ids()
    traktor_by_title: dict[str, list[str]] = defaultdict(list)
    for row in db.execute("SELECT title,artist_names FROM traktor_entries"):
        key = canonical_title(row["title"] or "")
        if key:
            traktor_by_title[key].append(row["artist_names"] or "")

    rows = list(
        db.execute(
            """SELECT t.spotify_id,t.uri,t.title,t.artist_names,t.isrc,t.popularity,t.library_sources
               FROM tracks t JOIN acquisition_queue q USING(spotify_id)
               WHERE q.reason='spotify_only' AND q.acquisition_state='needs_source'
               ORDER BY CASE WHEN lower(t.library_sources) LIKE '%liked songs%' THEN 0 ELSE 1 END,
                        COALESCE(t.popularity,0) DESC,t.spotify_id"""
        )
    )
    selected: list[dict] = []
    seen_isrc: set[str] = set()
    seen_recording: set[tuple[str, str]] = set()
    stats = defaultdict(int)
    for row in rows:
        item = dict(row)
        sid = item["spotify_id"]
        if sid in excluded_missing:
            stats["excluded_missing_playlist_map"] += 1
            continue
        key = canonical_title(item["title"])
        possible = traktor_by_title.get(key, ())
        if possible and max(artist_overlap(item["artist_names"], artist) for artist in possible) >= 0.48:
            stats["excluded_possible_traktor_overlap"] += 1
            continue
        isrc = (item.get("isrc") or "").upper()
        recording = (key, norm(item["artist_names"]))
        if isrc and isrc in seen_isrc:
            stats["deduped_isrc"] += 1
            continue
        if recording in seen_recording:
            stats["deduped_recording"] += 1
            continue
        if isrc:
            seen_isrc.add(isrc)
        seen_recording.add(recording)
        selected.append(item)
    stats["selected"] = len(selected)
    stats["candidate_rows"] = len(rows)
    stats["known_missing_spotify_ids"] = len(excluded_missing)
    return selected, dict(stats)


def preview(items: list[dict], stats: dict, count: int = 40) -> None:
    print(json.dumps(stats, ensure_ascii=False, indent=2, sort_keys=True))
    print("Preview:")
    for index, item in enumerate(items[:count], 1):
        print(f"{index:3}. {item['title']} — {item['artist_names']} [{item['spotify_id']}]")


def existing_playlist_items(client: SpotifyClient, playlist_id: str) -> set[str]:
    return {
        item.get("track", {}).get("id")
        for item in client.playlist_tracks(playlist_id)
        if item.get("track", {}).get("id")
    }


def create_playlists(db, items: list[dict], part_size: int) -> list[dict]:
    client = SpotifyClient()
    me = client.current_user()
    part_count = math.ceil(len(items) / part_size)
    results = []
    for part_index in range(part_count):
        part = part_index + 1
        tracks = items[part_index * part_size : (part_index + 1) * part_size]
        name = f"Local Library Blindspots {part:02d}/{part_count:02d}"
        stored = db.execute(
            "SELECT * FROM spotify_export_playlists WHERE purpose=? AND part=?",
            (PURPOSE, part),
        ).fetchone()
        if stored:
            playlist_id = stored["playlist_id"]
            playlist_url = stored["playlist_url"]
            already = existing_playlist_items(client, playlist_id)
        else:
            playlist = client.create_playlist(
                me["id"], name,
                "Spotify-library tracks absent from the complete Traktor collection, "
                "absent from Missing Tracks playlists, and not matched to a local audio file. "
                f"Resumable canonical export {PURPOSE}.",
                public=False,
            )
            playlist_id = playlist["id"]
            playlist_url = playlist["external_urls"]["spotify"]
            already = set()
            with db:
                db.execute(
                    """INSERT INTO spotify_export_playlists
                       (purpose,part,playlist_id,playlist_url,name,expected_items,added_items,updated_at)
                       VALUES(?,?,?,?,?,?,0,?)""",
                    (PURPOSE, part, playlist_id, playlist_url, name, len(tracks), utcnow()),
                )

        pending = [track for track in tracks if track["spotify_id"] not in already]
        for start in range(0, len(pending), 100):
            batch = pending[start : start + 100]
            client.add_tracks(playlist_id, [track["uri"] for track in batch])
            now = utcnow()
            with db:
                db.executemany(
                    """INSERT OR REPLACE INTO spotify_export_items
                       (purpose,spotify_id,playlist_id,added_at) VALUES(?,?,?,?)""",
                    [(PURPOSE, track["spotify_id"], playlist_id, now) for track in batch],
                )
                db.execute(
                    """UPDATE spotify_export_playlists SET
                       added_items=(SELECT count(*) FROM spotify_export_items WHERE purpose=? AND playlist_id=?),
                       updated_at=? WHERE purpose=? AND part=?""",
                    (PURPOSE, playlist_id, now, PURPOSE, part),
                )
            print(f"part {part:02d}/{part_count:02d}: {min(start+len(batch),len(pending))}/{len(pending)} new", flush=True)

        payload = client.request("GET", f"/playlists/{playlist_id}").json()
        actual = payload.get("tracks", {}).get("total", 0)
        if actual != len(tracks):
            raise RuntimeError(f"Part {part}: expected {len(tracks)} Spotify items, got {actual}")
        results.append({"part": part, "tracks": actual, "url": playlist_url})
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--create", action="store_true")
    parser.add_argument("--part-size", type=int, default=DEFAULT_CHUNK)
    parser.add_argument("--preview", type=int, default=40)
    args = parser.parse_args()
    if not 100 <= args.part_size <= 9000:
        raise SystemExit("--part-size must be between 100 and 9000")
    db = connect()
    items, stats = select_candidates(db)
    preview(items, stats, args.preview)
    if not args.create:
        print("DRY RUN: Spotify was not changed.")
        return
    results = create_playlists(db, items, args.part_size)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
