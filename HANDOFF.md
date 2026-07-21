# Handoff: Spotify DJ Music Intelligence Database

This is the canonical cold-start document for the next AI agent. Read it
before changing code, restarting services, creating cloud resources, calling a
paid API, or modifying Spotify playlists.

Last manually verified: **2026-07-20, afternoon, Europe/Bratislava**. Live
counters will continue changing while the background workers run.

**MILESTONE 2026-07-21: the full-track audio layer is COMPLETE — 5,393 of
5,393 preparable tracks have all four stages (rhythm, MAEST, Essentia, CLAP)
analyzed and imported.** (Track 5,394 of the original target has a
permanently corrupt source file and never produced an Opus asset.) The whole
scaled run: 19 shards, 25.9 GPU-hours, **$5.88 total (~$0.0016/track)**, no
pods left running, spend $0.00/hr, balance $1.84. Next step per the approved
roadmap: a measured 100-track pilot of the Deezer 30-s preview tier (D-007
discipline) before the ~55k-track preview run is priced and funded.

**2026-07-20 cost/speed overhaul (D-025, D-026):** pod analysis now runs
detached (network drops no longer kill or bill-idle paid work), results
stream back incrementally, pods self-stop if uncollected, stop/terminate
caps are sized to the shard, the orchestrator sweeps unexplained pods every
cycle, blocks on unexplained spend, keeps a cost ledger, and can run two
balance-gated parallel pods. Shards grew to 200 tracks. A guaranteed-import
path healed shard-0018 (+100 already-paid tracks). New canonical oversight
command: `./.venv/bin/python pipeline_status.py`.

**Resolved 2026-07-19:** a second, untracked RunPod pod (`6k2dt0i0n5hy73`) was
found running alongside the real shard-0002 pod (`cp6v9hygqv0u60`), doubling
the account's hourly burn to about USD 0.45/hour. Its useful partial results
were recovered to
`data/cloud_full_shards/shard-0002/recovered/orphan-pod-6k2dt0i0n5hy73-results.jsonl`
(100/100 rhythm_full, 100/100 maest_full, 51/51 essentia_full), then the pod
was deleted and deletion confirmed (`deleted: true`); `runpodctl pod list` now
shows only `cp6v9hygqv0u60` and `currentSpendPerHr` is back to 0.226. Root
cause fixed in code (D-023, `runpod_pilot.terminate()` now confirms deletion
instead of assuming it); see `docs/DECISIONS.md` and `docs/OPERATIONS.md`
"Duplicate/orphaned pod after a cleanup failure".

## Mission

Build a local, provenance-preserving intelligence database for the user's
entire Spotify-derived library (currently **68,075 tracks**) and eventually
for every locally owned audio file. It must support unusually precise DJ
discovery from one reference track using:

- broad genres plus detailed subgenres and niche styles;
- many mood descriptors, including subtle/open-ended moods;
- BPM, key, mode, Camelot, energy, danceability and valence/happiness;
- instruments, voice/instrumental properties and production character;
- beat presence and beat type: beatless, steady/four-on-the-floor, broken,
  mixed/variable and unknown;
- full-track temporal profiles and reusable audio embeddings;
- labels, dates, catalog identifiers and Spotify listening history;
- explicit source, confidence and raw payload for every observation.

The user values **quality and trust above raw speed**. Cost should still be
minimal and every paid scale-up must follow a small measured pilot.

## Non-negotiable owner rules

1. **Never add money, buy credits, upgrade a plan or change billing.** Only the
   user may fund an account. Warn the user when credit is low.
2. RunPod may consume only existing credit. Production refuses pods above
   **USD 0.40/hour** and waits when balance is below **USD 1.00**.
3. Do not stop the active enrichment/audio workers unless necessary for a
   verified fix. Jobs must be resumable across sleep, restart and network loss.
4. Keep at least **50 GiB** free on the internal disk. Notify the user at the
   threshold; the user plans to move audio to an SSD later.
5. Preserve provenance and conflicting measurements. Never flatten all
   providers into an untraceable value.
