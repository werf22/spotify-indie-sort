#!/usr/bin/env python3
"""Continuously prepare and run bounded full-audio GPU shards."""

from __future__ import annotations

import csv
import fcntl
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from musicdb import connect
from runpod_full_shard import required_pairs, successful


ROOT = Path(__file__).resolve().parent
SHARDS = ROOT / "data" / "cloud_full_shards"
MANIFEST = ROOT / "data" / "cloud_full" / "manifest.csv"
STATUS = SHARDS / "orchestrator_status.json"
LOCK = SHARDS / "orchestrator.lock"
RUNPODCTL = Path.home() / ".local" / "bin" / "runpodctl"
# Immutable target selected by the currently running full-track preparation pass.
# Raise this when a later inventory pass deliberately appends more matched files.
EXPECTED = 5394
SHARD_SIZE = 100
MIN_BALANCE = 1.0


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_status(**values) -> None:
    SHARDS.mkdir(parents=True, exist_ok=True)
    current = {}
    try:
        current = json.loads(STATUS.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    current.update(values)
    current["updated_at"] = utcnow()
    temporary = STATUS.with_suffix(".partial.json")
    temporary.write_text(json.dumps(current, ensure_ascii=False, indent=2,
                                    sort_keys=True), encoding="utf-8")
    temporary.replace(STATUS)


def balance() -> tuple[float, float]:
    proc = subprocess.run([str(RUNPODCTL), "user"], cwd=ROOT,
                          capture_output=True, text=True, timeout=60)
    if proc.returncode:
        raise RuntimeError((proc.stderr or proc.stdout)[-1000:])
    data = json.loads(proc.stdout)
    return float(data.get("clientBalance") or 0), float(data.get("currentSpendPerHr") or 0)


def ready_count() -> int:
    if not MANIFEST.is_file():
        return 0
    with MANIFEST.open(encoding="utf-8", newline="") as handle:
        return sum(1 for _ in csv.DictReader(handle))


def completed_count() -> int:
    with connect() as db:
        return int(db.execute(
            """SELECT COUNT(*) FROM (
                 SELECT spotify_id FROM audio_analysis_artifacts
                 WHERE stage IN ('rhythm_full','maest_full','essentia_full','clap_full')
                 GROUP BY spotify_id HAVING COUNT(DISTINCT stage)=4
               )"""
        ).fetchone()[0])


def incomplete_shard() -> Path | None:
    for shard in sorted(SHARDS.glob("shard-*")):
        manifest = shard / "manifest.csv"
        if not manifest.is_file() or not (shard / "bundle.tar").is_file():
            continue
        if not required_pairs(manifest) <= successful(shard / "results.jsonl"):
            return shard
    return None


def build(minimum: int) -> Path | None:
    proc = subprocess.run([
        str(ROOT / ".venv" / "bin" / "python"), str(ROOT / "build_cloud_full_shard.py"),
        "--size", str(SHARD_SIZE), "--minimum", str(minimum),
    ], cwd=ROOT, capture_output=True, text=True, timeout=1800)
    if proc.returncode:
        raise RuntimeError((proc.stderr or proc.stdout)[-1500:])
    payload = json.loads(proc.stdout.strip().splitlines()[-1])
    return Path(payload["shard"]) if payload.get("status") == "ready" else None


def run_shard(shard: Path) -> None:
    proc = subprocess.run([
        str(ROOT / ".venv" / "bin" / "python"), str(ROOT / "runpod_full_shard.py"),
        "--shard", str(shard),
    ], cwd=ROOT, timeout=4 * 60 * 60)
    if proc.returncode:
        raise RuntimeError(f"Shard runner exited {proc.returncode}: {shard}")


def main() -> None:
    SHARDS.mkdir(parents=True, exist_ok=True)
    with LOCK.open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        failures = 0
        while True:
            try:
                done, ready = completed_count(), ready_count()
                funds, hourly = balance()
                if done >= EXPECTED:
                    write_status(phase="complete", completed_tracks=done,
                                 ready_tracks=ready, balance_usd=funds, hourly_usd=hourly)
                    return
                if funds < MIN_BALANCE:
                    write_status(phase="waiting_for_user_credit", completed_tracks=done,
                                 ready_tracks=ready, balance_usd=funds, hourly_usd=hourly,
                                 note="No automatic funding; user action required.")
                    time.sleep(600)
                    continue
                if hourly > 0.40:
                    write_status(phase="unexpected_existing_spend", hourly_usd=hourly,
                                 balance_usd=funds)
                    time.sleep(300)
                    continue
                shard = incomplete_shard()
                if shard is None:
                    minimum = 1 if ready >= EXPECTED else SHARD_SIZE
                    shard = build(minimum)
                if shard is None:
                    write_status(phase="waiting_for_full_tracks", completed_tracks=done,
                                 ready_tracks=ready, balance_usd=funds, hourly_usd=hourly)
                    time.sleep(60)
                    continue
                write_status(phase="running_shard", shard=str(shard),
                             completed_tracks=done, ready_tracks=ready,
                             balance_usd=funds, hourly_usd=hourly,
                             consecutive_failures=0, last_error=None)
                run_shard(shard)
                failures = 0
            except Exception as exc:
                failures += 1
                write_status(phase="retrying", consecutive_failures=failures,
                             last_error=repr(exc)[-2000:])
                time.sleep(min(60 * failures, 600))


if __name__ == "__main__":
    main()
