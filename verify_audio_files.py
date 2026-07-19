#!/usr/bin/env python3
"""Resumably verify that indexed audio files are real, complete and decodable."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from musicdb import connect, record_source_run


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def media_tools() -> tuple[str, str]:
    ffprobe = shutil.which("ffprobe") or str(Path.home() / ".local/bin/ffprobe")
    ffmpeg = shutil.which("ffmpeg") or str(Path.home() / ".local/bin/ffmpeg")
    if not Path(ffprobe).exists() or not Path(ffmpeg).exists():
        raise SystemExit("ffprobe/ffmpeg not found")
    return ffprobe, ffmpeg


def probe(ffprobe: str, path: Path) -> dict:
    proc = subprocess.run(
        [ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)],
        capture_output=True, text=True, timeout=60,
    )
    if proc.returncode:
        raise RuntimeError((proc.stderr or "ffprobe failed")[-1000:])
    payload = json.loads(proc.stdout)
    streams = [stream for stream in payload.get("streams", []) if stream.get("codec_type") == "audio"]
    if not streams:
        raise RuntimeError("no audio stream")
    stream = streams[0]
    fmt = payload.get("format") or {}
    duration = float(fmt.get("duration") or stream.get("duration") or 0)
    if duration < 15:
        raise RuntimeError(f"audio too short: {duration:.2f}s")
    return {
        "duration": duration,
        "codec": stream.get("codec_name") or fmt.get("format_name"),
        "bitrate": int(float(stream.get("bit_rate") or fmt.get("bit_rate") or 0)) or None,
        "sample_rate": int(stream.get("sample_rate") or 0) or None,
        "channels": int(stream.get("channels") or 0) or None,
    }


def deep_decode(ffmpeg: str, path: Path) -> None:
    proc = subprocess.run(
        [ffmpeg, "-nostdin", "-v", "error", "-i", str(path), "-map", "0:a:0", "-f", "null", "-"],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=900,
    )
    if proc.returncode:
        error = proc.stderr.decode("utf-8", "replace")[-1200:]
        raise RuntimeError(f"full decode failed: {error}")


def pending(db, mode: str, limit: int):
    target = "valid" if mode == "deep" else "quick_valid"
    if mode == "deep":
        # Deep decoding is phase two; require a successful cheap probe first so
        # quick and deep workers can run in parallel without selecting one file.
        where = "v.status='quick_valid'"
    else:
        where = "COALESCE(v.status,'') NOT IN ('quick_valid','valid')"
    return list(
        db.execute(
            f"""SELECT f.path,f.spotify_id,f.file_size,f.mtime_ns
                FROM audio_files f LEFT JOIN audio_verification v USING(path)
                WHERE f.scan_status='matched' AND {where}
                  AND COALESCE(v.attempts,0)<4
                ORDER BY CASE WHEN v.status='{target}' THEN 1 ELSE 0 END,f.path LIMIT ?""",
            (limit,),
        )
    )


def save(db, row, status: str, metadata: dict | None, error: str | None) -> None:
    metadata = metadata or {}
    now = utcnow()
    with db:
        db.execute(
            """INSERT INTO audio_verification
               (path,status,duration_seconds,codec,bitrate,sample_rate,channels,file_size,mtime_ns,
                sha256,attempts,last_error,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?,NULL,1,?,?)
               ON CONFLICT(path) DO UPDATE SET
                 status=excluded.status,duration_seconds=excluded.duration_seconds,
                 codec=excluded.codec,bitrate=excluded.bitrate,sample_rate=excluded.sample_rate,
                 channels=excluded.channels,file_size=excluded.file_size,mtime_ns=excluded.mtime_ns,
                 attempts=CASE WHEN excluded.status IN ('valid','quick_valid') THEN 0
                               ELSE audio_verification.attempts+1 END,
                 last_error=excluded.last_error,updated_at=excluded.updated_at""",
            (
                row["path"], status, metadata.get("duration"), metadata.get("codec"),
                metadata.get("bitrate"), metadata.get("sample_rate"), metadata.get("channels"),
                row["file_size"], row["mtime_ns"], error, now,
            ),
        )
        if row["spotify_id"]:
            if status == "valid":
                db.execute(
                    """UPDATE acquisition_queue SET local_state='verified',acquisition_state='complete',
                       reason='verified_local_audio',verified_path=?,last_error=NULL,updated_at=?
                       WHERE spotify_id=?""",
                    (row["path"], now, row["spotify_id"]),
                )
            elif status == "invalid":
                db.execute(
                    """UPDATE acquisition_queue SET local_state='invalid',acquisition_state='needs_source',
                       reason='local_audio_invalid',last_error=?,updated_at=? WHERE spotify_id=?""",
                    (error, now, row["spotify_id"]),
                )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("quick", "deep"), default="quick")
    parser.add_argument("--limit", type=int, default=250)
    args = parser.parse_args()
    ffprobe, ffmpeg = media_tools()
    db = connect()
    rows = pending(db, args.mode, args.limit)
    succeeded = failed = 0
    for index, row in enumerate(rows, 1):
        path = Path(row["path"])
        try:
            stat = path.stat()
            if stat.st_size != row["file_size"] or stat.st_mtime_ns != row["mtime_ns"]:
                raise RuntimeError("file changed since indexing; rescan required")
            metadata = probe(ffprobe, path)
            if args.mode == "deep":
                deep_decode(ffmpeg, path)
            save(db, row, "valid" if args.mode == "deep" else "quick_valid", metadata, None)
            succeeded += 1
        except Exception as exc:
            save(db, row, "invalid", None, str(exc)[:1200])
            failed += 1
        if index % 25 == 0:
            print(f"verify {args.mode}: {index}/{len(rows)} ok={succeeded} failed={failed}", flush=True)
    record_source_run(db, f"local-audio:verify-{args.mode}-v1", utcnow(), succeeded,
                      json.dumps({"selected": len(rows), "failed": failed}))
    print(f"verify {args.mode}: selected={len(rows)} valid={succeeded} invalid={failed}")


if __name__ == "__main__":
    main()
