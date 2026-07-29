#!/usr/bin/env python3
"""Undo fuzzy file->track matches that a now-known duration proves wrong.

WHY: `index_audio_files.match()` scores duration at a neutral 0.5 when the
file's duration is unknown at index time, so a strong artist+title agreement
alone can cross the acceptance threshold. Durations are filled in later (tag
re-reads, ffprobe verification), and some of those matches then turn out to
pair, say, a 196 s radio edit with a 450 s extended mix — the same song but a
different recording. Analyzing one and filing the result under the other is
exactly the "wrong metadata is worse than missing metadata" failure D-006
exists to prevent.

WHAT: demote such matches to unmatched. `promote_unmatched_local_tracks.py`
then gives the file its own local-only identity, so its analysis describes
the recording it actually came from. Any audio artifacts already imported
under the wrong track are removed, since they describe a different recording.

SCOPE: only `title_artist_duration` matches. An `isrc_tag` match is an
identity assertion by the publisher; differing masters under one ISRC are a
labelling reality, not a mismatch this script should second-guess.

HOW TO TWEAK: --tolerance is the allowed drift in seconds (default 20, the
point at which the matcher itself already scores duration as zero).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone

from musicdb import connect

FUZZY = "title_artist_duration"
STAGES = ("rhythm_full", "maest_full", "essentia_full", "clap_full")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tolerance", type=float, default=20.0)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    db = connect()
    rows = db.execute(
        """SELECT f.path, f.spotify_id, f.duration_seconds,
                  t.duration_ms/1000.0 AS catalog_seconds, f.title
           FROM audio_files f JOIN tracks t USING(spotify_id)
           WHERE f.match_method = ?
             AND f.duration_seconds IS NOT NULL AND t.duration_ms IS NOT NULL
             AND ABS(f.duration_seconds - t.duration_ms/1000.0) > ?""",
        (FUZZY, args.tolerance),
    ).fetchall()
    if args.dry_run:
        for row in rows[:10]:
            print(f"  {row['duration_seconds']:.0f}s vs {row['catalog_seconds']:.0f}s  "
                  f"{(row['title'] or '?')[:50]}")
        print(f"would demote {len(rows)} mismatched fuzzy matches")
        return
    now = datetime.now(timezone.utc).isoformat()
    dropped_artifacts = 0
    with db:
        for row in rows:
            # Only strip artifacts produced from THIS file; another file may
            # legitimately back the same track.
            cur = db.execute(
                f"""DELETE FROM audio_analysis_artifacts
                    WHERE spotify_id=? AND path=? AND stage IN {STAGES}""",
                (row["spotify_id"], row["path"]),
            )
            dropped_artifacts += cur.rowcount
            db.execute(
                """UPDATE audio_files
                   SET spotify_id=NULL, scan_status='indexed',
                       match_method='duration_conflict', match_confidence=0.0,
                       updated_at=?
                   WHERE path=?""",
                (now, row["path"]),
            )
    print(f"demoted={len(rows)} artifacts_removed={dropped_artifacts} "
          f"(re-run promote_unmatched_local_tracks.py to give them local identities)")


if __name__ == "__main__":
    main()
