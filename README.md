# Spotify Indie Sort

Sorts everything in your owned Spotify playlists + Liked Songs into one
playlist: everything that ISN'T afro house / organic house / shamanic house /
ecstatic-dance groove music. The taste line (what counts as "keep") lives in
`genre_line.py` — edit it any time your definition of "Indie" shifts.

## Pipeline

```
export.py        -> data/library_export.json   (your library, deduped, with artist genres)
classify.py       -> data/classification.json   (keep/exclude per track, via Claude)
build_playlist.py -> writes the real playlist, data/state.json, data/run_log.json
```

Run all three: `./run.sh`. Safe to re-run any time — `state.json` remembers
the playlist id and which tracks are already in it, so re-runs only add new
ones (newly liked songs, new playlists) instead of duplicating.

## Setup

1. `cp .env.example .env`, fill in `SPOTIFY_CLIENT_ID`/`SECRET` — the same
   Client ID/Secret already used by `dj-set-spotify` / `spotify-tidal-sync`
   work fine, no new Spotify app needed.
2. **Token bootstrap** — this tool needs a refresh token in `data/token.json`
   as `{"refresh_token": "..."}`. Easiest way to get one: the sibling
   `spotify-mcp-server` project already has a working `npm run auth` flow —
   run that once (it needs `http://127.0.0.1:8888/callback` added as a
   redirect URI on your Spotify app), then copy the `refreshToken` field
   from its `spotify-config.json` into this project's `data/token.json`.
3. For `classify.py` specifically: set `ANTHROPIC_API_KEY` in `.env` (get one
   at console.anthropic.com). Without it, `classify.py` exits with a clear
   error — `export.py` and `build_playlist.py` don't need it.
4. `./run.sh`

## Notes

- Only playlists **you own** are scanned — playlists you follow but didn't
  create are skipped (confirmed with the owner 2026-07-13).
- The target playlist is private by default (`build_playlist.py`,
  `public=False`) and named `Indie Sort` — change `TARGET_PLAYLIST_NAME` in
  `.env` any time, Spotify lets you rename the playlist directly too.
- `classify.py` batches ~60 tracks per Claude call, 4 batches at a time. If a
  batch errors, those tracks default to **keep** rather than silently
  dropping them — false positives are a quick manual removal in Spotify,
  false negatives (a good track never making it in) are invisible and
  wouldn't get fixed.
- Rate limits: `spotify_client.py` backs off on 429s using Spotify's
  `Retry-After` header. If you see a lot of waiting, that's expected on a
  library this size (1,300+ playlists) — it'll finish, just slowly.