6. Treat open-vocabulary CLAP labels as candidates. Canonical tags require a
   supervised model or independent-source consensus.
7. Never document, print, commit or paste credential values. Secrets belong in
   `.env`, Spotify token storage, RunPod CLI storage or the system keychain.
8. Audio acquisition must use files the user owns or is licensed to download.
   The current repository builds a queue and verifies files; it does **not**
   currently implement an unattended downloader.

## Live system at handoff

The following LaunchAgents were running when this handoff was written:

| Label | Purpose |
|---|---|
| `com.jakub.local-dj-enrichment` | Parallel catalog/API enrichment, indexing and verification supervisor |
| `com.jakub.music-db-cloud-full-prep` | Prepare full-track Opus copies from matched local audio |
| `com.jakub.music-db-essentia-full` | **Disabled**; preserved only as an offline fallback |
| `com.jakub.music-db-rhythm-full` | **Disabled**; preserved only as an offline fallback |
| `com.jakub.music-db-cloud-production` | Build/run/import bounded RunPod rhythm + MAEST + Essentia + CLAP shards |
| `com.jakub.music-library-sync-menu` | Menu-bar status and pause/resume control |
| `com.jakub.music-db-cloud-prep` | **Disabled 2026-07-19 (D-024)**; pre-full-track duplicate prep worker, dead output |
| `com.jakub.music-db-runpod-pilot` | **Disabled 2026-07-19 (D-024)**; old standalone pilot poll, independent pod-creation path |

At the last detailed database snapshot:

- tracks: 68,075;
- locally matched tracks and current cloud-audio target: 5,394; deep-verified:
  1,820;
- any genre tag: 64,464 (94.70%);
- mood tag: 53,694 (78.87%);
- BPM: 55,539 (81.59%); key: 56,419 (82.88%);
- energy: 56,653 (83.22%); danceability: 59,446 (87.32%);
- FreqBlog successes: 20,558 (56,348/150,000 monthly calls tracked); ReccoBeats
  successes: 49,863;
- `data/music.db`: about 2.3 GiB, WAL enabled;
- first production shard: 250/250 MAEST and 250/250 CLAP imported; pod deleted;
- shard-0002 in progress on pod `cp6v9hygqv0u60` (RTX 3090, uploaded/analyzing);
  see the open action above about its untracked duplicate pod;
- active cloud default: RTX 3090 at USD 0.22/hour;
- RunPod balance: about USD 7.7 (see open action above — currently paying for
  two pods at once, about USD 0.45/hour combined instead of USD 0.22).

These numbers are snapshots, not completion assertions. Get current values:

```bash
cd "/Users/jakub/Appky Claude/spotify-indie-sort"
./.venv/bin/python coverage_report.py
./.venv/bin/python sync_status.py
./.venv/bin/python audio_enrichment_status.py
cat data/cloud_full_shards/orchestrator_status.json
```

## Current quality-first audio decision

The old 45-second-only plan is superseded. We analyze **the entire available
track as a timeline of model-native windows**:

- MAEST: contiguous 10-second windows across the full track;
- CLAP: contiguous 10-second windows across the full track;
- Essentia Discogs-EffNet: native approximately 1 Hz patches across the track,
  reused by 19 supervised classifier heads;
- Beat This: 45-second windows every 40 seconds (5-second overlap).

The database stores temporal matrices/timelines and a separate robust summary.
Energy-weighted aggregation prevents silent intros/outros from dominating;
mean, p90 and section coverage preserve moods or styles that appear only in
part of a track. This is more trustworthy than one middle excerpt and more
informative than collapsing the whole track to one opaque prediction.

The three-track full-coverage RunPod smoke test completed all 12 combinations
(3 tracks x rhythm/MAEST/Essentia/CLAP), imported cleanly and cost only cents.
Production now runs all four stages in immutable GPU shards. Essentia executes
concurrently on pod CPUs while the GPU stages run, reducing paid wall time.
Local Essentia/rhythm agents are disabled to keep the laptop cool. Full-track
Opus preparation remains local at one background-priority FFmpeg worker because
the source files must be read and compressed before upload.

