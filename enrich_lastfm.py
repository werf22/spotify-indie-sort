"""Resumable Last.fm tag enrichment. Uses the free track.getInfo endpoint."""
from __future__ import annotations
import argparse, json, os, time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from dotenv import load_dotenv
from musicdb import connect, record_source_run

load_dotenv()
API = "https://ws.audioscrobbler.com/2.0/"

def call(artist, track, key):
    q = urlencode({"method":"track.getInfo", "api_key":key, "artist":artist,
                   "track":track, "autocorrect":1, "format":"json"})
    req = Request(API + "?" + q, headers={"User-Agent":"local-dj-music-db/1.0"})
    with urlopen(req, timeout=30) as r: return json.loads(r.read())

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--limit",type=int,default=250); ap.add_argument("--delay",type=float,default=0.25); args=ap.parse_args()
    key=os.getenv("LASTFM_API_KEY");
    if not key: raise SystemExit("LASTFM_API_KEY is missing in .env")
    db=connect(); rows=db.execute("SELECT * FROM tracks WHERE spotify_id NOT IN (SELECT spotify_id FROM tags WHERE source='last.fm') LIMIT ?",(args.limit,)).fetchall()
    done=errors=0
    for r in rows:
        artist=(r["artist_names"] or "").split(",")[0].strip()
        try:
            data=call(artist,r["title"],key); tags=data.get("track",{}).get("toptags",{}).get("tag",[])
            with db:
                for tag in tags[:30]:
                    name=(tag.get("name") or "").strip().lower()
                    if name: db.execute("INSERT OR IGNORE INTO tags VALUES (?,?,?,?,?)",(r["spotify_id"],name,"genre","last.fm",None))
            done+=1
        except Exception as e:
            errors+=1; print(f"warning: {artist} — {r['title']}: {e}")
        time.sleep(args.delay)
    record_source_run(db,"last.fm",datetime.now(timezone.utc).isoformat(),done,f"errors={errors}")
    print(f"Last.fm: enriched {done:,}, errors {errors:,}")
if __name__=="__main__": main()
