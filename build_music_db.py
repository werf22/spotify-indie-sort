"""Import the existing Spotify library export into the local DJ database."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from musicdb import connect

ROOT = Path(__file__).resolve().parent
tracks = json.loads((ROOT / "data" / "library_export.json").read_text())
now = datetime.now(timezone.utc).isoformat()
conn = connect()
with conn:
    for t in tracks:
        artists = t.get("artists", [])
        conn.execute(
            """INSERT INTO tracks
            (spotify_id,uri,title,album,spotify_url,artist_names,artist_ids,genres,library_sources,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(spotify_id) DO UPDATE SET
              uri=excluded.uri,title=excluded.title,album=excluded.album,
              artist_names=excluded.artist_names,artist_ids=excluded.artist_ids,
              genres=excluded.genres,library_sources=excluded.library_sources,
              updated_at=excluded.updated_at""",
            (
                t["id"], t["uri"], t.get("name", ""), t.get("album", ""),
                f"https://open.spotify.com/track/{t['id']}",
                ", ".join(str(a.get("name") or "") for a in artists),
                ", ".join(str(a.get("id") or "") for a in artists),
                ", ".join(str(g or "") for g in t.get("genres", [])),
                " | ".join(dict.fromkeys(t.get("sources", []))), now,
            ),
        )
    conn.execute(
        "INSERT OR REPLACE INTO source_runs VALUES (?,?,?,?)",
        ("spotify_library_export", now, len(tracks), "Imported from data/library_export.json"),
    )
print(f"Imported {len(tracks):,} tracks into {conn.execute('PRAGMA database_list').fetchone()[2]}")
print("Search example: python query_music.py 'melodic indie 115 bpm'")
