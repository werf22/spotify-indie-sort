"""Resolve Spotify history rows that were not in the library export."""
from __future__ import annotations
import argparse,re,time
from datetime import datetime,timezone
from spotify_client import SpotifyClient
from musicdb import connect
def norm(s): return re.sub(r"[^a-z0-9]+"," ",(s or "").casefold()).strip()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=200);ap.add_argument('--delay',type=float,default=.1);a=ap.parse_args();db=connect();sp=SpotifyClient()
 rows=db.execute("select title,artist_names from stream_events where spotify_id is null group by title,artist_names order by max(ms_played) desc limit ?",(a.limit,)).fetchall();resolved=failed=0
 for r in rows:
  try:
   q=f'track:"{r["title"]}" artist:"{r["artist_names"]}"'; data=sp.request('GET','/search',params={'q':q,'type':'track','limit':10}).json(); items=data.get('tracks',{}).get('items',[]); hit=None
   for x in items:
    names=[z.get('name','') for z in x.get('artists',[])]
    if norm(x.get('name'))==norm(r['title']) and any(norm(r['artist_names'])==norm(n) or norm(r['artist_names']) in norm(n) or norm(n) in norm(r['artist_names']) for n in names): hit=x;break
   if not hit: continue
   sid=hit['id']; now=datetime.now(timezone.utc).isoformat(); artists=hit.get('artists',[]); sources='spotify:stream_history'
   with db:
    db.execute("insert or ignore into tracks(spotify_id,uri,title,album,spotify_url,artist_names,artist_ids,genres,library_sources,updated_at) values(?,?,?,?,?,?,?,?,?,?)",(sid,hit.get('uri'),hit.get('name',''),hit.get('album',{}).get('name',''),f'https://open.spotify.com/track/{sid}',', '.join(x.get('name','') for x in artists),', '.join(x.get('id','') for x in artists),'',sources,now))
    db.execute("update stream_events set spotify_id=? where spotify_id is null and title=? and artist_names=?",(sid,r['title'],r['artist_names']))
   resolved+=1
  except Exception as e: failed+=1;print(f'warning: {r["artist_names"]} — {r["title"]}: {e}')
  time.sleep(a.delay)
 print(f'Stream history resolution: tracks={resolved}, failed={failed}')
if __name__=='__main__':main()
