import json
from pathlib import Path
from dotenv import load_dotenv
from spotify_client import SpotifyClient

ROOT = Path(__file__).parent; load_dotenv(ROOT/'.env'); data=ROOT/'data'
PLAYLIST_ID='2o80p5DW9YMMMqorQiFuYG'; TARGET=500
tracks={t['id']:t for t in json.loads((data/'library_export.json').read_text())}
decisions={x['id']:x for x in json.loads((data/'classification.json').read_text())}
positive={'indie':12,'alternative':10,'dream pop':11,'indie folk':11,'indie rock':11,'indie pop':11,'indie electronic':10,'lo-fi indie':10,'bedroom pop':10,'trip hop':9,'post-rock':9,'singer-songwriter':9,'folk':6,'rock':5,'synthpop':6,'new wave':6,'idm':7,'electronica':6,'ambient':4,'downtempo':4,'art pop':6,'experimental':5,'alté':5,'neofolk':5}
negative={'house':-15,'techno':-13,'trance':-15,'afro':-18,'tribal':-18,'organic':-18,'dance':-11,'drum and bass':-11,'jungle':-11,'gqom':-15,'amapiano':-15,'ecstatic':-18,'shamanic':-18,'psytrance':-18,'bass':-10,'garage':-8,'breakbeat':-8,'meditation':-25,'binaural':-25,'solfeggio':-25}
def score(t):
    gs=[str(g).lower() for g in t.get('genres',[])]
    s=sum(v for k,v in positive.items() if any(k in g for g in gs))+sum(v for k,v in negative.items() if any(k in g for g in gs))
    text=' '.join([str(t.get('name','')),*(str(a.get('name','')) for a in t.get('artists',[]))]).lower()
    if any(k in text for k in ('ecstatic','shamanic','ceremony','sound bath','singing bowl','432hz','528hz')): s-=30
    if any(k in text for k in ('indie','alternative','dream pop','singer-songwriter')): s+=5
    return s
client=SpotifyClient()
# The first 169 entries were the prior strict classification; avoid re-adding them.
existing={t['id'] for t in tracks.values() if 'Liked Songs' in t.get('sources',[]) and decisions.get(t['id'],{}).get('decision') == 'keep'}
candidates=[t for t in tracks.values() if 'Liked Songs' in t.get('sources',[]) and t['id'] not in existing]
candidates.sort(key=lambda t:(score(t),len(t.get('sources',[]))),reverse=True)
need=max(0,TARGET-len(existing)); add=candidates[:need]
added = 0
for i in range(0, len(add), 25):
    chunk = add[i:i+25]
    try:
        client.add_tracks(PLAYLIST_ID, [t['uri'] for t in chunk])
        added += len(chunk)
    except Exception as exc:
        print(f'chunk {i} failed: {exc}')
print(f'existing={len(existing)} added={added} total={len(existing)+added}')
