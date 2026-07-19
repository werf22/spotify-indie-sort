"""Import OneTagger/embedded DJ tags from local audio into music.db.

OneTagger writes standard MP4/ID3 fields plus key, energy, beatgrid and cuepoints.
The importer never changes audio files; it only reads metadata with ffprobe.
"""
from __future__ import annotations
import argparse, json, re, subprocess
from datetime import datetime, timezone
from pathlib import Path
from musicdb import connect

def norm(s): return re.sub(r"[^a-z0-9]+", " ", (s or "").casefold()).strip()
def probe(p):
    x=subprocess.run(["/Users/jakub/.local/bin/ffprobe","-v","quiet","-show_entries","format_tags","-of","json",str(p)],capture_output=True,text=True,timeout=30)
    return json.loads(x.stdout).get("format",{}).get("tags",{})
def main():
    ap=argparse.ArgumentParser(); ap.add_argument("path",nargs="?",default="/Users/jakub/Music/Tidal Spotify Imports"); args=ap.parse_args()
    db=connect(); rows=db.execute("select * from tracks").fetchall(); by_title={}
    for r in rows: by_title.setdefault(norm(r["title"]),[]).append(r)
    files=[p for p in Path(args.path).rglob("*") if p.suffix.lower() in {".m4a",".mp3",".flac",".wav",".aiff",".ogg"}]
    matched=features=tags=errors=0
    for p in files:
      try:
        m=probe(p); title=m.get("title") or m.get("TITLE") or p.stem; artist=m.get("artist") or m.get("ARTIST") or ""
        cand=by_title.get(norm(title),[]); r=next((x for x in cand if norm(x["artist_names"].split(",")[0]) in norm(artist)),None) or (cand[0] if len(cand)==1 else None)
        if not r: continue
        matched+=1; now=datetime.now(timezone.utc).isoformat(); key=m.get("key") or m.get("INITIALKEY"); energy=m.get("energylevel") or m.get("ENERGYLEVEL"); tempo=m.get("tempo") or m.get("BPM") or m.get("bpm")
        with db:
          if key or energy or tempo:
            db.execute("insert or replace into audio_features(spotify_id,source,source_id,bpm,key,energy,raw_json,updated_at) values(?,?,?,?,?,?,?,?)",(r["spotify_id"],"onetagger",str(p),float(tempo) if tempo else None,key,float(energy) if energy else None,json.dumps(m,ensure_ascii=False),now)); features+=1
          for k in ("genre","GENRE","style","STYLE","comment","COMMENT","label","LABEL"):
            for v in str(m.get(k) or "").split(";"):
              v=v.strip().lower()
              if v and len(v)<120: db.execute("insert or ignore into tags values(?,?,?,?,?)",(r["spotify_id"],v,"onetagger", "onetagger",None)); tags+=1
      except Exception: errors+=1
    with db: db.execute("insert or replace into source_runs values(?,?,?,?)",("onetagger",datetime.now(timezone.utc).isoformat(),matched,f"files={len(files)},features={features},tags={tags},errors={errors}"))
    print(f"OneTagger: files={len(files):,}, matched={matched:,}, features={features:,}, tags={tags:,}, errors={errors:,}")
if __name__=="__main__": main()
