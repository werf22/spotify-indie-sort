"""Resumable batched exact-Spotify-ID enrichment from ReccoBeats."""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from musicdb import connect, record_source_run

API = "https://api.reccobeats.com/v1"
SOURCE = "reccobeats"
KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get(url: str, timeout: int = 30) -> tuple[int, dict, int]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "local-dj-music-db/1.0"})
    try:
        with urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read()), int(response.headers.get("Retry-After") or 0)
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read())
        except Exception:
            payload = {"error": str(exc)}
        return exc.code, payload, int(exc.headers.get("Retry-After") or 0)
    except (URLError, TimeoutError, OSError) as exc:
        return 0, {"error": str(exc)}, 60


def ensure_schema(db) -> None:
    db.executescript(
        """CREATE TABLE IF NOT EXISTS reccobeats_status(
             spotify_id TEXT PRIMARY KEY,
             recco_id TEXT,
             status TEXT NOT NULL,
             attempts INTEGER NOT NULL DEFAULT 0,
             next_retry_at TEXT,
             last_error TEXT,
             updated_at TEXT NOT NULL
           );
           CREATE INDEX IF NOT EXISTS idx_reccobeats_status
             ON reccobeats_status(status,next_retry_at,attempts);"""
    )


def retry_at(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()


def set_status(db, sid: str, status: str, recco_id: str | None = None, error: str | None = None, delay: int = 0) -> None:
    with db:
        db.execute(
            """INSERT INTO reccobeats_status(
                 spotify_id,recco_id,status,attempts,next_retry_at,last_error,updated_at)
               VALUES(?,?,?,1,?,?,?) ON CONFLICT(spotify_id) DO UPDATE SET
                 recco_id=COALESCE(excluded.recco_id,reccobeats_status.recco_id),
                 status=excluded.status,attempts=attempts+1,next_retry_at=excluded.next_retry_at,
                 last_error=excluded.last_error,updated_at=excluded.updated_at""",
            (sid, recco_id, status, retry_at(delay) if delay else None, error, now()),
        )


def spotify_id_from_href(href: str | None) -> str | None:
    match = re.search(r"/track/([A-Za-z0-9]{22})", href or "")
    return match.group(1) if match else None


def fetch_batch(batch) -> tuple[object, int, dict, int]:
    """Fetch up to 40 features in one request using exact Spotify IDs."""
    ids = ",".join(row["spotify_id"] for row in batch)
    code, payload, retry = get(API + "/audio-features?" + urlencode({"ids": ids}), timeout=45)
    return batch, code, payload, retry


def save_features(db, item, data: dict) -> None:
    sid = item["spotify_id"]
    key_num = data.get("key")
    mode_num = data.get("mode")
    key = KEYS[int(key_num)] + ("-Major" if mode_num == 1 else "-Minor") if isinstance(key_num, (int, float)) and 0 <= int(key_num) < 12 else None
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True)
    timestamp = now()
    with db:
        db.execute(
            """INSERT INTO audio_features(
                 spotify_id,source,source_id,bpm,key,mode,danceability,energy,valence,
                 acousticness,instrumentalness,speechiness,liveness,loudness,
                 confidence,raw_json,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(spotify_id,source) DO UPDATE SET
                 source_id=excluded.source_id,bpm=excluded.bpm,key=excluded.key,mode=excluded.mode,
                 danceability=excluded.danceability,energy=excluded.energy,valence=excluded.valence,
                 acousticness=excluded.acousticness,instrumentalness=excluded.instrumentalness,
                 speechiness=excluded.speechiness,liveness=excluded.liveness,loudness=excluded.loudness,
                 confidence=excluded.confidence,raw_json=excluded.raw_json,updated_at=excluded.updated_at""",
            (
                sid, SOURCE, item["recco_id"], data.get("tempo"), key,
                "major" if mode_num == 1 else "minor" if mode_num == 0 else None,
                data.get("danceability"), data.get("energy"), data.get("valence"),
                data.get("acousticness"), data.get("instrumentalness"), data.get("speechiness"),
                data.get("liveness"), data.get("loudness"), 0.98, raw, timestamp,
            ),
        )
        db.execute(
            """UPDATE tracks SET isrc=COALESCE(isrc,?),updated_at=? WHERE spotify_id=?""",
            (data.get("isrc"), timestamp, sid),
        )
        derived = []
        def tag(value, kind, confidence=0.92):
            if value: derived.append((sid, value, kind, SOURCE, confidence))
        energy = data.get("energy")
        if isinstance(energy, (int, float)): tag("low" if energy < .35 else "medium" if energy < .70 else "high", "energy_band")
        dance = data.get("danceability")
        if isinstance(dance, (int, float)): tag("low" if dance < .40 else "medium" if dance < .70 else "high", "danceability_band")
        valence = data.get("valence")
        if isinstance(valence, (int, float)): tag("dark" if valence < .33 else "neutral" if valence < .67 else "positive", "valence_band")
        instrumental = data.get("instrumentalness")
        if isinstance(instrumental, (int, float)):
            if instrumental >= .50: tag("instrumental", "voice", 0.95)
            elif instrumental <= .10: tag("likely vocals", "voice", 0.85)
        acoustic = data.get("acousticness")
        if isinstance(acoustic, (int, float)) and acoustic >= .70: tag("acoustic", "production", 0.90)
        live = data.get("liveness")
        if isinstance(live, (int, float)) and live >= .80: tag("live", "recording_type", 0.90)
        if derived:
            db.executemany("INSERT OR REPLACE INTO tags VALUES(?,?,?,?,?)", derived)
        for field, value in data.items():
            if value is None: continue
            text = str(value) if isinstance(value, str) else None
            num = float(value) if isinstance(value, (int, float)) else None
            db.execute(
                """INSERT OR REPLACE INTO track_attributes
                   (spotify_id,attribute,source,value_text,value_num,confidence,updated_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (sid, field, SOURCE, text, num, 0.98, timestamp),
            )
    set_status(db, sid, "success", item["recco_id"])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=10000)
    parser.add_argument("--concurrency", type=int, default=3, choices=range(1, 7))
    parser.add_argument("--per-minute", type=int, default=60, choices=range(1, 301))
    args = parser.parse_args()
    db = connect(); ensure_schema(db)
    due = now()
    rows = db.execute(
        """SELECT t.spotify_id FROM tracks t LEFT JOIN reccobeats_status s USING(spotify_id)
           WHERE (s.spotify_id IS NULL OR s.status IN ('failed','mapped','not_found'))
             AND (s.next_retry_at IS NULL OR s.next_retry_at<=?)
           ORDER BY COALESCE(s.attempts,0),t.spotify_id LIMIT ?""",
        (due, args.limit),
    ).fetchall()
    batches = [rows[start:start + 40] for start in range(0, len(rows), 40)]
    success = missing = errors = 0
    pause = 60.0 * args.concurrency / args.per_minute
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for start in range(0, len(batches), args.concurrency):
            wave_start = time.monotonic()
            for batch, code, payload, retry in pool.map(fetch_batch, batches[start:start + args.concurrency]):
                if code == 200:
                    by_sid = {
                        spotify_id_from_href(item.get("href")): item
                        for item in (payload.get("content") or [])
                    }
                    for row in batch:
                        sid = row["spotify_id"]
                        data = by_sid.get(sid)
                        if data:
                            save_features(db, {"spotify_id": sid, "recco_id": data["id"]}, data)
                            success += 1
                        else:
                            set_status(db, sid, "not_found", error="audio features not found", delay=30 * 86400)
                            missing += 1
                else:
                    delay = retry or (60 if code == 429 else 300)
                    for row in batch:
                        set_status(db, row["spotify_id"], "failed", error=f"batch HTTP {code}: {str(payload)[:300]}", delay=delay)
                        errors += 1
            remaining = pause - (time.monotonic() - wave_start)
            if remaining > 0: time.sleep(remaining)
    finished = now()
    record_source_run(db, SOURCE, finished, success, f"batch40,selected={len(rows)},missing={missing},errors={errors}")
    print(f"ReccoBeats batch: enriched={success}, selected={len(rows)}, missing={missing}, errors={errors}")


if __name__ == "__main__":
    main()
