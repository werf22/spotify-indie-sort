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
