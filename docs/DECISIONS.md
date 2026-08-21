# Decision log

This log records binding decisions and why they were made. New agents should
append a dated entry instead of silently reversing one.

## D-001 — Provenance-preserving multi-source database

**Decision:** Store each provider separately with confidence and raw payload;
select preferred fields through policy/views.

**Why:** Providers disagree, coverage varies by catalog niche and future models
may improve. Overwriting would make quality impossible to audit.

## D-002 — SQLite-first local architecture

**Decision:** Use local SQLite in WAL mode rather than a hosted database.

**Why:** Lowest cost, private, portable and sufficient for 68k tracks plus
millions of observations. Hosted vector/search components can be added later
only if measured need justifies them.

## D-003 — Spotify normal API is not the audio-feature foundation

**Decision:** Do not block on Spotify Audio Features/Audio Analysis access.

**Why:** Access is deprecated/restricted and normal Spotify API does not expose
lifetime play counts. ReccoBeats, FreqBlog, legacy public datasets, local audio
models and imported streaming history cover the required functions.

## D-004 — FreqBlog Starter selected; SoundNet rejected

**Decision:** Use the manually purchased EUR 39/month FreqBlog Starter plan and
do not purchase/enable SoundNet.

**Why:** Individual probes found 40/40 including underground Tebra material.
ReccoBeats already covers exact Spotify IDs for free, while FreqBlog supplies
long-tail and metadata breadth. SoundNet would mostly duplicate the stack.

## D-005 — OneTagger must support database-only enrichment

**Decision:** Feed SQL identities directly to OneTagger-style matching instead
of requiring local files or M3U placeholders.

**Why:** The database covers far more tracks than the local audio collection.
The Python bridge and standalone Rust feeder make Discogs/Bandcamp enrichment
useful immediately and preserve provider fields in SQLite.

## D-006 — Exact-first identity matching

**Decision:** Spotify ID/ISRC first; conservative artist/title/duration second;
ambiguous matches remain unresolved.

**Why:** Wrong metadata attached to a track is worse than missing metadata for
DJ similarity and future acquisition.

## D-007 — Quality gate before paid scale-up

**Decision:** Test small stratified samples, measure quality/time/cost/failures,
then extrapolate before scaling.

**Why:** Prevents wasting money and detects underground-catalog gaps or model
hallucination before a 68k run.

## D-008 — Full-track temporal coverage supersedes a 45-second excerpt

**Decision:** Decode every available full track and tile it into model-native
windows. Store temporal outputs and aggregates.

**Why:** One short excerpt misses beatless intros, breakdowns, genre shifts and
localized moods. Passing one undifferentiated full track is impossible for
fixed-context models and would obscure temporal structure. Full tiling gives
the best combination of coverage and trust.

Implementation:

- MAEST and CLAP: 10-second full-track windows;
- Essentia: native approximately 1 Hz full-track patches;
- Beat This: 45-second windows, 40-second hop.

## D-009 — Supervised and consensus tags are canonical; CLAP is candidate-only

**Decision:** Preserve CLAP's open-ended vocabulary but do not promote it alone.

**Why:** Smoke testing produced plausible but false instruments such as violin,
bongos or djembe. CLAP remains valuable for semantic similarity and candidate
moods, but canonical tags need supervised support or independent agreement.

## D-010 — Historical split: local Essentia/rhythm, cloud MAEST/CLAP

**Status:** Superseded by D-020 after the owner prioritized a cool, minimally
loaded laptop.

**Why:** Smoke timing showed Essentia/rhythm did not gain enough from paid GPU
execution. MAEST/CLAP are GPU-friendly and together project within the existing
USD 10 credit.

## D-011 — One cloud shard/pod at a time

**Status:** Partly superseded by D-022. One bounded production pod remains the
default until measured balance projections justify a second parallel pod.

**Decision:** Use immutable 100-track shards sequentially with one bounded pod,
not the earlier four/eight-GPU plan.

**Why:** Existing credit is limited, local preparation is still feeding the
queue, and measured throughput is sufficient. Sequential execution minimizes
unexpected spend and simplifies resumability/audit.

## D-012 — No automatic funding

**Decision:** Agents may consume existing explicitly funded credit only.

**Why:** Direct owner instruction. Balance below USD 1 pauses production; hourly
pod cost above USD 0.40 is rejected.

## D-013 — Continue on internal disk until 50 GiB remains

**Decision:** Keep processing now; notify and pause at 50 GiB free, then migrate
to the SSD the user plans to buy.

**Why:** Avoid losing time while preserving a hard safety margin.

## D-014 — Blindspot playlists exclude Missing Tracks and all Traktor entries

**Decision:** Build separate Spotify playlists only for tracks absent from local
files, absent from Traktor and absent from the pre-existing Missing Tracks
playlist mapping.

**Why:** The user already had Spotify playlists for Missing Tracks and did not
want duplicates. Four playlists contain 26,142 Spotify-only blindspots.

## D-015 — Utility playlists are not taste evidence

**Decision:** Exclude technical Traktor/missing-track playlists from the
original Indie taste export/classification.

**Why:** A 9,500-track utility playlist and similar artifacts were matching
outputs, not curated listening preferences.

## D-016 — Original Indie classifier favors inclusion on transient failure

**Decision:** Classification batch failure defaults to keep, while deterministic
post-rules exclude known frequency-healing/solfeggio patterns.

**Why:** A false positive is visible and removable; a false negative is hidden.
The post-rule fixed inconsistent boundary versions across asynchronous batches.

## D-017 — Maximum Indie playlist size was corrected

**Decision:** The user rejected a 43k “everything non-organic” interpretation.
The intended output is narrowly Indie/adjacent (maximum 2,000, likely fewer),
and the Liked Songs-only version was extended to at least 500.

**Why:** “Not ecstatic dance” was a negative boundary, not permission to include
all other music.

## D-018 — Preserve older plans but label them superseded

**Decision:** Keep historical documents/code/data for audit; make the current
handoff explicitly authoritative.

**Why:** Deleting experiments would erase rationale, while leaving them
unlabelled could cause the next agent to restart obsolete 45-second or multi-GPU
paths.

## D-019 — Cloud bundle requires semantic preflight, not checksum alone

**Decision:** Every new shard/bundle format must pass path-membership checks and
one full MAEST + CLAP inference locally before paid production.

**Why:** The first production bundle was byte-valid but contained paths that did
not exist after extraction and omitted a Python import dependency. Checksums
cannot detect semantic packaging errors.

## D-020 — All heavy model inference runs in the cloud

**Decision:** Disable local Essentia, rhythm and older local model runners.
Run rhythm, MAEST, Essentia and CLAP on RunPod. Keep only one background-priority
FFmpeg preparation worker locally.

**Why:** The owner explicitly prefers minimum laptop heat/CPU load. Essentia is
run concurrently on pod CPUs while GPU stages execute, so much of its cost is
hidden rather than added sequentially.

## D-021 — RTX 3090 is the default price/performance GPU

**Decision:** Prefer community RTX 3090 at the observed USD 0.22/hour. Test
parallelism after one complete all-stage production shard rather than assuming
a more expensive GPU is cheaper.

**Why:** RunPod's current community reference prices are roughly USD 0.22/hour
for 3090 and USD 0.44/hour for 4090. A 4090 must exceed 2x end-to-end throughput
to reduce cost, while Essentia depends mainly on pod CPU. The attempted bounded
4090 benchmark found no available community machine and incurred no pod cost.

## D-022 — Parallelism is measurement- and balance-gated

**Decision:** Prefer RTX 3090 and overlap Essentia on pod CPU with the GPU lane.
Do not launch a second production pod until a complete 100-track, four-stage
shard proves the end-to-end cost and the remaining prepaid balance can cover it.

**Why:** Two identical pods can nearly halve elapsed time while keeping pure
inference cost similar, but duplicate setup/upload overhead and increase the
rate of spending. The owner prioritizes speed but forbids automatic funding.

## D-023 — Pod termination must be confirmed, never assumed

