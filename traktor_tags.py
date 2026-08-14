#!/usr/bin/env python3
"""Write our interpreted values into Traktor's collection — reversibly.

WHAT: fills Traktor's own fields from our analysis, and records the previous
value of every single field it touches so any of it can be put back exactly.

    Beat Type      -> RATING       (verified: Traktor's "Comment 2" is RATING,
                                    while the star rating is RANKING)
    Label          -> LABEL
    Genre + subgenre + style  -> GENRE       (the Genre-typed one first)
    Mood tags      -> KEY_LYRICS  (Traktor's "Lyrics" column)
    Energy         -> MIX
    Danceability   -> REMIXER
    Valence        -> PRODUCER

WHY NOT WRITE THE AUDIO FILES: Traktor reads its own collection, not the files.
Tagging 116,939 files would show nothing until every one was re-imported.

REVERSIBILITY, which is the whole point: `traktor_field_backup` stores one row
per changed field — entry key, attribute, the exact old value (including "it had
no value") and what we wrote. `--restore` puts those back and nothing else, so
reverting our changes never costs the owner the cue points, playlists or ratings
they made in the meantime. A whole-file backup cannot do that, which is why this
exists on top of one.

SAFETY: the new collection is written to a temporary file, parsed to prove it is
well-formed XML with the same number of entries, and only then swapped in. A
timestamped copy of the original is taken first regardless.

USAGE
  ./.venv/bin/python traktor_tags.py --dry-run
  ./.venv/bin/python traktor_tags.py --write
  ./.venv/bin/python traktor_tags.py --restore
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "music_app"))
import derive  # noqa: E402

ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "data" / "music.db"
NML = Path("/Users/jakub/Documents/Native Instruments/Traktor 4.0.2/collection.nml")
BACKUP_DIR = ROOT / "data" / "traktor_backups"

# our column -> Traktor attribute
FIELD_MAP = {
    "Beat Type":    "RATING",
    "Label":        "LABEL",
    "Genre":        "GENRE",
    "Mood":         "KEY_LYRICS",
    "Energy":       "MIX",
    "Danceability": "REMIXER",
    "Valence":      "PRODUCER",
}


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
        CREATE TABLE IF NOT EXISTS traktor_field_backup(
            entry_key TEXT NOT NULL,
            attribute TEXT NOT NULL,
            old_value TEXT,              -- NULL means the attribute was absent
            new_value TEXT,
            written_at TEXT NOT NULL,
            restored_at TEXT,
            PRIMARY KEY(entry_key, attribute, written_at));
        CREATE INDEX IF NOT EXISTS idx_tfb_key ON traktor_field_backup(entry_key);""")


def entry_key(location_tag: str) -> str:
    """Identity of an NML entry: its volume + directory + filename."""
    get = lambda name: (re.search(rf'{name}="([^"]*)"', location_tag) or [None, ""])[1]
    return f"{get('VOLUME')}|{get('DIR')}{get('FILE')}"


def values_for_tracks(db: sqlite3.Connection) -> dict[str, dict]:
    """spotify_id -> the interpreted values we intend to write."""
    import db as _unused  # noqa: F401  (keep music_app importable side effects out)
    return {}


