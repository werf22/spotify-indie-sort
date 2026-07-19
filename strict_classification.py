import json
from pathlib import Path

root = Path(__file__).parent; data = root/'data'
tracks = json.loads((data/'library_export.json').read_text())
positive = {
 'indie': 12, 'alternative': 10, 'dream pop': 11, 'indie folk': 11,
 'indie rock': 11, 'indie pop': 11, 'indie electronic': 10, 'lo-fi indie': 10,
 'bedroom pop': 10, 'trip hop': 9, 'post-rock': 9, 'singer-songwriter': 9,
 'folk': 6, 'rock': 5, 'synthpop': 6, 'new wave': 6, 'idm': 7,
 'electronica': 6, 'ambient': 4, 'downtempo': 4, 'art pop': 6,
 'experimental': 5, 'alté': 5, 'neofolk': 5,
}
negative = {
 'house': -15, 'techno': -13, 'trance': -15, 'afro': -18, 'tribal': -18,
 'organic': -18, 'dance': -11, 'drum and bass': -11, 'jungle': -11,
 'gqom': -15, 'amapiano': -15, 'ecstatic': -18, 'shamanic': -18,
 'psytrance': -18, 'bass': -10, 'garage': -8, 'breakbeat': -8,
 'meditation': -25, 'binaural': -25, 'solfeggio': -25,
}
def score(t):
    genres = [str(g).lower() for g in t.get('genres', [])]
    s = sum(v for k,v in positive.items() if any(k in g for g in genres))
    s += sum(v for k,v in negative.items() if any(k in g for g in genres))
    # Artist/title metadata helps when Spotify genres are sparse.
    text = ' '.join([str(t.get('name','')), *(str(a.get('name','')) for a in t.get('artists',[]))]).lower()
    if any(k in text for k in ('ecstatic','shamanic','ceremony','sound bath','singing bowl','432hz','528hz')): s -= 30
    if any(k in text for k in ('indie','alternative','dream pop','singer-songwriter')): s += 5
    return s
ranked = sorted(((score(t), len(t.get('sources',[])), t) for t in tracks), key=lambda x:(x[0],x[1]), reverse=True)
keep = {x[2]['id'] for x in ranked if x[0] >= 12}
if len(keep) > 2000: keep = {x[2]['id'] for x in ranked[:2000]}
out = []
for s,_,t in ranked:
    out.append({'id':t['id'], 'decision':'keep' if t['id'] in keep else 'exclude', 'reason':f'strict indie score {s}'})
(data/'classification.json').write_text(json.dumps(out, indent=2, ensure_ascii=False))
print(f'total={len(out)} keep={len(keep)} exclude={len(out)-len(keep)} cutoff={ranked[min(len(keep),len(ranked)-1)][0] if keep else None}')
