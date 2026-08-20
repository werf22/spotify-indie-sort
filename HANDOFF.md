# Handoff: Spotify DJ Music Intelligence Database

This is the canonical cold-start document for the next AI agent. Read it before
changing code, restarting services, creating cloud resources, calling a paid API,
or modifying Spotify playlists.

**STATUS 2026-08-20 — analysis RUNNING again after five dead days.**

**DO THIS NOW:** watch that rows keep landing
(`SELECT COUNT(*) FROM audio_analysis_artifacts WHERE stage LIKE '%_full'`) and
that spend stays explained (`pipeline_status.py`). Nothing else is urgent.

**WHAT WAS BROKEN (D-065):** every pod from 14-19 Aug analysed NOTHING. `scp`
of the 1.35 GB bundle died with "lost connection" 555 times in a row, zero
successes: one 34-minute session on a 685 KB/s uplink that the upload itself
saturates, and scp cannot resume, so each retry restarted at byte zero. Fixed
with `push_bundle()` — 64 MB chunks written via `dd seek=`, resumed from the
pod's own byte count, then sha256-verified on the pod. Proven: first bundle rose
470 -> 1351 MB with no retry, logged `bundle verified on the pod`, and 800 rows
(200 tracks x 4 stages) landed.

**DO NOT RESTART THE ORCHESTRATOR CASUALLY.** `launchctl kickstart -k` kills its
child runners, which orphans every pod they were driving. The reaper then
correctly terminates those pods — but a pod 26 minutes into analysis, whose
1.4 GB upload already cost ~34 min of uplink, is thrown away. Four pods were
lost that way on 20 Aug. Change code, then wait for the current shards to finish
before restarting, unless the running code is actually broken.

**PREP IS DELIBERATELY STOPPED.** `com.jakub.music-db-prep` is unloaded. 13,758
tracks already have clips — about 69 shards, far more than the uplink can carry
soon. The clip factory writes ~6.5 MB per track into the SAME disk the shard
builder needs, and it starved the builder into a deadlock (prep ran free space
to 40 GiB, builder refused below 45, nothing could consume clips to free space).
Re-enable it with `launchctl load ~/Library/LaunchAgents/com.jakub.music-db-prep.plist`
only once the backlog is drained and free space is comfortably above 70 GiB.

**MONEY, honestly:** 37,810 tracks still need analysis (35,283 on T7, 2,678 local
on the Mac). At the measured $0.0014/track that is **~$53**. The balance after
the owner's top-up is ~$10.6, i.e. roughly 7,000 tracks. The pipeline parks
itself at the $1 floor (`MIN_BALANCE`) and waits — it never auto-funds.

**GUARDS (both supervised, neither depends on an AI session):**
- `com.jakub.podreaper` (launchd, KeepAlive) runs `pod_reaper.py`. It had died
  silently twice with the session that started it. Proven by killing pid 90375
  and watching launchd start 90819 thirty seconds later (D-064).
- `com.jakub.music-db-cloud-production` (launchd) runs the orchestrator. NOTE:
  `pkill` does not stop it — launchd restarts it. Use `launchctl unload`.

**THE COMMENT COLUMN IS FIXED (D-063):** the owner's "06 Energy" labels were
being replaced by musical keys ("Em") one track per play, because most files
carried a key in their own comment tag and Traktor re-reads file tags on load.
577 already-lost labels were recovered from Traktor's own backups; the collection
value is now written INTO 30,471 files, so a re-import changes nothing. 99.7%+ of
a 1,200-file sample agrees. Reversible via `traktor_comment_pin.py --restore`.
603 entries flipped before the oldest surviving backup and are NOT recoverable.

**THE HARD LIMIT, state it before promising anything:** the uplink measures
685 KB/s. 25,665 tracks remain, which is 136 GB and ~55 h of pure upload. GPU is
NOT the constraint ($13 for the whole remainder) and neither is credit ($19.40,
28 h of running). An overnight window carries ~25 GB, i.e. 4,000-5,000 tracks.
Any plan that promises "all of it by morning" is wrong on arithmetic.

**THE EXTERNAL DISK IS PART OF THE SYSTEM.** 80,437 of the 116,939 known audio
files live on the T7 drive; only 36,502 are on the MacBook. Reading from an
unplugged volume does not fail, it BLOCKS — that is what made clip prep look
deadlocked for a night (six worker threads idle, no ffmpeg, 12 s of CPU across 19
minutes). Prep now drops candidates whose source is not present, so an absent T7
slows the pipeline to local-only work instead of hanging it, and its tracks
resume by themselves when the disk returns. `data/prep_loop.log` states the
disk's presence every cycle — read that FIRST when throughput looks wrong.

