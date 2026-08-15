#!/usr/bin/env python3
"""Keep the owner's own energy tag in Traktor's "Comment" column — permanently.

THE PROBLEM
The owner labels every track's energy in Comment ("06 Energy"). That label lives
in collection.nml. But most of these files ALSO carry a musical key ("Em", "F#m")
inside their own comment tag, written years ago by some other tagger. Traktor
re-reads a file's tags when the track is loaded, so the file's key overwrites the
collection's energy — one track at a time, every time one is played. It has been
eating the library slowly for months: 603 tracks in June, 1,180 by mid-August.
Measured on a 1,500-track sample, 56.5% of files still hold a key in their
comment tag, so ~50,000 more were primed to flip.

THE FIX, IN TWO PHASES
  --repair    entries whose Comment ALREADY became a key get their original
              energy back, recovered from Traktor's own older collection backups.
  --pin       the collection's Comment is written INTO each file's comment tag,
              so the file and Traktor finally agree and a re-import changes
              nothing. This is what makes it stick.

WHY OVERWRITING THE FILE IS THE RIGHT CALL: the file's key is a duplicate — the
key already lives in the KEY field, where Traktor shows it properly. The energy
label exists nowhere else, so Comment is the only place it can live.

REVERSIBILITY: every comment tag is copied into `comment_pin_backup` before it
is touched, and `--restore` puts each one back exactly (deleting the tag again
where there was none). Progress lives in `comment_pin`, so an interrupted run
resumes instead of restarting.

HOW TO TWEAK: KEY_RE decides what counts as "a musical key, not a real comment" —
widen it only if some other junk value needs recovering too.

USAGE
  ./.venv/bin/python traktor_comment_pin.py --repair          # fix flipped entries
  ./.venv/bin/python traktor_comment_pin.py --pin --limit 20  # cautious first batch
  ./.venv/bin/python traktor_comment_pin.py --pin             # full run (resumable)
  ./.venv/bin/python traktor_comment_pin.py --verify          # re-read from disk
  ./.venv/bin/python traktor_comment_pin.py --restore         # undo the file writes
"""

from __future__ import annotations

import argparse
import glob
import html
import json
import re
import shutil
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path

import mutagen
from mutagen.id3 import ID3, COMM
from mutagen.mp4 import MP4

sys.path.insert(0, str(Path(__file__).resolve().parent))
import traktor_tags as tt

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "music.db"
BACKUP_DIR = ROOT / "data" / "traktor_backups"
TRAKTOR_BACKUPS = Path.home() / "Documents/Native Instruments/Traktor 4.0.2/Backup/Collection"
COMMIT_EVERY = 200

# A bare musical key in Comment is the corruption we undo. Covers both notations
# seen in this library: "Em"/"F#m"/"Bbm" and Traktor's own "4m"/"11d".
KEY_RE = re.compile(r"^(([A-G][#b]?m?)|(\d{1,2}[dmAB]))$", re.IGNORECASE)
ENTRY_RE = re.compile(r"<ENTRY [^>]*>\s*<LOCATION([^>]*)/?>(.*?)</ENTRY>", re.S)


def log(msg: str) -> None:
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def location_path(location_tag: str) -> str:
    """Turn an NML <LOCATION> into a real filesystem path.

    Traktor stores the disk as VOLUME and uses "/:" as its folder separator;
    the boot disk has no /Volumes prefix.
    """
    get = lambda n: html.unescape((re.search(rf'{n}="([^"]*)"', location_tag) or [None, ""])[1])
    volume, directory, name = get("VOLUME"), get("DIR"), get("FILE")
    root = "" if volume in ("Macintosh HD", "") else f"/Volumes/{volume}"
    return root + directory.replace("/:", "/") + name


