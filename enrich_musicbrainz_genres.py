#!/usr/bin/env python3
"""Second-pass MusicBrainz genre/tag fetch for tracks with a known MBID.

WHAT: the identity pass (enrich_musicbrainz.py) resolved 23k+ recording MBIDs
but stored only identity fields. This worker pulls the community genre and
folksonomy tag lists for each known MBID — nearly free coverage (1 req/s,
no key) that the roadmap flagged as an easy fill.
WHY separate: identity matching and tag harvesting progress at different
rates and must not block each other (daemon one-loop-per-provider rule).
HOW TO TWEAK: --limit per batch, --delay (MusicBrainz asks >= 1 req/s).
"""
from __future__ import annotations

import argparse
import os
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

from enrich_lastfm_artists import kind
from enrich_musicbrainz import get
from musicdb import connect, record_source_run

API = "https://musicbrainz.org/ws/2"
SOURCE = "musicbrainz:genre"


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--delay", type=float, default=1.10)
    args = parser.parse_args()
    user_agent = os.getenv("MUSICBRAINZ_USER_AGENT", "local-dj-music-db/1.0 (contact: jakubcerulik)")
    db = connect()
    db.execute(
        """CREATE TABLE IF NOT EXISTS mb_genre_status(
             spotify_id TEXT PRIMARY KEY,status TEXT NOT NULL,
             attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT,updated_at TEXT NOT NULL
           )"""
    )
    rows = db.execute(
        """SELECT t.spotify_id,t.musicbrainz_id,COALESCE(s.attempts,0) AS attempts
           FROM tracks t LEFT JOIN mb_genre_status s USING(spotify_id)
           WHERE t.musicbrainz_id IS NOT NULL AND t.musicbrainz_id != ''
             AND COALESCE(s.status,'') NOT IN ('success','no_tags','permanent_fail')
           ORDER BY COALESCE(s.attempts,0),t.spotify_id LIMIT ?""",
        (args.limit,),
    ).fetchall()
    success = no_tags = errors = 0
    for row in rows:
        now = datetime.now(timezone.utc).isoformat()
        try:
            data = get(f"{API}/recording/{row['musicbrainz_id']}?inc=genres+tags&fmt=json",
                       user_agent)
            values = []
            # Genres are curated; community tags are noisier — both stored,
            # confidence scaled by vote count and capped by list type.
            for bucket, base in (("genres", 0.85), ("tags", 0.60)):
                items = data.get(bucket) or []
                top = max([int(i.get("count") or 0) for i in items] or [1])
                for item in items[:25]:
                    name = (item.get("name") or "").strip().lower()
                    votes = int(item.get("count") or 0)
                    if name:
                        values.append(
                            (row["spotify_id"], name, kind(name), SOURCE,
                             round(base * max(0.3, min(1.0, votes / top)), 3))
                        )
            with db:
                if values:
                    db.executemany("INSERT OR REPLACE INTO tags VALUES(?,?,?,?,?)", values)
                status = "success" if values else "no_tags"
                db.execute(
                    """INSERT INTO mb_genre_status VALUES(?,?,1,NULL,?)
                       ON CONFLICT(spotify_id) DO UPDATE SET status=excluded.status,
                       attempts=attempts+1,last_error=NULL,updated_at=excluded.updated_at""",
                    (row["spotify_id"], status, now),
                )
            success += bool(values)
            no_tags += not bool(values)
        except Exception as exc:
            status = "permanent_fail" if row["attempts"] + 1 >= 5 else "failed"
            with db:
                db.execute(
                    """INSERT INTO mb_genre_status VALUES(?,?,1,?,?)
                       ON CONFLICT(spotify_id) DO UPDATE SET status=excluded.status,
                       attempts=attempts+1,last_error=excluded.last_error,updated_at=excluded.updated_at""",
                    (row["spotify_id"], status, str(exc)[:300], now),
                )
            errors += 1
        time.sleep(args.delay)
    record_source_run(db, SOURCE, datetime.now(timezone.utc).isoformat(), success,
                      f"no_tags={no_tags},errors={errors}")
    print(f"MusicBrainz genres: tagged={success}, no_tags={no_tags}, errors={errors}")


if __name__ == "__main__":
    main()
