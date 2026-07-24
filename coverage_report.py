"""Print current enrichment coverage, separating real provider data from inference."""
from __future__ import annotations

from musicdb import connect


LOCAL_ONLY_FILTER = "spotify_id NOT LIKE 'local\\_%' ESCAPE '\\'"


def catalog_only(query: str) -> str:
    """Exclude synthetic local-only tracks (D-029) so percentages stay
    against the real 68,075-track Spotify catalog, not inflated by files
    that were never in it. Every metric query below reads a table with a
    spotify_id column, so this is a safe blanket append."""
    return f"{query} AND {LOCAL_ONLY_FILTER}" if " WHERE " in query else f"{query} WHERE {LOCAL_ONLY_FILTER}"


def main() -> None:
    db = connect()
    total = db.execute(catalog_only("SELECT COUNT(*) FROM tracks")).fetchone()[0]
    local_only = db.execute("SELECT COUNT(*) FROM tracks WHERE library_sources='local_only'").fetchone()[0]
    metrics = [
        ("Spotify legacy genres", "SELECT COUNT(*) FROM tracks WHERE genres<>''"),
        ("Any genre tag", "SELECT COUNT(DISTINCT spotify_id) FROM tags WHERE tag_type='genre'"),
        ("Any tag", "SELECT COUNT(DISTINCT spotify_id) FROM tags"),
        ("Mood tag", "SELECT COUNT(DISTINCT spotify_id) FROM tags WHERE tag_type='mood'"),
        ("Instrument tag", "SELECT COUNT(DISTINCT spotify_id) FROM tags WHERE tag_type='instrument'"),
        ("Voice tag", "SELECT COUNT(DISTINCT spotify_id) FROM tags WHERE tag_type='voice'"),
        ("BPM", "SELECT COUNT(*) FROM track_profile WHERE bpm IS NOT NULL"),
        ("Key", "SELECT COUNT(*) FROM track_profile WHERE musical_key IS NOT NULL"),
        ("Energy (any)", "SELECT COUNT(*) FROM track_profile WHERE energy IS NOT NULL"),
        ("Danceability (any)", "SELECT COUNT(*) FROM track_profile WHERE danceability IS NOT NULL"),
        ("Valence/happiness (any)", "SELECT COUNT(*) FROM track_profile WHERE valence IS NOT NULL"),
        ("Energy measured", "SELECT COUNT(DISTINCT spotify_id) FROM audio_features WHERE energy IS NOT NULL AND source<>'spotify:playlist-inference'"),
        ("Danceability measured", "SELECT COUNT(DISTINCT spotify_id) FROM audio_features WHERE danceability IS NOT NULL AND source<>'spotify:playlist-inference'"),
        ("Valence measured", "SELECT COUNT(DISTINCT spotify_id) FROM audio_features WHERE valence IS NOT NULL AND source<>'spotify:playlist-inference'"),
        ("Label", "SELECT COUNT(*) FROM tracks WHERE label IS NOT NULL AND label<>''"),
        ("Release date", "SELECT COUNT(*) FROM tracks WHERE release_date IS NOT NULL AND release_date<>''"),
        ("Duration", "SELECT COUNT(*) FROM tracks WHERE duration_ms IS NOT NULL"),
        ("ISRC", "SELECT COUNT(*) FROM tracks WHERE isrc IS NOT NULL AND isrc<>''"),
        ("MusicBrainz ID", "SELECT COUNT(*) FROM tracks WHERE musicbrainz_id IS NOT NULL AND musicbrainz_id<>''"),
    ]
    print(f"Tracks: {total:,}  (+ {local_only:,} local-only, not in the Spotify catalog)\n")
    width = max(len(name) for name, _ in metrics)
    for name, query in metrics:
        count = db.execute(catalog_only(query)).fetchone()[0]
        pct = count * 100 / total if total else 0
        print(f"{name:<{width}}  {count:>7,}  {pct:6.2f}%")

    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "freqblog_status" in tables:
        print("\nFreqBlog Starter")
        statuses = dict(db.execute("SELECT status,COUNT(*) FROM freqblog_status GROUP BY status"))
        successful = statuses.get("success", 0)
        for status in ("success", "queued", "processing", "failed", "quota_wait", "needs_review", "not_found"):
            if statuses.get(status):
                print(f"  {status:<14} {statuses[status]:>7,}")
        print(f"  {'untouched':<14} {max(0, total-sum(statuses.values())):>7,}")
        print(f"  {'coverage':<14} {successful*100/total if total else 0:>6.2f}%")
        if "freqblog_usage_runs" in tables:
            usage = db.execute(
                """SELECT COALESCE(SUM(selected),0),COALESCE(SUM(enriched),0),
                          COALESCE(SUM(reused),0),
                          COALESCE(SUM(MAX(quota_requests,selected-COALESCE(reused,0))),0)
                   FROM freqblog_usage_runs
                   WHERE substr(started_at,1,7)=strftime('%Y-%m','now')"""
            ).fetchone()
            print(f"  API selections {usage[0]:>7,}  enriched {usage[1]:>7,}  local reuse {usage[2]:>7,}")
            print(f"  tracked calls  {usage[3]:>6,} / 150,000")

    if "reccobeats_status" in tables:
        print("\nReccoBeats exact Spotify-ID audio features")
        statuses = dict(db.execute("SELECT status,COUNT(*) FROM reccobeats_status GROUP BY status"))
        successful = statuses.get("success", 0)
        for status in ("success", "mapped", "failed", "not_found"):
            if statuses.get(status):
                print(f"  {status:<14} {statuses[status]:>7,}")
        print(f"  {'untouched':<14} {max(0, total-sum(statuses.values())):>7,}")
        print(f"  {'coverage':<14} {successful*100/total if total else 0:>6.2f}%")

    if "onetagger_enrichment_status" in tables:
        print("\nOneTagger SQL bridge / Discogs v2")
        statuses = dict(db.execute(
            "SELECT status,COUNT(*) FROM onetagger_enrichment_status "
            "WHERE source='discogs_v2' GROUP BY status"
        ))
        for status in ("success", "no_match", "processing", "failed"):
            if statuses.get(status):
                print(f"  {status:<14} {statuses[status]:>7,}")
        print(f"  {'untouched':<14} {max(0, total-sum(statuses.values())):>7,}")

    if "deezer_status" in tables:
        print("\nDeezer exact-ISRC metadata")
        statuses = dict(db.execute("SELECT status,COUNT(*) FROM deezer_status GROUP BY status"))
        for status in ("success", "not_found", "failed"):
            if statuses.get(status):
                print(f"  {status:<14} {statuses[status]:>7,}")
        print(f"  {'untouched':<14} {max(0, total-sum(statuses.values())):>7,}")


if __name__ == "__main__":
    main()
