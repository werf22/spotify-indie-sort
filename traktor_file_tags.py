#!/usr/bin/env python3
"""Write the interpreted values into the AUDIO FILES' own tags — reversibly.

WHY: Traktor refreshes its browser columns from the file's tags when a track is
loaded, so values written only into collection.nml get overwritten per track the
moment the owner plays it. The fix is to make the files carry the same values,
so whatever Traktor re-reads agrees with the collection. (Comment 2 / Beat Type
is the exception: it is proprietary to Traktor, has no standard file frame, and
therefore cannot be overwritten by a file re-import at all.)

WHAT GOES WHERE (same values as collection.nml):
  column        MP3/WAV/AIFF (ID3)          M4A (MP4)                        FLAC/OGG
  Genre         TCON                        ©gen                             genre
  Label         TPUB                        ----:com.apple.iTunes:LABEL      label, organization
  Mood list     USLT (lyrics)               ©lyr                             lyrics
  Energy num    TIT3 + TXXX:MIX             ----:com.apple.iTunes:MIX        mix
  Dance num     TPE4 (remixer)              ----:com.apple.iTunes:REMIXER    remixer, mixartist
  Valence num   TXXX:PRODUCER               ----:com.apple.iTunes:PRODUCER   producer

TPUB and TPE4 are proven from this library (13/13 and 17/20 of Traktor-imported
values matched exactly those frames); TCON/USLT/©gen/©lyr are the universal
standards; the freeform/TXXX names follow the MusicBrainz-Picard convention.

REVERSIBILITY: before a file is modified, the current value of every frame we
touch is stored in `file_frame_backup`; `--restore` puts exactly those back
(including deleting frames that did not exist). Progress lives in
`file_tag_write`, so an interrupted run resumes where it stopped.

USAGE
  ./.venv/bin/python traktor_file_tags.py --limit 8        # cautious first batch
  ./.venv/bin/python traktor_file_tags.py                  # full run (resumable)
  ./.venv/bin/python traktor_file_tags.py --verify         # re-read a sample
  ./.venv/bin/python traktor_file_tags.py --restore        # undo everything
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import mutagen
from mutagen.id3 import ID3, TCON, TPUB, USLT, TPE4, TIT3, TXXX
from mutagen.mp4 import MP4, MP4FreeForm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import traktor_tags as tt

ROOT = Path(__file__).resolve().parent
COMMIT_EVERY = 200

FREEFORM = "----:com.apple.iTunes:"
VORBIS = {"Genre": ["genre"], "Label": ["label", "organization"],
          "Mood": ["lyrics"], "Energy": ["mix"],
          "Danceability": ["remixer", "mixartist"], "Valence": ["producer"]}


def ensure_tables(db: sqlite3.Connection) -> None:
    db.executescript("""
        CREATE TABLE IF NOT EXISTS file_frame_backup(
            path TEXT NOT NULL, frame TEXT NOT NULL,
            old_value TEXT, new_value TEXT,
            written_at TEXT NOT NULL, restored_at TEXT,
            PRIMARY KEY(path, frame, written_at));
        CREATE TABLE IF NOT EXISTS file_tag_write(
            path TEXT PRIMARY KEY, status TEXT NOT NULL,
            detail TEXT, updated_at TEXT NOT NULL);""")


def frames_for(handle) -> str:
    if isinstance(handle, MP4):
        return "mp4"
    if handle is not None and isinstance(handle.tags, ID3):
        return "id3"
    if handle is not None and handle.tags is not None and hasattr(handle.tags, "as_dict"):
        return "vorbis"
    return "unknown"


def read_frame(handle, kind: str, frame: str):
    """Current value of one frame, as JSON that --restore can REBUILD from.

    For ID3 that means the frame's text payload, never repr(frame): a repr
    cannot be turned back into a frame, which would have made every MP3 that
    already carried a genre or label irreversible — the exact opposite of this
    tool's contract.
    """
    try:
        if kind == "id3":
            got = handle.tags.getall(frame)
            if not got:
                return None
            texts: list[str] = []
            for item in got:
                payload = getattr(item, "text", None)
                if payload is None:
                    texts.append(str(item))
                elif isinstance(payload, (list, tuple)):
                    texts.extend(str(x) for x in payload)
                else:
                    texts.append(str(payload))
            return json.dumps(texts)
        value = handle.tags.get(frame)
        if value is None:
            return None
        return json.dumps([bytes(x).decode("utf-8", "replace") if isinstance(x, (bytes, MP4FreeForm))
                           else str(x) for x in value])
    except Exception:
        return None


def build_id3(frame: str, values: list[str]):
    """Rebuild an ID3 frame from the backed-up text payload (restore path)."""
    if frame == "USLT":
        return USLT(encoding=3, lang="eng", desc="", text=values[0] if values else "")
    if frame.startswith("TXXX:"):
        return TXXX(encoding=3, desc=frame.split(":", 1)[1], text=values)
    ctor = {"TCON": TCON, "TPUB": TPUB, "TPE4": TPE4, "TIT3": TIT3}[frame]
    return ctor(encoding=3, text=values)


def id3_writes(vals: dict) -> list[tuple[str, object, list[str]]]:
    """(frame name, frame object, text payload) — the payload is what gets
    stored as new_value, so verify/restore compare like with like."""
    out = []
    if vals["Genre"]:
        out.append(("TCON", TCON(encoding=3, text=[vals["Genre"]]), [vals["Genre"]]))
    if vals["Label"]:
        out.append(("TPUB", TPUB(encoding=3, text=[vals["Label"]]), [vals["Label"]]))
    if vals["Mood"]:
        out.append(("USLT", USLT(encoding=3, lang="eng", desc="", text=vals["Mood"]),
                    [vals["Mood"]]))
    if vals["Danceability"]:
        out.append(("TPE4", TPE4(encoding=3, text=[vals["Danceability"]]),
                    [vals["Danceability"]]))
    if vals["Energy"]:
        out.append(("TIT3", TIT3(encoding=3, text=[vals["Energy"]]), [vals["Energy"]]))
        out.append(("TXXX:MIX", TXXX(encoding=3, desc="MIX", text=[vals["Energy"]]),
                    [vals["Energy"]]))
    if vals["Valence"]:
        out.append(("TXXX:PRODUCER", TXXX(encoding=3, desc="PRODUCER",
                                          text=[vals["Valence"]]), [vals["Valence"]]))
    return out


def write_one(path: Path, vals: dict, db: sqlite3.Connection, stamp: str) -> str:
    handle = mutagen.File(path)
    if handle is None:
        return "unsupported"
    if handle.tags is None:
        try:
            handle.add_tags()
        except Exception:
            return "untaggable"
    kind = frames_for(handle)
    if kind == "unknown":
        return "unsupported"

    changes: list[tuple[str, str | None, str]] = []   # frame, old, new
    if kind == "id3":
        for frame, obj, payload in id3_writes(vals):
            old = read_frame(handle, kind, frame)
            new = json.dumps(payload)
            if old == new:
                continue
            handle.tags.delall(frame)
            handle.tags.add(obj)
            changes.append((frame, old, new))
    elif kind == "mp4":
        plan = {"\xa9gen": vals["Genre"], "\xa9lyr": vals["Mood"],
                FREEFORM + "LABEL": vals["Label"], FREEFORM + "MIX": vals["Energy"],
                FREEFORM + "REMIXER": vals["Danceability"],
                FREEFORM + "PRODUCER": vals["Valence"]}
        for frame, value in plan.items():
            if not value:
                continue
            old = read_frame(handle, kind, frame)
            new = json.dumps([value])
            if old == new:
                continue
            handle.tags[frame] = ([MP4FreeForm(value.encode("utf-8"))]
                                  if frame.startswith("----") else [value])
            changes.append((frame, old, new))
    else:
        for column, keys in VORBIS.items():
            value = vals[column]
            if not value:
                continue
            for frame in keys:
                old = read_frame(handle, kind, frame)
                new = json.dumps([value])
                if old == new:
                    continue
                handle.tags[frame] = [value]
                changes.append((frame, old, new))

    if not changes:
        return "no_change"
    # BACKUP FIRST — the file is only touched once its previous values are safe.
    with db:
        db.executemany("""INSERT OR REPLACE INTO file_frame_backup
            (path,frame,old_value,new_value,written_at) VALUES(?,?,?,?,?)""",
            [(str(path), f, o, n, stamp) for f, o, n in changes])
    if kind == "id3" and path.suffix.lower() == ".mp3":
        handle.save(v2_version=3)
    else:
        handle.save()
    return f"wrote_{len(changes)}"


def pending_files(db: sqlite3.Connection, limit: int) -> list[tuple[str, str]]:
    rows = db.execute("""
        SELECT f.path, f.spotify_id FROM audio_files f
        WHERE f.spotify_id IS NOT NULL
          AND f.path NOT IN (SELECT path FROM file_tag_write WHERE status IN
                             ('done','no_change','missing','unsupported','untaggable'))
        ORDER BY f.path""").fetchall()
    return [(r[0], r[1]) for r in rows][:limit] if limit else [(r[0], r[1]) for r in rows]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    db = tt.connect()
    ensure_tables(db)
    db.commit()
    if args.verify:
        return verify(db)
    if args.restore:
        return restore(db)

    todo = pending_files(db, args.limit)
    print(f"files to process: {len(todo):,}", flush=True)
    by_sid: dict[str, list[str]] = {}
    for path, sid in todo:
        by_sid.setdefault(sid, []).append(path)
    sids = list(by_sid)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    stats: dict[str, int] = {}
    done = 0
    for i in range(0, len(sids), 400):
        chunk = sids[i:i + 400]
        marks = ",".join("?" * len(chunk))
        rows = tt._rows_for_ids(db, chunk, marks)
        values = {r["spotify_id"]: {c: str(r.get(c) or "").strip()
                  for c in ("Genre", "Label", "Mood", "Energy", "Danceability", "Valence")}
                  for r in rows}
        batch: list[tuple[str, str, str, str]] = []
        for sid in chunk:
            vals = values.get(sid)
            for raw in by_sid[sid]:
                path = Path(raw)
                done += 1
                if vals is None or not any(vals.values()):
                    outcome = "no_values"
                elif not path.is_file():
                    outcome = "missing"          # unplugged disk: skip, never block
                else:
                    try:
                        outcome = write_one(path, vals, db, stamp)
                    except Exception as exc:
                        outcome = "failed"
                        batch.append((raw, "failed", f"{type(exc).__name__}: {exc}"[:200],
                                      stamp))
                        stats[outcome] = stats.get(outcome, 0) + 1
                        continue
                status = "done" if outcome.startswith("wrote") else outcome
                batch.append((raw, status, outcome, stamp))
                stats[status] = stats.get(status, 0) + 1
        with db:
            db.executemany("""INSERT OR REPLACE INTO file_tag_write
                (path,status,detail,updated_at) VALUES(?,?,?,?)""", batch)
        if (i // 400) % 5 == 0:
            print(f"  {done:,}/{len(todo):,}  {stats}", flush=True)
    print(f"\nDONE {done:,} files · {stats}", flush=True)


def verify(db: sqlite3.Connection) -> None:
    rows = db.execute("""SELECT path, frame, new_value FROM file_frame_backup
                         WHERE restored_at IS NULL ORDER BY RANDOM() LIMIT 80""").fetchall()
    ok = miss = gone = 0
    for r in rows:
        path = Path(r["path"])
        if not path.is_file():
            gone += 1
            continue
        handle = mutagen.File(path)
        current = read_frame(handle, frames_for(handle), r["frame"]) if handle else None
        if current == r["new_value"]:
            ok += 1
        else:
            miss += 1
            if miss <= 4:
                print(f"  MISMATCH {path.name[:40]} {r['frame']}: "
                      f"file={str(current)[:40]} expected={str(r['new_value'])[:40]}")
    print(f"verified {ok}/{ok + miss} sampled frames on disk ({gone} files unreachable)")
    print("VERDICT:", "written frames are in the files" if miss == 0 else "DRIFT — investigate")


def restore(db: sqlite3.Connection) -> None:
    rows = db.execute("""SELECT path, frame, old_value FROM file_frame_backup
                         WHERE restored_at IS NULL ORDER BY written_at DESC""").fetchall()
    want: dict[tuple[str, str], str | None] = {}
    for r in rows:                        # DESC order -> earliest generation wins
        want[(r["path"], r["frame"])] = r["old_value"]
    by_path: dict[str, list[tuple[str, str | None]]] = {}
    for (path, frame), old in want.items():
        by_path.setdefault(path, []).append((frame, old))
    print(f"restoring {len(want):,} frames across {len(by_path):,} files", flush=True)
    restored = failed = 0
    for raw, frames in by_path.items():
        path = Path(raw)
        if not path.is_file():
            continue
        try:
            handle = mutagen.File(path)
            if handle is None:
                continue
            kind = frames_for(handle)
            for frame, old in frames:
                if old is None:
                    if kind == "id3":
                        handle.tags.delall(frame)
                    elif handle.tags is not None and frame in handle.tags:
                        del handle.tags[frame]
                else:
                    values = json.loads(old)
                    if kind == "id3":
                        handle.tags.delall(frame)
                        handle.tags.add(build_id3(frame, values))
                    else:
                        handle.tags[frame] = ([MP4FreeForm(v.encode()) for v in values]
                                              if frame.startswith("----") else values)
            handle.save()
            restored += 1
        except Exception:
            failed += 1
    with db:
        db.execute("UPDATE file_frame_backup SET restored_at=? WHERE restored_at IS NULL",
                   (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),))
    print(f"restored {restored:,} files ({failed} failed)")


if __name__ == "__main__":
    main()
