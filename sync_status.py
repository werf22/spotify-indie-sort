#!/usr/bin/env python3
"""One cheap status snapshot for CLI and the macOS menu-bar app."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from musicdb import connect


ROOT = Path(__file__).resolve().parent


def scalar(db, sql: str, params=()):
    row = db.execute(sql, params).fetchone()
    return row[0] if row else 0


def grouped(db, sql: str) -> dict[str, int]:
    return {str(row[0]): int(row[1]) for row in db.execute(sql)}


def launch_agent_running() -> bool:
    result = subprocess.run(
        ["launchctl", "print", f"gui/{__import__('os').getuid()}/com.jakub.local-dj-enrichment"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def snapshot() -> dict:
    db = connect()
    control = db.execute("SELECT * FROM sync_control WHERE id=1").fetchone()
    output_root = Path(control["output_root"] or ROOT).expanduser()
    probe_root = output_root if output_root.exists() else Path.home()
    disk = shutil.disk_usage(probe_root)
    queue = grouped(db, "SELECT acquisition_state,count(*) FROM acquisition_queue GROUP BY acquisition_state")
    verification = grouped(db, "SELECT status,count(*) FROM audio_verification GROUP BY status")
    total = int(scalar(db, "SELECT count(*) FROM tracks"))
    avg_ms = float(scalar(db, "SELECT COALESCE(avg(duration_ms),284400) FROM tracks WHERE duration_ms IS NOT NULL"))
    still_needed = queue.get("needs_source", 0) + queue.get("locate_existing", 0)
    remaining_gib = still_needed * avg_ms / 1000 * 320000 / 8 / (1024**3)
    local_tracks = int(scalar(db, "SELECT count(DISTINCT spotify_id) FROM audio_files WHERE spotify_id IS NOT NULL AND scan_status='matched'"))
    rhythm = int(scalar(db, "SELECT count(DISTINCT spotify_id) FROM local_audio_analysis WHERE analyzer_version='rhythm-v1.0.5'"))
    maest = int(scalar(db, "SELECT count(DISTINCT spotify_id) FROM audio_embeddings WHERE model LIKE '%maest%'"))
    clap = int(scalar(db, "SELECT count(DISTINCT spotify_id) FROM audio_embeddings WHERE model LIKE '%clap%'"))
    freqblog = int(scalar(db, "SELECT count(*) FROM freqblog_status WHERE status='success'"))
    exported = int(scalar(db, "SELECT count(*) FROM spotify_export_items WHERE purpose='local-blindspots-2026-07-18'"))
    return {
        "tracks_total": total,
        "local_tracks_matched": local_tracks,
        "local_tracks_deep_verified": verification.get("valid", 0),
        "local_tracks_quick_verified": verification.get("quick_valid", 0),
        "queue": queue,
        "verification": verification,
        "rhythm": rhythm,
        "maest": maest,
        "clap": clap,
        "freqblog_success": freqblog,
        "blindspot_exported": exported,
        "free_gib": round(disk.free / (1024**3), 1),
        "min_free_gib": float(control["min_free_gib"]),
        "estimated_remaining_audio_gib": round(remaining_gib, 1),
        "output_root": str(output_root),
        "acquisition_paused": bool(control["paused"]),
        "pause_reason": control["pause_reason"],
        "daemon_running": launch_agent_running(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    data = snapshot()
    if args.json:
        print(json.dumps(data, ensure_ascii=False, sort_keys=True))
    else:
        print(f"Library: {data['tracks_total']:,}")
        print(f"Local matched: {data['local_tracks_matched']:,}; deep verified: {data['local_tracks_deep_verified']:,}")
        print(f"Queue: {data['queue']}")
        print(f"Rhythm/MAEST/CLAP: {data['rhythm']:,}/{data['maest']:,}/{data['clap']:,}")
        print(f"FreqBlog: {data['freqblog_success']:,}; blindspots exported: {data['blindspot_exported']:,}")
        print(f"Disk free: {data['free_gib']:.1f} GiB (stop threshold {data['min_free_gib']:.1f} GiB)")
        print(f"Daemon: {'running' if data['daemon_running'] else 'stopped'}")


if __name__ == "__main__":
    main()
