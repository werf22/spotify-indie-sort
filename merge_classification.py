import json, re
from pathlib import Path

root = Path(__file__).parent
data = root / 'data'
tracks = {t['id']: t for t in json.loads((data/'library_export.json').read_text())}
decisions = {}
for p in sorted((data/'results').glob('batch_*.json')):
    for row in json.loads(p.read_text()):
        decisions[row['id']] = row

# Conservative local fallback: exclude only unmistakable functional/ritual audio.
exclude = re.compile(r'(afro house|organic house|shamanic|ecstatic|ceremon|tribal|medicine music|dance journey|sound bath|singing bowl|binaural|solfeggio|chakra|432\s*hz|528\s*hz|meditation|deep healing|frequency zone|ritual|shaman)', re.I)
for tid, t in tracks.items():
    if tid in decisions:
        continue
    hay = ' '.join(str(x or '') for x in [t['name'], *(a['name'] for a in t['artists']), *t.get('genres', [])])
    if exclude.search(hay):
        decisions[tid] = {'id': tid, 'decision': 'exclude', 'reason': 'functional or ceremonial audio'}
    else:
        decisions[tid] = {'id': tid, 'decision': 'keep', 'reason': 'conservative local fallback'}

# Apply the deterministic wellness override to already-classified batches too.
for tid, row in decisions.items():
    t = tracks[tid]
    hay = ' '.join(str(x or '') for x in [t['name'], *(a['name'] for a in t['artists']), *t.get('genres', [])])
    if re.search(r'(hz\s*frequency|solfeggio|binaural|chakra|sound\s*bath|singing\s*bowl|meditat)', hay, re.I):
        row['decision'] = 'exclude'
        row['reason'] = 'wellness or frequency audio'

(data/'classification.json').write_text(json.dumps(list(decisions.values()), indent=2, ensure_ascii=False))
from collections import Counter
print(len(decisions), Counter(x['decision'] for x in decisions.values()))
