"""Persist FreqBlog's descriptive /tag projection with provenance.

Only tracks already resolved by /lookup are selected, so this worker does not
guess identities. Progress and retries live in SQLite and survive restarts.
"""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from musicdb import connect, record_source_run

BASE_URL = "https://api.freqblog.com"
SOURCE_PREFIX = "freqblog:tag"
CONFIDENCE = {
    "measured": 0.84,
    "derived": 0.66,
    "model-estimated": 0.58,
    "catalog-genre": 0.55,
}
CATEGORY_TYPES = {
    "mood": "mood",
    "genre": "genre",
    "energy": "energy_level",
    "danceability": "danceability_level",
    "valence": "valence_level",
    "acousticness": "acoustic_character",
    "instrumentalness": "vocal_character",
}


def iso(dt: datetime | None = None) -> str:
    return (dt or datetime.now(timezone.utc)).isoformat()


def ensure_schema(db) -> None:
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS freqblog_tag_status(
          spotify_id TEXT PRIMARY KEY,
          status TEXT NOT NULL,
          attempts INTEGER NOT NULL DEFAULT 0,
          next_retry_at TEXT,
          last_error TEXT,
          raw_json TEXT,
          updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_freqblog_tag_retry
          ON freqblog_tag_status(status,next_retry_at,attempts);
        """
    )


def candidates(db, limit: int):
    now = iso()
    return db.execute(
        """SELECT t.spotify_id,t.title,t.artist_names,a.source_id
           FROM tracks t
           JOIN freqblog_status f USING(spotify_id)
           LEFT JOIN audio_features a
             ON a.spotify_id=t.spotify_id AND a.source='freqblog'
           LEFT JOIN freqblog_tag_status s USING(spotify_id)
           WHERE f.status='success'
             AND (s.spotify_id IS NULL OR
                  (s.status IN ('failed','quota_wait') AND s.attempts<6
                   AND COALESCE(s.next_retry_at,'')<=?))
           ORDER BY COALESCE(s.attempts,0),t.spotify_id LIMIT ?""",
        (now, limit),
    ).fetchall()


def fetch(api_key: str, row) -> dict:
    params = {"track_id": row["source_id"]} if row["source_id"] else {
        "track": row["title"], "artist": (row["artist_names"] or "").split(",")[0].strip()
    }
    request = urllib.request.Request(
        BASE_URL + "/tag?" + urllib.parse.urlencode(params),
        headers={
            "X-Api-Key": api_key,
            "Accept": "application/json",
            "User-Agent": "local-dj-music-db/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return {"code": response.status, "data": json.load(response), "retry": 0}
    except urllib.error.HTTPError as exc:
        try:
            message = exc.read().decode("utf-8", "replace")[:1000]
        except Exception:
            message = str(exc)
        retry = int(exc.headers.get("Retry-After", "60") or 60)
        return {"code": exc.code, "error": message, "retry": retry}
    except Exception as exc:
        return {"code": 0, "error": str(exc), "retry": 300}


def save_success(db, sid: str, data: dict) -> int:
    now = iso()
    rows = []
    for item in data.get("tags") or []:
        tag = str(item.get("tag") or "").strip().lower()
        category = str(item.get("category") or "").strip().lower()
        provenance = str(item.get("provenance") or "unknown").strip().lower()
        confidence_label = str(item.get("confidence") or "").strip().lower()
        if not tag or category not in CATEGORY_TYPES:
            continue
        confidence = CONFIDENCE.get(confidence_label, 0.45)
        value = item.get("value")
        if isinstance(value, (int, float)) and confidence_label == "model-estimated":
            confidence *= max(0.25, min(1.0, float(value)))
        rows.append((sid, tag, CATEGORY_TYPES[category], f"{SOURCE_PREFIX}:{provenance}", confidence))
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True)
    with db:
        db.execute("DELETE FROM tags WHERE spotify_id=? AND source LIKE 'freqblog:tag:%'", (sid,))
        if rows:
            db.executemany("INSERT OR REPLACE INTO tags VALUES(?,?,?,?,?)", rows)
        db.execute(
            """INSERT INTO freqblog_tag_status
                 (spotify_id,status,attempts,next_retry_at,last_error,raw_json,updated_at)
               VALUES(?,'success',1,NULL,NULL,?,?)
               ON CONFLICT(spotify_id) DO UPDATE SET status='success',
                 attempts=attempts+1,next_retry_at=NULL,last_error=NULL,
                 raw_json=excluded.raw_json,updated_at=excluded.updated_at""",
            (sid, raw, now),
        )
    return len(rows)


def save_error(db, sid: str, status: str, message: str, delay: int) -> None:
    now = datetime.now(timezone.utc)
    with db:
        db.execute(
            """INSERT INTO freqblog_tag_status
                 (spotify_id,status,attempts,next_retry_at,last_error,updated_at)
               VALUES(?,?,1,?,?,?)
               ON CONFLICT(spotify_id) DO UPDATE SET status=excluded.status,
                 attempts=attempts+1,next_retry_at=excluded.next_retry_at,
                 last_error=excluded.last_error,updated_at=excluded.updated_at""",
            (sid, status, iso(now + timedelta(seconds=delay)), message[:1000], iso(now)),
        )


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--delay", type=float, default=0.12)
    args = parser.parse_args()
    key = (os.getenv("FREQBLOG_API_KEY") or "").strip()
    if not key:
        raise SystemExit("FREQBLOG_API_KEY is not configured")
    db = connect()
    ensure_schema(db)
    rows = candidates(db, args.limit)
    ok = tags = missing = errors = 0
    for row in rows:
        result = fetch(key, row)
        code = result["code"]
        if code == 200:
            tags += save_success(db, row["spotify_id"], result["data"])
            ok += 1
        elif code == 404:
            save_error(db, row["spotify_id"], "not_found", result.get("error", "not found"), 30 * 86400)
            missing += 1
        else:
            status = "quota_wait" if code == 429 else "failed"
            save_error(db, row["spotify_id"], status, result.get("error", "request failed"), result.get("retry", 300))
            errors += 1
            if code in {401, 403}:
                raise SystemExit(f"FreqBlog authentication failed: HTTP {code}")
        time.sleep(args.delay)
    now = iso()
    record_source_run(db, SOURCE_PREFIX, now, ok, f"tags={tags},not_found={missing},errors={errors}")
    print(f"FreqBlog tags: tracks={ok}, tags={tags}, not_found={missing}, errors={errors}")


if __name__ == "__main__":
    main()
