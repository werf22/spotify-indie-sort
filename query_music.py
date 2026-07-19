"""Small CLI for testing local DJ-library search."""
from __future__ import annotations

import sys
from musicdb import connect

q = " ".join(sys.argv[1:]).strip()
if not q:
    raise SystemExit("Usage: python query_music.py 'artist OR genre OR title'")
conn = connect()
rows = conn.execute(
    """SELECT t.title, t.artist_names, t.album, t.genres, t.library_sources,
              t.spotify_url
       FROM track_search s JOIN tracks t ON t.rowid=s.rowid
       WHERE track_search MATCH ? ORDER BY rank LIMIT 50""",
    (q,),
).fetchall()
for r in rows:
    print(f"{r['title']} — {r['artist_names']} | {r['genres']} | {r['spotify_url']}")
print(f"\n{len(rows)} results")