**DEFECT 2, fixed but worth knowing:** `pod_reaper.py` spent a night killing every
RESUMED shard's pod within minutes — "no results in 2053 min (age 3 min)" —
because it read the results FILE's mtime, which on a resume predates the pod, and
its setup grace only applied to an EMPTY file. Idle is now clamped to the pod's
own age and the grace applies on age alone (45 min, to cover a real 32-minute
upload). The regression is locked in as `tests_pod_reaper.py`; run it after ANY
change to that file — 11 branches, all must pass.

**What is running unattended right now:** the orchestrator (launchd, auto-restart)
building shards and driving pods; `prep_loop.sh` making clips; `pod_reaper.py`
every 2 min as a daemon job; `index_audio_files.py` walking all of T7 to fill in
the 16,214 tracks that still have no path. Watch with `pipeline_status.py`.

**Unfinished experiment:** the 96 kbps clip A/B (D-053) would halve the upload
wall from 55 h to 27 h. Its first two runs died — one on a non-UTF-8 byte from
the pod (fixed in `runpod_pilot.run`, which every runner shares), one incomplete.
BPM decides it: a tempo that moves is a wrong number in a DJ library, not a
tolerable quality trade. Build with `validate_bitrate.py --build`, run
`probe_bitrate_run.py`, compare with `--compare`.

**THE MONEY GUARD is `pod_reaper.py`** (D-050) — start here if a pod is ever
suspected of billing for nothing. It runs every 2 min as a daemon job and kills
any `music-db-*` pod that cannot prove it works: no runner owns it (3 min grace),
older than 75 min, or no results in 12 min past the setup grace. It judges from
the locally pulled `results.jsonl` files, never SSH, so it stays honest during
the network failures that cause abandonment in the first place. Log:
`data/pod_reaper.log`. Check it with:
`./.venv/bin/python pod_reaper.py --once --dry-run` (reports verdicts, kills
nothing).

**What guarantees a pod never bills while idle** (audited 2026-08-11):
a pod is not created until an upload slot is free (D-047, proven live: 9 runners,
2 pods, 7 waiting without pods); the GPU must compute before the 1.3 GB upload
(D-041); progress is counted in successes, not bytes (D-041); stalls abort after
15 min; the runner terminates its pod on completion; the orphan sweep deletes any
pod no live runner explains after a 10-min grace; and RunPod's own
--stop-after/--terminate-after, now 1.92 h instead of 5.1 h (D-048), is the only
one that survives the local machine dying. The pod CANNOT stop itself — its
injected API key is rejected by RunPod's own API, and the guard that pretended
otherwise had never once fired.

**READ THIS BEFORE OPTIMISING ANYTHING:** a shard's paid time is NOT mostly
analysis. Measured across 11 shards: 20.2 min of overhead against 9.6 min of
actual work — 68% of every paid shard. And that overhead is not fixed either;
`venv` + `pip install` of torch/librosa/essentia are CPU-bound, so a 28-vCPU pod
reached its first result in 11.4 min where the mixed-CPU fleet averaged 20.2.
Two claims made earlier the same day were wrong and are corrected in DECISIONS:
the vCPU floor is not "the biggest lever" (it moved end-to-end time 8%), and the
overhead is not fixed. Measure the overhead split before tuning threads again.

**What got cheaper today** (all measured on live pods, not estimated):
- D-037 runs all four stages concurrently on one pod: 37 min/shard instead of
  ~57, i.e. **$0.00066/track** against the $0.0017 lifetime ledger average.
- D-044 is the big one still to prove itself: three pods, all RTX 3090, all
  $0.22/h, had enforced CPU quotas of 6, 17.9 and 27.2. The same money buys a
  4x spread in CPU, and since rhythm (HPSS) and essentia (TensorFlow) are
  CPU-bound, wall clock — the thing actually billed — tracks CPU, not GPU. The
  runner now rejects hosts under 16 vCPU for two attempts, then takes what is
  free so a thin market cannot stall a shard.
- D-039 derives every thread pool from the container's real cgroup quota, which
  is what makes the above safe: no hardcoded CPU count is correct.
- D-042 gives the rhythm tail 4x its previous threads; it is the only stage
  still alive for roughly the last 46% of a shard.
- D-040 quarantines a (track, stage) pair after 3 identical failures. One
  unanalysable clip had been holding 199 finished tracks hostage and re-buying
  a pod every orchestrator cycle — 21 paid launches for one dead track.
- D-041 proves the GPU computes before uploading 1.3 GB, and counts progress in
  successes rather than bytes. A pod with a wedged CUDA driver had billed a
  full run while failing all 375 tracks, invisible to the byte-growth watchdog.
