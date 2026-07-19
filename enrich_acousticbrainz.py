"""Enrich tracks matched to MusicBrainz with free AcousticBrainz features."""
from __future__ import annotations
import argparse,json,time
from datetime import datetime,timezone
from urllib.request import Request,urlopen
from musicdb import connect, record_source_run

def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--limit',type=int,default=1000); ap.add_argument('--delay',type=float,default=.15); a=ap.parse_args(); db=connect()
 rows=db.execute("SELECT * FROM tracks WHERE musicbrainz_id IS NOT NULL AND spotify_id NOT IN (SELECT spotify_id FROM audio_features WHERE source='acousticbrainz') LIMIT ?",(a.limit,)).fetchall(); ok=err=0
 for r in rows:
  try:
   mb=r['musicbrainz_id']; req=Request(f'https://acousticbrainz.org/api/v1/{mb}/high-level',headers={'User-Agent':'local-dj-music-db/1.0'}); data=json.loads(urlopen(req,timeout=30).read()); hi=data.get('highlevel',{})
   def val(k):
    x=hi.get(k,{}); return x.get('all',{}).get('value') if isinstance(x,dict) else None
   with db:
    db.execute("INSERT OR REPLACE INTO audio_features(spotify_id,source,source_id,danceability,energy,valence,acousticness,instrumentalness,speechiness,liveness,confidence,raw_json,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",(r['spotify_id'],'acousticbrainz',mb,val('danceability'),val('energy'),val('valence'),val('acousticness'),val('instrumentalness'),val('speechiness'),val('liveness'),None,json.dumps(data),datetime.now(timezone.utc).isoformat()))
    for key in ('genre_rosamerica','mood_happy','mood_sad','mood_aggressive','mood_relaxed','voice_instrumental','timbre'):
     x=hi.get(key,{}); value=x.get('value') if isinstance(x,dict) else None
     if value: db.execute('INSERT OR IGNORE INTO tags VALUES (?,?,?,?,?)',(r['spotify_id'],str(value).lower(),key,'acousticbrainz',None))
   ok+=1
  except Exception as e: err+=1
  time.sleep(a.delay)
 record_source_run(db,'acousticbrainz',datetime.now(timezone.utc).isoformat(),ok,f'errors={err}')
 print(f'AcousticBrainz: enriched {ok:,}, errors {err:,}')
if __name__=='__main__': main()
