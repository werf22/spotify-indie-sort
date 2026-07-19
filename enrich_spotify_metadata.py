"""Resumable authoritative Spotify track metadata enrichment."""
from __future__ import annotations
import argparse,json,time
from datetime import datetime,timezone
from spotify_client import SpotifyClient
from musicdb import connect,record_source_run
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=250);ap.add_argument('--delay',type=float,default=.05);a=ap.parse_args();db=connect();sp=SpotifyClient();now=datetime.now(timezone.utc).isoformat()
 db.executescript("CREATE TABLE IF NOT EXISTS spotify_metadata_status(spotify_id TEXT PRIMARY KEY,status TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT,updated_at TEXT NOT NULL); CREATE TABLE IF NOT EXISTS spotify_albums(album_id TEXT PRIMARY KEY,name TEXT,release_date TEXT,label TEXT,raw_json TEXT,updated_at TEXT NOT NULL);")
 rows=db.execute("SELECT t.spotify_id FROM tracks t LEFT JOIN spotify_metadata_status s USING(spotify_id) WHERE COALESCE(s.status,'')<>'success' ORDER BY t.spotify_id LIMIT ?",(a.limit,)).fetchall();ok=errors=0
 for row in rows:
  sid=row['spotify_id']
  try:
   d=sp.request('GET',f'/tracks/{sid}').json();album=d.get('album') or {};artists=d.get('artists') or [];isrc=(d.get('external_ids') or {}).get('isrc')
   with db:
    db.execute("UPDATE tracks SET uri=?,title=?,album=?,album_id=?,duration_ms=?,release_date=?,isrc=?,popularity=?,explicit=?,artist_names=?,artist_ids=?,updated_at=? WHERE spotify_id=?",(d.get('uri'),d.get('name',''),album.get('name'),album.get('id'),d.get('duration_ms'),album.get('release_date'),isrc,d.get('popularity'),int(bool(d.get('explicit'))),', '.join(x.get('name','') for x in artists),', '.join(x.get('id','') for x in artists),now,sid))
    db.execute("INSERT OR REPLACE INTO spotify_metadata_status VALUES(?,'success',COALESCE((SELECT attempts FROM spotify_metadata_status WHERE spotify_id=?),0)+1,NULL,?)",(sid,sid,now))
   ok+=1
  except Exception as e:
   with db:db.execute("INSERT INTO spotify_metadata_status VALUES(?,'failed',1,?,?) ON CONFLICT(spotify_id) DO UPDATE SET status='failed',attempts=attempts+1,last_error=excluded.last_error,updated_at=excluded.updated_at",(sid,str(e),now))
   errors+=1
  time.sleep(a.delay)
 record_source_run(db,'spotify_track_metadata',now,ok,f'errors={errors}');print(f'Spotify metadata: enriched={ok}, errors={errors}')
if __name__=='__main__':main()
