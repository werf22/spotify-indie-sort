"""Database-only OneTagger platform bridge.

It uses OneTagger's same Discogs metadata endpoint and matching idea, but feeds
rows from music.db instead of AudioFileInfo/local audio. It only writes DB
metadata and never touches an audio file.
"""
from __future__ import annotations
import argparse, difflib, json, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from musicdb import connect, record_source_run

ROOT=Path(__file__).resolve().parent; CACHE=ROOT/"data"/"onetagger_cache"; CACHE.mkdir(exist_ok=True)
UA="OneTagger-DB/1.7.0 (local music database)"
def clean(s): return " ".join("".join(c.lower() if c.isalnum() else " " for c in (s or "")).split())
def release_identity(item):
    raw=str(item.get("title") or "")
    if " - " in raw:
        artist,title=raw.split(" - ",1)
        return title,artist
    return raw,str(item.get("artist") or "")
def score(title,artist,item):
    release,release_artist=release_identity(item); it=clean(release); ia=clean(release_artist)
    return .65*difflib.SequenceMatcher(None,clean(title),it).ratio()+.35*difflib.SequenceMatcher(None,clean(artist),ia).ratio()
def discogs(title,artist):
    key=clean(title+" "+artist).replace(" ","_"); cp=CACHE/f"discogs_v2_{key[:180]}.json"
    if cp.exists(): return json.loads(cp.read_text())
    q=urlencode({"type":"release,master","per_page":"10","page":"1","q":f"{title} {artist}"})
    req=Request("https://api.discogs.com/database/search?"+q,headers={"User-Agent":UA,"Accept":"application/json"})
    try:
        with urlopen(req,timeout=30) as r: data=json.loads(r.read())
    except HTTPError as e:
        if e.code in (429,500,502,503,504): raise RuntimeError(f"retryable HTTP {e.code}")
        raise
    results=data.get("results",[]); best=max(results,key=lambda x:score(title,artist,x),default=None)
    out=best if best and score(title,artist,best)>=.72 else None; cp.write_text(json.dumps(out or {},ensure_ascii=False)); return out
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--limit",type=int,default=100); ap.add_argument("--delay",type=float,default=2.5); ap.add_argument("--source",default="discogs_v2"); a=ap.parse_args()
    db=connect(); db.execute("CREATE TABLE IF NOT EXISTS onetagger_enrichment_status(spotify_id TEXT NOT NULL,source TEXT NOT NULL,status TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,last_error TEXT,updated_at TEXT NOT NULL,PRIMARY KEY(spotify_id,source))")
    rows=db.execute("SELECT t.* FROM tracks t LEFT JOIN onetagger_enrichment_status s ON s.spotify_id=t.spotify_id AND s.source=? WHERE COALESCE(s.status,'') NOT IN ('success','no_match') ORDER BY t.spotify_id LIMIT ?",(a.source,a.limit)).fetchall(); ok=nomatch=errors=0
    for r in rows:
        db.execute("INSERT INTO onetagger_enrichment_status(spotify_id,source,status,attempts,updated_at) VALUES(?,?,?,1,CURRENT_TIMESTAMP) ON CONFLICT(spotify_id,source) DO UPDATE SET status='processing',attempts=attempts+1,updated_at=CURRENT_TIMESTAMP",(r['spotify_id'],a.source,'processing')); db.commit()
        try:
            hit=discogs(r['title'],(r['artist_names'] or '').split(',')[0].strip())
            with db:
                if not hit:
                    db.execute("UPDATE onetagger_enrichment_status SET status='no_match',last_error=NULL,updated_at=CURRENT_TIMESTAMP WHERE spotify_id=? AND source=?",(r['spotify_id'],a.source)); nomatch+=1
                else:
                    conf=score(r['title'],r['artist_names'],hit); vals=[]
                    for typ,key in (("genre","genre"),("style","style")):
                        for v in hit.get(key) or []: vals.append((r['spotify_id'],str(v).lower(),typ,'onetagger:discogs',conf))
                    for v in (hit.get('format') or []): vals.append((r['spotify_id'],str(v).lower(),'format','onetagger:discogs',conf))
                    for v in (hit.get('label') or []): vals.append((r['spotify_id'],str(v).lower(),'label','onetagger:discogs',conf))
                    if hit.get('country'): vals.append((r['spotify_id'],str(hit['country']).lower(),'country','onetagger:discogs',conf))
                    db.executemany("INSERT OR IGNORE INTO tags VALUES(?,?,?,?,?)",vals)
                    labels=hit.get('label') or []
                    db.execute("UPDATE tracks SET release_date=COALESCE(release_date,?),label=COALESCE(label,?),updated_at=CURRENT_TIMESTAMP WHERE spotify_id=?",(str(hit.get('year')) if hit.get('year') else None,str(labels[0]) if labels else None,r['spotify_id']))
                    db.execute("INSERT OR REPLACE INTO track_attributes(spotify_id,attribute,source,value_json,confidence,updated_at) VALUES(?,?,'onetagger:discogs',?,?,CURRENT_TIMESTAMP)",(r['spotify_id'],'release',json.dumps(hit,ensure_ascii=False,sort_keys=True),conf))
                    db.execute("UPDATE onetagger_enrichment_status SET status='success',last_error=NULL,updated_at=CURRENT_TIMESTAMP WHERE spotify_id=? AND source=?",(r['spotify_id'],a.source)); ok+=1
        except (URLError,TimeoutError,RuntimeError,HTTPError) as e:
            errors+=1; db.execute("UPDATE onetagger_enrichment_status SET status='failed',last_error=?,updated_at=CURRENT_TIMESTAMP WHERE spotify_id=? AND source=?",(str(e),r['spotify_id'],a.source)); db.commit()
        time.sleep(a.delay)
    record_source_run(db,'onetagger:discogs',datetime.now(timezone.utc).isoformat(),ok,f'no_match={nomatch},errors={errors}'); print(f'OneTagger DB Discogs: matched={ok}, no_match={nomatch}, errors={errors}')
if __name__=='__main__': main()
