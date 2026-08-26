#!/usr/bin/env python3
"""Read the Traktor "Comment" out of every audio file into the database.

WHY: the owner stores his energy rating there — "06 Energy" — and it is the one
piece of his own judgement in the whole library. It lived only inside the files,
so the app could neither show it, sort by it, nor filter on it.

WHAT IT DOES: reads the comment frame from each file and writes it to
`track_comment`, together with the energy number parsed out of it. It NEVER
writes to a file; normalising the format is `normalise_comments.py`, separately,
so a read can never damage anything.

RESUMABLE: files already recorded with an unchanged mtime are skipped, so it can
be stopped and restarted at any point. Run it detached for a full library:

    screen -dmS comments ./.venv/bin/python scan_comments.py

HOW TO TWEAK: COMMENT_KEYS lists the tag names that count as a comment in the
formats this library uses.
"""
from __future__ import annotations

import re
import sqlite3
import sys
import time
from pathlib import Path

from mutagen import File as MutagenFile

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "music.db"

# MP3 uses COMM (with a language/description suffix), MP4/M4A uses ©cmt,
# FLAC/OGG use a plain "comment" field.
COMMENT_KEYS = ("comm", "©cmt", "comment", "description")

# "06 Energy" is the form the owner wants; "Energy 6" is the same thing written
# the other way round and is what needs normalising later.
ENERGY_RE = re.compile(r"^\s*(?:(\d{1,2})\s*energy|energy\s*(\d{1,2}))\s*$", re.I)


def energy_of(comment: str | None) -> int | None:
    """The energy number, whichever way round it was written."""
    if not comment:
        return None
    m = ENERGY_RE.match(comment)
    if not m:
        return None
    return int(m.group(1) or m.group(2))


def read_comment(path: str) -> str | None:
    try:
        audio = MutagenFile(path)
    except Exception:
        return None
    if not audio:
        return None
    for key in audio.keys():
        low = str(key).lower()
        if not low.startswith(COMMENT_KEYS):
            continue
        # iTunes writes technical data into comment frames too; those are not
        # the owner's note and must never be mistaken for it.
        if any(t in low for t in ("itunnorm", "itunsmpb", "itunes_cddb",
                                  "itunmovi", "itunpgap")):
            continue
        value = audio[key]
        if isinstance(value, list):
            value = value[0] if value else None
        text = str(value).strip() if value is not None else ""
        if text:
            return text
    return None


def main() -> None:
    db = sqlite3.connect(DB, timeout=120)
    db.execute("""CREATE TABLE IF NOT EXISTS track_comment (
                      path       TEXT PRIMARY KEY,
                      spotify_id TEXT,
                      comment    TEXT,
                      energy     INTEGER,
                      mtime_ns   INTEGER,
                      scanned_at TEXT DEFAULT (datetime('now')))""")
    db.execute("CREATE INDEX IF NOT EXISTS track_comment_sid ON track_comment(spotify_id)")
    db.commit()

    rows = db.execute("""SELECT path, spotify_id, mtime_ns FROM audio_files
                         WHERE scan_status='matched' AND path IS NOT NULL""").fetchall()
    known = {p: m for p, m in db.execute("SELECT path, mtime_ns FROM track_comment")}
    todo = [r for r in rows if known.get(r[0]) != r[2]]
    print(f"{len(rows):,} súborov · {len(todo):,} na prečítanie", flush=True)

    batch, done, found, missing = [], 0, 0, 0
    started = time.time()
    for path, sid, mtime in todo:
        if not Path(path).exists():
            missing += 1
            continue
        comment = read_comment(path)
        batch.append((path, sid, comment, energy_of(comment), mtime))
        if comment:
            found += 1
        done += 1
        if len(batch) >= 500:
            db.executemany("""INSERT INTO track_comment
                                  (path, spotify_id, comment, energy, mtime_ns)
                              VALUES (?,?,?,?,?)
                              ON CONFLICT(path) DO UPDATE SET
                                  spotify_id=excluded.spotify_id,
                                  comment=excluded.comment, energy=excluded.energy,
                                  mtime_ns=excluded.mtime_ns,
                                  scanned_at=datetime('now')""", batch)
            db.commit()
            batch.clear()
            rate = done / max(1e-9, time.time() - started)
            print(f"   {done:,}/{len(todo):,} · s komentárom {found:,} · "
                  f"{rate:.0f}/s", flush=True)
    if batch:
        db.executemany("""INSERT INTO track_comment
                              (path, spotify_id, comment, energy, mtime_ns)
                          VALUES (?,?,?,?,?)
                          ON CONFLICT(path) DO UPDATE SET
                              spotify_id=excluded.spotify_id,
                              comment=excluded.comment, energy=excluded.energy,
                              mtime_ns=excluded.mtime_ns,
                              scanned_at=datetime('now')""", batch)
        db.commit()

    total = db.execute("SELECT COUNT(*) FROM track_comment WHERE comment IS NOT NULL").fetchone()[0]
    with_energy = db.execute("SELECT COUNT(*) FROM track_comment WHERE energy IS NOT NULL").fetchone()[0]
    print(f"hotovo · prečítaných {done:,} · chýbajúcich súborov {missing:,}")
    print(f"v databáze: {total:,} s komentárom, z toho {with_energy:,} s energiou")
    db.close()


if __name__ == "__main__":
    sys.exit(main())
