# Tasks and definition of done

Statuses reflect the last verified handoff. Background counters continue to
change.

## Completed

- [x] Spotify MCP/OAuth and reusable Spotify client access established in the
  surrounding workspace.
- [x] Original owned-playlist + Liked Songs export completed and deduplicated.
- [x] Original Indie Sort classification completed for 63,213 exported tracks.
- [x] `Indie Sort` Spotify playlist created with 1,805 tracks.
- [x] Liked Songs-only Indie playlist extended to 500 tracks.
- [x] SQLite music intelligence database created for 68,075 tracks.
- [x] Spotify Account Data and available streaming history imported.
- [x] Multi-provider provenance schema and preferred-field views implemented.
- [x] Free catalog enrichers implemented and supervised by LaunchAgent.
- [x] ReccoBeats completed across all Spotify IDs (success/no-match accounted).
- [x] FreqBlog Free underground test and Starter validation completed.
- [x] FreqBlog Starter enabled after the user manually paid EUR 39.
- [x] SoundNet evaluated and intentionally disabled.
- [x] OneTagger database-only Python bridge implemented.
- [x] Standalone Rust `onetagger-db` compiled; Bandcamp worker integrated.
- [x] Traktor collection and `Missing Tracks.m3u` parsed into SQLite.
- [x] Acquisition/inventory/verification tables and queue implemented.
- [x] Four Spotify-only blindspot playlists created, 26,142 total tracks.
- [x] Menu-bar app built and installed with status/pause/resume controls.
- [x] Beat presence/type analyzer implemented with Beat This + DSP.
- [x] MAEST Discogs400, CLAP and controlled mood/genre taxonomies integrated.
- [x] Essentia shared EffNet + 19 supervised heads integrated.
- [x] Full temporal schema/artifact storage and conservative consensus importer
  implemented.
- [x] Three-track full-coverage smoke completed: 12/12 stages, successful import,
  paid pod deleted.
- [x] MAEST remote model code pinned to immutable commit.
- [x] Quality-first full-track decision implemented.
- [x] Bounded RunPod production sharding/orchestration implemented.
- [x] LaunchAgents installed for full preparation, Essentia, rhythm and cloud.
- [x] Comprehensive project handoff/documentation created.

## In progress — leave running

- [x] Prepare full-track Opus analysis assets for the current 5,394-track
  initial local batch. (5,393 prepared; 1 source file permanently corrupt)
- [x] Analyze all 5,394 with cloud Essentia supervised heads. (5,393 done
  2026-07-21 — the whole 4-stage batch: 19 shards, 25.9 GPU-h, $5.88)
- [x] Analyze all 5,394 with cloud Beat This + DSP full-track rhythm timelines.
  (5,393 done 2026-07-21)
- [x] Analyze all 5,394 with cloud MAEST + CLAP under existing RunPod credit.
  (5,393 done 2026-07-21)
- [ ] Continue FreqBlog enrichment within existing 150k monthly quota.
  (43,429 success; quota ~exhausted at 145k/150k — auto-resumes on monthly reset)
- [ ] Continue Last.fm, MusicBrainz, Deezer, TheAudioDB, OneTagger and Spotify
  metadata workers.
- [ ] Continue local file indexing and deep verification.

## Next priority after the first audio batch

- [ ] Verify no RunPod pod remains and reconcile actual spend.
- [ ] Run a stratified manual audit of at least 100 tracks, preferably 500 for
  final calibration.
- [ ] Measure false positives for mood, instruments and niche subgenres.
- [ ] Calibrate Essentia mean/p90/coverage thresholds without re-running audio.
- [ ] Calibrate CLAP candidate promotion and semantic vocabulary using audited
  examples; keep raw scores.
- [ ] Validate beatless/four-on-floor/broken/mixed labels on hand-labelled tracks.
- [ ] Recompute provider conflicts and `source_field_policy` weights.
- [ ] Test `find_similar.py` on representative DJ seeds and record judged quality.
- [ ] Produce a final coverage/no-match report by provider and field.

## Enrichment expansion (researched 2026-07-20 — docs/ENRICHMENT_ROADMAP.md)

