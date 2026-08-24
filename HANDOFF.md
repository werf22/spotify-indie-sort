# Handoff: Spotify DJ Music Intelligence Database

This is the canonical cold-start document for the next AI agent. Read it before
changing code, restarting services, creating cloud resources, calling a paid API,
or modifying Spotify playlists.

**STATUS 2026-08-24 — analysis running; the similarity app is now a NATIVE macOS app.**

**THE APP IS NO LONGER A WEB PAGE.** `Similar Tracks.app` (built from
`native/SimilarTracksApp.swift` by `native/build.sh`, git-ignored) is an AppKit
window hosting the existing HTML UI in a WKWebView. It starts its own engine and
owns the drag. Rebuild after ANY change to the Swift file; the HTML/JS/Python
need no rebuild, just ⌘R in the app. Diagnostics land in `native/app.log`
(page + drag events) and `native/engine.log` (the engine's stdout).

**DO THIS NOW — money is the binding constraint.** The RunPod balance is
**$5.89** and the remaining 11,566 tracks cost about **$15.96** at the
measured $0.00138/track. That buys roughly 4,276 of them — about
37 % of what is left. The run parks itself cleanly below
$1.00 (`MIN_BALANCE`, D-012), so nothing will be left billing; it will simply
stop with ~7,290 tracks unanalysed until the owner tops up.
Tell the owner the number — do not silently let it stall.

**Analysis state:** 55,267 of 66,833 tracks complete (82.7 %).
Ledger to date: $75.25 over 344 pod-hours, 1159 shards.
Read progress with `cloud_production_orchestrator.completed_count()` — NOT by
counting `audio_analysis_artifacts`, which is pruned once payloads are folded
into features and therefore reads far too low (20.6k vs the real 54.7k).

**Supervision:** launchd keeps `com.jakub.music-db-cloud-production` alive; the
clip prep agent and the workspace GC run beside it. `cloud_pod_guard.py` is the
separately-supervised sweeper — it terminates pods no runner is watching, which
is why a shard whose state says `termination_unconfirmed` is usually already
gone (verified again today: 4 live runners, exactly 1 real pod, $0.17/h).

---

## The similarity app (music_app) — current shape

Open it by double-clicking `Similar Tracks.command`; it serves on
http://127.0.0.1:8765/similar.

Scoring is `score = Σ_groups group_weight × Σ(signal_weight × z)` over 77
signals: CLAP / MAEST / Essentia embeddings, 40 tag types, 32 numbers, and the
musical fields. Presets, per-signal weights, contrast rules and the Camelot
filter live in `similarity_engine.py`; the feature loader is
`similarity_features.py`.

Three panels are open on load and fold independently, remembering what was
folded (`shutPanels` in `similar.js`): **Čo porovnávať** (what must match),
**Čo posunúť** (what must differ, with must/must-not tag rules and its own
weights), and **Profily**. The five system presets sit on the mode bar and can
each be unpinned and restored; pinned user profiles render as chips on the same
bar. Profiles live in folders split on `/` and render as a real treeview whose
expand/collapse state persists.

Playback: local file first, then a freshly fetched Deezer preview via
`/api/preview` (stored preview URLs expire and 403 — always refetch), then a
Spotify embed as the last resort. CUE output goes through `setSinkId()`.
Traktor integration is `music_app/traktor_bridge.py` — reveal, .m3u playlist,
and drag payloads.

On-demand analysis (`analyze_now.py`) starts an `express-` pod, which the
orchestrator deliberately ignores as not its own. It waits up to 330 s for SSH
and tries up to 3 pods, because community hosts often fail to boot. Verified
end to end: 4/4 stages saved for a single track, and the pod terminated after.

---
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


---

## The native app (added 2026-08-24, D-072)

**Why it exists.** A browser may not put a filesystem path on the drag
pasteboard, so dragging a track from the app into Traktor could never work while
the app was a page on localhost. It is now a real application and the drag is a
genuine `NSDraggingSession` carrying file URLs — the same pasteboard Finder
writes, which is why Traktor accepts it.

**How the drag works.** The page arms it: on `mousedown` over a row it posts the
file paths to the app (`armDrag`), and a local `.leftMouseDragged` monitor turns
that into a drag once the pointer has actually moved. The checkbox column is
excluded, so dragging across checkboxes still selects rows. Finder's rule
applies: dragging a row that is part of the selection drags the whole selection.
Verified with a synthetic CGEvent drag — `native/app.log` shows `armDrag` with a
real path followed by `startDrag: … natívna session spustená`.

**setSinkId works in WKWebView** (verified from inside the app and logged), so
CUE routing to headphones survived the move. Do not "fix" it with native audio.

**Engine lifecycle.** The app starts the engine if nothing answers on 8765 and
reuses it otherwise. It deliberately does NOT kill it on quit: a cold start
costs about 164 s (34 s embeddings, 44 s tags, 80 s numbers — measured), so
reopening would pay that again. The engine retires itself after
`IDLE_EXIT_MINUTES = 45` with no requests (`music_app/server.py`), and the page
pings `/api/similar/status` every 30 s while open, which is what keeps it alive.
Measured: cold start 164 s, quit-and-reopen 0 s.

**Known cost, not yet fixed:** the first launch of the day still pays 164 s. The
proper fix is caching the built Library to disk and refreshing it in the
background; it has NOT been done and was not asked for.

## Multi-seed similarity (D-072)

`similarity_engine.similar()` takes `refs=[id, …]` as well as a single `ref`.
Each seed's opinion per signal is z-scored and the seeds are then averaged
**without re-normalising** — that one choice is the whole feature: where the
seeds agree the average keeps its size, where they disagree it cancels toward
zero, so what the tracks have in common drives the ranking on its own. It also
returns `agreement` per signal and `common` (tags at least half the seeds share,
shown under the seed bar). Key and BPM filters pass on the BEST-matching seed,
because in a set a record only has to sit next to one of them.

Verified: Lila + Camo & Krooked returns pure drum'n'bass with 0 of 5 overlap
against either seed alone.

**In the UI:** seed chips under the presets, `＋ pridať track` (or ⌘/Shift-click
a search hit) to add, and `◎ Použi vybrané ako seed` to promote ticked rows.
The last seed set is restored on start — and that restore **waits for
`window.signalsReady`**, because it used to race the signal panel and quietly
compare on three signals instead of twenty-four.
