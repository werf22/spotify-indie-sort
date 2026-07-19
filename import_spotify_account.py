"""Import Spotify Account Data playlists and saved library into music.db."""
from __future__ import annotations
import hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path
from musicdb import connect

def track_id(t):
    uri=t.get("trackUri") or t.get("uri") or ""
    return uri.rsplit(":",1)[-1] if "spotify:track:" in uri else None
def main():
    root=Path(sys.argv[1] if len(sys.argv)>1 else "/Users/jakub/Downloads/Spotify Data/Spotify Account Data")
    db=connect(); db.executescript("""
      CREATE TABLE IF NOT EXISTS playlists(
        playlist_id TEXT PRIMARY KEY, name TEXT NOT NULL, source_file TEXT NOT NULL,
        last_modified TEXT, item_count INTEGER NOT NULL, imported_at TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS playlist_tracks(
        playlist_id TEXT NOT NULL, spotify_id TEXT, position INTEGER NOT NULL,
        added_at TEXT, track_name TEXT, artist_name TEXT, album_name TEXT,
        PRIMARY KEY(playlist_id,position));
      CREATE INDEX IF NOT EXISTS idx_playlist_tracks_spotify ON playlist_tracks(spotify_id);
    """)
    imported=members=library=0; now=datetime.now(timezone.utc).isoformat()
    with db:
      for f in sorted(root.glob("Playlist*.json")):
        data=json.loads(f.read_text())
        for pi,p in enumerate(data.get("playlists",[])):
          name=p.get("name") or f"{f.stem} #{pi+1}"; pid="spotify-export:"+hashlib.sha1(f"{f.name}\0{pi}\0{name}".encode()).hexdigest()[:24]
          items=p.get("items",[]); db.execute("INSERT OR REPLACE INTO playlists VALUES(?,?,?,?,?,?)",(pid,name,f.name,p.get("lastModifiedDate"),len(items),now)); imported+=1
          for pos,item in enumerate(items):
            t=item.get("track") or {}; sid=track_id(t); db.execute("INSERT OR REPLACE INTO playlist_tracks VALUES(?,?,?,?,?,?,?)",(pid,sid,pos,item.get("addedDate"),t.get("trackName"),t.get("artistName"),t.get("albumName"))); members+=1
            if sid:
              row=db.execute("SELECT library_sources FROM tracks WHERE spotify_id=?",(sid,)).fetchone()
              if row:
                src=(row[0] or "").split(" | "); marker=f"playlist:{name}"
                if marker not in src: src.append(marker); db.execute("UPDATE tracks SET library_sources=?,updated_at=? WHERE spotify_id=?",(" | ".join(src),now,sid))
      lib=json.loads((root/"YourLibrary.json").read_text())
      for t in lib.get("tracks",[]):
        uri=t.get("uri",""); sid=uri.rsplit(":",1)[-1] if "spotify:track:" in uri else None
        if sid:
          row=db.execute("SELECT library_sources FROM tracks WHERE spotify_id=?",(sid,)).fetchone()
          if row:
            src=(row[0] or "").split(" | ");
            if "spotify:saved-library" not in src: src.append("spotify:saved-library"); db.execute("UPDATE tracks SET library_sources=?,updated_at=? WHERE spotify_id=?",(" | ".join(src),now,sid))
          library+=1
      db.execute("INSERT OR REPLACE INTO source_runs VALUES(?,?,?,?)",("spotify_account_export",now,members,f"playlists={imported},saved_library={library},path={root}"))
    print(f"Spotify account: playlists={imported:,}, playlist_memberships={members:,}, saved_library_matches={library:,}")
if __name__=="__main__": main()