**Decision:** `runpod_pilot.terminate()` retries `runpodctl pod delete` a few
times and only writes local `status="terminated"` when RunPod's response
explicitly says `deleted: true`. Any other outcome is saved as
`status="termination_unconfirmed"` with a loud stderr warning, and every
caller's existing "is this pod really gone" check (`status == "terminated"`)
already treats that new status as *not* gone, so the next run reuses the
saved pod/SSH info instead of creating a duplicate.

**Why:** Found live on 2026-07-19: two pods billing simultaneously for
shard-0002 (`cp6v9hygqv0u60` and an untracked `6k2dt0i0n5hy73`), pushing the
account's `currentSpendPerHr` above the $0.40 ceiling. Root cause: a prior
run's cleanup `finally:` block hit a transient DNS failure
(`dial tcp: lookup api.runpod.io: no such host`) while calling
`runpodctl pod delete`; the error payload still parsed as JSON, so the old
`terminate()` saved `status="terminated"` unconditionally. The next shard
invocation saw `status == "terminated"`, assumed the old pod was gone, and
created a fresh one — orphaning the first, which kept running and billing
with nothing local tracking it. That pod had already produced valid results
(100/100 `rhythm_full`, 100/100 `maest_full`, 51/51 `essentia_full`),
recovered to `data/cloud_full_shards/shard-0002/recovered/` before deletion.
Deleting the orphan itself required a `runpodctl pod delete` call, which this
assistant is not permitted to run directly (blocked by the coding
environment's own safety classifier for actions against paid external
infrastructure) — the owner deleted it manually. See `docs/OPERATIONS.md`
"Duplicate/orphaned pod after a cleanup failure" for the recovery steps.

## D-024 — Retire stale pre-full-track LaunchAgents left running

**Decision:** Disabled and stopped two installed LaunchAgents that predate
the current design and were never cleaned up: `com.jakub.music-db-cloud-prep`
and `com.jakub.music-db-runpod-pilot`
(`launchctl disable` + `launchctl bootout`, same mechanism already used for
`essentia-full`/`rhythm-full` under D-020). Their `.plist` source files stay
in the repo root for history; only the installed copies under
`~/Library/LaunchAgents/` were disabled.

**Why:** Found live on 2026-07-19 while auditing "is everything running."
`com.jakub.music-db-cloud-prep` runs `prepare_cloud_audio_pilot.py` with 4
workers and no `--full-track`, writing to `data/cloud_production/` — the
pre-D-008 45-second-clip pipeline. Nothing in the codebase reads that
directory; it was pure duplicate CPU/disk work competing with the real
single-worker full-track prep agent (`music-db-cloud-full-prep`) for the same
machine resources, on every reboot, indefinitely. `com.jakub.music-db-runpod-
pilot` runs the standalone `runpod_pilot.py` every 120 seconds
(`StartInterval`); its own pilot already reached its 300-result completion
target on 2026-07-18, so it had been silently no-op-ing on every run — but it
retains its own independent pod-creation path, so if `data/cloud_pilot/
runpod-results.jsonl` were ever touched or lost, it would start creating pods
on its own schedule, outside anything the production orchestrator (or D-023's
fix) tracks. Neither agent was documented in `HANDOFF.md` or
`docs/OPERATIONS.md`, which is how they went unnoticed.

## D-025 — Detached pod execution; billed compute decoupled from local network

**Decision:** `runpod_full_shard.py` no longer drives the analysis through a
live SSH session. The pipeline runs detached on the pod (`nohup` + `run.done`
/`run.fail` markers); the local runner polls cheaply, pulls results
incrementally by byte offset, relaunches a dead remote runner (max 2), and
aborts on a genuine stall (no result growth for 15 min after a 25-min setup
grace). Server-side stop/terminate deadlines are computed from the shard's
actual pending stage-pairs instead of a fixed 3 h/3.5 h. The pod additionally
stops itself ~15 min after the done/fail marker if nobody collected it (via
the pod-scoped `runpodctl` credential; best-effort, unverified until the next
funded shard). A complete-but-unimported shard is now always imported
(idempotent, serialized by `import.lock`, confirmed by `imported.ok`).

**Why:** Three of the first 17 shards lost 2–5 hours each to network drops:
the SSH session died, the remote pipeline died with it (SIGHUP), and the pod
idled on billing until its distant fixed deadline. Measured waste ≈ $1.3 of
≈ $7 spent. Separately, a crash between result download and import left
shard-0018's 100 tracks absent from the DB while the builder would have
re-bought them on a new pod — the guaranteed-import path recovered them for
free. With detached execution a network drop costs nothing: the work
continues, and reconnection resumes collection.

## D-026 — Orchestrator: balance-gated parallelism, orphan sweep, cost ledger

**Decision:** `cloud_production_orchestrator.py` manages up to 2 concurrent
shard runners (2nd pod only above $4 balance; 0 below $1, D-012 unchanged);
sweeps every cycle for `music-db-*` pods that no shard state explains and
deletes them immediately; blocks new launches while actual account spend/hr
exceeds what tracked pods explain (+$0.06 tolerance); appends a per-shard
cost ledger (`cost_ledger.jsonl`) and exposes it plus per-shard progress in
`orchestrator_status.json`. Shard size raised 100 → 200 to halve per-pod
setup overhead; the endgame builds a final small shard (minimum 1) when the
remaining pool is smaller than a full shard. Monitoring reads go through a
new read-only DB connection (`musicdb.connect_readonly`) so status loops can
no longer die on, or contribute to, `database is locked`.

**Why:** The owner's directive of 2026-07-20: same quality, less money, more
speed, and paid resources must be physically unable to run without doing
work. The sweep is the standing enforcement of the D-023 class of failure;
the ledger makes cost per track a measured number instead of an estimate;
parallelism is the D-022 gate finally exercised (17 clean all-stage shards
measured at ≈ $0.005/track).

## D-027 — Shard builder excludes tracks claimed by unimported shards

**Decision:** `build_cloud_full_shard.py` skips every track present in the
manifest of any existing shard without an `imported.ok` marker.

**Why:** Caught live within minutes of enabling parallel mode (2026-07-20):
the builder selected pending tracks by database state only, and with two
builds in one orchestrator cycle (plus retries) the DB knew nothing about
in-flight work — shards 0019/0020/0021/0022 came out as four IDENTICAL
200-track shards. Two duplicate pods were running before containment; total
damage ≈ $0.11 because all failed/stopped before analyzing (the first two on
a repeatedly bad community host, 99.69.17.69, that reset every scp — the
same host as the D-023 orphan). Duplicates were deleted, the exclusion was
added, and a rebuilt shard-0020 verified 0-track overlap against the
in-flight shard-0019. Sequential operation never exposed this because a
shard always finished importing before the next build (D-011).

## D-028 — Owner-approved pod scale-out; funds-scaled parallelism

**Decision (owner, 2026-07-20):** run as many pods in parallel as useful —
total cost is identical at any parallelism, only wall-clock changes. Cap
implemented at 8 concurrent pods: above that the laptop's uplink (a 1.5 GB
bundle upload per shard) and community RTX 3090 availability become the
serializer, so extra pods would idle-bill while queueing for upload.
`allowed_parallel` scales with balance headroom (one pod per ~$0.50 of
spendable balance above the $1 floor); the per-pod $0.40/h ceiling and the
never-fund rule (D-012) are unchanged. The runner's account-level spend
check moved to the orchestrator (which knows its own pods); the runner keeps
a balance-only gate — otherwise no parallel runner could ever start, since
siblings already bill more than the old whole-account $0.40/h sanity limit.
Measured baseline for the scaled run: $0.0021/track, ~2 h per 200-track
shard (ledger, shards 0023/0024).

## D-029 — Enrichment expansion wave 1 (roadmap items B and D1)

