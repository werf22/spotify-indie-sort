"""Probe FreqBlog's on-demand coverage with a small stratified sample.

Unlike /bulk, /lookup waits for on-demand backfill. Re-running the script polls
the same deterministic sample and merges the latest result into the report.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import load_dotenv

from enrich_freqblog import BASE_URL, ensure_status_schema, save_success
from musicdb import connect
from validate_freqblog import first_artist, sample_tracks

ROOT = Path(__file__).resolve().parent
OUT_JSON = ROOT / "data" / "freqblog_individual_probe.json"
OUT_CSV = ROOT / "data" / "freqblog_individual_probe.csv"
OUT_MD = ROOT / "data" / "freqblog_individual_probe.md"
FIELDS = (
    "bpm", "key", "camelot", "energy", "danceability", "valence",
    "acousticness", "instrumentalness", "liveness", "speechiness",
    "loudness_db", "mood", "genre", "release_date", "duration_ms", "isrc",
)
GROUP_LIMITS = {
    "tebra_original": 12,
    "tebra_versions": 8,
    "tebra_collabs": 4,
    "underground_other": 12,
    "indie_control": 4,
}


def choose_sample(db, size: int) -> list[tuple[str, object]]:
    grouped: dict[str, list] = defaultdict(list)
    for group, row in sample_tracks(db, 200):
        grouped[group].append(row)
    chosen = []
    for group, limit in GROUP_LIMITS.items():
        chosen.extend((group, row) for row in grouped[group][:limit])
    if len(chosen) < size:
        used = {row["spotify_id"] for _, row in chosen}
        for group, rows in grouped.items():
            for row in rows:
                if row["spotify_id"] not in used:
                    chosen.append((group, row)); used.add(row["spotify_id"])
                    if len(chosen) >= size:
                        return chosen
    return chosen[:size]


def lookup(api_key: str, item: tuple[str, object], wait: int) -> dict:
    group, row = item
    params = {"wait": str(wait)}
    if row["isrc"]:
        params["isrc"] = row["isrc"][:15]
        query_type = "isrc"
    else:
        params.update(track=row["title"][:200], artist=first_artist(row["artist_names"])[:200])
        query_type = "name"
    request = Request(
        BASE_URL + "/lookup?" + urlencode(params),
        headers={
            "X-Api-Key": api_key,
            "Accept": "application/json",
            "User-Agent": "local-dj-db-validator/1.0",
        },
    )
    try:
        with urlopen(request, timeout=wait + 20) as response:
            payload = json.loads(response.read())
            http = response.status
            retry_after = response.headers.get("Retry-After")
    except HTTPError as exc:
        http = exc.code
        retry_after = exc.headers.get("Retry-After")
        try:
            payload = json.loads(exc.read())
        except Exception:
            payload = {"detail": str(exc)}
    except (URLError, TimeoutError) as exc:
        http = 0
        retry_after = None
        payload = {"detail": f"{type(exc).__name__}: {exc}"}
    found = http == 200 and isinstance(payload, dict) and payload.get("track_name")
    status = "found" if found else (
        "processing" if http in (202, 504) else "rate_limited" if http == 429 else "not_found" if http == 404 else "error"
    )
    return {
        "group": group,
        "spotify_id": row["spotify_id"],
        "title": row["title"],
        "artist": row["artist_names"],
        "input_isrc": row["isrc"] or "",
        "query_type": query_type,
        "http": http,
        "status": status,
        "retry_after": retry_after or "",
        "data": payload if found else None,
        "detail": "" if found else str(payload.get("detail") or payload.get("message") or "")[:300],
    }


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", type=int, default=40)
    parser.add_argument("--concurrency", type=int, default=5, choices=range(1, 7))
    parser.add_argument("--wait", type=int, default=25, choices=range(1, 26))
    parser.add_argument(
        "--only-status",
        choices=("all", "unresolved", "processing", "rate_limited", "error", "not_found"),
        default="all",
        help="poll only rows with this status from the preceding run",
    )
    parser.add_argument("--limit", type=int, default=0, help="maximum rows to query; 0 means all")
    args = parser.parse_args()
    api_key = (os.getenv("FREQBLOG_API_KEY") or "").strip()
    if not api_key:
        raise SystemExit("FREQBLOG_API_KEY is missing")

    db = connect(); ensure_status_schema(db)
    sample = choose_sample(db, args.size)
    previous = {}
    if OUT_JSON.exists():
        previous = {r["spotify_id"]: r for r in json.loads(OUT_JSON.read_text())["details"]}
    query_sample = sample
    if args.only_status != "all":
        wanted = {"processing", "rate_limited", "error", "not_found"} if args.only_status == "unresolved" else {args.only_status}
        query_sample = [item for item in sample if previous.get(item[1]["spotify_id"], {}).get("status") in wanted]
    if args.limit:
        query_sample = query_sample[: args.limit]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as pool:
        current = list(pool.map(lambda item: lookup(api_key, item, args.wait), query_sample))

    merged = dict(previous)
    for row in current:
        old = merged.get(row["spotify_id"])
        if row["status"] == "found" or not old or old["status"] != "found":
            merged[row["spotify_id"]] = row
    details = [merged[row["spotify_id"]] for _, row in sample]
    now = datetime.now(timezone.utc).isoformat()
    for item in details:
        if item["status"] == "found":
            source_row = next(row for _, row in sample if row["spotify_id"] == item["spotify_id"])
            save_success(db, source_row, item["data"], now)

    OUT_JSON.write_text(json.dumps({"created_at": now, "details": details}, ensure_ascii=False, indent=2))
    flat = []
    for item in details:
        data = item["data"] or {}
        flat.append({k: v for k, v in item.items() if k != "data"} | {k: data.get(k, "") for k in FIELDS})
    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=flat[0].keys()); writer.writeheader(); writer.writerows(flat)

    statuses = Counter(r["status"] for r in details)
    groups = Counter(r["group"] for r in details)
    found_groups = Counter(r["group"] for r in details if r["status"] == "found")
    found = statuses["found"]
    field_counts = Counter(k for r in details if r["data"] for k in FIELDS if r["data"].get(k) is not None)
    lines = [
        "# FreqBlog individual lookup probe", "", f"Tested: **{len(details)}**",
        f"Found: **{found}/{len(details)} ({found/len(details):.1%})**", "",
        "## Status", "",
    ]
    lines.extend(f"- {name}: {count}" for name, count in statuses.items())
    lines.extend(["", "## By group", ""])
    lines.extend(f"- {group}: {found_groups[group]}/{count} ({found_groups[group]/count:.1%})" for group, count in groups.items())
    lines.extend(["", "## Field coverage among found", ""])
    lines.extend(f"- {field}: {field_counts[field]}/{found} ({field_counts[field]/found:.1%})" for field in FIELDS) if found else None
    OUT_MD.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nDetails: {OUT_CSV}\nRaw: {OUT_JSON}\nReport: {OUT_MD}")


if __name__ == "__main__":
    main()
