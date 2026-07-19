"""Resumable FreqBlog bulk enrichment for cloud-only DJ audio features.

The worker uses ISRC + title + artist together: ISRC gives an exact recording
match while the names allow the provider to fall back to on-demand analysis.
Every response is retained both in the typed tables and as raw JSON.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from musicdb import connect, record_source_run

BASE_URL = "https://api.freqblog.com"
SOURCE = "freqblog"

# Reliability is deliberately field-specific. FreqBlog's BPM/key are mature
# Essentia outputs; several Spotify-shaped perceptual fields are useful only as
# weak relative signals. Keeping this distinction in the DB prevents a filled
# value from being mistaken for a highly reliable value.
FIELD_CONFIDENCE = {
    "bpm": 0.90, "bpm_alt": 0.82, "bpm_confidence": 0.90,
    "key": 0.88, "key_int": 0.88, "mode": 0.88,
    "key_confidence": 0.90, "camelot": 0.88, "open_key": 0.88,
    "loudness_db": 0.62, "energy": 0.45, "danceability": 0.35,
    "valence": 0.12, "acousticness": 0.08, "instrumentalness": 0.08,
    "liveness": 0.04, "speechiness": 0.12, "time_signature": 0.10,
    "genre": 0.55, "mood": 0.25, "mood_vector": 0.30,
    "track_name": 0.95, "artist_name": 0.95, "album_name": 0.90,
    "isrc": 0.98, "release_date": 0.92, "duration_ms": 0.90,
    "mbid": 0.98, "itunes_track_id": 0.98, "explicit": 0.85,
    "is_remix": 0.78, "mix_name": 0.78, "remixer": 0.78,
    "feature_source": 1.0, "source": 1.0,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).isoformat()


def first_artist(artists: str | None) -> str:
    return (artists or "").split(",", 1)[0].strip()


def norm(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    return " ".join("".join(c.lower() if c.isalnum() else " " for c in text).split())


def identity_confidence(row, data: dict) -> tuple[float, str]:
    """Return a conservative match score and the strongest matching method."""
    input_isrc = re.sub(r"[^A-Z0-9]", "", (row["isrc"] or "").upper())
    output_isrc = re.sub(r"[^A-Z0-9]", "", str(data.get("isrc") or "").upper())
    if input_isrc and output_isrc:
        if input_isrc == output_isrc:
            return 1.0, "isrc_exact"
        title = SequenceMatcher(None, norm(row["title"]), norm(data.get("track_name"))).ratio()
        artist = SequenceMatcher(None, norm(first_artist(row["artist_names"])), norm(data.get("artist_name"))).ratio()
        if title >= 0.94 and artist >= 0.70:
            return 0.78, "name_exact_isrc_variant"
        return 0.0, "isrc_conflict"
    title = SequenceMatcher(None, norm(row["title"]), norm(data.get("track_name"))).ratio()
    artist = SequenceMatcher(None, norm(first_artist(row["artist_names"])), norm(data.get("artist_name"))).ratio()
    score = 0.72 * title + 0.28 * artist
    return score, "name_artist"


def identity_keys(row, data: dict | None = None) -> list[str]:
    data = data or {}
    keys = set()
    for isrc in (row["isrc"], data.get("isrc")):
        clean = re.sub(r"[^A-Z0-9]", "", str(isrc or "").upper())
        if clean:
            keys.add("isrc:" + clean)
    artist = norm(data.get("artist_name") or first_artist(row["artist_names"]))
    title = norm(data.get("track_name") or row["title"])
    if artist and title:
        keys.add(f"name:{artist}|{title}")
    return sorted(keys)


def field_confidence(field: str, data: dict, fallback: float = 0.50) -> float:
    base = FIELD_CONFIDENCE.get(field, fallback)
    if field.startswith(("bpm", "key", "camelot", "open_key")):
        reported = data.get("key_confidence" if field.startswith(("key", "camelot", "open_key")) else "bpm_confidence")
        if isinstance(reported, (int, float)):
            # Some Essentia BPM confidences exceed 1; treat them as strong, not
            # as probabilities.
            reported_norm = min(1.0, max(0.25, float(reported)))
            base = 0.55 * base + 0.45 * reported_norm
    return round(min(1.0, max(0.01, base)), 4)


def confidence_for(data: dict) -> float:
    return {
        "essentia_preview": 0.85,
        "acousticbrainz": 0.80,
        "fma": 0.72,
        "msd": 0.68,
        "user_upload": 0.90,
    }.get(data.get("feature_source"), 0.65)


def mode_name(value) -> str | None:
    if value in (1, "1", "major", "Major"):
        return "major"
    if value in (0, "0", "minor", "Minor"):
        return "minor"
    return str(value) if value is not None else None


def tag_rows(spotify_id: str, data: dict, confidence: float) -> list[tuple]:
    rows: list[tuple] = []

    def add(tag, tag_type, conf=confidence):
        if tag is not None and str(tag).strip():
            rows.append((spotify_id, str(tag).strip().lower(), tag_type, SOURCE, conf))

    add(data.get("genre"), "genre", field_confidence("genre", data))
    add(data.get("mood"), "mood", field_confidence("mood", data))
    if data.get("is_remix"):
        add("remix", "version")
    add(data.get("mix_name"), "version")
    add(data.get("remixer"), "remixer")

    for mood, score in (data.get("mood_vector") or {}).items():
        if isinstance(score, (int, float)) and score >= 0.40:
            add(mood, "mood", min(field_confidence("mood_vector", data), float(score)))

    extended = data.get("extended") or {}
    gender = extended.get("gender")
    if gender:
        add(f"{gender} vocals", "voice")
    add(extended.get("timbre"), "timbre")
    add(extended.get("tonal_atonal"), "tonality")

    bpm = data.get("bpm")
    if isinstance(bpm, (int, float)):
        add("slow" if bpm < 100 else "midtempo" if bpm < 118 else "club tempo" if bpm < 130 else "fast", "tempo_band", field_confidence("bpm", data))
    energy = data.get("energy")
    if isinstance(energy, (int, float)):
        add("low" if energy < 0.60 else "medium" if energy < 0.80 else "high", "energy_band", field_confidence("energy", data))
    dance = data.get("danceability")
    if isinstance(dance, (int, float)):
        add("low" if dance < 0.70 else "medium" if dance < 0.82 else "high", "danceability_band", field_confidence("danceability", data))
    if data.get("mode") in (0, "0", "minor", "Minor"):
        add("minor", "harmonic_mode", field_confidence("mode", data))
    elif data.get("mode") in (1, "1", "major", "Major"):
        add("major", "harmonic_mode", field_confidence("mode", data))
    return rows


def attribute_rows(spotify_id: str, data: dict, confidence: float, now: str) -> list[tuple]:
    """Keep every provider field, including future fields not in our schema."""
    rows = []
    for name, value in data.items():
        if value is None:
            continue
        text_value = num_value = json_value = None
        if isinstance(value, bool):
            num_value = float(value)
            text_value = "true" if value else "false"
        elif isinstance(value, (int, float)):
            num_value = float(value)
        elif isinstance(value, (dict, list)):
            json_value = json.dumps(value, ensure_ascii=False, sort_keys=True)
        else:
            text_value = str(value)
        rows.append((spotify_id, name, SOURCE, text_value, num_value, json_value, field_confidence(name, data, confidence), now))
    return rows


def ensure_status_schema(db) -> None:
    db.executescript(
        """CREATE TABLE IF NOT EXISTS freqblog_status(
             spotify_id TEXT PRIMARY KEY,
             status TEXT NOT NULL,
             attempts INTEGER NOT NULL DEFAULT 0,
             next_retry_at TEXT,
             last_error TEXT,
             updated_at TEXT NOT NULL,
             match_confidence REAL,
             match_method TEXT,
             feature_source TEXT,
             provider_source TEXT
           );
           CREATE INDEX IF NOT EXISTS idx_freqblog_status_retry
             ON freqblog_status(status,next_retry_at,attempts);
           CREATE TABLE IF NOT EXISTS freqblog_usage_runs(
             id INTEGER PRIMARY KEY,
             started_at TEXT NOT NULL,
             finished_at TEXT NOT NULL,
             selected INTEGER NOT NULL,
             enriched INTEGER NOT NULL,
             queued INTEGER NOT NULL,
             not_found INTEGER NOT NULL,
             errors INTEGER NOT NULL,
             review INTEGER NOT NULL,
             quota_requests INTEGER NOT NULL
           );
           CREATE TABLE IF NOT EXISTS freqblog_review_candidates(
             spotify_id TEXT PRIMARY KEY,
             match_confidence REAL NOT NULL,
             match_method TEXT NOT NULL,
             provider_track TEXT,
             provider_artist TEXT,
             provider_isrc TEXT,
             raw_json TEXT NOT NULL,
             updated_at TEXT NOT NULL
           );
           CREATE TABLE IF NOT EXISTS freqblog_identity_cache(
             identity_key TEXT PRIMARY KEY,
             raw_json TEXT NOT NULL,
             source_spotify_id TEXT NOT NULL,
             updated_at TEXT NOT NULL
           );"""
    )
    columns = {r[1] for r in db.execute("PRAGMA table_info(freqblog_status)")}
    for name, kind in (
        ("match_confidence", "REAL"), ("match_method", "TEXT"),
        ("feature_source", "TEXT"), ("provider_source", "TEXT"),
    ):
        if name not in columns:
            db.execute(f"ALTER TABLE freqblog_status ADD COLUMN {name} {kind}")
    usage_columns = {r[1] for r in db.execute("PRAGMA table_info(freqblog_usage_runs)")}
    if "reused" not in usage_columns:
        db.execute("ALTER TABLE freqblog_usage_runs ADD COLUMN reused INTEGER NOT NULL DEFAULT 0")
    db.commit()


def save_review(db, row, data: dict, score: float, method: str, now: str) -> None:
    with db:
        db.execute(
            """INSERT OR REPLACE INTO freqblog_review_candidates(
                 spotify_id,match_confidence,match_method,provider_track,
                 provider_artist,provider_isrc,raw_json,updated_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (
                row["spotify_id"], score, method, data.get("track_name"),
                data.get("artist_name"), data.get("isrc"),
                json.dumps(data, ensure_ascii=False, sort_keys=True), now,
            ),
        )
    save_pending(db, row["spotify_id"], "needs_review", f"{method}:{score:.3f}", 30 * 86400)


