"""Fill in the true duration of local files whose tags could not be read.

WHY: index_audio_files reads duration with mutagen. When a file's tags are
damaged or unusual mutagen returns nothing and the row keeps duration 0 - which
is exactly the population that never got matched. Two later steps then refuse to
touch those rows: promote_unmatched_local_tracks skips unknown-duration files
rather than guessing them into scope, and any name match has nothing to verify
against. So a file with an unreadable tag was stuck forever.

ffprobe reads the duration from the stream itself and does not care about tags.

INPUTS : data/music.db (audio_files), ffprobe on PATH
OUTPUTS: audio_files.duration_seconds filled in for rows that had none

TWEAK: --limit caps how many files are probed in one run; the script is
idempotent, so running it again simply continues.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "music.db"


def connect() -> sqlite3.Connection:
    last = None
    for _ in range(10):
        try:
            db = sqlite3.connect(DB, timeout=60)
            db.execute("PRAGMA busy_timeout=60000")
            db.execute("select 1")
            return db
        except sqlite3.OperationalError as exc:
            last = exc
            time.sleep(10)
    raise SystemExit(f"nepodarilo sa otvoriť databázu: {last}")


def probe_seconds(path: str) -> float | None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
            capture_output=True, text=True, timeout=60)
        return float(json.loads(out.stdout)["format"]["duration"])
    except Exception:
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=100000)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db = connect()
    rows = db.execute(
        """select path from audio_files
           where scan_status='unmatched'
             and (duration_seconds is null or duration_seconds<=0)
           limit ?""", (args.limit,)).fetchall()
    print(f"súborov bez dĺžky: {len(rows):,}")

    found, failed = [], 0
    for i, (path,) in enumerate(rows, 1):
        seconds = probe_seconds(path)
        if seconds and seconds > 0:
            found.append((seconds, path))
        else:
            failed += 1
        if i % 200 == 0:
            print(f"  prečítaných {i:,}/{len(rows):,}", flush=True)

    print(f"dĺžka zistená:  {len(found):,}")
    print(f"nečitateľných:  {failed:,}")
    if found:
        short = sum(1 for s, _ in found if s <= 900)
        print(f"  z toho <=900 s (pôjdu do pipeline): {short:,}")

    if not args.apply:
        print("\nSKÚŠOBNÝ BEH — nič sa nezapísalo. Spusti s --apply.")
        return

    db.execute("BEGIN IMMEDIATE")
    for seconds, path in found:
        db.execute("update audio_files set duration_seconds=? where path=?", (seconds, path))
    db.commit()
    print(f"\nzapísaná dĺžka pre {len(found):,} súborov")


if __name__ == "__main__":
    main()
