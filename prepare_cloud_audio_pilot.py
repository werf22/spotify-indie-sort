#!/usr/bin/env python3
"""Prepare a deterministic, representative cloud-analysis pilot.

Only short analysis excerpts are produced.  The script is restart-safe: valid
clips are reused, failed files are recorded, and the manifest is rewritten
atomically after every successful clip.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import shutil
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from musicdb import connect


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "data" / "cloud_pilot"


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def candidates(db):
    """Load only local candidates, then enrich them through indexed lookups.

    Keeping tag aggregation out of the main query matters on the live 1.6 GB
    WAL database: a CTE join made SQLite reread most of the tag table while
    ingestion was writing concurrently.
    """
    rows = [dict(row) for row in db.execute(
        """WITH one_file AS (
             SELECT *,row_number() OVER (
               PARTITION BY spotify_id
               ORDER BY CASE lower(codec)
                 WHEN 'flac' THEN 1 WHEN 'alac' THEN 2 WHEN 'wav' THEN 3
                 WHEN 'aac' THEN 4 WHEN 'mp3' THEN 5 ELSE 9 END,
                 file_size DESC,path) pick
             FROM audio_files
             WHERE spotify_id IS NOT NULL AND scan_status='matched'
           )
           SELECT f.spotify_id,f.path,f.duration_seconds,f.codec,
                  t.title track_name,t.artist_names,t.album album_name,t.isrc
           FROM one_file f JOIN tracks t USING(spotify_id)
           WHERE f.pick=1 ORDER BY f.spotify_id"""
    )]
    if not rows:
        return rows

    by_id = {row["spotify_id"]: row for row in rows}
    genres = defaultdict(set)
    moods = defaultdict(set)
    ids = list(by_id)
    for offset in range(0, len(ids), 500):
        chunk = ids[offset:offset + 500]
        marks = ",".join("?" for _ in chunk)
        for tag in db.execute(
            f"""SELECT spotify_id,tag_type,tag FROM tags
                WHERE spotify_id IN ({marks})
                  AND tag_type IN ('genre','subgenre','mood')""", chunk
        ):
            target = moods if tag["tag_type"] == "mood" else genres
            target[tag["spotify_id"]].add(tag["tag"])
        for analysis in db.execute(
            f"""SELECT spotify_id,path,rhythm_pattern FROM local_audio_analysis
                WHERE spotify_id IN ({marks})
                  AND analyzer_version='rhythm-v1.0.5'""", chunk
        ):
            row = by_id.get(analysis["spotify_id"])
            if row and row["path"] == analysis["path"]:
                row["rhythm_pattern"] = analysis["rhythm_pattern"]
    for spotify_id, row in by_id.items():
        row["genre_tags"] = " | ".join(sorted(genres[spotify_id]))
        row["mood_tags"] = " | ".join(sorted(moods[spotify_id]))
        row.setdefault("rhythm_pattern", "unknown")
    return rows


def primary_bucket(row) -> str:
    if row["rhythm_pattern"] != "unknown":
        return "rhythm:" + row["rhythm_pattern"]
    tags = [x.strip().lower() for x in row["genre_tags"].split("|") if x.strip()]
    return "genre:" + (tags[0] if tags else "untagged")


def select_balanced(rows, limit: int):
    """Round-robin across rhythm/genre buckets, deduplicating recordings."""
    buckets = defaultdict(list)
    for row in rows:
        buckets[primary_bucket(row)].append(row)
    ordered = sorted(buckets, key=lambda key: (len(buckets[key]), key))
    selected, seen_isrc, seen_path = [], set(), set()
    while ordered and len(selected) < limit:
        next_round = []
        for key in ordered:
            pool = buckets[key]
            while pool:
                row = pool.pop(0)
                recording = (row["isrc"] or row["spotify_id"]).upper()
                path = str(Path(row["path"]).resolve())
                if recording in seen_isrc or path in seen_path or not Path(path).is_file():
                    continue
                selected.append(row)
                seen_isrc.add(recording)
                seen_path.add(path)
                break
            if pool:
                next_round.append(key)
            if len(selected) >= limit:
                break
        ordered = next_round
    return selected


def clip_is_valid(ffprobe: str, path: Path, expected: float) -> bool:
    if not path.is_file() or path.stat().st_size < 50_000:
        return False
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, timeout=30,
    )
    try:
        return proc.returncode == 0 and float(proc.stdout.strip()) >= expected - 1.0
    except ValueError:
        return False


def extract(ffmpeg: str, source: Path, target: Path, duration: float, seconds: float,
            codec: str, full_track: bool = False) -> float:
    start = 0.0 if full_track else max(
        0.0, min(duration * 0.30, max(0.0, duration - seconds - 1.0))
    )
    tmp = target.with_name(target.stem + ".partial" + target.suffix)
    tmp.unlink(missing_ok=True)
    encode = (["-c:a", "flac", "-compression_level", "5"] if codec == "flac" else
              ["-c:a", "libopus", "-b:a", "192k", "-vbr", "on", "-compression_level", "10"])
    command = [ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-ss", f"{start:.3f}",
               "-i", str(source)]
    if not full_track:
        command += ["-t", f"{seconds:.3f}"]
    command += ["-map", "0:a:0", "-vn", "-ac", "1",
                "-ar", "48000" if codec == "opus" else "44100", *encode, str(tmp)]
    proc = subprocess.run(command, capture_output=True, text=True,
                          timeout=max(240, int(duration * 0.75)))
    if proc.returncode:
        tmp.unlink(missing_ok=True)
        raise RuntimeError((proc.stderr or "ffmpeg failed")[-1000:])
    tmp.replace(target)
    return start


def write_manifest(path: Path, records: list[dict]) -> None:
    tmp = path.with_suffix(".partial.csv")
    fields = [
        "spotify_id", "track_name", "artist_names", "album_name", "isrc",
        "source_path", "clip_path", "segment_start", "segment_seconds",
        "coverage_mode", "genre_tags", "mood_tags", "rhythm_pattern", "prepared_at",
    ]
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    tmp.replace(path)


def prepare_row(row, clips: Path, codec: str, seconds: float, ffmpeg: str, ffprobe: str,
                full_track: bool = False):
    target = clips / f"{row['spotify_id']}.{codec}"
    duration = float(row["duration_seconds"] or seconds + 1)
    start = 0.0 if full_track else max(
        0.0, min(duration * 0.30, max(0.0, duration - seconds - 1.0))
    )
    expected = duration if full_track else min(seconds, duration)
    try:
        if not clip_is_valid(ffprobe, target, expected):
            start = extract(ffmpeg, Path(row["path"]), target, duration, seconds, codec, full_track)
        return {
            "spotify_id": row["spotify_id"], "track_name": row["track_name"],
            "artist_names": row["artist_names"], "album_name": row["album_name"],
            "isrc": row["isrc"] or "", "source_path": row["path"],
            "clip_path": str(target), "segment_start": f"{start:.3f}",
            "segment_seconds": f"{expected:.3f}",
            "coverage_mode": "full_track" if full_track else "single_excerpt",
            "genre_tags": row["genre_tags"],
            "mood_tags": row["mood_tags"], "rhythm_pattern": row["rhythm_pattern"],
            "prepared_at": utcnow(),
        }, None
    except Exception as exc:
        return None, {"spotify_id": row["spotify_id"], "path": row["path"], "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--seconds", type=float, default=45.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--codec", choices=("flac", "opus"), default="flac")
    parser.add_argument("--workers", type=int, choices=range(1, 17), default=1)
    parser.add_argument("--full-track", action="store_true",
                        help="Transcode the complete track instead of one excerpt")
    args = parser.parse_args()
    ffmpeg = shutil.which("ffmpeg") or str(Path.home() / ".local" / "bin" / "ffmpeg")
    ffprobe = shutil.which("ffprobe") or str(Path.home() / ".local" / "bin" / "ffprobe")
    if not Path(ffmpeg).is_file() or not Path(ffprobe).is_file():
        raise SystemExit("ffmpeg and ffprobe are required")
    clips = args.output / "clips"
    clips.mkdir(parents=True, exist_ok=True)
    selected = select_balanced(candidates(connect()), args.limit)
    records, failures = [], []
    worker = lambda row: prepare_row(
        row, clips, args.codec, args.seconds, ffmpeg, ffprobe, args.full_track
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        for index, (record, failure) in enumerate(pool.map(worker, selected), 1):
            if record:
                records.append(record)
            if failure:
                failures.append(failure)
            if index % 25 == 0:
                write_manifest(args.output / "manifest.csv", records)
                print(f"pilot: {index}/{len(selected)} ready={len(records)} failed={len(failures)}", flush=True)
    write_manifest(args.output / "manifest.csv", records)
    (args.output / "failures.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
    total_bytes = sum(Path(row["clip_path"]).stat().st_size for row in records)
    print(f"pilot: ready={len(records)} failed={len(failures)} size_mib={total_bytes/1024/1024:.1f}")


if __name__ == "__main__":
    main()
