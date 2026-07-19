# Project history

This reconstructs the full available conversation and repository history so a
new agent understands how the project expanded and which requests are proven
complete versus merely requested.

## Phase 1 — Spotify control and the Indie playlist

The project began with a request to install/use a Spotify MCP server with broad
library and metadata access. References included Spotify Backstage MCP docs,
Zapier's Spotify MCP and `marcelmarais/spotify-mcp-server`. A sibling
`spotify-mcp-server` was built and OAuth-authenticated; the local callback used
by that flow is `http://127.0.0.1:8888/callback`.

The first playlist goal was to collect “normal” Indie/adjacent listening music,
including melodic Indie techno, while excluding afro house, organic house,
shamanic/ecstatic-dance and similar functional dance music. Eight Spotify track
references calibrated the positive boundary.

An early interpretation produced roughly 43,000 candidates. The user rejected
that as far too broad: the playlist should contain only Indie/adjacent styles,
maximum 2,000 and likely fewer. The desired output format briefly changed from
Excel to Soundiiz import, then back to direct Spotify API creation.

The original export scanned owned playlists plus Liked Songs. Utility playlists
from an unrelated Traktor matching project were discovered and excluded from
taste evidence, including one 9,500-track “missing tracks” playlist.

Spotify rate limiting exposed duplicate-process risk. A long 429 ban led to a
client change: waits above 120 seconds now fail visibly rather than sleeping for
hours. Classification also encountered a Claude account spend limit. Completed
batches were preserved; missing batches were resumed instead of restarted.

A boundary gap for solfeggio/binaural/frequency-healing material was fixed with
a deterministic post-merge exclusion. Final result:

- 63,213 classified tracks;
- 1,805 kept;
- 61,408 excluded;
- Spotify playlist `Indie Sort` created with 1,805 tracks.

The user then requested the same idea only from Liked Songs and insisted it
contain at least 500. `Indie Sort – Obľúbené skladby` now has 500 tracks.

## Phase 2 — What metadata Spotify can and cannot provide

The user asked whether Spotify exposed danceability, BPM, key and personal play
counts. Research established:

- normal Spotify play history/counts are not exposed as lifetime per-track
  statistics through the Web API;
- Spotify Extended Streaming History can reconstruct stats.fm-like counts,
  listening time and first/last play locally;
- Spotify Audio Features/Analysis access is deprecated/restricted for many new
  apps, so the project should not depend on approval;
- metadata must be assembled from multiple APIs and local/cloud audio analysis.

This changed the project from a playlist script into a local music intelligence
database modeled after stats.fm for personal history and Cyanite for semantic
audio retrieval.

## Phase 3 — Multi-source 60k+ database

The user set the core goal: a highly complete database for about 60,000 tracks,
now measured at 68,075, with enough detail that giving one track retrieves very
similar tracks for DJ sets.

The budget preference was EUR 250, hard ceiling around EUR 500, with free/open
sources preferred. Initially the user requested cloud/API-only processing and
no local analysis. Spotify Account Data was later supplied at:

`/Users/jakub/Downloads/Spotify Data/Spotify Account Data/`

Last.fm and MusicBrainz application credentials were supplied and stored
locally. MusicBrainz public enrichment uses rate-limited reads; OAuth is not
required for ordinary metadata lookup. AcousticBrainz historical data was also
requested. Workers were made parallel by provider, resumable and LaunchAgent-
managed so intermittent internet, sleep and reboot do not lose progress.

The database gained Spotify catalog/account/history, Last.fm, MusicBrainz,
Deezer, TheAudioDB, Discogs/OneTagger, ReccoBeats, a public Spotify legacy
dataset, AcousticBrainz fallback and semantic/playlist derivations.

## Phase 4 — OneTagger without local audio

The user specifically asked to enrich the entire SQL database with OneTagger,
not merely tag audio files. An M3U-only workaround was considered insufficient.
Because OneTagger is open source, the project added:

- a database-only Python bridge using the same provider/matching idea;
- a standalone Rust SQL feeder and compiled release binary;
- an experimental crate in a local OneTagger fork;
- import support for tags from real files when available.

Discogs and Bandcamp currently contribute. Broken/changed Beatport,
Traxsource/Juno paths remain disabled pending a new proven integration.

## Phase 5 — Provider research and FreqBlog

Research considered SoundNet, Soundcharts, Bridge.audio, Discogs, Gracenote,
Last.fm, Music Story, MusicBrainz, OneMusicAPI, TiVo, TheAudioDB and melod.ie.
FreqBlog and SoundNet were compared directly. The decision was FreqBlog without
SoundNet because ReccoBeats covers exact Spotify-ID audio features for free and
FreqBlog adds broad fallback/metadata.

The initial FreqBlog Free bulk test looked poor (3/200 immediate matches), but an
individual lookup probe resolved 40/40 stratified underground and Indie tracks,
including Tebra-related material, with complete core fields. The user then
manually purchased the EUR 39/month Starter plan (150,000 requests/month). The
new key was stored locally and the worker scaled only after a small test.

FreqBlog, ReccoBeats and local/source policies were designed so heuristic fields
do not override stronger exact measurements.

## Phase 6 — Mood, genre and rhythm become primary

The user emphasized three especially important requirements:

1. many detailed moods, not only coarse happy/sad;
2. broad genre plus niche subgenres/styles;
3. whether a beat exists and, if so, whether it is steady/four-on-the-floor or
   broken/irregular.

Research and implementation selected:

- Beat This neural beat tracking plus custom DSP for beat presence, BPM,
  regularity, syncopation, kick placement and rhythm class;
- MAEST Discogs400 for specialist genres/styles and embeddings;
- Essentia Discogs-EffNet plus 19 supervised heads for mood/theme, genre,
  instruments, voice, danceability and production character;
- CLAP for open-ended moods and semantic embeddings, but candidate-only labels;
- a detailed controlled taxonomy of DJ-relevant subgenres, moods, instruments
  and voice types.

The user later confirmed all library tracks would eventually exist locally as
MP3/M4A/FLAC/OGG and allowed cloud upload. Cost/speed scenarios were evaluated,
always requiring a small sample before paid scale-up.

## Phase 7 — Playlist side requests

Several playlist requests accompanied the database work:

- 200 sensual tracks similar to Spotify track `5mPD9BQWOOglxSOV9S9htW`;
  `build_sensual_playlist.py` implements a local multi-signal ranker called
  `Made of Gold — Sensual 200`, but no durable playlist URL was found and it
  must not be claimed complete without Spotify verification;
- a playlist based on the user's `second-brain` GitHub repository and listening
  period September 2024–January 2026, intended to reconnect the user with a
  period of depth, self, God and poetry. No verifiable artifact for that request
  is present in this repository; it remains an explicit backlog item;
- direct Spotify blindspot playlists for tracks never in Traktor, not in
  `Missing Tracks.m3u` and not local. Four playlists totaling 26,142 tracks were
  created and persisted in SQLite.

## Phase 8 — Local library synchronization and acquisition inventory

The user supplied:

- `/Users/jakub/Documents/Missing Tracks.m3u`;
- the Traktor collection at the default Traktor 4 path;
- the rule that Traktor entries not listed as missing are believed to exist and
  should be located, not downloaded again.

The desired final system synchronizes Spotify, local audio, Traktor and the
database; deduplicates; verifies complete high-quality files; retries safely;
shows progress in a menu-bar app; and continues after outages/reboots.

Implemented pieces are inventory reconciliation, acquisition states, matching,
verification, blindspot playlist export, disk guard and menu app. The user also
requested Tidal/Spotify downloader integration for purchased/licensed content,
but no active downloader is proven in this repository. Future work must remain
lawful and avoid duplicate or incomplete files.

The user instructed processing to continue on the internal disk until 50 GiB
free, then notify them so they can migrate to a new SSD.

## Phase 9 — RunPod pilot and final quality decision

The user manually added USD 10 to RunPod and explicitly prohibited automatic
funding. A three-track full-audio smoke sample (Safari by Omiki/TERRA, About A
Girl, I Miss You) ran four stages each and completed 12/12 results. The pod was
deleted; cost was only cents.

Smoke inspection found MAEST/rhythm convincing and CLAP instrument
hallucinations, leading to conservative candidate/consensus rules. Essentia
supervised results correctly separated electronic/trance from rock/indie and
identified sensible core instruments.

The user then chose trust/quality over cost: use the full track if it adds
quality; otherwise use multiple windows. The implemented answer combines both:
the **whole track is covered by model-native windows**, and every window plus
aggregate statistics is stored.

Current production design:

- prepare the current 5,394 matched tracks as full-track Opus analysis assets
  locally with one background-priority worker;
- run rhythm, MAEST, Essentia and CLAP in bounded RunPod shards;
- overlap Essentia on pod CPUs with the GPU stages;
- immutable checksums, retries, result download and guaranteed cleanup attempt;
- no pod above USD 0.40/hour;
- pause under USD 1 balance; never add funds.

The first production shard selected an RTX 3090 at USD 0.22/hour. The exact
MAEST repository commit was pinned before production.

The owner subsequently asked to move Essentia and rhythm off the laptop because
sustained CPU load made it hot. Their LaunchAgents and the older local model
fallback were disabled. Preparation was reduced from four FFmpeg workers to one
background-priority worker. An RTX 4090 community benchmark was attempted but
no machine was available, so no benchmark pod/cost was created; RTX 3090
remained the measured cost-efficiency default pending an all-stage shard.

A bounded three-track RTX 3090 benchmark then completed all four stages and
deleted its pod. Mean times were 25.41 s rhythm (cold-start skewed), 7.04 s
MAEST, 4.58 s Essentia and 6.50 s CLAP. The original 250-track production shard
subsequently completed 250/250 MAEST and 250/250 CLAP, downloaded/imported its
results and deleted its pod. It was rebuilt from database provenance so its
next run requested only genuinely missing stage/track pairs.

The first production packaging attempt found two defects: manifest paths were
local-preparation paths rather than paths inside the shard, and the bundle
omitted `musicdb.py`, imported by the analyzer modules. All 250 attempted MAEST
rows failed safely and were not imported; the pod was deleted. A replacement
pod was stopped as soon as the repeated upload was noticed. The shard builder
was repaired, its checksum and all 250 bundled paths were verified, and local
full-track preflights passed MAEST and CLAP before production resumed. This is
why old error output can coexist with zero imported production successes.

## Historical artifacts retained

- Root git history contains the original four commits for project scaffold,
  rate-limit handling, frequency-healing exclusion and old blocker handoff.
- `PROJECT_STATUS_AND_SCALING.md` preserves the earlier 45-second/four-GPU
  scenario analysis. It is no longer the current decision.
- Old pilot directories under `data/` are evidence and benchmarks; do not treat
  them as active queues.
- The working tree contains extensive user/project changes that were never
  committed. Preserve them.
