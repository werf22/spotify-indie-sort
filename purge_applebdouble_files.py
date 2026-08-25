"""Remove macOS AppleDouble sidecars from the audio file index.

WHAT: copying music onto an exFAT disk (the T7) makes macOS write a companion
"._name.mp3" file next to every real "name.mp3". It holds Finder metadata, not
audio - typically 4 KB starting with the AppleDouble magic 0x00051607. The
scanner treated them as audio, so 58k of them sat in audio_files, and 1.2k were
even matched to tracks, meaning those tracks pointed at a 4 KB stub instead of
the music.

WHY BY CONTENT, NOT BY NAME: a handful of real files legitimately start with
"._", so deleting on the filename pattern would throw away real audio. Every
candidate is opened and judged by its first four bytes instead.

INPUTS : data/music.db (audio_files)
OUTPUTS: rows deleted from audio_files; a backup table audio_files_backup_<ts>
         holding every row this removes, so the change is reversible with one
         INSERT ... SELECT.

TWEAK: --apply performs the deletion; without it nothing is written.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "music.db"
APPLEDOUBLE = b"\x00\x05\x16\x07"


def connect() -> sqlite3.Connection:
    """Open the DB, waiting out the analysis importer if it holds the lock."""
    last = None
    for _ in range(10):
        try:
            db = sqlite3.connect(DB, timeout=60)
            db.execute("PRAGMA busy_timeout=60000")
            db.execute("select 1")
            return db
        except sqlite3.OperationalError as exc:      # importer mid-write
            last = exc
            time.sleep(10)
    raise SystemExit(f"nepodarilo sa otvoriť databázu: {last}")


def classify(path: str) -> str:
    """appledouble | audio | missing — decided by the file's first bytes."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(4)
    except FileNotFoundError:
        return "missing"
    except OSError:
        return "unreadable"
    return "appledouble" if head.startswith(APPLEDOUBLE) else "audio"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="actually delete (default: report only)")
    args = ap.parse_args()

    db = connect()
    rows = db.execute(
        "select path, spotify_id, scan_status from audio_files where path like '%/._%'"
    ).fetchall()
    print(f"kandidátov s názvom ._*: {len(rows):,}")

    buckets: dict[str, list] = {}
    for i, (path, sid, status) in enumerate(rows, 1):
        buckets.setdefault(classify(path), []).append((path, sid, status))
        if i % 10000 == 0:
            print(f"  overených {i:,}/{len(rows):,}", flush=True)

    for kind, items in sorted(buckets.items()):
        matched = sum(1 for _, sid, st in items if st == "matched")
        print(f"  {kind:<12} {len(items):>7,}   (z toho spárovaných {matched:,})")

    doomed = buckets.get("appledouble", []) + buckets.get("missing", [])
    if not doomed:
        print("nič na odstránenie.")
        return

    # Which tracks would be left with no file at all? They must be reported
    # BEFORE the delete, never discovered afterwards.
    sids = sorted({sid for _, sid, st in doomed if sid and st == "matched"})
    orphaned = []
    if sids:
        marks = ",".join("?" * len(sids))
        keeps = {r[0] for r in db.execute(
            f"""select distinct spotify_id from audio_files
                where spotify_id in ({marks}) and scan_status='matched'
                  and path not like '%/._%'""", sids)}
        orphaned = [s for s in sids if s not in keeps]
    print(f"\ntrackov, ktoré prídu o jediný súbor: {len(orphaned):,}")

    if not args.apply:
        print("\nSKÚŠOBNÝ BEH — nič sa nezmazalo. Spusti s --apply.")
        return

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    table = f"audio_files_backup_{stamp}"
    # BEGIN IMMEDIATE: this transaction reads and then writes while the analysis
    # importer is also writing; a deferred transaction upgrading its lock gets
    # SQLITE_BUSY_SNAPSHOT immediately and busy_timeout does not retry it.
    db.execute("BEGIN IMMEDIATE")
    db.execute(f"CREATE TABLE {table} AS SELECT * FROM audio_files WHERE 0")
    paths = [p for p, _, _ in doomed]
    for i in range(0, len(paths), 500):
        chunk = paths[i:i + 500]
        marks = ",".join("?" * len(chunk))
        db.execute(f"INSERT INTO {table} SELECT * FROM audio_files WHERE path IN ({marks})", chunk)
        db.execute(f"DELETE FROM audio_files WHERE path IN ({marks})", chunk)
    db.commit()
    print(f"\nodstránených {len(paths):,} riadkov; záloha v tabuľke {table}")
    print(f"vrátiť späť: INSERT INTO audio_files SELECT * FROM {table};")


if __name__ == "__main__":
    main()
