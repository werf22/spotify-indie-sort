# Spotify DJ database — status and scaling decision

> **Historical/superseded plan.** This document preserves the earlier
> 45-second, multi-GPU scenario analysis. The binding decision is now full-track
> temporal coverage with local Essentia/rhythm and sequential bounded RunPod
> MAEST/CLAP shards. Start with [HANDOFF.md](HANDOFF.md) and
> [docs/DECISIONS.md](docs/DECISIONS.md).

Status captured: 2026-07-18 (Europe/Bratislava). No credentials or API keys are
stored in this document.

## Objective

Build a provenance-preserving database for all 68,075 Spotify-library tracks,
optimized for DJ discovery and nearest-track search. The final profile should
contain identity/catalog metadata, multiple genre and niche-subgenre tags,
multiple moods, BPM, key/Camelot, energy, danceability, valence, instruments,
voice properties, audio embeddings, and an audio-verified distinction between
beatless, steady four-on-the-floor, broken beat, mixed/variable, and unknown.

## Current live state

- Library: 68,075 tracks.
- Local files indexed: 10,767; matched files: 9,220 files / 5,100 unique tracks.
- Any genre tag: 63,292 (92.97%).
- Any tag: 65,981 (96.92%).
- Mood: 48,548 (71.32%).
- BPM: 51,084 (75.04%); key: 52,328 (76.87%).
- Energy: 53,144 (78.07%); danceability: 56,369 (82.80%); valence: 51,765 (76.04%).
- ISRC: 50,996 (74.91%); label: 17,174 (25.23%); release date: 17,707 (26.01%).
- Local audio completed: rhythm 201, MAEST 121, CLAP 81 of the 5,100 matched tracks.
- FreqBlog success: 3,768; tracked calls: 7,665 / 150,000 monthly quota.
- ReccoBeats exact Spotify-ID success: 49,863 (73.25%).

The macOS LaunchAgent is running. Every source checkpoints to SQLite, retries
transient failures, waits through internet outages, and restarts after login,
reboot, sleep, or worker failure.

## Data-source stack

### Already paid

- **FreqBlog Starter — EUR 39/month, 150,000 requests/month.** BPM, key,
  Camelot/Open Key, audio/perceptual features, metadata, genre/mood fields, and
  long-tail on-demand analysis. Identity is checked using ISRC first and
  artist/title second. Raw responses and confidence are retained. FreqBlog's
  heuristic acousticness/liveness/speechiness/instrumentalness are deliberately
  treated as lower-confidence than exact ReccoBeats/legacy measurements.

### Free cloud/catalog layers already active

- Spotify account export/API: track identity, playlists, saved tracks, play
  history, ISRC, album/artist IDs, label/date/duration/popularity where exposed.
- ReccoBeats: Spotify-style audio features for exact Spotify IDs.
- Spotify 114k historical public dataset: legacy audio features on exact ID overlap.
- Last.fm: community genres, scenes, moods, instruments, and vocal descriptors.
- MusicBrainz: canonical identities, MBIDs, ISRC links, dates, labels, tags.
- Deezer: ISRC cross-check, album/label/date/genre/rank and occasional BPM.
- TheAudioDB: genre, mood, style, catalog identifiers and descriptive metadata.
- OneTagger SQL bridge + Discogs/Bandcamp: release genres/styles, labels, year,
  country and format without requiring OneTagger to mutate local files.
- AcousticBrainz historical layer: free but frozen and currently only 43 matches.
- Playlist/semantic derivation: low-confidence context tags retained separately.

### Free audio-derived layers already active

- Beat This + librosa/DSP: beat presence, BPM, beat/downbeat activity,
  regularity, syncopation, tempo stability, kick placement, four-on-the-floor,
  broken beat, mixed rhythm, beatless and confidence.
- MAEST Discogs400: specialist genres/subgenres and reusable similarity embeddings.
- LAION larger-CLAP-music: fine-grained zero-shot mood vocabulary, semantic
  embeddings, and instrument/voice candidates.
- FFmpeg and SQLite: deterministic clip decoding, resumable queues, raw payloads,
  source-specific confidence, and no overwrite of conflicting observations.