A separate bounded RTX 3090 benchmark measured 25.41 s rhythm (including cold
startup), 7.04 s MAEST, 4.58 s Essentia and 6.50 s CLAP per track across three
full tracks. Its pod was deleted automatically. RTX 4090 community capacity was
unavailable during the bounded comparison attempt, so no 4090 pod or cost was
created. Do not add a second production pod until a complete larger all-stage
shard validates cost against the remaining prepaid balance.

## Immediate continuation checklist

1. **Observe; do not duplicate workers.** Confirm each LaunchAgent has exactly
   one parent process before starting anything manually.
2. Check `data/cloud_full_shards/shard-0001/runpod_state.json`. If a pod exists,
   let `runpod_full_shard.py` finish. It downloads results and deletes the pod
   in `finally`.
3. Check RunPod independently with `~/.local/bin/runpodctl pod list` and
   `~/.local/bin/runpodctl user`. Never infer deletion only from a local state
   file.
4. Allow `prepare_cloud_audio_pilot.py` to finish its 5,394-track manifest.
   The cloud queue consumes it incrementally.
5. After each cloud shard, verify all required stages per track and that the
   pod was deleted. The orchestrator should create the next shard itself.
6. When all 5,394 current tracks finish, run coverage/conflict reports and a
   stratified manual audit before calling the audio layer complete.
7. Generalize the hard-coded `EXPECTED = 5394` batch into a dynamic queue for
   newly matched files. Do this only after the first immutable batch finishes.

## Where to continue reading

- [Documentation index](docs/README.md)
- [Current status and verification commands](docs/STATUS.md)
- [Architecture and file map](docs/ARCHITECTURE.md)
- [Database schema and trust model](docs/DATA_MODEL.md)
- [Providers, cost and matching](docs/PROVIDERS.md)
- [Operations and recovery runbook](docs/OPERATIONS.md)
- [Decision log](docs/DECISIONS.md)
- [Backlog and definition of done](docs/TASKS.md)
- [Project history and playlist work](docs/HISTORY.md)
- [Spotify playlists created by this project](docs/PLAYLISTS.md)
- [Security and credential handling](docs/SECURITY.md)

## Known traps

- `PROJECT_STATUS_AND_SCALING.md` records an earlier 45-second/four-GPU plan.
  It is retained as historical analysis, not the current execution contract.
- `prepare_cloud_audio_pilot.py` has a historical name but its `--full-track`
  mode creates full-track Opus assets.
- `sync_status.py` reports older local MAEST/CLAP counters separately from the
  new `audio-full:*` artifacts. Do not use one counter as total audio coverage.
- The source tree is very dirty/untracked. Existing changes belong to the user.
  Do not reset, clean or overwrite them. No project-wide commit was made.
- `.env`, Spotify refresh tokens and RunPod credentials exist locally. Never
  inspect values unless required for a narrowly scoped repair; never echo them.
- Spotify legacy Audio Features/Analysis access is not assumed. ReccoBeats,
  FreqBlog, public legacy datasets and local audio analysis replace it.
- FreqBlog bulk responses and individual `/lookup` behave differently. The
  paid-plan pilot showed individual lookup can resolve underground tracks that
  the first bulk validation did not immediately return.
- CLAP can hallucinate plausible instruments. It is deliberately candidate-only.
- AcousticBrainz is a frozen historical source with low overlap, not the core
  audio engine.
- Run `./.venv/bin/python verify_handoff_access.py --live` to verify active
  credentials without displaying secret values or consuming FreqBlog quota.

## Definition of complete

The project is not complete merely when workers stop. Completion requires:

- every one of the 68,075 catalog tracks accounted for in provider coverage;
- every available local audio file identity-matched and deep-verified;
- full-track temporal audio analysis for every locally available recording;
- no active paid pods and no orphaned cloud storage/resource;
- retry queues either empty or explicitly classified as permanent no-match;
- calibrated source policies and a manual quality audit;
- search validated on representative DJ use cases;
- dynamic ingestion of newly liked/playlist/local tracks;
- a current backup/export and updated status documentation.
