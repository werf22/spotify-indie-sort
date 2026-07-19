"""Parallel, resumable SoundNet/RapidAPI audio-feature enrichment."""
from __future__ import annotations

import argparse
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from musicdb import connect, record_source_run

SOURCE = "soundnet"
HOST = "track-analysis.p.rapidapi.com"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalized(value):
    if value is None or value == "":
        return None
    number = float(value)
    return number / 100.0 if number > 1.0 else number


def loudness(value):
    if value is None:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", str(value))
    return float(match.group()) if match else None


def fetch(api_key: str, row) -> tuple[str, dict | None, str | None, bool]:
    req = Request(
        f"https://{HOST}/pktx/spotify/{row['spotify_id']}",
        headers={"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": HOST,
                 "User-Agent": "local-dj-music-db/1.0"},
    )
    try:
        with urlopen(req, timeout=45) as response:
            return row["spotify_id"], json.loads(response.read()), None, False
    except HTTPError as exc:
        body = exc.read().decode(errors="replace")[:1000]
        return row["spotify_id"], None, f"HTTP {exc.code}: {body}", exc.code == 404
    except Exception as exc:
        return row["spotify_id"], None, str(exc), False


def attributes(sid: str, data: dict, timestamp: str) -> list[tuple]:
    rows = []
    for key, value in data.items():
        if value is None:
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
        rows.append((sid, key, SOURCE, text, num, raw, 0.80, timestamp))
    return rows


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--concurrency", type=int, default=20)
    args = parser.parse_args()
    key = (os.getenv("SOUNDNET_RAPIDAPI_KEY") or "").strip()
    if not key:
        raise SystemExit("SOUNDNET_RAPIDAPI_KEY is missing")
    db = connect()
    db.execute(
        """CREATE TABLE IF NOT EXISTS soundnet_status(
             spotify_id TEXT PRIMARY KEY,status TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,
             last_error TEXT,updated_at TEXT NOT NULL)"""
    )
    rows = db.execute(
        """SELECT t.spotify_id FROM tracks t LEFT JOIN soundnet_status s USING(spotify_id)
           WHERE COALESCE(s.status,'') NOT IN ('success','not_found')
           ORDER BY COALESCE(s.attempts,0),t.spotify_id LIMIT ?""",
        (args.limit,),
    ).fetchall()
    succeeded = not_found = errors = 0
    with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        futures = [pool.submit(fetch, key, row) for row in rows]
        for future in as_completed(futures):
            sid, data, error, terminal = future.result()
            timestamp = now()
            if data:
                bpm = data.get("tempo", data.get("bpm"))
                genre = data.get("genre")
                with db:
                    db.execute(
                        """INSERT INTO audio_features(
                             spotify_id,source,source_id,bpm,key,mode,danceability,energy,valence,
                             acousticness,instrumentalness,speechiness,liveness,loudness,
                             confidence,raw_json,updated_at)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                           ON CONFLICT(spotify_id,source) DO UPDATE SET
                             source_id=excluded.source_id,bpm=excluded.bpm,key=excluded.key,
                             mode=excluded.mode,danceability=excluded.danceability,
                             energy=excluded.energy,valence=excluded.valence,
                             acousticness=excluded.acousticness,
                             instrumentalness=excluded.instrumentalness,
                             speechiness=excluded.speechiness,liveness=excluded.liveness,
                             loudness=excluded.loudness,confidence=excluded.confidence,
                             raw_json=excluded.raw_json,updated_at=excluded.updated_at""",
                        (sid, SOURCE, str(data.get("id") or ""), float(bpm) if bpm else None,
                         data.get("key"), data.get("mode"), normalized(data.get("danceability")),
                         normalized(data.get("energy")), normalized(data.get("happiness", data.get("valence"))),
                         normalized(data.get("acousticness")), normalized(data.get("instrumentalness")),
                         normalized(data.get("speechiness")), normalized(data.get("liveness")),
                         loudness(data.get("loudness")), 0.80,
                         json.dumps(data, ensure_ascii=False, sort_keys=True), timestamp),
                    )
                    if genre:
                        for value in str(genre).replace("/", ",").split(","):
                            value = value.strip().lower()
                            if value:
                                db.execute("INSERT OR REPLACE INTO tags VALUES(?,?,?,?,?)",
                                           (sid, value, "genre", SOURCE, 0.75))
                    attrs = attributes(sid, data, timestamp)
                    if attrs:
                        db.executemany(
                            """INSERT OR REPLACE INTO track_attributes
                               (spotify_id,attribute,source,value_text,value_num,value_json,confidence,updated_at)
                               VALUES(?,?,?,?,?,?,?,?)""", attrs,
                        )
                    db.execute(
                        """INSERT INTO soundnet_status VALUES(?,'success',1,NULL,?)
                           ON CONFLICT(spotify_id) DO UPDATE SET status='success',attempts=attempts+1,
                           last_error=NULL,updated_at=excluded.updated_at""", (sid, timestamp),
                    )
                succeeded += 1
            else:
                status = "not_found" if terminal else "failed"
                with db:
                    db.execute(
                        """INSERT INTO soundnet_status VALUES(?,?,1,?,?)
                           ON CONFLICT(spotify_id) DO UPDATE SET status=excluded.status,
                           attempts=attempts+1,last_error=excluded.last_error,updated_at=excluded.updated_at""",
                        (sid, status, error, timestamp),
                    )
                not_found += terminal
                errors += not terminal
    record_source_run(db, SOURCE, now(), succeeded,
                      f"not_found={not_found},errors={errors},concurrency={args.concurrency}")
    print(f"SoundNet: enriched={succeeded}, not_found={not_found}, errors={errors}")


if __name__ == "__main__":
    main()
