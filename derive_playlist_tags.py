"""Derive low-confidence genre/mood/audio priors from Spotify playlist names."""
from __future__ import annotations
import re
from collections import defaultdict
from datetime import datetime,timezone
from musicdb import connect,record_source_run

GENRES=['afro house','organic house','melodic techno','melodic house','deep house','tropical house','tribal house','progressive house','tech house','afro tech','uk garage','speed garage','liquid dnb','drum and bass','breakbeat','downtempo','indie folk','indie rock','indie pop','indie dance','synthpop','new wave','psytrance','reggaeton','dancehall','afrobeats','afrobeat','amapiano','gqom','baile funk','brazilian funk','hip hop','trap','grime','drill','house','techno','ambient','classical','piano','acoustic','folk','jazz','rock','pop','soul','funk','reggae','latin','world','electronica','experimental','chillstep','dubstep','trance']
MOODS=['happy','dark','chill','euphoric','uplifting','atmospheric','melancholic','emotional','sensual','nostalgic','energetic','relaxed','psychedelic','spiritual','ritual','sunny','positive','aggressive','peaceful','dreamy']
INSTR=['piano','guitar','strings','percussion','saxophone','violin','cello','flute','drums']
def clean(s):return ' '.join(re.sub(r'[^a-z0-9]+',' ',(s or '').casefold()).split())
def main():
 db=connect(); hints=defaultdict(lambda:{'e':[],'v':[],'d':[]});tag_rows=[]
 for r in db.execute('SELECT pt.spotify_id,p.name FROM playlist_tracks pt JOIN playlists p USING(playlist_id) WHERE pt.spotify_id IS NOT NULL'):
  sid=r['spotify_id'];n=clean(r['name'])
  for g in GENRES:
   if g in n:tag_rows.append((sid,g,'genre','spotify:playlist-inference',.55))
  for m in MOODS:
   if m in n:tag_rows.append((sid,m,'mood','spotify:playlist-inference',.5))
  for x in INSTR:
   if x in n:tag_rows.append((sid,x,'instrument','spotify:playlist-inference',.55))
  for key,dest in [('energy','e'),('happiness','v'),('dance','d')]:
   m=re.search(rf'\b{key}\s*(\d{{1,3}})\b',n)
   if m:hints[sid][dest].append(min(1,float(m.group(1))/100))
  if any(x in n for x in ['hard','peak time','rave','energetic']):hints[sid]['e'].append(.88)
  if any(x in n for x in ['chill','ambient','calm','slow']):hints[sid]['e'].append(.32)
  if any(x in n for x in ['happy','sunny','positive','euphoric','uplifting']):hints[sid]['v'].append(.82)
  if any(x in n for x in ['dark','melancholic','sad']):hints[sid]['v'].append(.25)
  if any(x in n for x in ['dance','party','club','house','techno','garage','funk']):hints[sid]['d'].append(.78)
  if any(x in n for x in ['ambient','classical','piano','meditation']):hints[sid]['d'].append(.2)
 now=datetime.now(timezone.utc).isoformat()
 with db:
  db.executemany('INSERT OR IGNORE INTO tags VALUES(?,?,?,?,?)',tag_rows)
  for sid,h in hints.items():
   avg=lambda xs:sum(xs)/len(xs) if xs else None
   db.execute("INSERT OR REPLACE INTO audio_features(spotify_id,source,energy,valence,danceability,confidence,updated_at) VALUES(?,?,?,?,?,?,?)",(sid,'spotify:playlist-inference',avg(h['e']),avg(h['v']),avg(h['d']),.35,now))
 record_source_run(db,'spotify:playlist-inference',now,len(hints),f'tag_candidates={len(tag_rows)}');print(f'Playlist inference: tracks={len(hints):,}, tag candidates={len(tag_rows):,}')
if __name__=='__main__':main()
