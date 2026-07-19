import json
from pathlib import Path
from dotenv import load_dotenv
from spotify_client import SpotifyClient

ROOT = Path(__file__).parent
load_dotenv(ROOT / '.env')
data = ROOT / 'data'
tracks = {t['id']: t for t in json.loads((data/'library_export.json').read_text())}
decisions = {x['id']: x for x in json.loads((data/'classification.json').read_text())}
selected = [t for t in tracks.values() if 'Liked Songs' in t.get('sources', []) and decisions.get(t['id'], {}).get('decision') == 'keep']

client = SpotifyClient()
me = client.current_user()
playlist = client.create_playlist(
    me['id'], 'Indie Sort – Obľúbené skladby',
    'Indie-style selection from my Spotify Liked Songs.', public=False
)
client.add_tracks(playlist['id'], [t['uri'] for t in selected])
print(f"{len(selected)} tracks -> {playlist['external_urls']['spotify']}")
