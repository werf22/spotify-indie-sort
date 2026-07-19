"""Apply free Last.fm artist top tags to every track by that artist."""
from __future__ import annotations
import argparse,json,os,time
from datetime import datetime,timezone
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from dotenv import load_dotenv
from musicdb import connect,record_source_run
load_dotenv();API='https://ws.audioscrobbler.com/2.0/'
MOODS={'happy','sad','melancholic','melancholy','chill','relaxing','relaxed','energetic','dark','euphoric','uplifting','dreamy','atmospheric','emotional','romantic','calm','aggressive','peaceful','mellow','moody'}
INSTR={'piano','guitar','acoustic guitar','electric guitar','violin','cello','saxophone','flute','drums','percussion','synthesizer','strings','brass','bass'}
VOICE={'instrumental','female vocalists','male vocalists','female vocalist','male vocalist','vocal','vocals','choir','spoken word'}
def kind(tag):
 t=tag.lower();return 'mood' if t in MOODS else 'instrument' if t in INSTR else 'voice' if t in VOICE else 'genre'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=150);ap.add_argument('--delay',type=float,default=.25);a=ap.parse_args();key=os.getenv('LASTFM_API_KEY');db=connect();now=datetime.now(timezone.utc).isoformat()
 db.execute("CREATE TABLE IF NOT EXISTS lastfm_artist_status(artist_name TEXT PRIMARY KEY,status TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT,updated_at TEXT NOT NULL)")
 by={}
 for r in db.execute('SELECT spotify_id,artist_names FROM tracks'):
  artist=(r['artist_names'] or '').split(',')[0].strip()
  if artist:by.setdefault(artist,[]).append(r['spotify_id'])
 done={r[0] for r in db.execute("SELECT artist_name FROM lastfm_artist_status WHERE status IN ('success','no_tags')")};artists=[x for x in by if x not in done][:a.limit];ok=none=errors=0
 for artist in artists:
  try:
   q=urlencode({'method':'artist.getTopTags','api_key':key,'artist':artist,'autocorrect':1,'format':'json'});req=Request(API+'?'+q,headers={'User-Agent':'local-dj-music-db/1.0'});data=json.loads(urlopen(req,timeout=30).read());ts=(data.get('toptags') or {}).get('tag') or [];top=max([int(x.get('count') or 0) for x in ts] or [1]);vals=[]
   for x in ts[:30]:
    name=(x.get('name') or '').strip().lower();count=int(x.get('count') or 0);conf=max(.15,min(1.0,count/top))
    if name:
     for sid in by[artist]:vals.append((sid,name,kind(name),'last.fm:artist',conf))
   with db:
    if vals:db.executemany('INSERT OR IGNORE INTO tags VALUES(?,?,?,?,?)',vals)
    db.execute("INSERT OR REPLACE INTO lastfm_artist_status VALUES(?,?,?,?,?)",(artist,'success' if vals else 'no_tags',1,None,now))
   ok+=bool(vals);none+=not bool(vals)
  except Exception as e:
   with db:db.execute("INSERT INTO lastfm_artist_status VALUES(?,'failed',1,?,?) ON CONFLICT(artist_name) DO UPDATE SET status='failed',attempts=attempts+1,last_error=excluded.last_error,updated_at=excluded.updated_at",(artist,str(e),now))
   errors+=1
  time.sleep(a.delay)
 record_source_run(db,'last.fm:artist',now,ok,f'no_tags={none},errors={errors}');print(f'Last.fm artists: tagged={ok}, no_tags={none}, errors={errors}')
if __name__=='__main__':main()