- [ ] Direct Discogs API enricher (free; canonical styles vocabulary; replaces
  slow OneTagger bridge for the 43k untouched tail). Recommended first.
- [ ] Deezer 30-s preview audio tier for ~55.5k unmatched tracks (beat type,
  audio genre/mood candidates at 10× coverage) — OWNER APPROVAL REQUIRED
  (rule 8 / licensing stance; ~$8–15 compute or free-but-warm laptop).
- [ ] MusicBrainz genre second pass over the 23.5k known MBIDs (free, 1 req/s).
- [ ] FreqBlog needs_review queue (2,414) supervised fuzzy-acceptance pass.

## Engineering backlog

- [x] Replace hard-coded `EXPECTED = 5394` with a dynamic append-only audio queue
  for every newly matched local track. (D-030, 2026-07-21 — `target_count()`)
- [ ] Make menu pause/resume cover the dedicated full-track/cloud LaunchAgents,
  or clearly expose separate controls for them.
- [x] Add a single canonical status command that combines old and new audio
  pipeline counters. (`pipeline_status.py`, 2026-07-20)
- [x] Add an automated orphan-pod monitor that deletes only project-owned pods
  after safely collecting results; it must never fund an account.
  (orchestrator sweep, D-026, 2026-07-20 — deletes `music-db-*` pods no shard
  state explains; incremental result pull makes pre-delete collection moot)
- [ ] Add consistent model revision pins for every downloadable model.
- [ ] Add SQLite live-backup tooling and a documented restore test.
- [ ] Add schema migration tests and JSONL corruption/truncation tests.
- [ ] Add per-track quality/conflict flags for mood/genre/rhythm disagreement.
- [ ] Add temporal similarity options so a DJ can match a section or trajectory,
  not only whole-track aggregates.
- [ ] Add ANN/vector indexing only after full embeddings exist and brute-force
  performance is measured.
- [ ] Normalize Camelot/Open Key and aliases consistently across providers.
- [ ] Improve label/release-date gaps using exact MusicBrainz/Discogs releases.
- [ ] Review the experimental `vendor/onetagger` crate, preserve user changes,
  and either finish integration or standardize on standalone `onetagger-db`.
- [ ] Cleanly package the app/repository only after safeguarding the dirty tree;
  no destructive git cleanup.

## Audio acquisition backlog

The user ultimately wants all 60k+ tracks locally, but automation must remain
lawful and entitlement-aware.

- [ ] Locate the 7,172 tracks Traktor claims exist before sourcing replacements.
- [ ] Verify all present files; deduplicate by Spotify ID/ISRC/content.
- [ ] Define explicit lawful provider adapters for purchased/licensed files.
- [ ] Add complete-file/codec/bitrate verification and atomic finalization.
- [ ] Route outputs to the future SSD and update paths transactionally.
- [ ] Keep a visible per-provider progress/retry/error queue.
- [ ] Never download the same recording twice unless versions/releases differ.

No bulk downloader is currently documented as active.

## Playlist/product backlog

- [ ] Confirm whether the `Made of Gold — Sensual 200` playlist was created; the
  ranking script exists but no durable local state/URL was found.
- [ ] Complete or recreate the requested September 2024–January 2026 reflective
  “return to depth” playlist using the second-brain repository and listening
  history; no verifiable artifact is present in this repository.
- [ ] Build future playlists from calibrated DB queries, with saved query/ranking
  provenance and resumable Spotify writes.

## Definition of done

- [ ] All 68,075 tracks have an explicit state for each required provider/field,
  including permanent no-match where appropriate.
- [ ] Every locally available track has verified full-track audio analysis.
- [ ] Newly added Spotify/local tracks automatically enter the pipeline.
- [ ] Genre/subgenre, mood and rhythm quality pass the owner's manual audit.
- [ ] Similar-track retrieval is demonstrably useful for real DJ set preparation.
- [ ] No paid cloud resources remain active after work finishes.
- [ ] A verified backup and restore procedure exists.
- [ ] Documentation and status snapshot are updated at final handoff.
