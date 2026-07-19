# Spotify DJ Music Intelligence Database

Local, resumable, multi-source music database for the user's complete Spotify
library and DJ workflow. It currently contains **68,075 tracks** and combines
Spotify identity/history, catalog APIs, detailed tags, audio features,
full-track temporal analysis and semantic embeddings.

The original repository began as `Spotify Indie Sort`; that playlist tooling
still exists, but the database/synchronization system is now the primary project.

## New agent start here

Read [HANDOFF.md](HANDOFF.md). It contains the current mission, live services,
cost limits, quality decisions, continuation checklist and links to the full
[documentation package](docs/README.md).

Important owner rules:

- never add funds, buy credits or upgrade a plan;
- preserve at least 50 GiB free disk space;
- keep background work resumable across outages/restarts;
- preserve provider provenance and raw/conflicting observations;
- use full-track temporal coverage for quality-critical audio analysis;
- never expose or commit credentials.

## Current architecture

- SQLite/WAL: `data/music.db`.
- General enrichment: Spotify, FreqBlog, ReccoBeats, Last.fm, MusicBrainz,
  Deezer, TheAudioDB, OneTagger/Discogs/Bandcamp and public datasets.
- Local full-track analysis: Essentia supervised heads and Beat This + DSP.
- Bounded RunPod analysis: Beat This, MAEST Discogs400, Essentia and CLAP in
  resumable 100-track shards.
- Search: weighted BPM/key/features/tags/rhythm plus MAEST/CLAP embeddings.
- Sync: Spotify, Traktor, Missing Tracks, local file index and verification.
- UX: menu-bar status and pause/resume app.

## Status

```bash
./.venv/bin/python coverage_report.py
./.venv/bin/python sync_status.py
./.venv/bin/python audio_enrichment_status.py
cat data/cloud_full_shards/orchestrator_status.json
```

See [docs/STATUS.md](docs/STATUS.md) for the latest timestamped snapshot and
[docs/OPERATIONS.md](docs/OPERATIONS.md) before restarting any worker.

## Search

```bash
./.venv/bin/python query_music.py "indie folk"
./.venv/bin/python find_similar.py "SPOTIFY_TRACK_URL" --limit 30
```

## Original Indie Sort pipeline

```text
export.py -> data/library_export.json
classify.py / merge_classification.py -> data/classification.json
build_playlist.py -> Spotify playlist + data/state.json + data/run_log.json
```

`genre_line.py` defines the calibrated Indie/adjacent boundary. The final
playlist contains 1,805 tracks; the Liked Songs-only version contains 500.
Technical Traktor/missing-track playlists must not be used as taste evidence.

## Secrets and runtime assets

`.env`, `data/`, virtual environments, model caches and local audio are not
source artifacts. Never print secret values or copy the live SQLite file
without handling its WAL safely. See [docs/SECURITY.md](docs/SECURITY.md).