- D-045 installs dependencies WHILE the bundle uploads, worth a MEASURED 4.8
  min per shard (16-19% of wall clock, taking $0.00066/track to ~$0.00053).
  The install used to run after the upload because it lived inside run.sh,
  which cannot start until the 1.3 GB bundle lands. Measured on ONE pod
  (install duration vs the same pod's upload) — comparing two shards gives
  nonsense, because each uploads under different contention. Verified in production by
  watching two pods side by side: shard-0165 had its venv built while its bundle
  was 1% transferred; shard-0163, created minutes earlier without the change,
  had almost its whole bundle and had installed nothing. Fail-safe: if the
  prewarm never starts or dies, run.sh does the identical setup itself.
- D-043 fixed the one enrichment lane that was quietly stuck: 603 bandcamp
  tracks orphaned in `processing` since 2026-07-18, unreachable by a selector
  that only looked at missing-or-failed rows. Orphans now self-heal hourly.

**Enrichment backlogs closed 2026-08-11:**
- Bandcamp: the 603 orphans reclaimed by D-043 have all resolved — 512 became
  successes, 92 no-match. The lane now reports zeros because it is genuinely
  exhausted; the last 55 failures have attempts=3 and a real cause (49 are
  "Missing artist tag!", i.e. tracks with no artist metadata at all).
- FreqBlog review: 210 rejected as unrelated, 3,478 kept, NOTHING accepted —
  see D-046. Do not try to clear the rest with looser string matching: of the
  1,084 that a parenthesis-stripping rule would match, 1,083 differ inside the
  brackets, so it would put the original's BPM on "Truth Hurts (DaBaby Remix)"
  and a slow-motion mix's on "Vivo". Resolving these needs ISRC/duration
  cross-checks or listening.

**Enrichment state — everything else is genuinely finished**, not idle: all
71,306 tracks carry a terminal status for ReccoBeats, TheAudioDB, MusicBrainz,
Last.fm and Deezer. The 6,207 tracks with no Deezer row simply have no ISRC,
which is what Deezer matches on.

**One decision waiting for the owner:** FreqBlog has 3,686 tracks in
`needs_review`. Of those, 1,089 have an exactly-matching normalised title AND
artist (almost certainly correct, just below the auto-accept threshold), 1,894
match on one field only, and 703 match on neither. Only 20% are already covered
by our own 4-stage analysis, so the rest would genuinely gain data. Auto-
accepting changes the meaning of data in a DJ database — wrong BPM or key is
worse than a missing value — so it was left for an explicit decision.

**Disk:** 51 GiB free. Acquisition is paused by the disk guard (`paused=1` in
sync_control) — that gates music DOWNLOADING only, not clip prep or analysis,
and leaving it paused protects the headroom the shards need. Resume manually
with `sync_control.py resume-all` when the collection work is done.

**Note on results.jsonl:** imported shards get theirs deleted by
prune_analyzed_clips.py. That is safe and intended — the per-window timelines
live in `audio_analysis_artifacts.payload_blob` (json+zlib), and the runner now
short-circuits on `imported.ok` so a stripped shard can never re-buy a pod.

*The full loop is now automatic* (D-031/D-032): hourly index → duration
re-verification of fuzzy matches → identity assignment → Opus prep →
GPU analysis → clip/bundle pruning. New downloads enter it by themselves;
this was the day's main structural fix.

*Metadata enrichment is effectively COMPLETE.* Every free provider has
attempted every eligible track and now returns zeros because its queue is
drained, not because it is broken: Deezer 57,035 (the ~9k "remaining" have
no ISRC, so they are unreachable by design), MusicBrainz 28,505, MB genres
6,494 tagged of all known MBIDs, TheAudioDB 8,677, Last.fm tracks 2,271
(67,251 genuinely have no tags upstream), Discogs 45,531 across sources.
FreqBlog is at its 150,000/150,000 monthly cap and resumes automatically on
the August reset — no action needed.

*Opus prep* runs at 4 FFmpeg workers (raised from 1 on 2026-07-29 because
it is the only work advanceable while pods are unfunded; revert to 1 in
`com.jakub.music-db-cloud-full-prep.plist` if the laptop runs hot, D-020).
~750 clips left. A prior pass recorded 320 prep failures whose causes land
in `data/cloud_full/failures.json` only when the run ends — a sample of the
not-yet-processed files transcodes fine, so the cause is still unknown and
should be read from that file rather than assumed.

**Earlier milestone 2026-07-21: the first full-track batch completed —
5,393 of 5,393 preparable catalog tracks** have all four stages (rhythm,
MAEST, Essentia, CLAP) analyzed and imported. (Track 5,394 of the original target has a
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
