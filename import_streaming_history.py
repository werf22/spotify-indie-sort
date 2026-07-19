"""Import Spotify Extended Streaming History JSON files into music.db.

Usage: python import_streaming_history.py /path/to/spotify-data.zip
       python import_streaming_history.py /path/to/unzipped-folder
"""
from __future__ import annotations

import hashlib, json, sys, zipfile
from pathlib import Path
from musicdb import connect

ROOT = Path(__file__).resolve().parent

def files_from(path: Path):
    if path.is_file() and path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as z:
            for n in z.namelist():
                if Path(n).name.lower().startswith(("endsong", "streaminghistory")) and n.endswith(".json"):
                    yield n, z.open(n)
    else:
        for p in path.rglob("*.json"):
            if p.name.lower().startswith(("endsong", "streaminghistory")):
                yield str(p), p.open("rb")

def norm(s):
    return " ".join((s or "").casefold().split())

def main():
    if len(sys.argv) != 2:
        raise SystemExit("Pass ZIP or extracted Spotify data directory")
    source = Path(sys.argv[1]).expanduser()
    conn = connect()
    lookup = {(norm(r["title"]), norm(r["artist_names"].split(",")[0])): r["spotify_id"]
              for r in conn.execute("SELECT spotify_id,title,artist_names FROM tracks")}
    imported = 0
    with conn:
        for name, fh in files_from(source):
            rows = json.load(fh)
            for r in rows:
                uri = r.get("spotify_track_uri") or r.get("trackUri") or ""
                sid = uri.rsplit(":", 1)[-1] if "spotify:track:" in uri else None
                title = r.get("master_metadata_track_name") or r.get("trackName") or ""
                artist = r.get("master_metadata_album_artist_name") or r.get("artistName") or ""
                sid = sid or lookup.get((norm(title), norm(artist)))
                played = r.get("ts") or r.get("endTime") or ""
                ms = r.get("ms_played", r.get("msPlayed"))
                payload = json.dumps(r, ensure_ascii=False, sort_keys=True)
                digest = hashlib.sha256((played + "\0" + title + "\0" + artist + "\0" + str(ms)).encode()).hexdigest()
                conn.execute("""INSERT OR IGNORE INTO stream_events
                    (event_hash,played_at,spotify_id,title,artist_names,ms_played,skipped,offline,shuffle,platform,raw_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""", (digest, played, sid, title, artist, ms,
                    int(bool(r.get("skipped"))) if r.get("skipped") is not None else None,
                    int(bool(r.get("offline"))) if r.get("offline") is not None else None,
                    int(bool(r.get("shuffle"))) if r.get("shuffle") is not None else None,
                    r.get("platform"), payload))
                imported += conn.execute("SELECT changes()").fetchone()[0]
        conn.execute("INSERT OR REPLACE INTO source_runs VALUES (?,?,?,?)",
                     ("spotify_streaming_history", __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(), imported, str(source)))
    print(f"Imported {imported:,} new streaming events")
    print(f"Tracks with history: {conn.execute('SELECT COUNT(*) FROM track_play_stats').fetchone()[0]:,}")

if __name__ == "__main__": main()
