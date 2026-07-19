# Status snapshot

Captured on **2026-07-19** in Europe/Bratislava while all workers were left
running. Values will change. Re-run the commands at the end instead of treating
this file as a live dashboard.

## Catalog and coverage

| Metric | Count | Coverage |
|---|---:|---:|
| Tracks | 68,075 | 100% |
| Spotify legacy artist genres | 47,927 | 70.40% |
| Any genre tag | 64,464 | 94.70% |
| Any tag | 66,418 | 97.57% |
| Mood | 53,694 | 78.87% |
| Instrument | 5,269 | 7.74% |
| Voice | 48,399 | 71.10% |
| BPM | 55,539 | 81.59% |
| Key | 56,419 | 82.88% |
| Energy | 56,653 | 83.22% |
| Danceability | 59,446 | 87.32% |
| Valence/happiness | 55,470 | 81.48% |
| Label | 29,550 | 43.41% |
| Release date | 32,001 | 47.01% |
| ISRC | 53,791 | 79.02% |
| MusicBrainz ID | 11,639 | 17.10% |

## Provider queues

- FreqBlog: 20,558 success; 252 queued; 669 processing; 7 failed;
  659 quota-wait; 1,207 review; 11,238 not-found; 33,485 untouched.
- FreqBlog tracked calls: 56,348 of the 150,000 monthly Starter allowance.
- ReccoBeats: 49,863 exact Spotify-ID successes; 18,212 not-found; no untouched.
- OneTagger/Discogs v2: 2,055 success; 8,431 no-match; 57,589 untouched.
- Deezer: 29,285 success; 968 not-found; 547 failed; 37,275 untouched.

## Local-library and acquisition inventory

- locally matched unique Spotify tracks: 5,394;
- deep-verified at the cited sync snapshot: 1,820;
- acquisition queue: 1,567 complete, 3,606 verify-local, 7,172 locate-existing,
  55,730 needs-source;
- Spotify-only blindspots exported to four playlists: 26,142;
- current safety floor: 50 GiB free;
- free disk during documentation: approximately 400.8 GiB.

The current dedicated full-audio target is **5,394** matched tracks. Preparation
is resumable and the manifest is replaced atomically while it grows.

## Database size and rows

At capture time:

| Table | Rows |
|---|---:|
| `tracks` | 68,075 |
| `audio_features` | 100,891 |
| `tags` | 1,607,265 |
| `track_attributes` | 2,479,898 |
| `audio_files` | 11,171 |
| `local_audio_analysis` | 726 |
| `audio_embeddings` | 787 |
| `audio_temporal_features` | 3,506 |
| `audio_analysis_artifacts` | 206 |
| `stream_events` | 32,241 |
| `traktor_entries` | 93,842 |
| `audio_verification` | 3,010 |
| `acquisition_queue` | 68,075 |

`data/music.db` was about 1.8 GiB plus a live WAL. Never copy only the main DB
file while writers are active; use SQLite backup or checkpoint safely first.

## Audio-production state at capture

- full-track Opus preparation and manifest growth: running;
- local Essentia follower: disabled (cloud-only heavy inference);
- local Beat This/rhythm follower: disabled (cloud-only heavy inference);
- cloud production orchestrator: running;
- first cloud shard: 250/250 MAEST + 250/250 CLAP imported, pod deleted;
- repaired shard continuation: 178 missing rhythm pairs only, RTX 3090,
  USD 0.22/hour, bounded stop/termination deadlines;
- RunPod credit after the first production shard and benchmark: approximately
  USD 9.69;
- full-track smoke: 3 tracks x 4 stages = 12/12 successes; pod deleted;
- measured mean smoke times: rhythm 20.94 s, MAEST 7.97 s,
  Essentia 7.91 s, CLAP 9.07 s per track.
- separate RTX 3090 benchmark: rhythm 25.41 s (cold-start skewed), MAEST
  7.04 s, Essentia 4.58 s, CLAP 6.50 s; pod deleted.

The first production attempt exposed two packaging defects before any valid
results were accepted: remote manifest clip paths pointed to the preparation
directory and `musicdb.py` was omitted from the inference bundle. Both failed
pods were deleted. `build_cloud_full_shard.py` now writes remote-safe paths,
includes the dependency and supports `--repair`. A preflight then passed
both MAEST and CLAP on a complete 399-second track (40 windows each) before
cloud production was restarted. Historical error rows are not counted as
success and were replaced by downloaded remote results.

The cloud production path runs rhythm + MAEST + Essentia + CLAP. Essentia runs
on pod CPU concurrently with the GPU lane. A bounded three-track RTX 3090
benchmark measured mean stage times of 25.41 s rhythm, 7.04 s MAEST, 4.58 s
Essentia and 6.50 s CLAP; the rhythm mean includes cold model startup. The
first complete 100-track all-stage shard is the cost gate before any second
parallel pod. Production must remain within existing credit.

**2026-07-19 incident:** shard-0002's cleanup hit a transient DNS failure
mid-run, which the old `terminate()` mistook for a successful pod delete
(D-023 in `docs/DECISIONS.md`). The next invocation then created a second
pod for the same shard instead of reusing the first, doubling the hourly
burn to about USD 0.45/hour until noticed. The orphaned pod's partial
results (100/100 rhythm_full, 100/100 maest_full, 51/51 essentia_full) were
recovered before cleanup. `terminate()` now verifies deletion before trusting
local state; see `docs/OPERATIONS.md` "Duplicate/orphaned pod after a cleanup
failure" for the general recovery steps if this pattern ever recurs.

## Live checks

```bash
cd "/Users/jakub/Appky Claude/spotify-indie-sort"

./.venv/bin/python coverage_report.py
./.venv/bin/python sync_status.py
./.venv/bin/python audio_enrichment_status.py

cat data/cloud_full_shards/orchestrator_status.json
cat data/cloud_full_shards/shard-0001/runpod_state.json

~/.local/bin/runpodctl user
~/.local/bin/runpodctl pod list

for label in \
  com.jakub.local-dj-enrichment \
  com.jakub.music-db-cloud-full-prep \
  com.jakub.music-db-essentia-full \
  com.jakub.music-db-rhythm-full \
  com.jakub.music-db-cloud-production; do
  launchctl print "gui/$(id -u)/$label" | grep -E 'state =|pid =|last exit code'
done
```

## Truth caveats

- `sync_status.py` shows the earlier per-model local pipeline; the new full
  pipeline uses `audio_analysis_artifacts` stages `rhythm_full`, `maest_full`,
  `essentia_full` and `clap_full`.
- Manifest lines can temporarily trail clip files because manifest replacement
  is atomic and batched.
- Local result JSONL can be ahead of imported DB counts while an importer is
  waiting on SQLite contention.
- A local RunPod state saying `terminated` is not sufficient proof. Always
  query RunPod itself.