**Decision:** (a) The OneTagger Discogs bridge gains optional token auth
(`DISCOGS_TOKEN` in `.env`) — 25 → 60 req/min — and a structured
`track=`+`artist=` search (Discogs indexes tracklists) gated on artist
similarity ≥ 0.75, falling back to the legacy free-text query; cache keys
bumped to v3 for the structured path. (b) New `enrich_musicbrainz_genres.py`
harvests genre/tag lists for the 23.5k already-resolved MBIDs. Because
MusicBrainz allows ~1 req/s per IP and TWO workers now share it, all MB
requests serialize through a cross-process file-lock limiter in
`enrich_musicbrainz.get()` — verified live after the unlimited first attempt
produced SSL connection drops. The Deezer 30-s preview audio tier was also
owner-approved and is queued to start after the 5,394 full-track batch
finishes (docs/ENRICHMENT_ROADMAP.md, task list).

## D-030 — Local-only tracks get synthetic identity; queue generalized (D-011 follow-through)

**Decision (owner, 2026-07-21):** every locally-owned audio file under 15
minutes — including the 1,585 that matched nothing in the 68,075-track
Spotify catalog — is now eligible for the full audio pipeline, matching the
owner's "analyze everything on my computer except long DJ/ED sets" request.
`promote_unmatched_local_tracks.py` does two passes: (1) ISRC recovery,
restricted to ISRCs that map to exactly one catalog track — an ISRC shared
across 2+ tracks (common for reissues/compilations; ~130 cases found) stays
unresolved per D-006 rather than guessed; (2) everything else with a known
duration ≤ 900s gets a synthetic identity (`local_<sha1(path)[:16]>` — never
a valid 22-char Spotify ID) and a minimal `tracks` row
(`library_sources='local_only'`, `uri='local:<path>'`, empty `artist_ids`/
`genres` — the real values arrive through the same tag pipeline). Result:
71 ISRC recoveries, 1,496 synthetic local-only tracks, 20 excluded as >15 min,
1 skipped for unknown duration. Nothing else changed: the shard/pod pipeline
keys everything by an opaque `spotify_id` string already, so local-only
tracks flow through D-025/D-026 unmodified.

Follow-through: `cloud_production_orchestrator.py`'s `EXPECTED = 5394`
(D-011's deliberately-immutable first-batch target) is replaced by a live
`target_count()` — every `audio_files` row with `scan_status='matched'` —
per the engineering-backlog item deferred until the first immutable batch
finished (it now has, 2026-07-21). `coverage_report.py` and
`pipeline_status.py` exclude `local_only` tracks from the 68,075-catalog
percentages so this never silently inflates "Tracks: 68,075" — reported as
a separate line instead.

**Why:** the owner explicitly wants maximum tag/mood/beat-type coverage
usable without listening, for every real song on the machine, not only the
Spotify-catalog subset. Synthetic identity (vs. a schema/FK change) was
chosen because `audio_analysis_artifacts`/`tags`/`track_attributes` treat
`spotify_id` as an opaque string throughout — reusing it costs one small
script instead of forking the entire analysis+import path.

**Known gap (closed by D-031):** the two prior scans covered `~/Music` and
(from an earlier ad-hoc run) `~/Downloads`; the owner confirmed `~/Music` is
the whole collection, so no broader rescan was run. If other folders exist,
extending `index_audio_files.py --root` before re-running the promoter is
the path.

## D-031 — Whole-collection scope; indexing, identity and pruning automated

**Decision (owner, 2026-07-29):** analyze *every* audio file on the machine
under 15 minutes, catalog-matched or not. Three changes make that real:

1. **Indexing is automatic.** `index_audio_files.py` had never been wired
   into any automation — it ran only by hand, so ~17,700 files downloaded
   after the last manual run were invisible to the entire pipeline while
   sitting in `~/Music`. It is now an hourly daemon job (with
   `promote_unmatched_local_tracks.py` behind it), roots from
   `AUDIO_LIBRARY_ROOTS`. Rescan result: **28,828 files** indexed, up from
   11,171; 27,619 matched; 1,183 new local-only identities.
2. **The 15-minute rule is enforced everywhere.** It previously applied only
   to local-only promotion, so 95 catalog-matched DJ/continuous mixes (up to
   109 minutes) were still eligible. `prepare_cloud_audio_pilot.py` now
   filters on `COALESCE(file duration, catalog duration) <= 900`. This is
   also the largest single cost lever, since GPU time scales with length.
3. **Derived data is pruned continuously.** Clips and shard bundles were
   kept forever: 82 GB of shard directories plus 36 GB of clips, and the
   clips could not be freed at all because shard directories hold hardlinks
   to the same inodes. `prune_analyzed_clips.py` (half-hourly daemon job)
   removes both once all four stages are in the database, keeping
   `manifest.csv`/`results.jsonl`/state as the audit trail and never
   touching an unfinished shard. First run freed **76.9 GiB** (182 → 258 GiB
   free). Prep skips fully-analyzed tracks, so a pruned clip is never
   re-encoded.

**Resulting scope:** 24,320 eligible tracks, 5,438 already analyzed,
**18,882 remaining ≈ $23** at the measured $0.0012/track. Peak clip storage
would be ~125 GB unpruned; with continuous pruning it stays a small rolling
window, which is what makes the full collection feasible at all.

**Excluded deliberately:** `Library/Group Containers` (application sounds),
`Desktop/GitHub` (repository assets) and `Documents/Journal ALL` (121
personal voice recordings — genre/mood analysis is meaningless there and the
owner asked for music). `~/Music/Music` (Apple Music managed) is empty.

**Prep throughput:** `ProcessType=Background` (set under D-020 to keep the
laptop cool) put each FFmpeg worker under macOS background QoS at ~2.3% CPU,
giving 24 clips/hour — 33 days for this backlog. Switched to `Standard`:
51-73% CPU per worker, ~4,000-5,000 clips/hour, roughly 4 hours total. The
plist is the revert point once the backlog is done.

## D-032 — A later-known duration retracts a fuzzy match

**Decision:** `verify_match_durations.py` (hourly daemon job, ahead of the
identity promoter) unmatches any `title_artist_duration` match whose file
and catalog durations differ by more than 20 seconds, deletes the audio
artifacts produced from that file, and lets the promoter give the file its
own local-only identity.

**Why:** `index_audio_files.match()` scores duration a neutral 0.5 when the
file's duration is unknown at index time, so artist+title agreement alone
can clear the 0.82 threshold (0.72x1.0 + 0.28x0.5 = 0.86, matching the 0.95
confidence seen on the bad rows). Durations arrive later from tag re-reads
and ffprobe verification, and 89 of those matches then proved to pair
different recordings of the same song — a 196 s radio edit filed under a
450 s extended mix, "Come To Me" at 188 s under a 394 s track, and so on.
Analyzing one recording and storing the result under another is precisely
the failure D-006 exists to prevent, so the match is retracted rather than
kept. First run: 89 demoted, 188 artifact rows removed, all 89 re-identified
as local-only; a second run finds nothing, so the loop converges.

**Scope limit:** `isrc_tag` matches are left alone. An ISRC is the
publisher's own identity assertion; differing masters sharing one ISRC is a
labelling reality, not something this check should overrule.

## D-034 — Adaptive rhythm coverage; full tiling kept where it earns its cost

**Decision (owner asked to cut cost without losing quality, 2026-08-10):**
the rhythm stage analyses a probe of 4 evenly spaced windows first and stops
there when they unanimously agree on rhythm pattern, beat presence and tempo
(BPM spread <= 1.0); otherwise it analyses the whole track as before. MAEST
and CLAP keep full tiling.

**Why, and why only rhythm.** Both were measured by replaying the per-window
timelines of already-paid results — no GPU spend for the study
(`study_window_budget.py`):

- *Blind truncation is not viable.* Fixed budgets of 3-8 windows reproduced
  the full-track rhythm verdict in only 82-94% of 4,061 tracks. Cheap, but a
  DJ database that is wrong about the beat on 1 track in 10 is not the goal.
- *Adaptive is free.* Probing 4 windows and only trusting a unanimous verdict
  matched the full-track answer on rhythm pattern, beat presence AND BPM
  (within 0.5) in **100.0% of the same 4,061 tracks, while skipping 28% of
  the windows**. Tracks whose probe disagrees — the layered, shifting ones —
  still get complete coverage, which is exactly where it matters.
- *Genre cannot be cut.* The same study on 2,538 MAEST tracks (avg 30.3
  windows): 12 windows reproduced the top genre only 90.9% of the time and
  the top-3 set 78.5%. Adaptive probing gives 100% top-1 but saves just 3%,
  because only 5% of tracks are genre-uniform window to window. Genre
  genuinely varies inside a track, so full tiling is justified spend, not
  waste.

`window_count` now reports what was actually analysed, with
`window_count_available` alongside and `coverage_mode` set to
`adaptive_probe_uniform_track`, so a shortened run can never be mistaken for
full coverage (D-001).

**Related, same session:** the rhythm stage's real cost turned out not to be
GPU at all — librosa's harmonic/percussive separation is ~3.1 s per window,
single-threaded, and matched the whole stage's runtime while the paid GPU sat
idle. It now runs concurrently across the pod's vCPUs (identical output).
Measured cost by GPU tier was also compared: RTX 3090 ($0.22/h, 99 min/shard)
and RTX A4000 ($0.17/h, 127 min) both land at $0.0018/track and the 4090 at
$0.0025, so GPU selection offers nothing further and was left alone.

## D-035 — CLAP capped at 16 windows; MAEST stays full; fp16 gated on a probe

**Decision (owner: cut cost aggressively, small quality loss acceptable,
2026-08-10):** CLAP analyses at most 16 evenly spaced windows per track.
MAEST keeps full tiling. Half precision (AUDIO_FP16=1) is wired into both
GPU models but stays OFF until a 20-track probe — built from tracks already
analysed in float32 so the comparison itself is nearly free — confirms the
labels hold on real CUDA hardware.

**Evidence (all from replayed, already-paid results; no GPU spend):**

- *CLAP:* on 1,283 tracks (avg 30.7 windows), a 16-window subset reproduces
  the full unweighted aggregate embedding at median cosine 0.9997
  (p5 0.9987, p1 0.9970) — less drift than the energy-weighting scheme
  itself contributes (its full-vs-stored cosine: median 0.9996, p5 0.9973).
  The subsample error is therefore below the pipeline's own design noise
  while cutting CLAP inference ~47% (~6% of total per-track cost) and
  shrinking the largest results.jsonl payloads. Adaptive probing was also
  tested and rejected for CLAP: only 11% of tracks are mood-uniform, saving
  just 8% — the fixed cap is strictly better here.
- *MAEST:* the earlier label-proxy finding (D-034) was re-verified on the
  TRUE aggregate (softmax over stored segment_logits, subset mean vs full
  mean): even 20 of ~30 windows change the top-1 genre on 4.8% of tracks
  and the top-3 set on 11.1%. Genre genuinely accumulates across the whole
  track; full coverage stays.

Coverage honesty: subsampled CLAP results carry
`coverage_mode=subsampled_16_evenly` plus `window_count_available` (D-001).

## D-036 — fp16 rejected by measurement; the window cap is label-validated

**Decision (2026-08-10):** half precision stays OFF. The isolating A/B on one
pod (22 tracks, two CLAP passes with identical windows) measured: embeddings
byte-identical in effect (cosine 1.0000 median AND minimum) yet mood top-3
sets agree only 11/22 — pure rank jitter among near-tied tags, not semantic
drift — and the speedup is **3%** (4.50 s → 4.35 s/track), because CLAP is
bound by CPU-side feature extraction, not GPU math. Trading label stability
for 3% is a bad deal; the AUDIO_FP16 plumbing remains in the code, default
off, for future hardware where the math might dominate.

The same probe isolated the 16-window cap's label effect (fp32+cap vs stored
fp32 full-window): mood top-3 20/22, instrument top-3 22/22, voice top-1
22/22, embedding cosine median 0.9999 (min 0.9984) — confirming D-035 at the
label level, so the cap stays in production.