def read_collection(path: Path, report: bool = False) -> dict[str, str]:
    """path on disk -> Comment, for every entry that has one.

    25,281 files are referenced by MORE THAN ONE collection entry, and 1,274 of
    those carry different energy labels on different entries. A file holds one
    comment, so a choice is unavoidable: take the value the majority of entries
    agree on, and break a tie deterministically (first alphabetically) so the
    same run always produces the same result instead of depending on file order.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    seen: dict[str, list[str]] = {}
    for match in ENTRY_RE.finditer(text):
        comment = re.search(r'COMMENT="([^"]*)"', match.group(2))
        if comment:
            seen.setdefault(location_path(match.group(1)), []).append(
                html.unescape(comment.group(1)).strip())
    out, ambiguous = {}, 0
    for file_path, values in seen.items():
        if len(set(values)) > 1:
            ambiguous += 1
        counts = Counter(values)
        best = max(counts, key=lambda v: (counts[v], [-ord(c) for c in v]))
        out[file_path] = best
    if report and ambiguous:
        log(f"note: {ambiguous:,} files had duplicate entries disagreeing on the "
            f"label; kept the majority value for each")
    return out


def ensure_tables(db: sqlite3.Connection) -> None:
    db.execute("""CREATE TABLE IF NOT EXISTS comment_pin (
                    path TEXT PRIMARY KEY, status TEXT, detail TEXT, ts TEXT)""")
    db.execute("""CREATE TABLE IF NOT EXISTS comment_pin_backup (
                    path TEXT, frame TEXT, value_json TEXT, ts TEXT,
                    PRIMARY KEY (path, frame))""")
    db.commit()


# --------------------------------------------------------------- phase 1
def repair(db: sqlite3.Connection) -> None:
    """Give back the energy label to entries whose Comment already became a key.

    The originals come from Traktor's OWN rolling backups: the corruption spread
    gradually, so an older backup still holds the real value for most of them.
    """
    if tt.traktor_running():
        log("REFUSING: Traktor is running — it would overwrite this on quit.")
        return
    live = tt.NML
    current = read_collection(live)
    broken = {p: c for p, c in current.items() if KEY_RE.match(c)}
    log(f"entries whose Comment is a musical key: {len(broken):,}")
    if not broken:
        return

    recovered: dict[str, str] = {}
    for backup in sorted(TRAKTOR_BACKUPS.glob("*.nml")):      # oldest first
        if not broken:
            break
        old = read_collection(backup)
        for path in list(broken):
            value = old.get(path)
            if value and not KEY_RE.match(value):
                recovered[path] = value
                del broken[path]
    log(f"recovered {len(recovered):,} originals from Traktor's own backups; "
        f"{len(broken):,} have no pre-corruption value anywhere")

    if not recovered:
        return
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    safety = BACKUP_DIR / f"collection.before-comment-repair.{stamp}.nml"
    shutil.copy2(live, safety)
    log(f"backup: {safety.name}")

    text = live.read_text(encoding="utf-8", errors="replace")
    fixed = 0

    def swap(match: re.Match) -> str:
        nonlocal fixed
        path = location_path(match.group(1))
        want = recovered.get(path)
        if not want:
            return match.group(0)
        body, n = re.subn(r'COMMENT="[^"]*"',
                          'COMMENT="%s"' % html.escape(want, quote=True),
                          match.group(2), count=1)
        # Count only entries whose text ACTUALLY changed. Counting successful
        # regex matches instead reported 1,046 repairs for 577 real ones — a log
        # that overstates the work is a log nobody can trust.
        if n and body != match.group(2):
            fixed += 1
            return match.group(0).replace(match.group(2), body)
        return match.group(0)

    text = ENTRY_RE.sub(swap, text)
    tmp = live.with_suffix(".nml.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(live)
    log(f"repaired {fixed:,} Comment values in the collection")


# --------------------------------------------------------------- phase 2
def comment_frames(handle) -> list[str]:
    """Names of the comment tags this file actually has."""
    if handle is None or handle.tags is None:
        return []
    out = []
    for key in handle.tags.keys():
        name = str(key)
        if name.startswith("©cmt") or name.lower() == "comment" or (
                name.startswith("COMM") and name.split(":")[1:2] in ([""], [])):
            out.append(name)
    return out


def read_value(handle, frame: str):
    try:
        raw = handle.tags[frame]
    except KeyError:
        return None
    if hasattr(raw, "text"):
        return [str(t) for t in raw.text]
    if isinstance(raw, list):
        return [str(t) for t in raw]
    return [str(raw)]


def write_comment(path: Path, want: str, db: sqlite3.Connection, stamp: str) -> str:
    try:
        handle = mutagen.File(path)
    except Exception as exc:                       # damaged media, unknown codec
        return f"failed:{type(exc).__name__}"
    if handle is None:
        return "unsupported"
    if handle.tags is None:
        try:
            handle.add_tags()
        except Exception as exc:
            return f"failed:{type(exc).__name__}"

    existing = comment_frames(handle)
    if existing and all(read_value(handle, f) == [want] for f in existing):
        return "no_change"

    for frame in existing or []:                   # back up BEFORE touching
        db.execute("""INSERT OR IGNORE INTO comment_pin_backup
                      VALUES (?,?,?,?)""",
                   (str(path), frame, json.dumps(read_value(handle, frame)), stamp))
    if not existing:                               # record "there was nothing"
        db.execute("INSERT OR IGNORE INTO comment_pin_backup VALUES (?,?,?,?)",
                   (str(path), "<none>", json.dumps(None), stamp))

    try:
        if isinstance(handle, MP4):
            handle.tags["©cmt"] = [want]
        elif isinstance(handle.tags, ID3):
            for frame in existing:
                del handle.tags[frame]
            handle.tags.add(COMM(encoding=3, lang="eng", desc="", text=[want]))
        else:                                      # FLAC / OGG (Vorbis comments)
            handle.tags["comment"] = [want]
        handle.save()
    except Exception as exc:
        return f"failed:{type(exc).__name__}"
    return "done"


def pin(db: sqlite3.Connection, limit: int) -> None:
    if tt.traktor_running():
        log("REFUSING: Traktor is running — close it first.")
        return
    wanted = read_collection(tt.NML, report=True)
    wanted = {p: c for p, c in wanted.items() if c and not KEY_RE.match(c)}
    log(f"collection entries carrying a real Comment: {len(wanted):,}")

    done = {r[0] for r in db.execute(
        "SELECT path FROM comment_pin WHERE status IN ('done','no_change','unsupported')")}
    todo = [(p, c) for p, c in wanted.items() if p not in done]
    if limit:
        todo = todo[:limit]
    log(f"to process now: {len(todo):,}")

    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    counts: dict[str, int] = {}
    for index, (path, want) in enumerate(todo, 1):
        target = Path(path)
        try:
            present = target.is_file()
        except OSError:                            # bad sector -> skip, never abort
            present = False
        status = write_comment(target, want, db, stamp) if present else "missing"
        head = status.split(":")[0]
        counts[head] = counts.get(head, 0) + 1
        db.execute("INSERT OR REPLACE INTO comment_pin VALUES (?,?,?,?)",
                   (path, head, status, stamp))
        if index % COMMIT_EVERY == 0:
            db.commit()
            log(f"  {index:,}/{len(todo):,}  {counts}")
    db.commit()
    log(f"finished: {counts}")


def verify(db: sqlite3.Connection, sample: int = 80) -> None:
    wanted = read_collection(tt.NML)
    rows = db.execute("""SELECT path FROM comment_pin WHERE status='done'
                         ORDER BY RANDOM() LIMIT ?""", (sample,)).fetchall()
    ok = bad = skipped = 0
    for (path,) in rows:
        try:
            handle = mutagen.File(Path(path))
        except Exception:
            skipped += 1
            continue
        if handle is None or handle.tags is None:
            skipped += 1
            continue
        frames = comment_frames(handle)
        value = read_value(handle, frames[0]) if frames else None
        if value == [wanted.get(path)]:
            ok += 1
        else:
            bad += 1
            if bad <= 5:
                log(f"  MISMATCH {Path(path).name[:44]}: file={value} want={wanted.get(path)!r}")
    log(f"verified {ok} correct, {bad} wrong, {skipped} unreadable (of {len(rows)} sampled)")
    log("VERDICT: " + ("the energy label is in the files" if bad == 0 else "PROBLEM — see above"))


def restore(db: sqlite3.Connection) -> None:
    rows = db.execute("SELECT path, frame, value_json FROM comment_pin_backup").fetchall()
    log(f"restoring {len(rows):,} saved comment tags")
    restored = 0
    for path, frame, value_json in rows:
        try:
            handle = mutagen.File(Path(path))
            if handle is None or handle.tags is None:
                continue
            values = json.loads(value_json)
            if frame == "<none>" or values is None:
                for existing in comment_frames(handle):
                    del handle.tags[existing]
            elif isinstance(handle, MP4):
                handle.tags["©cmt"] = values
            elif isinstance(handle.tags, ID3):
                for existing in comment_frames(handle):
                    del handle.tags[existing]
                handle.tags.add(COMM(encoding=3, lang="eng", desc="", text=values))
            else:
                handle.tags["comment"] = values
            handle.save()
            restored += 1
        except Exception:
            continue
    log(f"restored {restored:,} files")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repair", action="store_true", help="fix flipped collection Comments")
    parser.add_argument("--pin", action="store_true", help="write Comment into the files")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    db = sqlite3.connect(DB_PATH, timeout=120)
    db.execute("PRAGMA busy_timeout=120000")
    ensure_tables(db)
    try:
        if args.repair:
            repair(db)
        if args.pin:
            pin(db, args.limit)
        if args.verify:
            verify(db)
        if args.restore:
            restore(db)
        if not any((args.repair, args.pin, args.verify, args.restore)):
            parser.print_help()
    finally:
        db.close()


if __name__ == "__main__":
    main()