def candidates(db, limit: int):
    now = iso()
    return db.execute(
        """SELECT t.spotify_id,t.title,t.artist_names,t.isrc
           FROM tracks t
           LEFT JOIN freqblog_status s USING(spotify_id)
           WHERE COALESCE(s.status,'') <> 'success'
             AND COALESCE(s.status,'') <> 'unavailable'
             AND (s.next_retry_at IS NULL OR s.next_retry_at <= ?)
           ORDER BY
             CASE COALESCE(s.status,'')
               WHEN 'queued' THEN 0 WHEN 'processing' THEN 0
               WHEN 'failed' THEN 1 ELSE 2 END,
             COALESCE(s.attempts,0), t.spotify_id
           LIMIT ?""",
        (now, limit),
    ).fetchall()


def post_bulk(api_key: str, payload: list[dict], timeout: int = 90) -> tuple[dict, dict]:
    req = Request(
        BASE_URL + "/bulk",
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
            "User-Agent": "local-dj-music-db/1.0",
        },
        method="POST",
    )
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read()), dict(response.headers)


def fetch_batch(api_key: str, batch) -> tuple[object, dict | None, dict | None]:
    payload = [
        {
            "track": row["title"][:200],
            "artist": first_artist(row["artist_names"])[:200] or None,
            **({"isrc": row["isrc"][:15]} if row["isrc"] else {}),
        }
        for row in batch
    ]
    try:
        response, headers = post_bulk(api_key, payload)
        return batch, response, {"headers": headers}
    except HTTPError as exc:
        return batch, None, {
            "kind": "http", "code": exc.code,
            "retry": int(exc.headers.get("Retry-After") or (120 if exc.code in {502, 504} else 3600 if exc.code == 429 else 300)),
            "message": exc.read().decode(errors="replace")[:1000],
        }
    except (URLError, TimeoutError, OSError, RuntimeError) as exc:
        return batch, None, {"kind": "transport", "retry": 300, "message": str(exc)}