Probe safety lesson: all four earlier probe failures were the orchestrator's
own orphan sweep deleting the probe pod (named music-db-* but tracked outside
cloud_full_shards). Probe pods are now named probe-*-musicdb, outside the
sweep's prefix guard. Total probe spend across the whole saga: ~$0.20.

## D-037 — Every stage runs concurrently; CPU and GPU overlap inside rhythm too

**Decision (owner: maximise both CPU and GPU on every pod, 2026-08-10):**
the remote pipeline launches all four stages at once — Essentia (CPU-TF),
rhythm, MAEST and CLAP — instead of essentia || (rhythm → maest || clap).
Each stage is its own process with its own model; appends are
flock-serialized and (track, stage) keys are disjoint, so concurrency is
write-safe by construction. Thread caps (essentia TF 2 threads, OMP=1 for
the GPU stages) stop four processes from oversubscribing the ~6 vCPUs, and
completion markers now require every stage's exit code to be zero. Inside
the rhythm stage, HPSS futures cook on the CPU pool while the GPU tracker
consumes windows as each one lands (max_workers 4, order preserved) —
verified locally to produce identical output.

**Why:** measured stage shares were rhythm 56%, essentia 18%, clap 13%,
maest 13%, running mostly serially — so the GPU idled during rhythm's CPU
half and the CPU idled during GPU forwards. With all stages concurrent the
shard wall-time trends toward max(stage totals) instead of their sum.
VRAM fits comfortably (three small models on 16-24 GB cards). Expected
effect is a further ~30-40% wall-clock cut per shard; the honest number
will come from the cost ledger once new-code shards complete, since bundles
bake the analysis code at build time and old/new shards currently mix.

## D-038 — The manifest is derived from disk, not from one pass's progress

**Decision:** `prepare_cloud_audio_pilot.py` now rebuilds `manifest.csv` from
every clip present in the clips directory (`seed_from_disk`) on every write,
using the current pass's rows only as the metadata source.

**Why:** the manifest is the shard builder's sole view of schedulable work,
but each pass rewrote it from that pass's own record list. A pass killed
early (daemon restart, the 2 h job timeout) therefore published a fragment —
and because every later pass re-selected the same tracks in the same order,
it republished the same fragment. Found stuck at exactly 200 rows while
10,348 finished clips sat on disk: the orchestrator reported
`waiting_for_full_tracks`, ran zero pods and idled with $5.79 of credit and
15,018 tracks outstanding. The earlier merge fix (D-034 era) prevented a
partial pass from *deleting* prior rows but could not add rows the fragment
never contained; deriving from disk removes the whole failure class, since
the file becomes a function of reality rather than of a process lifetime.

**Verified:** seed_from_disk found all 10,348 clips, the rebuilt manifest let
the builder produce shard-0146 immediately.

## D-039 — Thread pools are sized from the cgroup quota, never from a guess

**Decision:** both the pod-side stage launcher (`runpod_full_shard.py`) and the
analyser (`cloud_audio_full.py`) read `/sys/fs/cgroup/cpu.max` and derive their
thread counts from it: essentia gets quota/4, the feature stages quota/8, and
the HPSS pool `max(2, min(8, quota/2))`.

**Why:** the previous caps (`OMP_NUM_THREADS=1`, `TF_NUM_INTRAOP_THREADS=2`,
HPSS pool of 4) were written against an assumed ~6 vCPU container. Measured on
a live pod, `cat /sys/fs/cgroup/cpu.max` returned `1785000 100000` — 17.85 CPUs.
Under a quarter of the paid CPU allocation was in use while the GPU stages
waited on CPU-side HPSS and feature extraction. `nproc` is worse than useless
here: it reports the 128-core host, so sizing from it would oversubscribe the
quota by 7x and thrash.

**Verified:** the quota reader falls back through cgroup v1 to `os.cpu_count()`
and returned 10 on the local machine; `bash -n` passes on the generated remote
script.

## D-040 — A pair that cannot be analysed is quarantined, not retried forever