### Add to the final cloud audio pass

- Upgrade the MAEST head to Discogs519 (trained for 519 styles on 4M tracks).
- Reuse Essentia embeddings for mood/theme, MIREX moods, arousal/valence,
  happy/sad/relaxed/aggressive/party, danceability, acoustic/electronic,
  voice/instrumental, voice gender, instrumentation, timbre and tonal/atonal.
- Keep CLAP for the open-ended vocabulary that fixed taxonomies miss: sensual,
  sacred, earthy, ritual, nocturnal, tender, euphoric, melancholic, ominous,
  hypnotic, cinematic, etc. Calibrate thresholds on manually audited samples.
- Analyze a middle segment first; only low-confidence rhythm results get a
  second/third segment. This catches tracks with beatless intros or breakdowns
  without tripling compute for every track.

## Small-sample gate before every scale-up

1. Use 100 stratified tracks: afro/organic, indie, electronic, acoustic,
   beatless, broken beat, four-on-the-floor, vocals and instrumentals.
2. Record wall time, failure rate, GPU utilization, per-track cost and every
   output field. Compare against the existing local baseline and manually audit
   ambiguous rhythm plus top mood/subgenre tags.
3. Do not scale if there are rate-limit errors, identity regressions, missing
   provenance, or worse quality. Paid pilot hard limit: EUR 5.
4. Extrapolate the measured full-library cost; enforce an automatic spend cap.
5. Process immutable shards and upload result JSON after every track/batch, so
   preemption or disconnection loses no completed work.

The first gate was already applied to FreqBlog: 100 calls completed in 67.5 s,
with no HTTP 429s. Its daemon was therefore changed from 1 concurrent / 60 per
minute to 10 concurrent / 300 per minute. Timeout rows remain in the retry queue.

## Three all-in scenarios

Times below start once all 68,075 audio files exist and are identity-matched.
They are estimates until the 100-track CUDA pilot supplies measured throughput.

| Scenario | Total project spend for first run | Full 68k audio pass | What changes |
|---|---:|---:|---|
| 1. Minimum/free compute | EUR 39 already-paid FreqBlog; EUR 0 additional | about 6–9 days on this M1 Pro | Adaptive 20–25 s rhythm first pass, persistent model processes, larger batches; no guaranteed free Colab dependency |
| 2. Best value — selected | about EUR 50–80 all-in | about 5–10 hours end-to-end; 3–7 h GPU portion | FreqBlog + compressed 45 s clips in R2 + 100-track pilot + four RTX 4090 workers + full Essentia/MAEST/CLAP/Beat This stack |
| 3. Maximum under budget | about EUR 90–160 all-in | about 3–6 hours end-to-end | Eight RTX 4090/5090 workers, multi-segment quality pass, wider tag ensemble and larger manual audit; clip preparation/upload becomes the bottleneck |

Pricing basis used for the estimates: RunPod RTX 4090 USD 0.69/GPU-hour,
RTX 5090 USD 0.99/GPU-hour, billed by the second; Cloudflare R2 Standard has a
10 GB free tier and USD 0.015/GB-month thereafter with free egress. Roughly 49
GB of 45-second Opus clips for 68k tracks would cost about USD 0.59/month in R2
after the free tier. Temporary RunPod storage and contingency are included in
the scenario ranges. Audio acquisition and the user's existing Spotify plan are
not counted as project costs.

## Decision

Use **Scenario 2**. Four RTX 4090 workers are the price/performance sweet spot:
the GPU bill itself should remain in the low tens of euros, it finishes within
one working day, and it allows the complete open-model ensemble instead of a
weaker speed-only pass. Spending above this primarily shortens the final few
hours because local clip preparation/upload becomes the bottleneck.

Execution order:

1. Continue all current free/API enrichment and ingest every newly available file.
2. Build 45-second middle clips plus optional extra segments only for uncertain tracks.
3. Run the same 100 tracks locally and on one RTX 4090; require quality parity.
4. If the measured projection is within EUR 50–80, shard across four workers.
5. Merge results transactionally, recompute coverage/conflicts, and manually
   audit a stratified 500-track result set before declaring the database complete.
