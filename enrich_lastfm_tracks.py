"""Resumable free Last.fm per-track tags (genre, mood, voice, instruments)."""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from enrich_lastfm_artists import kind
from musicdb import connect, record_source_run

API = "https://ws.audioscrobbler.com/2.0/"
SOURCE = "last.fm:track"


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=150)
    parser.add_argument("--delay", type=float, default=0.45)
    args = parser.parse_args()
    key = (os.getenv("LASTFM_API_KEY") or "").strip()
    if not key:
        raise SystemExit("LASTFM_API_KEY is missing")
    db = connect()
    db.execute(
        """CREATE TABLE IF NOT EXISTS lastfm_track_status(
             spotify_id TEXT PRIMARY KEY,status TEXT NOT NULL,
             attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT,updated_at TEXT NOT NULL
           )"""
    )
    rows = db.execute(
        """SELECT t.spotify_id,t.title,t.artist_names,COALESCE(s.attempts,0) AS attempts
           FROM tracks t LEFT JOIN lastfm_track_status s USING(spotify_id)
           WHERE COALESCE(s.status,'') NOT IN ('success','no_tags','permanent_fail')
           ORDER BY COALESCE(s.attempts,0),t.spotify_id LIMIT ?""",
        (args.limit,),
    ).fetchall()
    success = no_tags = errors = 0
    for row in rows:
        now = datetime.now(timezone.utc).isoformat()
        artist = (row["artist_names"] or "").split(",", 1)[0].strip()
        # A request without both artist and title can only produce HTTP 400;
        # classify immediately instead of retrying forever.
        if not artist or not (row["title"] or "").strip():
            with db:
                db.execute(
                    """INSERT INTO lastfm_track_status VALUES(?,'permanent_fail',1,'missing artist/title',?)
                       ON CONFLICT(spotify_id) DO UPDATE SET status='permanent_fail',
                       attempts=attempts+1,last_error='missing artist/title',updated_at=excluded.updated_at""",
                    (row["spotify_id"], now),
                )
            errors += 1
            continue
        try:
            query = urlencode(
                {"method": "track.getTopTags", "api_key": key, "artist": artist,
                 "track": row["title"], "autocorrect": 1, "format": "json"}
            )
            req = Request(API + "?" + query, headers={"User-Agent": "local-dj-music-db/1.0"})
            data = json.loads(urlopen(req, timeout=30).read())
            tags = (data.get("toptags") or {}).get("tag") or []
            maximum = max([int(t.get("count") or 0) for t in tags] or [1])
            values = []
            for tag in tags[:30]:
                name = (tag.get("name") or "").strip().lower()
                count = int(tag.get("count") or 0)
                if name:
                    values.append(
                        (row["spotify_id"], name, kind(name), SOURCE,
                         max(0.15, min(1.0, count / maximum)))
                    )
            with db:
                if values:
                    db.executemany("INSERT OR REPLACE INTO tags VALUES(?,?,?,?,?)", values)
                status = "success" if values else "no_tags"
                db.execute(
                    """INSERT INTO lastfm_track_status VALUES(?,?,1,NULL,?)
                       ON CONFLICT(spotify_id) DO UPDATE SET status=excluded.status,
                       attempts=attempts+1,last_error=NULL,updated_at=excluded.updated_at""",
                    (row["spotify_id"], status, now),
                )
            success += bool(values)
            no_tags += not bool(values)
        except Exception as exc:
            # After 5 total attempts the failure is treated as permanent so the
            # queue can drain; 34 tracks previously looped 170+ retries each.
            status = "permanent_fail" if row["attempts"] + 1 >= 5 else "failed"
            with db:
                db.execute(
                    """INSERT INTO lastfm_track_status VALUES(?,?,1,?,?)
                       ON CONFLICT(spotify_id) DO UPDATE SET status=excluded.status,
                       attempts=attempts+1,last_error=excluded.last_error,updated_at=excluded.updated_at""",
                    (row["spotify_id"], status, str(exc), now),
                )
            errors += 1
        time.sleep(args.delay)
    record_source_run(db, SOURCE, datetime.now(timezone.utc).isoformat(), success,
                      f"no_tags={no_tags},errors={errors}")
    print(f"Last.fm tracks: tagged={success}, no_tags={no_tags}, errors={errors}")


if __name__ == "__main__":
    main()
