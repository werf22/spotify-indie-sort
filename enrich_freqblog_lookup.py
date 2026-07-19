"""Fast two-phase FreqBlog enrichment via non-blocking /lookup calls.

Cold tracks return 202 quickly and enter FreqBlog's server-side analysis queue.
The restart-safe worker polls them only after Retry-After; cached/finished tracks
return 200 and are persisted with full provenance by enrich_freqblog.save_success.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import time
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from enrich_freqblog import (
    BASE_URL, SOURCE, candidates, ensure_status_schema, first_artist,
    apply_identity_cache, identity_confidence, iso, save_pending, save_success,
    save_review,
)
from musicdb import connect, record_source_run


def lookup(api_key: str, row) -> dict:
    if row["isrc"]:
        params = {"isrc": row["isrc"][:15], "wait": "0"}
        query_type = "isrc"
    else:
        params = {"track": row["title"][:200], "artist": first_artist(row["artist_names"])[:200], "wait": "0"}
        query_type = "name_artist"
    request = Request(
        BASE_URL + "/lookup?" + urlencode(params),
        headers={
            "X-Api-Key": api_key,
            "Accept": "application/json",
            "User-Agent": "local-dj-music-db/1.0",
        },
    )
    try:
        # wait=0 is documented as non-blocking. A short transport timeout keeps
        # a few slow edge requests from holding a 300-track batch for an hour.
        with urlopen(request, timeout=10) as response:
            payload = json.loads(response.read())
            return {
                "row": row, "http": response.status, "payload": payload,
                "retry": int(response.headers.get("Retry-After") or 0),
                "query_type": query_type,
            }
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read())
        except Exception:
            payload = {"detail": str(exc)}
        return {
            "row": row, "http": exc.code, "payload": payload,
            "retry": int(exc.headers.get("Retry-After") or 0),
            "query_type": query_type,
        }
    except (URLError, TimeoutError, OSError) as exc:
        return {"row": row, "http": 0, "payload": {"detail": str(exc)}, "retry": 60, "query_type": query_type}


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=600)
    parser.add_argument("--concurrency", type=int, default=10, choices=range(1, 11))
    parser.add_argument("--per-minute", type=int, default=540, choices=range(1, 601))
    args = parser.parse_args()
    api_key = (os.getenv("FREQBLOG_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit("FREQBLOG_API_KEY is not configured")

    db = connect(); ensure_status_schema(db)
    monthly_quota = int(os.getenv("FREQBLOG_MONTHLY_QUOTA") or "150000")
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    used = db.execute(
        """SELECT COALESCE(SUM(MAX(quota_requests,selected-COALESCE(reused,0))),0)
           FROM freqblog_usage_runs WHERE substr(started_at,1,7)=?""",
        (month,),
    ).fetchone()[0]
    available = max(0, monthly_quota - int(used))
    if available == 0:
        print(f"FreqBlog monthly quota guard: {used:,}/{monthly_quota:,}; waiting for reset")
        return
    selected_rows = candidates(db, min(args.limit, available))
    rows, reused = apply_identity_cache(db, selected_rows)
    started = iso()
    succeeded = queued = unavailable = errors = review = 0
    # Waves provide a simple global rate limiter while preserving concurrency.
    wave_pause = 60.0 * args.concurrency / args.per_minute
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        for start in range(0, len(rows), args.concurrency):
            wave_started = time.monotonic()
            results = list(pool.map(lambda row: lookup(api_key, row), rows[start:start + args.concurrency]))
            for result in results:
                row, code, payload = result["row"], result["http"], result["payload"]
                now = iso()
                if code == 200 and isinstance(payload, dict) and payload.get("track_name"):
                    score, method = identity_confidence(row, payload)
                    if score >= 0.72:
                        save_success(db, row, payload, now, score, method)
                        succeeded += 1
                    else:
                        save_review(db, row, payload, score, method, now)
                        review += 1
                elif code == 202:
                    status = str(payload.get("status") or payload.get("backfill_status") or "processing")
                    delay = max(120, result["retry"] or 0)
                    save_pending(db, row["spotify_id"], "queued" if status == "queued" else "processing", None, delay)
                    queued += 1
                elif code == 404:
                    save_pending(db, row["spotify_id"], "not_found", str(payload.get("detail") or "no match"), 7 * 86400)
                    unavailable += 1
                elif code == 429:
                    delay = result["retry"] or 60
                    save_pending(db, row["spotify_id"], "quota_wait", str(payload.get("detail") or "rate/quota limit"), delay)
                    errors += 1
                else:
                    delay = result["retry"] or (120 if code in {502, 504} else 300)
                    save_pending(db, row["spotify_id"], "failed", f"HTTP {code}: {str(payload.get('detail') or payload)[:500]}", delay)
                    errors += 1
                    if code in {401, 403}:
                        raise SystemExit(f"FreqBlog authentication failed: HTTP {code}")
            remaining = wave_pause - (time.monotonic() - wave_started)
            if remaining > 0:
                time.sleep(remaining)

    finished = iso()
    # Starter quota is request-based: 200/202/404/error lookups all count as
    # outbound API calls. Cache hits are excluded because they never leave SQL.
    quota_estimate = len(rows)
    with db:
        db.execute(
            """INSERT INTO freqblog_usage_runs(
                 started_at,finished_at,selected,enriched,queued,not_found,errors,review,quota_requests,reused)
               VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (started, finished, len(selected_rows), succeeded + reused, queued, unavailable, errors, review, quota_estimate, reused),
        )
    record_source_run(
        db, SOURCE, finished, succeeded,
        f"transport=lookup,reused={reused},queued={queued},not_found={unavailable},errors={errors},review={review},quota_estimate={quota_estimate}",
    )
    print(
        f"FreqBlog lookup: enriched={succeeded}, queued={queued}, not_found={unavailable}, "
        f"errors={errors}, review={review}, reused={reused}, selected={len(selected_rows)}, "
        f"api_calls={len(rows)}, month_before={used}/{monthly_quota}"
    )


if __name__ == "__main__":
    main()
