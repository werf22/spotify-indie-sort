#!/usr/bin/env python3
"""Rewrite every "Energy 7" comment in the audio files as "07 Energy".

WHY: the owner's energy rating is written two ways across the library — the
wanted "07 Energy" and the older "Energy 7". They mean the same thing, but a
column sorted by the NUMBER then looks random, because the eye reads the text.
One spelling everywhere fixes the look and makes Traktor's own sorting useful.

WHAT IT TOUCHES: only files whose ENTIRE comment is an energy rating. Anything
else — catalogue numbers, "PMEDIA", a real note — is never touched. The old
value of every frame is written to `comment_pin_backup` BEFORE the write, so a
restore is exact (`traktor_comment_pin.py restore`).

RESUMABLE + SAFE TO RE-RUN: files already in the wanted form are skipped, and
the file's CURRENT comment is re-read before writing, so a stale database row
can never cause a wrong rewrite. Run it detached for the whole library:

    screen -dmS normalise ./.venv/bin/python normalise_comments.py

    --dry-run   show what would change, write nothing
    --limit N   stop after N files (used for the verified test batch)

HOW TO TWEAK: WANT_FORM is the spelling produced; ENERGY_RE decides what counts
as an energy comment at all. Widening ENERGY_RE means touching more files —
change it only with a dry-run first.
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
import time
from pathlib import Path

import mutagen

import traktor_comment_pin as pin
from scan_comments import read_comment

ROOT = Path(__file__).resolve().parent
DB = ROOT / "data" / "music.db"

# The wanted spelling. "07 Energy" — two digits, space, the word.
WANT_FORM = "{n:02d} Energy"
# What counts as an energy comment: the WHOLE comment, nothing else in it.
ENERGY_RE = re.compile(r"^\s*(?:(\d{1,2})\s*energy|energy\s*(\d{1,2}))\s*$", re.I)


def energy_of(comment: str | None) -> int | None:
    if not comment:
        return None
    m = ENERGY_RE.match(comment)
    return int(m.group(1) or m.group(2)) if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    db = sqlite3.connect(DB, timeout=120)
    pin.ensure_tables(db)

    todo = db.execute("""SELECT path, spotify_id, comment, energy FROM track_comment
                         WHERE energy IS NOT NULL
                           AND comment NOT GLOB '[0-9][0-9] Energy'
                         ORDER BY path""").fetchall()
    if args.limit:
        todo = todo[:args.limit]
    print(f"{len(todo):,} súborov na prepis"
          + (" (NASUCHO — nič sa nezapíše)" if args.dry_run else ""), flush=True)

    stamp = time.strftime("%Y-%m-%dT%H:%M:%S")
    done = skipped = failed = 0
    changed_examples: list[str] = []
    started = time.time()

    for path_s, sid, db_comment, db_energy in todo:
        path = Path(path_s)
        if not path.exists():
            skipped += 1
            continue

        # NEVER trust the database row alone. The file may have been edited in
        # Traktor since the scan; rewriting from a stale row would overwrite a
        # real change with an old value.
        current = read_comment(path_s)
        n = energy_of(current)
        if n is None:
            skipped += 1
            continue
        want = WANT_FORM.format(n=n)
        if current == want:
            skipped += 1
            continue

        if args.dry_run:
            if len(changed_examples) < 15:
                changed_examples.append(f"{current!r} -> {want!r}   {path.name}")
            done += 1
            continue

        status = pin.write_comment(path, want, db, stamp)
        if status not in ("done", "no_change"):
            failed += 1
            print(f"   ZLYHALO {status}: {path}", flush=True)
            continue

        # VERIFY the write instead of trusting the return value: re-read the
        # file and refuse to record success unless the wanted text is there.
        after = read_comment(path_s)
        if after != want:
            failed += 1
            print(f"   NEOVERENÉ (v súbore ostalo {after!r}): {path}", flush=True)
            continue

        try:
            mtime = path.stat().st_mtime_ns
        except OSError:
            mtime = None
        db.execute("""UPDATE track_comment
                      SET comment=?, energy=?, mtime_ns=?, scanned_at=datetime('now')
                      WHERE path=?""", (want, n, mtime, path_s))
        done += 1
        if len(changed_examples) < 15:
            changed_examples.append(f"{current!r} -> {want!r}   {path.name}")
        if done % 200 == 0:
            db.commit()
            rate = done / max(1e-9, time.time() - started)
            print(f"   {done:,}/{len(todo):,} · {rate:.0f}/s", flush=True)

    db.commit()

    print(f"\nprepísaných {done:,} · preskočených {skipped:,} · zlyhalo {failed:,}")
    if changed_examples:
        print("ukážka:")
        for line in changed_examples:
            print("   " + line)
    if not args.dry_run:
        left = db.execute("""SELECT COUNT(*) FROM track_comment
                             WHERE energy IS NOT NULL
                               AND comment NOT GLOB '[0-9][0-9] Energy'""").fetchone()[0]
        print(f"v databáze ostáva v starom tvare: {left:,}")
    db.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
