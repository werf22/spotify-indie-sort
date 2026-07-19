"""Compact progress report for the restart-safe local audio pipeline."""
from __future__ import annotations

from musicdb import connect

RHYTHM_VERSION = "rhythm-v1.0.4"
MAEST_KEY = "mtg-upf/discogs-maest-10s-dw-75e@maest-discogs400-v1.0.2"
CLAP_KEY = "laion/larger_clap_music@clap-taxonomy-v1.1.0"


def scalar(db, sql: str, params=()) -> int:
    return int(db.execute(sql, params).fetchone()[0] or 0)


def main() -> None:
    db = connect()
    tracks = scalar(db, "SELECT COUNT(*) FROM tracks")
    files = scalar(db, "SELECT COUNT(*) FROM audio_files")
    matched_files = scalar(db, "SELECT COUNT(*) FROM audio_files WHERE scan_status='matched'")
    matched_tracks = scalar(db, "SELECT COUNT(DISTINCT spotify_id) FROM audio_files WHERE scan_status='matched'")
    rhythm = scalar(db, "SELECT COUNT(DISTINCT spotify_id) FROM local_audio_analysis WHERE analyzer_version=?", (RHYTHM_VERSION,))
    maest = scalar(db, "SELECT COUNT(DISTINCT spotify_id) FROM audio_embeddings WHERE model=?", (MAEST_KEY,))
    clap = scalar(db, "SELECT COUNT(DISTINCT spotify_id) FROM audio_embeddings WHERE model=?", (CLAP_KEY,))
    print(f"Library tracks:              {tracks:,}")
    print(f"Indexed local audio files:   {files:,}")
    print(f"Matched files / tracks:      {matched_files:,} / {matched_tracks:,}")
    print(f"Rhythm current version:      {rhythm:,} / {matched_tracks:,}")
    print(f"MAEST genre current version: {maest:,} / {matched_tracks:,}")
    print(f"CLAP mood current version:   {clap:,} / {matched_tracks:,}")
    print("Rhythm classes:")
    rows = db.execute(
        """SELECT rhythm_pattern,COUNT(DISTINCT spotify_id)
           FROM local_audio_analysis WHERE analyzer_version=?
           GROUP BY rhythm_pattern ORDER BY 2 DESC""",
        (RHYTHM_VERSION,),
    )
    for label, count in rows:
        print(f"  {label or 'unknown':24s} {count:,}")


if __name__ == "__main__":
    main()