def save_success(db, row, data: dict, now: str, match_score: float = 1.0, match_method: str = "validated") -> None:
    sid = row["spotify_id"]
    conf = confidence_for(data)
    raw = json.dumps(data, ensure_ascii=False, sort_keys=True)
    with db:
        db.execute(
            """INSERT INTO audio_features(
                 spotify_id,source,source_id,bpm,key,mode,time_signature,
                 danceability,energy,valence,acousticness,instrumentalness,
                 speechiness,liveness,loudness,confidence,raw_json,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(spotify_id,source) DO UPDATE SET
                 source_id=excluded.source_id,bpm=excluded.bpm,key=excluded.key,
                 mode=excluded.mode,time_signature=excluded.time_signature,
                 danceability=excluded.danceability,energy=excluded.energy,
                 valence=excluded.valence,acousticness=excluded.acousticness,
                 instrumentalness=excluded.instrumentalness,
                 speechiness=excluded.speechiness,liveness=excluded.liveness,
                 loudness=excluded.loudness,confidence=excluded.confidence,
                 raw_json=excluded.raw_json,updated_at=excluded.updated_at""",
            (
                sid, SOURCE, data.get("itunes_track_id"), data.get("bpm"),
                data.get("key"), mode_name(data.get("mode")), data.get("time_signature"),
                data.get("danceability"), data.get("energy"), data.get("valence"),
                data.get("acousticness"), data.get("instrumentalness"),
                data.get("speechiness"), data.get("liveness"), data.get("loudness_db"),
                conf, raw, now,
            ),
        )
        db.execute(
            """UPDATE tracks SET
                 album=COALESCE(album,?), duration_ms=COALESCE(duration_ms,?),
                 release_date=COALESCE(release_date,?), isrc=COALESCE(isrc,?),
                 musicbrainz_id=COALESCE(musicbrainz_id,?),
                 explicit=COALESCE(explicit,?), updated_at=?
               WHERE spotify_id=?""",
            (
                data.get("album_name"), data.get("duration_ms"), data.get("release_date"),
                data.get("isrc"), data.get("mbid"),
                int(data["explicit"]) if data.get("explicit") is not None else None,
                now, sid,
            ),
        )
        tags = tag_rows(sid, data, conf)
        if tags:
            db.executemany("INSERT OR REPLACE INTO tags VALUES(?,?,?,?,?)", tags)
        attrs = attribute_rows(sid, data, conf, now)
        if attrs:
            db.executemany(
                """INSERT OR REPLACE INTO track_attributes
                   (spotify_id,attribute,source,value_text,value_num,value_json,confidence,updated_at)
                   VALUES(?,?,?,?,?,?,?,?)""",
                attrs,
            )
        db.execute(
            """INSERT INTO freqblog_status(
                 spotify_id,status,attempts,next_retry_at,last_error,updated_at,
                 match_confidence,match_method,feature_source,provider_source)
               VALUES(?,'success',1,NULL,NULL,?,?,?,?,?)
               ON CONFLICT(spotify_id) DO UPDATE SET status='success',
                 attempts=attempts+1,next_retry_at=NULL,last_error=NULL,
                 updated_at=excluded.updated_at,match_confidence=excluded.match_confidence,
                 match_method=excluded.match_method,feature_source=excluded.feature_source,
                 provider_source=excluded.provider_source""",
            (sid, now, match_score, match_method, data.get("feature_source"), data.get("source")),
        )
        for key in identity_keys(row, data):
            db.execute(
                """INSERT INTO freqblog_identity_cache(identity_key,raw_json,source_spotify_id,updated_at)
                   VALUES(?,?,?,?) ON CONFLICT(identity_key) DO UPDATE SET
                     raw_json=excluded.raw_json,source_spotify_id=excluded.source_spotify_id,
                     updated_at=excluded.updated_at""",
                (key, raw, sid, now),
            )


