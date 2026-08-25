# Handoff: Spotify DJ Music Intelligence Database

This is the canonical cold-start document for the next AI agent. Read it before
changing code, restarting services, creating cloud resources, calling a paid API,
or modifying Spotify playlists.

**STATUS 2026-08-25 12:0x — analysis running unattended; funded to finish.**

**26 Aug 00:30 — THE PIPELINE WAS STUCK FOR EIGHT HOURS; THREE BUGS, ALL FIXED.**
Analysis ran and results downloaded the whole time, but nothing reached the
database: last import 15:42, results.jsonl rewritten at 19:28, 20:24, 20:33.
Now 62,254 of 66,703 complete and imports are flowing again.

1. **A remote "fail" threw away 198 good tracks.** The pod raises its fail marker
   when ANY track fails, and that exception skipped the completeness check - the
   only place quarantine.json is written. With no quarantine file the
   orchestrator saw the shard as incomplete and bought another pod for it,
   forever. Two undecodable tracks held 198 finished ones hostage. The runner now
   falls through to the check; a run that produced nothing still fails at
   `required <= successful`. Ten shards have written quarantine.json since.
2. **Resuming an upload corrupted the bundle.** `dd bs=1M seek=N` only starts on
   a mebibyte boundary but the payload was read from the exact byte the pod held,
   so any chunk that died part-way shifted everything after it by up to 1 MiB.
   The bundle then failed its checksum and all ~1.4 GB was re-sent (17 mismatches
   in this run). Every resume point is now snapped down to a whole mebibyte.
3. **The chunk timeout fired during the dependency install.** Failures clustered
   at 10-25 MB - the install window - while anything past it ran clean to the
   end. CHUNK_TIMEOUT 90 -> 240 s.

Diagnosing this needed a logging fix first: messages were truncated from the LEFT
at 70 chars and every ssh failure starts with the same 70 chars of command line,
so an hour of failures looked identical. The tail is logged now, with the ssh
return code (255 = transport died, anything else = dd's exit status).

**THE BINDING CONSTRAINT IS THE HOME UPLINK — not money, not GPUs.**
Measured 25 Aug: 1.72 MB/s. Each shard ships a ~1.4 GB bundle, and a runner takes
a pod only once it holds the single upload slot, so pods are never left idle
paying for a queue. Remaining work ≈ 6,005 tracks ≈ 34 shards ≈ 50 GB,
which is about 8 hours of pure upload. Adding pods or GPU types CANNOT beat this;

Two supply fixes went in anyway, both real:
- GPU pool widened from 4 cards to 8 (`runpod_pilot.GPU_CANDIDATES`), all
  verified with `runpodctl get cloud -c`, all under the $0.40 cap, several
  cheaper than the 3090. Cards under ~12 GB VRAM stay out: four stages share one
  card, and an OOM costs more than a dearer card that finishes.
- A slow uplink is no longer misread as a slow pod (see below).

**STATUS: 62,056 tracks complete on all four stages, 6,005 still in the pool.**
Earlier numbers in this file (61,661 / 59,465 / "remaining 5,042") were written
at different hours of the same night — this line is the current one. Read it
from `cloud_production_orchestrator.completed_count()` and `pending_pool()`,
never by counting `audio_analysis_artifacts`.

**DO THIS NOW — check three things, in this order.**

1. **Disk.** It hit 100 % during the night (465 MiB left) and a database backup
   `cp` died half-written; deleting that truncated file was what freed 47 GiB.
   `df -h .` must show comfortable headroom. `data/music.db` alone is 62 GB, so a
   plain `cp` backup CANNOT fit — use `VACUUM INTO` or back up single tables.
   `gc_analysis_workspace.py` reports 0 reclaimable: the 41 GB in
   `data/cloud_full/clips` is pending work, not garbage.

2. **Analysis.** Orchestrator runs under launchd
   (`com.jakub.music-db-cloud-production`), log `data/cloud_production.log`.
   Progress is keyed by **spotify_id, NOT by `path`** — `audio_analysis_artifacts.path`
   is empty for 141k rows because shard manifests carry no `source_path`.
   Counting distinct `path` makes a healthy run look completely stalled; that
   mistake was made and corrected on 25 Aug.
   Now: see the STATUS line above — that is the one kept current.


3. **A slow uplink is not a slow pod.** Three pods in a row measured
   0.34-0.39 MB/s against the 0.40 floor and were each discarded for "a faster
   one", so the shard made no progress while still paying create/terminate
   cycles. `runpod_full_shard.py` now counts consecutive speed rejections in a
   shared file and, after `SPEED_REJECTS_BEFORE_ACCEPT` (2), rides the pod it
   has. A rate at or above the floor clears the counter.

4. **Money — no longer the constraint.** The balance is **$7.99** and the last
   24 hours cost **$4.99 for 6,789 tracks — $0.00074/track**, about half the
   historical average of $0.00129 ($79.71 over 363 pod-hours, 1,195 shards). The
   remaining 6,005 tracks cost roughly **$4.40**, so the run is funded to finish
   for the first time. At the historical average it would be $7.72 — inside the
   balance, but only just. Watch it rather than assume it.

**Health checked 25 Aug midday:** nothing stuck (0 jobs in `processing` older
than two hours), 56 GiB free, T7 mounted, one pod at $0.22/h, no orphans. The
15,668 rows marked `blocked_missing` all point at `~/Music` paths that no longer
exist — ordinary drift from moved or deleted files, not a fault.


**FILE INDEX — cleaned 25 Aug, do not re-index without the sidecar guard.**
Copying the library onto the exFAT T7 made macOS write a 4 KB AppleDouble
`._name.mp3` beside every real file. 59,652 of those were indexed as music and
1,552 were matched to tracks, so those tracks pointed at a metadata stub.
`purge_applebdouble_files.py` removed them by CONTENT (first four bytes), never
by filename — 169 real songs legitimately start with `._`. Removed rows are
recoverable from `audio_files_backup_20260825034323`.
`index_audio_files.py` now skips AppleDouble on every future scan.

**FILE INDEX — 'matched' now means the file is really on the disk.**
A full inventory of both disks (98,044 real audio files) against the index found
15,668 rows pointing into ~/Music/Tidal Spotify Imports at files that had been
deleted ('Local Library Blindspots 01-04' and siblings). 15,608 tracks counted as
having a file that was not there. Pruned with `index_audio_files.py --prune`;
15,474 of those tracks already had a second live file, so only 134 lost their
last reference. Index now: 96,465 matched, 15,669 missing, 1,575 unmatched.
Of 281 files on disk but not indexed, 279 are in ~/Library (mail, iCloud caches).

**MATCHING CEILING — 16,903 tracks have no file, and no matching can change that.**
66,837 of 83,740 tracks have a file. A full re-scan of ~/Music, ~/Downloads,
~/Documents, ~/Desktop and every T7 music folder added 972 files and matched 441.
`match_unmatched_by_duration.py` then took the leftovers: of 92 unique
"artist title" name matches only **9** had a duration within 5 s — the other 83
were different versions and would have been the WRONG file on the right track.
The remaining ~1.5k unmatched files are ambient/meditation recordings, videos and
untagged Spotify-downloader files that are not in the library at all.

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
