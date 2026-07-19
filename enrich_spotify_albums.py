"""Resumable Spotify album metadata enrichment for label/release data."""
from __future__ import annotations
import argparse,json,time
from datetime import datetime,timezone
from spotify_client import SpotifyClient
from musicdb import connect,record_source_run
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=150);ap.add_argument('--delay',type=float,default=.05);a=ap.parse_args();db=connect();sp=SpotifyClient();now=datetime.now(timezone.utc).isoformat()
 db.execute("CREATE TABLE IF NOT EXISTS spotify_albums(album_id TEXT PRIMARY KEY,name TEXT,release_date TEXT,label TEXT,raw_json TEXT,updated_at TEXT NOT NULL)")
 rows=db.execute("SELECT DISTINCT album_id FROM tracks WHERE album_id IS NOT NULL AND album_id NOT IN (SELECT album_id FROM spotify_albums) LIMIT ?",(a.limit,)).fetchall();ok=errors=0
 for row in rows:
  aid=row['album_id']
  try:
   d=sp.request('GET',f'/albums/{aid}').json();label=d.get('label');release=d.get('release_date')
   with db:
    db.execute("INSERT OR REPLACE INTO spotify_albums VALUES(?,?,?,?,?,?)",(aid,d.get('name'),release,label,json.dumps(d,ensure_ascii=False),now))
    db.execute("UPDATE tracks SET label=COALESCE(?,label),release_date=COALESCE(?,release_date),updated_at=? WHERE album_id=?",(label,release,now,aid))
    if label:db.execute("INSERT OR IGNORE INTO tags SELECT spotify_id,?,'label','spotify',1.0 FROM tracks WHERE album_id=?",(label.lower(),aid))
   ok+=1
  except Exception as e:errors+=1
  time.sleep(a.delay)
 record_source_run(db,'spotify_album_metadata',now,ok,f'errors={errors}');print(f'Spotify albums: enriched={ok}, errors={errors}')
if __name__=='__main__':main()