def apply_identity_cache(db, rows) -> tuple[list, int]:
    remaining = []
    reused = 0
    for row in rows:
        hit = None
        for key in identity_keys(row):
            hit = db.execute("SELECT raw_json FROM freqblog_identity_cache WHERE identity_key=?", (key,)).fetchone()
            if hit:
                break
        if not hit:
            remaining.append(row)
            continue
        data = json.loads(hit["raw_json"])
        score, method = identity_confidence(row, data)
        if score >= 0.72:
            save_success(db, row, data, iso(), score, "local_cache_" + method)
            reused += 1
        else:
            remaining.append(row)
    return remaining, reused


def save_pending(db, sid: str, status: str, message: str | None, delay: int) -> None:
    now_dt = utcnow()
    with db:
        db.execute(
            """INSERT INTO freqblog_status(
                 spotify_id,status,attempts,next_retry_at,last_error,updated_at)
               VALUES(?,?,1,?,?,?)
               ON CONFLICT(spotify_id) DO UPDATE SET status=excluded.status,
                 attempts=attempts+1,next_retry_at=excluded.next_retry_at,
                 last_error=excluded.last_error,updated_at=excluded.updated_at""",
            (sid, status, iso(now_dt + timedelta(seconds=delay)), message, iso(now_dt)),
        )


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=500, help="tracks per invocation")
    parser.add_argument("--batch-size", type=int, default=5, choices=range(1, 51))
    parser.add_argument("--concurrency", type=int, default=3, choices=range(1, 11))
    parser.add_argument("--delay", type=float, default=0.2, help="delay between bulk calls")
    args = parser.parse_args()
    api_key = (os.getenv("FREQBLOG_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit("FREQBLOG_API_KEY is not configured")

    started_at = iso()
    db = connect()
    ensure_status_schema(db)
    monthly_quota = int(os.getenv("FREQBLOG_MONTHLY_QUOTA") or "150000")
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    used = int(db.execute(
        """SELECT COALESCE(SUM(MAX(quota_requests,selected-COALESCE(reused,0))),0)
           FROM freqblog_usage_runs WHERE substr(started_at,1,7)=?""",
        (month,),
    ).fetchone()[0])
    available = max(0, monthly_quota - used)
    if available == 0:
        print(f"FreqBlog monthly quota guard: {used:,}/{monthly_quota:,}; waiting for reset")
        return
    selected_rows = candidates(db, min(args.limit, available))
    rows, reused = apply_identity_cache(db, selected_rows)
    succeeded = queued = unavailable = errors = requests_used = review = 0

    batches = [rows[start : start + args.batch_size] for start in range(0, len(rows), args.batch_size)]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        outcomes = pool.map(lambda batch: fetch_batch(api_key, batch), batches)
        for batch, response, outcome in outcomes:
            if response is not None:
                results = response.get("results") or []
                requests_used += int(response.get("requests_used") or 0)
                if len(results) != len(batch):
                    for row in batch:
                        save_pending(db, row["spotify_id"], "failed", f"bulk result count {len(results)} != {len(batch)}", 300)
                    errors += len(batch)
                    continue
                for row, result in zip(batch, results):
                    data = result.get("result")
                    if result.get("found") and data:
                        match_score, match_method = identity_confidence(row, data)
                        if match_score >= 0.72:
                            save_success(db, row, data, iso(), match_score, match_method)
                            succeeded += 1
                        else:
                            save_review(db, row, data, match_score, match_method, iso())
                            review += 1
                    elif result.get("backfill_status") in {"queued", "processing"}:
                        save_pending(db, row["spotify_id"], result["backfill_status"], None, 30)
                        queued += 1
                    elif result.get("backfill_status") in {"over_limit", "invalid_no_query"}:
                        save_pending(db, row["spotify_id"], "failed", result["backfill_status"], 300)
                        errors += 1
                    else:
                        # Name+artist misses can become available later; revisit weekly.
                        save_pending(db, row["spotify_id"], "not_found", "no match", 7 * 86400)
                        unavailable += 1
            else:
                code = outcome.get("code") if outcome else None
                retry = int((outcome or {}).get("retry") or 300)
                message = (outcome or {}).get("message") or "unknown request failure"
                status = "quota_wait" if code == 429 else "failed"
                prefix = f"HTTP {code}: " if code else ""
                for row in batch:
                    save_pending(db, row["spotify_id"], status, prefix + message, retry)
                errors += len(batch)
                if code in {401, 403}:
                    raise SystemExit(f"FreqBlog authentication failed: HTTP {code}")
            time.sleep(args.delay)

    now = iso()
    with db:
        db.execute(
            """INSERT INTO freqblog_usage_runs(
                 started_at,finished_at,selected,enriched,queued,not_found,errors,review,quota_requests,reused)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (started_at, now, len(selected_rows), succeeded + reused, queued, unavailable,
             errors, review, requests_used, reused),
        )
    record_source_run(
        db, SOURCE, now, succeeded,
        f"transport=bulk,reused={reused},queued={queued},not_found={unavailable},"
        f"errors={errors},review={review},quota_requests={requests_used}",
    )
    print(
        f"FreqBlog: enriched={succeeded}, queued={queued}, not_found={unavailable}, "
        f"errors={errors}, review={review}, reused={reused}, selected={len(selected_rows)}, "
        f"quota_requests={requests_used}, month_before={used}/{monthly_quota}"
    )


if __name__ == "__main__":
    main()