def interpreted_by_path(db: sqlite3.Connection) -> dict[str, dict]:
    """Map a Traktor entry key to interpreted values, via traktor_entries."""
    sys.path.insert(0, str(ROOT / "music_app"))
    import db as appdb

    # Which Traktor entries do we have a track for?
    rows = db.execute("""SELECT e.path, e.spotify_id FROM traktor_entries e
                         WHERE e.spotify_id IS NOT NULL""").fetchall()
    by_sid: dict[str, list[str]] = {}
    for r in rows:
        by_sid.setdefault(r["spotify_id"], []).append(r["path"])
    sids = list(by_sid)
    print(f"  {len(sids):,} tracks are referenced by the collection", flush=True)

    out: dict[str, dict] = {}
    CHUNK = 400
    for i in range(0, len(sids), CHUNK):
        chunk = sids[i:i + CHUNK]
        marks = ",".join("?" * len(chunk))
        page = appdb.page_for_ids(chunk) if hasattr(appdb, "page_for_ids") else None
        if page is None:
            page = _rows_for_ids(db, chunk, marks)
        for row in page:
            vals = {col: row.get(col) for col in FIELD_MAP}
            for path in by_sid.get(row["spotify_id"], []):
                out[path] = vals
        if (i // CHUNK) % 20 == 0:
            print(f"    prepared {min(i+CHUNK, len(sids)):,}/{len(sids):,}", flush=True)
    return out


def _rows_for_ids(db: sqlite3.Connection, ids: list[str], marks: str) -> list[dict]:
    """Interpreted values for a batch of tracks, using the app's own rules."""
    rows = [dict(r) for r in db.execute(
        f"""SELECT t.spotify_id, t.label FROM tracks t WHERE t.spotify_id IN ({marks})""", ids)]
    index = {r["spotify_id"]: r for r in rows}
    # analysis payloads
    import json as _json, zlib as _zlib
    for r in db.execute(
            f"""SELECT spotify_id, stage, payload_blob FROM audio_analysis_artifacts
                WHERE spotify_id IN ({marks}) AND stage='rhythm_full'""", ids):
        try:
            payload = _json.loads(_zlib.decompress(r["payload_blob"]).decode())
        except Exception:
            continue
        row = index.get(r["spotify_id"])
        if row is not None:
            for field in ("rhythm_pattern", "four_on_floor_score", "broken_beat_score"):
                row[f"rhythm_{field}"] = payload.get(field)
    # provider numbers
    for r in db.execute(
            f"""SELECT spotify_id, energy, danceability, valence FROM audio_features
                WHERE source='freqblog' AND spotify_id IN ({marks})""", ids):
        row = index.get(r["spotify_id"])
        if row is not None:
            row["energy"], row["danceability"] = r["energy"], r["danceability"]
            row["valence"] = r["valence"]
    # tags, with their source and confidence, for the ranking rules
    candidates: dict[str, dict[str, list[dict]]] = {}
    for r in db.execute(
            f"""SELECT spotify_id, tag_type, tag, source, confidence FROM tags
                WHERE spotify_id IN ({marks})""", ids):
        candidates.setdefault(r["spotify_id"], {}).setdefault(r["tag_type"], []).append(
            {"tag": r["tag"], "source": r["source"], "confidence": r["confidence"]})
    out = []
    for sid, row in index.items():
        tags = candidates.get(sid, {})
        row.update(derive.interpret(row, tags))
        row["Genre"] = _joined(tags, ["genre", "genre_audio_candidate"], row.get("Genre"))
        row["Mood"] = _joined(tags, ["mood", "mood_candidate"], row.get("Mood"))
        row["Label"] = (row.get("label") or "").strip()
        row["Valence"] = derive.band(row.get("valence"))
        out.append(row)
    return out


def _joined(tags: dict, types: list[str], leader: str | None) -> str:
    """All English values of these tag types, the interpreted one first."""
    seen, ordered = set(), []
    if leader:
        ordered.append(leader); seen.add(leader.lower())
    pooled = []
    for tag_type in types:
        pooled.extend(tags.get(tag_type) or [])
    for c in sorted(pooled, key=lambda c: (derive.source_rank(c.get("source") or ""),
                                           -float(c.get("confidence") or 0))):
        tag = (c.get("tag") or "").strip()
        if tag and derive.is_english(tag) and tag.lower() not in seen:
            seen.add(tag.lower()); ordered.append(tag)
    return ", ".join(ordered[:12])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()

    db = connect()
    ensure_table(db)
    db.commit()

    if args.restore:
        return restore(db)

    if not NML.is_file():
        raise SystemExit("collection.nml not found")
    print("reading the collection …", flush=True)
    text = NML.read_text(encoding="utf-8", errors="replace")
    print(f"  {len(text):,} chars", flush=True)

    print("preparing interpreted values …", flush=True)
    wanted = interpreted_by_path(db)
    print(f"  values ready for {len(wanted):,} collection paths", flush=True)

    stamp = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    changes: list[tuple] = []
    stats = {"entries": 0, "matched": 0, "fields": 0}

    def fix_entry(match: re.Match) -> str:
        entry = match.group(0)
        stats["entries"] += 1
        loc = re.search(r'<LOCATION[^>]*>', entry)
        info = re.search(r'<INFO[^>]*?/?>', entry)
        if not loc or not info:
            return entry
        get = lambda n: (re.search(rf'{n}="([^"]*)"', loc.group(0)) or [None, ""])[1]
        volume = get("VOLUME")
        path = f"/{volume}{get('DIR')}{get('FILE')}" if volume and volume.lower() not in (
            "macintosh hd", "macintosh hd - data") else f"{get('DIR')}{get('FILE')}"
        path = path.replace("/:", "/")
        vals = wanted.get(path)
        if not vals:
            return entry
        stats["matched"] += 1
        tag = info.group(0)
        key = entry_key(loc.group(0))
        for column, attr in FIELD_MAP.items():
            new = (vals.get(column) or "")
            if not new:
                continue
            new = str(new)
            existing = re.search(rf'(?<![A-Z_]){attr}="([^"]*)"', tag)
            old = existing.group(1) if existing else None
            if old == html.escape(new, quote=True) or old == new:
                continue
            changes.append((key, attr, old, new, stamp))
            stats["fields"] += 1
            escaped = html.escape(new, quote=True)
            if existing:
                tag = tag[:existing.start(1)] + escaped + tag[existing.end(1):]
            else:
                insert = " " + f'{attr}="{escaped}"'
                tag = tag[:-2] + insert + tag[-2:] if tag.endswith("/>") else \
                      tag[:-1] + insert + tag[-1:]
        return entry[:info.start()] + tag + entry[info.end():]

    print("applying …", flush=True)
    new_text = re.sub(r'<ENTRY\b.*?</ENTRY>', fix_entry, text, flags=re.S)
    print(f"  entries {stats['entries']:,} · matched {stats['matched']:,} · "
          f"fields to change {stats['fields']:,}", flush=True)

    if args.dry_run or not args.write:
        by_attr: dict[str, int] = {}
        for _, attr, _, _, _ in changes:
            by_attr[attr] = by_attr.get(attr, 0) + 1
        for attr, n in sorted(by_attr.items(), key=lambda x: -x[1]):
            print(f"    {attr:12} {n:,}")
        print("\ndry run — nothing written. Pass --write to apply.")
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    copy = BACKUP_DIR / f"collection.before-write.{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}.nml"
    shutil.copy2(NML, copy)
    print(f"  full copy taken: {copy.name}", flush=True)

    tmp = NML.with_suffix(".nml.tmp")
    tmp.write_text(new_text, encoding="utf-8")
    # Prove it is still valid XML with the same entry count BEFORE swapping.
    root = ET.parse(tmp).getroot()
    n_new = len(root.findall(".//ENTRY"))
    n_old = len(re.findall(r'<ENTRY\b', text))
    if n_new != n_old:
        tmp.unlink(missing_ok=True)
        raise SystemExit(f"refusing to swap: entry count changed {n_old} -> {n_new}")
    tmp.replace(NML)
    print(f"  collection written and validated ({n_new:,} entries)", flush=True)

    with db:
        db.execute("BEGIN IMMEDIATE")
        db.executemany("""INSERT OR REPLACE INTO traktor_field_backup
            (entry_key,attribute,old_value,new_value,written_at) VALUES(?,?,?,?,?)""", changes)
    print(f"\nDONE · {stats['fields']:,} fields written across {stats['matched']:,} tracks")
    print(f"every previous value is stored — undo with: traktor_tags.py --restore")


def restore(db: sqlite3.Connection) -> None:
    rows = db.execute("""SELECT entry_key, attribute, old_value FROM traktor_field_backup
                         WHERE restored_at IS NULL""").fetchall()
    if not rows:
        print("nothing to restore")
        return
    print(f"restoring {len(rows):,} fields …", flush=True)
    text = NML.read_text(encoding="utf-8", errors="replace")
    want = {(r["entry_key"], r["attribute"]): r["old_value"] for r in rows}
    restored = 0

    def fix(match: re.Match) -> str:
        nonlocal restored
        entry = match.group(0)
        loc = re.search(r'<LOCATION[^>]*>', entry)
        info = re.search(r'<INFO[^>]*?/?>', entry)
        if not loc or not info:
            return entry
        key = entry_key(loc.group(0))
        tag = info.group(0)
        for (k, attr), old in list(want.items()):
            if k != key:
                continue
            existing = re.search(rf'(?<![A-Z_]){attr}="([^"]*)"', tag)
            if old is None:
                if existing:                      # it had no attribute before
                    tag = tag[:existing.start()].rstrip() + tag[existing.end():]
                    restored += 1
            elif existing:
                tag = tag[:existing.start(1)] + html.escape(old, quote=True) + tag[existing.end(1):]
                restored += 1
        return entry[:info.start()] + tag + entry[info.end():]

    new_text = re.sub(r'<ENTRY\b.*?</ENTRY>', fix, text, flags=re.S)
    tmp = NML.with_suffix(".nml.tmp")
    tmp.write_text(new_text, encoding="utf-8")
    ET.parse(tmp)
    tmp.replace(NML)
    with db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE traktor_field_backup SET restored_at=? WHERE restored_at IS NULL",
                   (time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),))
    print(f"restored {restored:,} fields to their previous values")


if __name__ == "__main__":
    main()
