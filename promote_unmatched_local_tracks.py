#!/usr/bin/env python3
"""Give every remaining local audio file a database identity to analyze.

Two passes over audio_files rows with spotify_id IS NULL:

1. ISRC recovery — an embedded ISRC that maps to EXACTLY ONE catalog track
   (D-006: ambiguous ISRCs, common for reissues/compilations, are left alone
   rather than guessed) is a real match; the file is attached to that track.
2. Local-only synthesis — everything else, restricted to duration <= 900s
   (the owner's "no DJ sets / long mixes" boundary; unknown-duration files
   are skipped, not guessed into scope) gets a stable synthetic identity and
   a minimal `tracks` row so it can flow through the EXACT SAME shard/pod
   pipeline as catalog tracks — no other script changes needed.

Synthetic rows are unmistakably non-Spotify: spotify_id is prefixed
"local_" (never a valid 22-char Spotify ID), uri is "local:<path>", and
library_sources is the literal "local_only" so any report can filter them
out of the Spotify-catalog counts.

Idempotent and restart-safe: already-matched files (real or synthetic) are
never revisited.
"""
from __future__ import annotations

import argparse
import hashlib
from datetime import datetime, timezone

from musicdb import connect

MAX_DURATION_SECONDS = 900  # 15 minutes — the owner's DJ-set/long-mix cutoff


def local_id(path: str) -> str:
    return "local_" + hashlib.sha1(path.encode("utf-8")).hexdigest()[:16]


def recover_by_isrc(db) -> int:
    rows = db.execute(
        """SELECT af.path, t.spotify_id FROM audio_files af
           JOIN (
             SELECT isrc, MIN(spotify_id) AS spotify_id FROM tracks
             WHERE isrc IS NOT NULL AND isrc != ''
             GROUP BY isrc HAVING COUNT(DISTINCT spotify_id) = 1
           ) t ON t.isrc = af.isrc
           WHERE af.spotify_id IS NULL AND af.isrc IS NOT NULL AND af.isrc != ''"""
    ).fetchall()
    now = datetime.now(timezone.utc).isoformat()
    with db:
        for row in rows:
            db.execute(
                """UPDATE audio_files SET spotify_id=?, scan_status='matched',
                   match_method='isrc_recovery', match_confidence=1.0, updated_at=?
                   WHERE path=?""",
                (row["spotify_id"], now, row["path"]),
            )
    return len(rows)


def synthesize_local_only(db, limit: int) -> tuple[int, int, int]:
    rows = db.execute(
        f"""SELECT path,title,artist_names,album,duration_seconds FROM audio_files
            WHERE spotify_id IS NULL
              AND duration_seconds IS NOT NULL AND duration_seconds <= {MAX_DURATION_SECONDS}
            ORDER BY path LIMIT ?""",
        (limit,),
    ).fetchall()
    now = datetime.now(timezone.utc).isoformat()
    created = 0
    with db:
        for row in rows:
            sid = local_id(row["path"])
            db.execute(
                """INSERT INTO tracks
                (spotify_id,uri,title,album,duration_ms,artist_names,artist_ids,
                 genres,library_sources,first_seen_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(spotify_id) DO NOTHING""",
                (
                    sid, f"local:{row['path']}", row["title"] or "", row["album"] or "",
                    int(round((row["duration_seconds"] or 0) * 1000)),
                    row["artist_names"] or "", "", "", "local_only", now, now,
                ),
            )
            db.execute(
                """UPDATE audio_files SET spotify_id=?, scan_status='matched',
                   match_method='local_only_synthetic', match_confidence=1.0, updated_at=?
                   WHERE path=?""",
                (sid, now, row["path"]),
            )
            created += 1
    skipped_long = db.execute(
        "SELECT COUNT(*) FROM audio_files WHERE spotify_id IS NULL AND duration_seconds > ?",
        (MAX_DURATION_SECONDS,),
    ).fetchone()[0]
    skipped_unknown = db.execute(
        "SELECT COUNT(*) FROM audio_files WHERE spotify_id IS NULL AND duration_seconds IS NULL"
    ).fetchone()[0]
    return created, skipped_long, skipped_unknown


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100000)
    args = parser.parse_args()
    db = connect()
    recovered = recover_by_isrc(db)
    created, skipped_long, skipped_unknown = synthesize_local_only(db, args.limit)
    print(
        f"isrc_recovered={recovered} synthesized={created} "
        f"skipped_long(>{MAX_DURATION_SECONDS}s)={skipped_long} skipped_unknown_duration={skipped_unknown}"
    )


if __name__ == "__main__":
    main()
