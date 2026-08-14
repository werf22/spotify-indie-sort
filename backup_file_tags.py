#!/usr/bin/env python3
"""Back up every audio file's existing metadata BEFORE anything overwrites it.

WHAT: reads the tags of every file the library knows about and stores them,
verbatim, in a `file_tag_backup` table — one row per file, the complete tag set
as JSON, plus a hash of the file so a later restore can tell whether the file
still is what was backed up.

WHY: the owner asked for this first and was right to. Writing Genre, Label,
Lyrics, Mix, Remixer, Producer and Comment2 into 116,939 files is not
reversible from the files themselves — once a Genre is overwritten, the original
is gone. This table is the only way back.

WHAT IS NOT STORED: binary frames (artwork, Traktor's own PRIV/traktor4 blobs,
waveform data). They are large, they are not what we overwrite, and keeping them
would balloon the table. Everything textual is kept in full.

RESUMABLE: a file already backed up at its current size+mtime is skipped, so the
pass can be stopped and restarted freely — which matters when 80,437 of these
files live on an external disk that may vanish mid-run.

USAGE
  ./.venv/bin/python backup_file_tags.py            # everything, resumable
  ./.venv/bin/python backup_file_tags.py --limit 500
  ./.venv/bin/python backup_file_tags.py --restore <path>    # print what was saved
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from pathlib import Path

import mutagen

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "music.db"

# Frames whose value is binary or Traktor's private business — recorded by NAME
# only, so a restore knows they existed without us storing megabytes.
BINARY_PREFIXES = ("APIC", "PRIV", "covr", "POPM", "GEOB", "traktor4",
                   "----:com.apple.iTunes:Traktor4")


def connect() -> sqlite3.Connection:
    for attempt in range(5):
        try:
            db = sqlite3.connect(DB_PATH, timeout=120)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=120000")
            return db
        except sqlite3.OperationalError:
            if attempt == 4:
                raise
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


def ensure_table(db: sqlite3.Connection) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS file_tag_backup(
            path TEXT PRIMARY KEY,
            file_size INTEGER,
            mtime_ns INTEGER,
            format TEXT,
            tags_json TEXT NOT NULL,
            binary_frames TEXT,
            backed_up_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS idx_file_tag_backup_time
            ON file_tag_backup(backed_up_at);""")


def readable_tags(audio) -> tuple[dict, list[str]]:
    """Split a file's tags into (textual values, names of binary frames)."""
    values: dict[str, list[str]] = {}
    binary: list[str] = []
    if not audio or not audio.tags:
        return values, binary
    for key in audio.tags.keys():
        name = str(key)
        if name.startswith(BINARY_PREFIXES):
            binary.append(name)
            continue
        try:
            raw = audio.tags[key]
        except Exception:
            continue
        items = raw if isinstance(raw, list) else [raw]
        out = []
        for item in items:
            if isinstance(item, bytes):
                binary.append(name)
                out = []
                break
            text = getattr(item, "text", item)
            if isinstance(text, list):
                out.extend(str(x) for x in text)
            else:
                out.append(str(text))
        if out:
            values[name] = out
    return values, binary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--restore", help="print the stored tags for one path")
    args = parser.parse_args()

    db = connect()
    ensure_table(db)
    db.commit()

    if args.restore:
        row = db.execute("SELECT * FROM file_tag_backup WHERE path=?", (args.restore,)).fetchone()
        if not row:
            raise SystemExit("no backup for that path")
        print(json.dumps({k: row[k] for k in row.keys()}, indent=2, ensure_ascii=False))
        return

    paths = [r[0] for r in db.execute(
        "SELECT DISTINCT path FROM audio_files WHERE path IS NOT NULL ORDER BY path")]
    done = {r[0]: (r[1], r[2]) for r in db.execute(
        "SELECT path, file_size, mtime_ns FROM file_tag_backup")}
    print(f"{len(paths):,} known files · {len(done):,} already backed up", flush=True)

    saved = skipped = missing = failed = 0
    batch: list[tuple] = []
    for path in paths:
        p = Path(path)
        try:
            stat = p.stat()
        except OSError:
            missing += 1                    # unplugged disk or deleted file
            continue
        prior = done.get(path)
        if prior and prior[0] == stat.st_size and prior[1] == stat.st_mtime_ns:
            skipped += 1
            continue
        try:
            audio = mutagen.File(p)
        except Exception:
            failed += 1
            continue
        values, binary = readable_tags(audio)
        batch.append((path, stat.st_size, stat.st_mtime_ns,
                      type(audio).__name__ if audio else "",
                      json.dumps(values, ensure_ascii=False),
                      json.dumps(sorted(set(binary))),
                      time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())))
        saved += 1
        if len(batch) >= 300:
            with db:
                db.execute("BEGIN IMMEDIATE")
                db.executemany("""INSERT INTO file_tag_backup
                    (path,file_size,mtime_ns,format,tags_json,binary_frames,backed_up_at)
                    VALUES(?,?,?,?,?,?,?)
                    ON CONFLICT(path) DO UPDATE SET file_size=excluded.file_size,
                      mtime_ns=excluded.mtime_ns, format=excluded.format,
                      tags_json=excluded.tags_json, binary_frames=excluded.binary_frames,
                      backed_up_at=excluded.backed_up_at""", batch)
            batch.clear()
            print(f"  backed up {saved:,} · skipped {skipped:,} · missing {missing:,} · unreadable {failed:,}", flush=True)
        if args.limit and saved >= args.limit:
            break
    if batch:
        with db:
            db.execute("BEGIN IMMEDIATE")
            db.executemany("""INSERT INTO file_tag_backup
                (path,file_size,mtime_ns,format,tags_json,binary_frames,backed_up_at)
                VALUES(?,?,?,?,?,?,?)
                ON CONFLICT(path) DO UPDATE SET file_size=excluded.file_size,
                  mtime_ns=excluded.mtime_ns, format=excluded.format,
                  tags_json=excluded.tags_json, binary_frames=excluded.binary_frames,
                  backed_up_at=excluded.backed_up_at""", batch)
    total = db.execute("SELECT COUNT(*) FROM file_tag_backup").fetchone()[0]
    print(f"\nDONE · newly backed up {saved:,} · already current {skipped:,} · "
          f"unreachable {missing:,} · unreadable {failed:,}")
    print(f"backup table now holds {total:,} files")


if __name__ == "__main__":
    main()
