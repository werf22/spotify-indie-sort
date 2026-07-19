import csv, json
from pathlib import Path

root = Path(__file__).parent
out = Path('/Users/jakub/.codex/visualizations/2026/07/14/019f6041-0ce1-79a1-9b36-3b762d0b52de/spotify_indie_sort_soundiiz.csv')
tracks = json.loads((root/'data/library_export.json').read_text())
decisions = json.loads((root/'data/classification.json').read_text())
keep = {x['id'] for x in decisions if x['decision'] == 'keep'}
out.parent.mkdir(parents=True, exist_ok=True)
with out.open('w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['title', 'artist', 'album', 'isrc'])
    for t in tracks:
        if t['id'] in keep:
            w.writerow([t.get('name',''), ', '.join(a.get('name','') for a in t.get('artists',[])), t.get('album',''), ''])
print(f'{len(keep)} tracks -> {out}')