**Decision:** `analysable()` subtracts every (track, stage) pair that has failed
`MAX_PAIR_ATTEMPTS` (3) times from the shard's required set, records it with its
last error in `quarantine.json`, and lets the shard complete and import.

**Why:** completeness was defined as "every required pair succeeded", so one
deterministically-failing track blocked its whole shard. shard-0130 held 199
finished tracks hostage to a single clip whose EffNet embedding comes back
empty, and the orchestrator re-bought a GPU pod for that one pair on every
cycle — 21 identical failures, 21 paid launches. Retrying a deterministic
failure is the purest form of the thing this pipeline must never do: a pod
that bills without being able to produce work.

**Correction 2026-08-11 (same day):** as first written this rule counted EVERY
failure, including ones caused by the pod rather than the track. The wedged-GPU
host in D-041 wrote 375 CUDA failures into shard-0153; three such runs would
have retired 375 analysable tracks and let the shard report itself complete
without them — silent data loss wearing a clean finish. `poisoned()` now ignores
errors naming an environmental cause (CUDA, cuDNN, OOM, missing module, model
download, connection/timeout). Verified against the real files: those 375
failures quarantine nothing and all 800 pairs stay required, while shard-0130's
deterministic EffNet failure is still classified as a track fault.

**Verified:** shard-0130 imported 799 stage-results for 200 tracks immediately
after the change; a scan of every shard's results found this is the only
poisoned pair in the corpus (all other failures were transient CUDA errors that
later succeeded on retry).

## D-041 — A pod must prove its GPU works, and progress is counted in successes

**Decision:** three changes to `runpod_full_shard.py`: `gpu_healthy()` runs a
tiny CUDA matmul over SSH *before* the 1.3 GB bundle upload; a `BARREN_MIN`
watchdog aborts after 8 minutes of result rows with zero successes; and the
pod-side CPU probe falls back through cgroup v1 and never to `os.cpu_count()`.

**Why:** pod `music-db-shard-0153` was handed a host with a wedged CUDA driver.
`nvidia-smi` answered (0 %, 1 MiB) but every context raised "CUDA unknown
error", so all 375 attempted tracks failed. The stall watchdog watched
`results.jsonl` grow — and it *was* growing, because a failure row is the same
size as a success row. The pod billed a full run for nothing. The same host had
no `/sys/fs/cgroup/cpu.max` at all, which exposed the second bug: the D-039
probe's fallback was `os.cpu_count()`, i.e. the 128-core host, which would have
set 32 Essentia threads inside an 18-CPU slice.

**Verified:** the wedged pod was terminated on discovery; a stripped, imported
shard now exits with "already imported" and creates no pod; `bash -n` passes on
the generated remote script.

**Related:** the per-window timelines that `results.jsonl` holds are already
stored in `audio_analysis_artifacts.payload_blob` (json+zlib), so
`prune_analyzed_clips.py` deleting the file after import loses nothing — the
`imported.ok` short-circuit is what makes its absence safe.

## D-042 — The rhythm tail gets the CPU it was leaving idle

**Decision:** `rhythm_full` runs at `OMP_NUM_THREADS = quota/4` instead of
`quota/8`; the pod-side launcher prints `rhythm_threads=` so the setting is
visible in every run log.

**Why:** measured on live pod shard-0151 (quota 17.85 CPUs): `/proc/loadavg`
read 8.44 and the GPU averaged 6 % over 20 samples spanning a minute, with
`rhythm_full` the only surviving stage. The arithmetic matches exactly — the
adaptive probe picks 4 windows, the HPSS pool runs them concurrently, and each
was capped at 2 OMP threads: 4x2 = 8. Rhythm is the tail of every shard (~46 %
of its wall clock), so half the paid CPU sat idle for nearly half of each run.

**Not done, deliberately:** running several TRACKS concurrently inside the
rhythm stage would fill the box completely, but torch, librosa and beat_this
are not installed locally, so identical-output could not be proven without
spending GPU credit on a validation run. Thread count cannot change per-window
results; track-level concurrency could, and unvalidated numeric changes are how
the fp16 experiment (D-036) went wrong. Revisit when credit allows a paid A/B.

**Verified:** `bash -n` passes on the generated remote script; a monitor is
armed to report `rhythm_threads=` and the resulting load from the first pod
that runs it.

## D-043 — A lane that reports zeros must be provably finished, not merely quiet

**Decision:** the OneTagger selector reclaims rows left in `processing` for over
an hour; the binary sets `busy_timeout(30s)` and opens `BEGIN IMMEDIATE`
transactions. The 603 already-orphaned bandcamp rows were reset to
`failed/attempts=0` so the existing retry path picks them up (prior rows backed
up to `data/backup_onetagger_processing_20260811T085848Z.json`).

**Why:** every enricher was logging `ok=0, failed=0` each cycle, which reads as
"nothing left to do". For most lanes that was true — all 71,306 tracks have a
terminal status row. For bandcamp it was not: 603 tracks had been marked
`processing` on 2026-07-18 by a batch that died, and the selector only ever
looked at rows that were missing or `failed AND attempts<3`. Silence is not
evidence of completion, and a status value that no query can ever select is a
leak with no error message attached.

The lock race is the same class of problem: the default deferred transaction
takes a read lock and upgrades on first write, which returns `BUSY_SNAPSHOT`
*immediately* — `busy_timeout` never retries it. With the daemon, orchestrator,
importer and audio verifier all writing, nearly every batch died after one
track and left that track in `processing`, feeding the orphan pool.

**Verified:** the reclaimed rows are now selected (the lane moved rows for the
first time since 2026-08-02); `cargo build --release` clean. Note the deep audio
verifier holds the write lock for long stretches, so batches still lose the race
sometimes — that is now harmless, because an orphan self-heals within the hour.

**Also:** `data/music.db-wal` had grown to 4.48 GiB because a long-lived reader
held checkpoints back. `wal_checkpoint(TRUNCATE)` took it to zero and returned
free disk from 51 to 54 GiB.

## D-044 — CPU allocation, not GPU, decides what a pod costs per track

**Decision:** `create_pod()` accepts a `vcpu_floor` and immediately returns any
host below it; the runner hunts for >= `MIN_VCPU` (16) for two attempts, then
accepts whatever is free so a thin market cannot stall a shard.

**Why:** three live pods measured on the same day, all RTX 3090, all $0.22/h:

| shard | advertised vcpuCount | enforced cgroup quota | RAM |
|---|---|---|---|
| shard-0159 | 8 | (cgroup v1, no quota file) | 30 GB |
| shard-0153 | 21 | 17.9 | 41 GB |
| shard-0155 | 32 | 27.2 | 62 GB |

The same hourly price buys a 4x spread in CPU. Since rhythm (HPSS) and essentia
(TensorFlow) are CPU-bound, and wall clock is what is billed, the thin host is
straightforwardly worse value at identical cost. `vcpuCount` is readable from
`pod get` seconds after creation — before the 1.3 GB upload — so a rejection
costs a few cents of billing at most.

**Corrects an earlier claim:** D-039 was written as though pods have ~17.85 CPUs
and the code had been using a quarter of them. The true statement is that the
allocation *varies* between hosts, which is exactly why deriving thread counts
from the cgroup quota is right and any hardcoded number is wrong. On the 6-CPU
pod the new code computes 2/2/1 threads and `/proc/loadavg` read 5.65 — that
host was already saturated and gained nothing; the 17.9 and 27.2 hosts are where
the win is.

**Verified in production 2026-08-11 09:36Z:** the first two pods created under
the floor were accepted at **25 and 32 vCPU**, both at the same $0.22/h — against
the 8 vCPU that shard-0159 drew from the same market an hour earlier without it.
Neither creation logged a rejection, so the feared create/terminate churn cost
nothing on a normal market. Leak safety confirmed by reading `sweep_orphans()`:
it matches on `pod_id`, and a rejected pod's id is never written to a shard state
file, so a failed terminate lands in the `tracked is None` branch and the pod is
deleted on the next sweep rather than billing unnoticed.

