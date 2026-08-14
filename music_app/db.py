#!/usr/bin/env python3
"""Data layer for the track browser: reads the library, writes edits safely.

WHAT: turns the database's EAV shape (4.2M tag rows, 7.1M attribute rows across
81k tracks) into the flat, column-per-field view a DJ expects, and applies edits
back to the right underlying table.

WHY IT IS BUILT THIS WAY: nothing here ever loads the whole library. Every query
is bounded by a page, because the browser must stay usable against a 32 GB
database that four other processes are writing to at the same time.

HOW TO TWEAK: COLUMNS is the whole column catalogue — each entry says where a
field lives and whether it can be edited. Add a row there and it appears in the
app automatically.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "music.db"

# name -> (source, sql_expression, editable)
#   track      : a column on tracks
#   file       : a column on audio_files (one row per file; we show the best pick)
#   feature    : a value from audio_features, chosen per source
#   tag        : comma-joined tags of one tag_type
COLUMNS: dict[str, tuple[str, str, bool]] = {
    "title":         ("track", "t.title", True),
    "artist_names":  ("track", "t.artist_names", True),
    "album":         ("track", "t.album", True),
    "release_date":  ("track", "t.release_date", True),
    "isrc":          ("track", "t.isrc", True),
    "label":         ("track", "t.label", True),
    "popularity":    ("track", "t.popularity", False),
    "duration_ms":   ("track", "t.duration_ms", False),
    "spotify_id":    ("track", "t.spotify_id", False),
    "path":          ("file",  "f.path", False),
    "codec":         ("file",  "f.codec", False),
    "file_size":     ("file",  "f.file_size", False),
    "analysis":      ("file",  "f.analysis_status", False),
}

# Feature columns are pivoted from audio_features by source, newest wins.
FEATURE_COLUMNS = {
    "bpm_analysis":  ("audio-full:beat-this-v2", "bpm"),
    "bpm_freqblog":  ("freqblog", "bpm"),
    "key_freqblog":  ("freqblog", "key"),
    "energy":        ("freqblog", "energy"),
    "danceability":  ("freqblog", "danceability"),
    "valence":       ("freqblog", "valence"),
}

# Tag columns are comma-joined tags of one tag_type.
TAG_COLUMNS = ["genre", "style", "mood", "instrument", "audio_style_candidate",
               "acoustic_character", "label", "country", "format"]


def connect(write: bool = False) -> sqlite3.Connection:
    """Open the library. Always writable: a WAL database with no live writer
    cannot materialise its -shm file from a read-only handle, which fails with a
    bare 'unable to open database file' — seen repeatedly against this library."""
    for attempt in range(5):
        try:
            db = sqlite3.connect(DB_PATH, timeout=60)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA busy_timeout=60000")
            return db
        except sqlite3.OperationalError:
            if attempt == 4:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def all_columns() -> list[str]:
    return list(COLUMNS) + list(FEATURE_COLUMNS) + [f"tag_{t}" for t in TAG_COLUMNS]


def editable_columns() -> list[str]:
    return [name for name, (_, _, editable) in COLUMNS.items() if editable]


def _base_query(search: str, only_missing: str | None) -> tuple[str, list]:
    """One row per track, with its best file. Bounded by the caller's page."""
    where, params = ["1=1"], []
    if search:
        where.append("(t.title LIKE ? OR t.artist_names LIKE ? OR t.album LIKE ? OR f.path LIKE ?)")
        like = f"%{search}%"
        params += [like, like, like, like]
    if only_missing == "path":
        where.append("f.path IS NULL")
    elif only_missing == "analysis":
        where.append("""t.spotify_id NOT IN (SELECT spotify_id FROM audio_analysis_artifacts
                        WHERE stage IN ('rhythm_full','maest_full','essentia_full','clap_full')
                        GROUP BY spotify_id HAVING COUNT(DISTINCT stage)=4)""")
    sql = f"""FROM tracks t
              LEFT JOIN (SELECT spotify_id, MIN(path) path, MIN(codec) codec,
                                MIN(file_size) file_size, MIN(analysis_status) analysis_status
                         FROM audio_files WHERE spotify_id IS NOT NULL
                         GROUP BY spotify_id) f USING(spotify_id)
              WHERE {' AND '.join(where)}"""
    return sql, params


