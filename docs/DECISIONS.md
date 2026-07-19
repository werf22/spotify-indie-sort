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
