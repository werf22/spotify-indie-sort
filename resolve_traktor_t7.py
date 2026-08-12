#!/usr/bin/env python3
"""Reconnect the Traktor collection's T7 tracks to the files actually on the disk.

WHAT: for every Traktor entry whose NML volume is T7 and which already matches a
track in our database, find the real file on the mounted disk and register it in
`audio_files`. From there the normal loop takes over: clip prep, shard build,
GPU analysis.

WHY IT IS NEEDED: Traktor stores the volume separately from the path, so these
entries live in our database as `/T7/...`, which resolves to nothing. Worse, the
folder layout on the disk has changed since the collection was written — the very
first entry points at `Hudba August 2025/Afro Dengue August 2025/`, a directory
that no longer exists. Path-based resolution therefore recovers nothing, while
matching on FILENAME recovers 79,880 of 80,188 entries (99.6%).

HOW AMBIGUITY IS HANDLED: 15,150 filenames occur more than once on the disk
(backups of the same track). The Traktor entry knows its duration, so the
candidate whose actual duration is closest wins, and anything off by more than
DURATION_TOLERANCE seconds is refused rather than guessed. A wrong file here
would attach one track's audio analysis to another track's identity, which is
worse than leaving it unanalysed.

HOW TO TWEAK: --dry-run reports what would change and writes nothing. --limit
caps the number of entries processed, for a cautious first pass.

USAGE
  ./.venv/bin/python resolve_traktor_t7.py --dry-run
  ./.venv/bin/python resolve_traktor_t7.py --limit 500
  ./.venv/bin/python resolve_traktor_t7.py
"""

from __future__ import annotations

import argparse
import subprocess
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from musicdb import connect, connect_readonly

T7 = Path("/Volumes/T7")
AUDIO_SUFFIXES = {".mp3", ".m4a", ".flac", ".wav", ".aiff", ".aif",
                  ".ogg", ".opus", ".alac", ".wma", ".aac"}
DURATION_TOLERANCE = 5.0     # seconds; beyond this a candidate is refused, not guessed


def norm(name: str) -> str:
    """macOS stores NFD on disk while the NML carries NFC — compare on one form."""
    return unicodedata.normalize("NFC", name).casefold()


def index_disk() -> dict[str, list[Path]]:
    found: dict[str, list[Path]] = defaultdict(list)
    for path in T7.rglob("*"):
        try:
            if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES:
                found[norm(path.name)].append(path)
        except OSError:
            continue
    return found


def probe_duration(path: Path) -> float | None:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=nw=1:nk=1", str(path)],
            capture_output=True, text=True, timeout=30).stdout.strip()
        return float(out) if out else None
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None


def pick(candidates: list[Path], want: float | None) -> tuple[Path | None, str]:
    """Choose among same-named files; refuse rather than guess when unsure."""
    if len(candidates) == 1:
        return candidates[0], "unique_name"
    if not want:
        return None, "ambiguous_no_duration"
    best, best_gap = None, None
    for candidate in candidates:
        actual = probe_duration(candidate)
        if actual is None:
            continue
        gap = abs(actual - want)
        if best_gap is None or gap < best_gap:
            best, best_gap = candidate, gap
    if best is not None and best_gap is not None and best_gap <= DURATION_TOLERANCE:
        return best, f"duration_match_{best_gap:.1f}s"
    return None, "ambiguous_duration_mismatch"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    if not T7.is_dir():
        raise SystemExit("T7 is not mounted; connect the disk and retry")

    print("indexing the disk ...", flush=True)
    disk = index_disk()
    print(f"  {sum(len(v) for v in disk.values()):,} audio files, "
          f"{len(disk):,} distinct names", flush=True)

    with connect_readonly() as db:
        rows = db.execute("""
            SELECT e.entry_id, e.path, e.spotify_id, e.duration_seconds
            FROM traktor_entries e
            WHERE e.path LIKE '/T7/%' AND e.spotify_id IS NOT NULL
              AND e.spotify_id NOT IN (
                  SELECT spotify_id FROM audio_analysis_artifacts
                  WHERE stage IN ('rhythm_full','maest_full','essentia_full','clap_full')
                  GROUP BY spotify_id HAVING COUNT(DISTINCT stage)=4)
            ORDER BY e.entry_id""").fetchall()
        known = {r[0] for r in db.execute("SELECT path FROM audio_files")}
    if args.limit:
        rows = rows[:args.limit]
    print(f"  {len(rows):,} Traktor entries to resolve", flush=True)

    stamp = datetime.now(timezone.utc).isoformat()
    resolved = skipped = already = 0
    reasons: dict[str, int] = defaultdict(int)
    pending: list[tuple] = []

    for entry_id, path, spotify_id, want in rows:
        filename = norm(Path(path).name)
        candidates = disk.get(filename) or []
        if not candidates:
            reasons["no_file_of_that_name"] += 1
            skipped += 1
            continue
        chosen, why = pick(candidates, want)
        if chosen is None:
            reasons[why] += 1
            skipped += 1
            continue
        reasons[why.split("_")[0]] += 1
        if str(chosen) in known:
            already += 1
            continue
        try:
            stat = chosen.stat()
        except OSError:
            skipped += 1
            continue
        pending.append((str(chosen), spotify_id, chosen.name, want,
                        stat.st_size, stat.st_mtime_ns,
                        chosen.suffix.lower().lstrip("."), stamp, entry_id))
        resolved += 1

    print(f"\nresolved {resolved:,} | already registered {already:,} | refused {skipped:,}")
    for reason, count in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"    {reason:28} {count:,}")

    if args.dry_run:
        print("\ndry run — nothing written")
        return

    db = connect()
    db.execute("PRAGMA busy_timeout=120000")
    with db:
        for (path, sid, title, dur, size, mtime, codec, ts, entry_id) in pending:
            db.execute("""
                INSERT INTO audio_files(path,spotify_id,title,duration_seconds,file_size,
                                        mtime_ns,codec,match_method,match_confidence,
                                        scan_status,analysis_status,attempts,updated_at)
                VALUES(?,?,?,?,?,?,?,'traktor_t7',0.9,'matched','queued',0,?)
                ON CONFLICT(path) DO UPDATE SET
                    spotify_id=excluded.spotify_id, scan_status='matched',
                    match_method='traktor_t7', updated_at=excluded.updated_at""",
                (path, sid, title, dur, size, mtime, codec, ts))
            db.execute("""UPDATE traktor_entries
                          SET resolved_path=?, path_exists=1, updated_at=?
                          WHERE entry_id=?""", (path, ts, entry_id))
    print(f"\nregistered {len(pending):,} files in audio_files — the normal loop "
          f"(prep -> shard -> analysis) picks them up from here")


if __name__ == "__main__":
    main()