**Verified:** measured directly over SSH on all three live pods; module compiles.

## D-045 — Two thirds of a shard was overhead, and half of it was serialised for no reason

**Decision:** `prewarm()` uploads the 483-byte requirements file immediately
after the GPU proof and starts apt+venv+pip detached on the pod, so the
dependency install runs *while* the 1.3 GB bundle uploads.

**Why:** the cost model was wrong, and measuring it corrected several claims
made earlier the same day. Across 11 shards:

| | minutes |
|---|---|
| fixed overhead per shard | 20.2 |
| actual analysis per shard | 9.6 |
| total | 29.8 |

**68% of every paid shard was overhead.** D-039, D-042 and D-044 were all
optimising the 9.6-minute third — which is why D-044's 3-4x CPU gain produced
only an 8% end-to-end improvement (shard-0161 at 0.418 h against a 0.453 h
average for the previous nine). Two overhead blocks are independent: receiving
the bundle, and installing torch/librosa/essentia. They ran back to back purely
because the installer lived inside `run.sh`, which cannot start until the upload
lands.

**Fail-safe by construction:** if `prewarm()` cannot start, or the install dies
halfway, `run.sh` performs the identical setup itself. It waits up to 15 minutes
for an in-flight prewarm rather than racing it into the same venv, and bundle
extraction is now keyed on `$SHARD/clips` existing rather than on `.setup_done`,
because a successful prewarm sets that flag having never seen the bundle. The
worst outcome is no speedup, never a broken shard.

**Verified:** `bash -n` passes on the generated `run.sh` and on the prewarm body
exactly as it lands on the pod. NOT yet verified in production — no pod has been
created since the commit. The number to check on the next shard is the gap
between `created_at` and the first result row, which should fall by roughly the
shorter of the upload and install times.

**Verified in production 2026-08-11 10:25Z** by observing two pods side by side,
one created either side of the commit:

| | shard-0163 (no prewarm) | shard-0165 (prewarm) |
|---|---|---|
| bundle on pod | 1.06 GB, nearly complete | 11.7 MB, still uploading |
| venv | absent | `musicdb-venv/bin/python` already built |
| install state | not started | `.setup_running` present, pip running |

shard-0165 had its virtualenv built while its bundle was 1% transferred, which
is precisely the overlap this change exists to create; shard-0163, whose bundle
had almost fully landed, had not begun installing anything.

**SAVING QUANTIFIED 2026-08-11 11:00Z — ~4.8 min per shard.** Measured on a
single pod, which is the only way this comparison is valid: on shard-0166 the
dependency install took **4.8 min** and completed **0.3 min before** the bundle
finished arriving, so it was entirely hidden inside the upload window.
shard-0167 shows the same pattern (install done 0.1 min before the bundle).
Since the install is fully overlapped, the saving equals its duration: ~4.8 min
off a ~25-30 min shard, i.e. **16-19% of wall clock**, taking the measured
$0.00066/track to roughly $0.00053.

Note this is smaller than the change was predicted to give, because the premise
was wrong in the pipeline's favour: the install was assumed to take 8-10 min but
takes 4.8 on a well-provisioned pod — pip is CPU-bound, so D-044's fat pods had
already shortened it. The saving is real but bounded by how long the install
takes, never by how long the upload takes.

**What was and was not proven before this measurement.** The MECHANISM is proven: on shard-0165 the
dependency install wrote `.setup_done` a full 6 minutes BEFORE `full-shard.tar`
finished arriving, so the entire install was hidden inside the upload window —
time that was previously spent after the upload, in series.

The SAVING is not yet quantified, and the obvious comparison misleads. The
end-to-end setup gap was 11.9 min for shard-0165 (with prewarm) against 11.4 min
for shard-0164 (without) — apparently no gain. That comparison is confounded:
the two pods uploaded under different contention (UPLOAD_SLOTS=2 shares one home
uplink), the gap is sampled on a 60 s poll, and n=1 on each side. Do not read it
either way. To measure the saving properly, compare `.setup_done` minus prewarm
start against the same shard's upload duration across several shards, or run a
deliberate A/B with the prewarm disabled while upload contention is held equal.

Leaving it enabled costs nothing regardless: the path is fail-safe, and hiding
the install inside the upload cannot be slower than running it afterwards.

**Baseline correction, measured after the fact:** shard-0164 (28 vCPU, created
BEFORE this commit, so no prewarm) reached its first result 11.4 min after pod
creation — against the 20.2 min mean overhead computed from the earlier
mixed-CPU fleet. The overhead is therefore NOT fixed: `python -m venv` and
`pip install` of torch/librosa/essentia are CPU-bound, so the D-044 pods already
halve it. Two consequences: D-044's real benefit is larger than the 8%
end-to-end figure suggested (that sample only captured the analysis third), and
D-045 must be judged against the ~11 min high-vCPU baseline, not against 20.2 —
comparing to the old number would credit the prewarm with D-044's gain.

**Remaining lever, unmeasured:** of the 20.2 min overhead, the split between
truly fixed cost (container start, model download) and cost that scales with
shard size (the bundle upload) is not yet known. If the fixed part dominates,
larger shards would amortise it further; 400 tracks instead of 200 is a one-line
change in the builder, at the price of a 2.6 GB bundle and more disk.

## D-046 — The FreqBlog review backlog has no safe automatic accepts

**Decision:** `resolve_freqblog_review.py` rejects only the 210 candidates whose
title AND artist are both below 0.5 similarity, and accepts nothing. 3,478 stay
in review. An earlier plan to auto-accept ~1,089 "exact" matches was abandoned
after measuring what it would actually have written.

**Why the acceptance rule is vacuous, and correctly so:** acceptance required
`fb.norm(title)` and `fb.norm(artist)` to be identical to the provider's. But a
candidate that satisfies that already scores 1.0 in `identity_confidence()` and
is auto-accepted, so it never reaches review. The same holds for a matching
ISRC, which short-circuits to `isrc_exact`. By construction the review bucket
contains only genuine ambiguity.

**Why the looser rule was dangerous.** The 1,089 figure came from normalising
with parenthetical suffixes stripped. Of the 1,084 that rule matches, **1,083
have titles that differ inside the brackets** — and for DJ material the bracket
is often the whole point:

| ours | FreqBlog would have supplied |
|---|---|
| Truth Hurts (DaBaby Remix) | Truth Hurts |
| Vivo | Vivo (Slow Motion Mix) |
| Extreme Ways | Extreme Ways (Bourne's Legacy) |

Accepting those writes the original's BPM and energy onto a remix, and a slow-
motion mix's onto an original, across a thousand tracks. That is exactly the
harm the review queue exists to prevent, and the proposal contradicted the very
principle it was argued under ("a wrong BPM is worse than a missing one").

**Verified:** dry run first, then applied; every candidate row backed up to
`data/backup_freqblog_review_20260811T104719Z.json` before any write. Result:
accepted=0 rejected=210 failed=0 kept=3,478. Final status spread — success
64,125, not_found 3,684, needs_review 3,478, failed 11, queued 10.

**What would make the rest resolvable:** an ISRC or duration cross-check, or
listening. Not string similarity — that ceiling has been reached.

## D-047 — A pod is never created until the uplink is free to feed it

**Decision:** `acquire_upload_slot()` is taken BEFORE `create_pod()` and released
the moment the bundle has landed; analysis does not need the uplink.

**Why:** the runner created its pod and then queued for one of `UPLOAD_SLOTS=2`.
At the 1-5 pods a low balance allowed this was invisible. The moment the balance
was topped up to $11.57 the orchestrator scaled to its 16-pod cap and the defect
became live: nine pods existed, two held slots, and **six were billing $0.22/h
each purely to wait their turn to receive a bundle** — $1.32/h for nothing. Those
six were terminated by hand and their shards requeued.

Waiting before creation costs nothing, because no pod exists yet. The slot is
released on every exit path, including a failed pod creation.

**Verified:** four processes against an isolated lock directory — exactly two
acquire immediately (0.2 s) and two wait for a release (10.2 s).

## D-048 — The pod cannot stop itself, and parallelism is bounded by the uplink

**Three findings from auditing "a pod must never bill while idle".**

**The self-stop guard had never fired.** `run.sh` gated it on
`[[ -n "${RUNPOD_POD_ID:-}" ]]`, but RunPod injects that variable into PID 1 and
`/etc/rp_environment`, never into an ssh session — so the test was always false.
`run.sh` now sources that file (with a `/proc/1/environ` fallback) and logs the
id it resolved.

**Even with the id, a pod cannot stop itself.** The `RUNPOD_API_KEY` RunPod
injects is rejected by RunPod's own API — "Error: Unauthorized", verified on a
live pod both from the environment and after explicitly configuring the key.
This is now documented at the call site so no future reader counts it as a layer
of protection. What actually holds, in order: the runner terminates its pod on
completion; the orchestrator's orphan sweep deletes any pod no live runner
explains; and `--stop-after`/`--terminate-after` are enforced by RunPod itself,
surviving the local machine dying entirely.

**MAX_PARALLEL 16 → 8, bounded by the uplink.** A 1.3 GB bundle through one of
two slots takes ~9 min, so the home line can start ~13 shards/h, and a shard
holds its pod ~0.45 h — about 6 pods can be kept genuinely busy. 16 was correct
when a shard ran ~2 h and the upload was a rounding error; D-037 cut the shard to
0.45 h and inverted the ratio. Runners above the limit are harmless since D-047,
but they add nothing and their polling contends for `runpodctl`.

**Related, same audit:** `estimate_caps()` still summed PER_STAGE_SECONDS as if
the four stages ran in series, producing a 5.1 h server-side cap for a shard that
takes 0.4-0.9 h. Since that cap is the last line of defence when the local runner
is dead, it now uses measured wall clock per TRACK (17 s, the worst of the last
twelve shards against a ~8 s median) — 1.92 h for 200 tracks. Worst-case idle
billing across a full fleet drops from ~$18 to ~$7.

## D-049 — A big local upload can starve the pipeline's control plane

**Incident 2026-08-11:** pushing this repository to GitHub for the first time
(266 MB packed) saturated the same home uplink the pipeline uses. DNS lookups
for `api.runpod.io` began failing ("no such host"), every `runpodctl` call
errored, shard runners died, and two pods (0187, 0190) were left billing with no
runner. The orchestrator correctly detected `unexplained_spend` and set target=0,
and its orphan sweep would have deleted both after the 10-minute grace; the pods
were terminated by hand to stop the bleed sooner.

**What this proves about the guarantees.** Every local protection — the runner's
terminate, the orphan sweep, the watchdogs — needs the network to act. When the
uplink is saturated or down, none of them can run. The ONLY guarantee that
survives is the server-side `--stop-after`/`--terminate-after`, enforced by
RunPod itself. That is exactly why D-048 cut it from 5.1 h to 1.92 h: it is not a
formality, it is the last line that holds when the machine cannot reach the API.

**Rule:** do not push large artifacts, run bulk transfers, or otherwise saturate
the uplink while paid pods are running. The pipeline's control plane shares that
link with its own 1.3 GB bundle uploads, and starving it converts a cheap local
operation into paid idle time on every live pod.

## D-050 — A pod must prove it is working, on a 75-minute leash

**Decision:** `pod_reaper.py` runs every 2 minutes under the daemon and
terminates any `music-db-*` pod that cannot show it is working. Four verdicts:

| verdict | condition | action |
|---|---|---|
| UNMANAGED | no runner process owns the shard | kill after 3 min |
| EXPIRED | older than `MAX_POD_MINUTES` (75) | kill |
| STALLED | past setup grace, no results in 12 min | kill |
| WORKING | the shard's results file grew recently | leave alone |

**Why a separate process.** The runner babysits its own pod and the orchestrator
sweeps orphans, but on 2026-08-11 both died together when a large upload
saturated the uplink, and two pods billed unwatched (D-049). A guard that shares
a process — or a failure mode — with the thing it guards is not a guard.

**Why it judges local files, not SSH.** Results are pulled to
`data/cloud_full_shards/<shard>/results.jsonl` as they are produced, so growth in
that file is direct proof of paid work being done. The check costs nothing,
cannot hang, and stays honest when SSH is unreachable — exactly when pods get
abandoned. An SSH-based check would go blind in the one situation it exists for.

**The leash is layered so the story is consistent:** the reaper kills an idle pod
at 75 min; if the reaper itself is dead, RunPod's own `--stop-after` kills it at
90 min (down from 5.1 h before this work). A healthy shard measures 25-55 min, so
both limits clear real work comfortably.

**Verified:** nine synthetic cases cover every branch. The critical one is the
safety case — when `pgrep` cannot report which runners exist, the reaper does NOT
kill on the UNMANAGED rule and falls through to the progress check, so a failing
local tool can never wipe out healthy paid work. A dry run against the live
account was clean, and the daemon was restarted so the guard is active.

## D-053 — 96 kbps clips REJECTED: one track's tempo moved

**Decision:** clips stay at 192 kbps. The upload wall (~55 h for the remaining
collection at the measured 685 KB/s) stands; there is no shortcut.

**The experiment:** 25 tracks whose 192 kbps answers are already in the database
were re-analysed from 96 kbps clips on one pod, all four stages.

| measure | result |
|---|---|
| BPM identical (<0.5) | **24/25 — one track drifted 5.00 BPM** |
| genre top-1 identical | 25/25 |
| mood/instrument labels retained | 50/50 (100%) |

**Why this is a rejection and not a pass.** The acceptance bar was written before
the data existed: adopt only if BPM is identical on EVERY track. 5 BPM is not a
rounding difference, it is a mis-mixed transition, and at 4% it would put roughly
a thousand tracks in this library on the wrong tempo. Genre and mood survived
intact, which is exactly what would make it easy to argue the other way — the
pre-registered threshold is what stops that.

**Cost of the answer:** ~$0.60. The probe pod also idled ~2.5 h after finishing
because it never wrote its done-marker and nothing was watching it —
`pod_reaper.py` only guards `music-db-*` pods, so a differently-named pod bills
unwatched. Worth fixing before the next probe.

## D-063 — the Comment column was being eaten one track at a time (2026-08-15)

The owner labels every track's energy in Traktor's **Comment** column ("06
Energy"). Loading a track made that label turn into a musical key, "Em".

**It was not our write.** Every backup says so: the collection held 1,179
key-comments on 14 Aug, BEFORE our first write, and exactly ZERO Comment values
changed between the pre-write backup and now. Traktor's own rolling backups date
the rot precisely: 603 in June, 700 a week later, 1,138, 1,179 by 10 July, 1,180
now. This has been running for months, one track per play.

**Cause.** 120 of 120 checked files carry a musical key inside their OWN comment
tag (`©cmt`), written by some earlier tagger; the key is a duplicate, since the
real key already lives in Traktor's KEY field. Traktor re-reads a file's tags
when the track is loaded, so the file's key overwrites the collection's energy.
On a 1,500-file sample, **56.5% of files still disagreed with the collection** —
about 50,000 tracks primed to flip on their next play. Our file-tag sweep did not
write this, but it changed 92k file mtimes, which is exactly what makes Traktor
re-read them, so it would have accelerated the loss sharply.

**Fix — `traktor_comment_pin.py`, two phases.**
`--repair` recovered the originals for **577** already-flipped entries from
Traktor's own backups (keys 1,180 → 603; energy labels +577). The remaining 603
flipped before the oldest surviving backup and are not recoverable from anything
on this machine.
`--pin` writes the collection's Comment INTO each file's comment tag, so the file
and the collection finally agree and a re-import is a no-op. 61,886 files.

**Two judgement calls, stated rather than buried.** Overwriting the file's key is
correct because the key is redundant while the energy label exists nowhere else.
And 25,281 files are referenced by more than one collection entry, 1,274 of them
disagreeing about the energy; a file holds one comment, so the majority value
wins with a deterministic tiebreak — never file order.

Reversible: every comment tag is copied to `comment_pin_backup` before it is
touched, and `--restore` puts each one back, including deleting the tag again
where there was none.

## D-064 — the money guard now outlives the session (2026-08-19)

`pod_reaper.py` is the only thing that terminates RunPod pods billing without
doing work. It died twice this month simply because the shell that started it
went away, and nothing noticed — the exact failure D-049 was written about, one
level up: the watchdog had no watchdog.

Fixed with a launchd agent (`~/Library/LaunchAgents/com.jakub.podreaper.plist`,
`KeepAlive`), so macOS restarts it within seconds of any death, including a
reboot, with no terminal and no AI session involved. **Proven, not assumed:**
the running reaper was killed with `kill -9` (pid 90375) and launchd had a new
one up 30 s later (pid 90819) — a guard nobody has seen fire is not a guard.

## D-065 — five days of pods that analysed nothing (2026-08-20)

The last full-audio row landed **2026-08-14 08:37**. Every pod created since was
billed, ran, and terminated with `rows=0`. The logs held the answer in one line,
repeated: `scp: lost connection`. **555 upload attempts, zero successes.**

**Cause.** A shard bundle is ~1.35 GB and this uplink measures ~685 KB/s, so one
`scp` must hold a single session open for ~34 minutes — while the upload itself
saturates the very link its SSH keepalives ride on (`ServerAliveInterval=15`,
`CountMax=4` → dropped after 60 s of delayed replies). The transfer strangles
itself, and because `scp` has no resume, all three retries restarted from byte
zero and died at the same place. This is D-049's lesson one level down: we
saturated our own control channel.

**Fix — `push_bundle()` in `runpod_full_shard.py`.** The bundle now goes in 64 MB
chunks written straight into place with `dd seek=`, which makes each chunk
idempotent. After any failure the pod is asked how many bytes it already holds
and the transfer continues from exactly there — a drop costs ~90 s, not 34
minutes. The whole bundle is then `sha256sum`-checked ON THE POD before any GPU
time is spent on it.

**Verified, not assumed:** the first bundle went up as `470 → 1351 MB` with no
retries and logged `bundle verified on the pod` — after 555 consecutive failures.

**Also fixed:** while diagnosing, `pkill` on the orchestrator kept "failing" —
it is supervised by launchd (`com.jakub.music-db-cloud-production`), which
restarts it. Good design, but it means stopping the pipeline needs
`launchctl unload`, not `pkill`. Noted here because it cost time twice.

## D-066 — "waiting_for_full_tracks" while 12,256 prepared tracks sat idle (2026-08-20)

With the upload fixed, the orchestrator still built nothing and reported
`waiting_for_full_tracks`. Two independent blockers, both silent:

**1. A counting bug.** The build gate read `pool = ready - done`, where `ready`
counts rows in the CURRENT manifest (14,656) and `done` counts every track ever
analysed (33,868). Once the lifetime total passed the manifest size the
subtraction went permanently negative and clamped to zero, so the orchestrator
concluded there was no work while 12,256 tracks with clips already on disk
waited. Replaced with `pending_pool()`, which compares the manifest against the
finished set directly — the two numbers now mean the same thing.

**2. The disk, not money.** A shard is only built above `MIN_FREE_GIB_TO_BUILD`
(45 GiB) and only 12.9 GiB were free: five broken days had piled up 96 GB of
staged clips plus 20 GB of shard directories, each holding a tar AND a second
copy of the same clips. `gc_analysis_workspace.py` reclaimed **56.7 GB** — a clip
only when its track has all four stages, a shard directory only when EVERY track
in its manifest does. Verified after the sweep: all 12,256 pending tracks still
had their clip, zero missing.

**Revised cost, measured not estimated:** the 2,400 tracks analysed since the
upload fix cost **$1.12 — $0.00047/track**. The old $0.0014 figure was inflated
by the wasted spend it averaged in. Finishing all 37,810 remaining tracks is
therefore ~$18, not ~$53.

## D-067 — the reaper was killing healthy pods minutes before they delivered (2026-08-20)

With uploads fixed, shards still died. The reaper judged "is this pod working?"
by growth of `results.jsonl` — but that file does not appear until the run is
well under way, so a healthy shard looked dead for its entire ~34 min upload.
With `SETUP_GRACE_MIN=45` + `NO_PROGRESS_MIN=12` the verdict landed at 57 min,
and a healthy shard now needs ~60 (34 upload + ~25 analysis). The guard was
destroying exactly the work it existed to protect.

**Fix.** The runner already records each step it completes in
`runpod_state.json` (`ssh_ready` -> `uploaded` -> `analysis_started`). The reaper
now treats a recent state update in one of those statuses as proof of work, and
falls back to the results file otherwise. A pod whose runner has gone quiet is
still reaped; one that is mid-upload is not. `MAX_POD_MINUTES` also went 75 ->
100 to match measured reality (worst case a wedged pod bills ~$0.37).

**Proven in production:** shard-0339 sat at age 50 min reporting
`analysis_started`, with a 246 MB results file growing — the old rule would have
terminated it at 57 min, minutes before delivery.

**Two more defects found the same hour.**
`connect_readonly()` opened `mode=ro`, which cannot create the WAL index when no
writer exists — the normal state between shard runs — so the orchestrator kept
dropping into `retrying` with nothing wrong. It now falls back to a plain handle
(monitoring callers only SELECT, so no write lock is taken).
`balance()` mapped a missing `clientBalance` field to `$0.00` via `or 0`, which
reads as "out of credit" and parks the pipeline. Observed live: the status tool
reported $0.00 and 0 pods while the account held $9.37 and two pods were
analysing. A read failure now raises so the caller retries.

**Operational note, learned the expensive way:** restarting the orchestrator
kills its child runners and orphans their pods. Four pods were lost that way
today, two of them 26 minutes into analysis, each having already spent ~34 min
of uplink. Their results were recovered by hand with
`import_full_audio_results.py` (+38 fully analysed tracks). Change code, then
WAIT for running shards before restarting.

## D-068 — similarity search: "find me the same track, 50 times" (2026-08-21)

First use of the audio EMBEDDINGS the GPU pass has been producing all along.
`similar_tracks.py` ranks the library against one reference track using all three
models — CLAP (512d, mood/texture), MAEST (400d, genre/style) and Essentia
effnet (1280d, general music) — over the ~42,900 tracks that have them.

**Why all three and not the tags.** Tags are a lossy summary; the embeddings are
what the models actually heard. And each model is confidently wrong in its own
way, so a track ranking high on all three is similar in every sense we can
measure. Tag overlap (Jaccard) and BPM/key/rhythm distance are added as smaller
terms, so the audio decides and the metadata breaks ties.

**The one real subtlety: z-scores, not raw cosines.** Each model's similarities
are standardised across the whole library before averaging. Raw cosines are not
comparable between models — one may spread every track over 0.85-0.99 and
another over 0.1-0.6, and a plain average would silently let the narrow model
dominate the ranking.

**Two bugs caught before they reached Spotify.**
The `MODELS` dict held model ids abbreviated from a truncated console dump, so
every SQL match found nothing and all three models were "skipped" — the run
produced zero results rather than wrong ones, which is the good failure.
Worse: `--spotify-only` tested `len(sid) != 22`, but a local-only id looks like
`local_c1e89649e0ddf452` — **exactly 22 characters**. Nine local files reached the
first playlist build; Spotify would have rejected them. The test now also checks
the `local_` prefix.

**Result for iLee — Lila (125 BPM, E-minor, four-on-the-floor):** 50 tracks,
tag overlap 0.44-0.70, nearly all afro/organic house at 120-125 BPM and mostly
E-minor. iLee's own "Malaya" surfaced at #49 without any artist hint — a useful
sanity check. Versions of one song are collapsed to the best-scoring one, since
"Samsara" alone had taken three of the fifty slots.
