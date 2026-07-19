"""Normalize legacy Spotify artist genres from tracks.genres into tags."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from musicdb import connect, record_source_run

SOURCE = "spotify:artist-genre"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5000)
    args = parser.parse_args()
    db = connect()
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        """CREATE TABLE IF NOT EXISTS spotify_genre_sync_status(
             spotify_id TEXT PRIMARY KEY, updated_at TEXT NOT NULL
           )"""
    )
    rows = db.execute(
        """SELECT spotify_id,genres FROM tracks
           WHERE genres<>'' AND genres IS NOT NULL
             AND spotify_id NOT IN (SELECT spotify_id FROM spotify_genre_sync_status)
           LIMIT ?""",
        (args.limit,),
    ).fetchall()
    inserted = 0
    with db:
        for row in rows:
            genres = sorted({g.strip().lower() for g in row["genres"].split(",") if g.strip()})
            for genre in genres:
                db.execute(
                    "INSERT OR REPLACE INTO tags VALUES(?,?,?,?,?)",
                    (row["spotify_id"], genre, "genre", SOURCE, 0.85),
                )
                inserted += 1
            db.execute(
                "INSERT OR REPLACE INTO spotify_genre_sync_status VALUES(?,?)",
                (row["spotify_id"], now),
            )
    record_source_run(db, SOURCE, now, len(rows), f"tags={inserted}")
    print(f"Spotify genres: tracks={len(rows)}, tags={inserted}")


if __name__ == "__main__":
    main()