def page(offset: int, limit: int, search: str = "", sort: str = "title",
         only_missing: str | None = None) -> dict:
    db = connect()
    try:
        base, params = _base_query(search, only_missing)
        total = db.execute(f"SELECT COUNT(*) {base}", params).fetchone()[0]
        order = COLUMNS.get(sort, ("", "t.title", False))[1]
        select = ", ".join(f"{expr} AS {name}" for name, (_, expr, _) in COLUMNS.items())
        rows = [dict(r) for r in db.execute(
            f"SELECT {select} {base} ORDER BY {order} LIMIT ? OFFSET ?",
            params + [limit, offset])]
        ids = [r["spotify_id"] for r in rows]
        if ids:
            marks = ",".join("?" * len(ids))
            for name, (source, field) in FEATURE_COLUMNS.items():
                for r in db.execute(
                        f"""SELECT spotify_id, {field} v FROM audio_features
                            WHERE source=? AND spotify_id IN ({marks}) AND {field} IS NOT NULL""",
                        [source] + ids):
                    for row in rows:
                        if row["spotify_id"] == r["spotify_id"]:
                            row[name] = r["v"]
            for tag_type in TAG_COLUMNS:
                joined: dict[str, list[str]] = {}
                for r in db.execute(
                        f"""SELECT spotify_id, tag FROM tags
                            WHERE tag_type=? AND spotify_id IN ({marks})""",
                        [tag_type] + ids):
                    joined.setdefault(r["spotify_id"], []).append(r["tag"])
                for row in rows:
                    row[f"tag_{tag_type}"] = ", ".join(sorted(joined.get(row["spotify_id"], [])))
        return {"total": total, "rows": rows}
    finally:
        db.close()


def update_cell(spotify_id: str, column: str, value: str) -> None:
    spec = COLUMNS.get(column)
    if not spec or not spec[2]:
        raise ValueError(f"column '{column}' is not editable")
    source, expr, _ = spec
    field = expr.split(".", 1)[1]
    db = connect()
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            if source == "track":
                db.execute(f"UPDATE tracks SET {field}=?, updated_at=CURRENT_TIMESTAMP "
                           f"WHERE spotify_id=?", (value, spotify_id))
            else:
                db.execute(f"UPDATE audio_files SET {field}=? WHERE spotify_id=?",
                           (value, spotify_id))
    finally:
        db.close()


def bulk_update(column: str, ids: list[str], value: str) -> int:
    """Set one column to the same value across many tracks."""
    for sid in ids:
        update_cell(sid, column, value)
    return len(ids)


def find_replace(column: str, ids: list[str], find: str, replace: str) -> int:
    """Literal find-and-replace inside ONE column, over the given tracks."""
    spec = COLUMNS.get(column)
    if not spec or not spec[2]:
        raise ValueError(f"column '{column}' is not editable")
    source, expr, _ = spec
    field = expr.split(".", 1)[1]
    table = "tracks" if source == "track" else "audio_files"
    if not ids:
        return 0
    marks = ",".join("?" * len(ids))
    db = connect()
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            cur = db.execute(
                f"""UPDATE {table} SET {field} = REPLACE({field}, ?, ?)
                    WHERE spotify_id IN ({marks}) AND {field} LIKE ?""",
                [find, replace] + ids + [f"%{find}%"])
            return cur.rowcount
    finally:
        db.close()


def swap_columns(left: str, right: str, ids: list[str]) -> int:
    """Exchange the contents of two editable columns on the given tracks."""
    for name in (left, right):
        spec = COLUMNS.get(name)
        if not spec or not spec[2]:
            raise ValueError(f"column '{name}' is not editable")
    if COLUMNS[left][0] != COLUMNS[right][0]:
        raise ValueError("swap needs two columns from the same table")
    table = "tracks" if COLUMNS[left][0] == "track" else "audio_files"
    lf = COLUMNS[left][1].split(".", 1)[1]
    rf = COLUMNS[right][1].split(".", 1)[1]
    if not ids:
        return 0
    marks = ",".join("?" * len(ids))
    db = connect()
    try:
        with db:
            db.execute("BEGIN IMMEDIATE")
            cur = db.execute(
                f"""UPDATE {table} SET {lf} = {rf}, {rf} = {lf}
                    WHERE spotify_id IN ({marks})""", ids)
            return cur.rowcount
    finally:
        db.close()


def stats() -> dict:
    db = connect()
    try:
        one = lambda sql: db.execute(sql).fetchone()[0]
        return {
            "tracks": one("SELECT COUNT(*) FROM tracks"),
            "with_path": one("""SELECT COUNT(DISTINCT spotify_id) FROM audio_files
                                WHERE spotify_id IS NOT NULL"""),
            "analysed": one("""SELECT COUNT(*) FROM (SELECT spotify_id FROM audio_analysis_artifacts
                               WHERE stage IN ('rhythm_full','maest_full','essentia_full','clap_full')
                               GROUP BY spotify_id HAVING COUNT(DISTINCT stage)=4)"""),
            "tags": one("SELECT COUNT(*) FROM tags"),
        }
    finally:
        db.close()
