"""Free, exact-ISRC Deezer enrichment for label, date, genre and catalog data."""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from musicdb import connect, record_source_run

API = "https://api.deezer.com"
SOURCE = "deezer"


def get(path: str) -> dict:
    # Accept-Language pins Deezer's genre names to English. Without it the API
    # localises them to the account's locale and the library filled with Slovak
    # genres — 57,386 rows of "elektronická", 33,323 of "tanečná" — which are the
    # same genres under names nothing else in the pipeline can match.
    req = Request(API + path, headers={"User-Agent": "local-dj-music-db/1.0",
                                       "Accept-Language": "en-US,en;q=0.9"})
    data = json.loads(urlopen(req, timeout=30).read())
    if data.get("error"):
        if (data["error"] or {}).get("code") == 800:
            raise LookupError("not found")
        raise RuntimeError(json.dumps(data["error"], ensure_ascii=False))
    return data


def attribute_rows(sid: str, prefix: str, data: dict, now: str) -> list[tuple]:
    rows = []
    for key, value in data.items():
        if value is None or key in {"artist", "album", "contributors", "tracks", "genres"}:
            continue
        text = num = raw = None
        if isinstance(value, bool):
            text, num = str(value).lower(), float(value)
        elif isinstance(value, (int, float)):
            num = float(value)
        elif isinstance(value, (dict, list)):
            raw = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            text = str(value)
        rows.append((sid, f"{prefix}.{key}", SOURCE, text, num, raw, 0.90, now))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=150)
    parser.add_argument("--delay", type=float, default=0.30)
    args = parser.parse_args()
    db = connect()
    db.executescript(
        """CREATE TABLE IF NOT EXISTS deezer_status(
             spotify_id TEXT PRIMARY KEY,status TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,
             last_error TEXT,updated_at TEXT NOT NULL,next_retry_at TEXT);
           CREATE TABLE IF NOT EXISTS deezer_albums(
             album_id TEXT PRIMARY KEY,raw_json TEXT NOT NULL,updated_at TEXT NOT NULL);"""
    )
    status_columns = {row[1] for row in db.execute("PRAGMA table_info(deezer_status)")}
    if "next_retry_at" not in status_columns:
        db.execute("ALTER TABLE deezer_status ADD COLUMN next_retry_at TEXT")
        db.commit()
    due = datetime.now(timezone.utc).isoformat()
    rows = db.execute(
        """SELECT t.spotify_id,t.isrc FROM tracks t
           LEFT JOIN deezer_status s USING(spotify_id)
           WHERE t.isrc IS NOT NULL AND t.isrc<>''
             AND COALESCE(s.status,'') NOT IN ('success','not_found')
             AND (s.next_retry_at IS NULL OR s.next_retry_at<=?)
           ORDER BY COALESCE(s.attempts,0),t.spotify_id LIMIT ?""",
        (due, args.limit),
    ).fetchall()
    success = not_found = errors = 0
    for row in rows:
        sid, now = row["spotify_id"], datetime.now(timezone.utc).isoformat()
        try:
            track = get("/track/isrc:" + quote(row["isrc"]))
            album_id = str((track.get("album") or {}).get("id") or "")
            if not track.get("id"):
                raise LookupError("not found")
            cached = db.execute("SELECT raw_json FROM deezer_albums WHERE album_id=?", (album_id,)).fetchone()
            album = json.loads(cached[0]) if cached else (get("/album/" + album_id) if album_id else {})
            genres = (album.get("genres") or {}).get("data") or []
            bpm = track.get("bpm")
            bpm = float(bpm) if bpm not in (None, 0, "0") else None
            attrs = attribute_rows(sid, "track", track, now) + attribute_rows(sid, "album", album, now)
            with db:
                if album_id and not cached:
                    db.execute("INSERT OR REPLACE INTO deezer_albums VALUES(?,?,?)",
                               (album_id, json.dumps(album, ensure_ascii=False), now))
                db.execute(
                    """UPDATE tracks SET album=COALESCE(album,?),label=COALESCE(label,?),
                       release_date=COALESCE(release_date,?),duration_ms=COALESCE(duration_ms,?),
                       explicit=COALESCE(explicit,?),updated_at=? WHERE spotify_id=?""",
                    ((track.get("album") or {}).get("title"), album.get("label"),
                     album.get("release_date"), int(track.get("duration") or 0) * 1000 or None,
                     int(bool(track.get("explicit_lyrics"))), now, sid),
                )
                if bpm:
                    db.execute(
                        """INSERT INTO audio_features(spotify_id,source,source_id,bpm,confidence,raw_json,updated_at)
                           VALUES(?,?,?,?,?,?,?) ON CONFLICT(spotify_id,source) DO UPDATE SET
                           source_id=excluded.source_id,bpm=excluded.bpm,confidence=excluded.confidence,
                           raw_json=excluded.raw_json,updated_at=excluded.updated_at""",
                        (sid, SOURCE, str(track.get("id")), bpm, 0.90,
                         json.dumps(track, ensure_ascii=False), now),
                    )
                for genre in genres:
                    name = (genre.get("name") or "").strip().lower()
                    if name:
                        db.execute("INSERT OR REPLACE INTO tags VALUES(?,?,?,?,?)",
                                   (sid, name, "genre", SOURCE, 0.90))
                if album.get("label"):
                    db.execute("INSERT OR REPLACE INTO tags VALUES(?,?,?,?,?)",
                               (sid, album["label"].strip().lower(), "label", SOURCE, 0.95))
                if attrs:
                    db.executemany(
                        """INSERT OR REPLACE INTO track_attributes
                           (spotify_id,attribute,source,value_text,value_num,value_json,confidence,updated_at)
                           VALUES(?,?,?,?,?,?,?,?)""", attrs,
                    )
                db.execute(
                    """INSERT INTO deezer_status(spotify_id,status,attempts,last_error,updated_at,next_retry_at)
                       VALUES(?,'success',1,NULL,?,NULL)
                       ON CONFLICT(spotify_id) DO UPDATE SET status='success',attempts=attempts+1,
                       last_error=NULL,updated_at=excluded.updated_at,next_retry_at=NULL""", (sid, now),
                )
            success += 1
        except LookupError as exc:
            with db:
                db.execute("""INSERT OR REPLACE INTO deezer_status
                           (spotify_id,status,attempts,last_error,updated_at,next_retry_at)
                           VALUES(?,'not_found',1,?,?,NULL)""",
                           (sid, str(exc), now))
            not_found += 1
        except Exception as exc:
            retry_seconds = int(exc.headers.get("Retry-After") or 60) if isinstance(exc, HTTPError) and exc.code == 429 else 300
            retry_at = (datetime.now(timezone.utc) + timedelta(seconds=retry_seconds)).isoformat()
            with db:
                db.execute(
                    """INSERT INTO deezer_status
                       (spotify_id,status,attempts,last_error,updated_at,next_retry_at)
                       VALUES(?,'failed',1,?,?,?)
                       ON CONFLICT(spotify_id) DO UPDATE SET status='failed',attempts=attempts+1,
                       last_error=excluded.last_error,updated_at=excluded.updated_at,
                       next_retry_at=excluded.next_retry_at""",
                    (sid, str(exc), now, retry_at),
                )
            errors += 1
        time.sleep(args.delay)
    record_source_run(db, SOURCE, datetime.now(timezone.utc).isoformat(), success,
                      f"not_found={not_found},errors={errors}")
    print(f"Deezer: enriched={success}, not_found={not_found}, errors={errors}")


if __name__ == "__main__":
    main()
