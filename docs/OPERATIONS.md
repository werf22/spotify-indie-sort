# Operations and recovery runbook

All commands assume:

```bash
cd "/Users/jakub/Appky Claude/spotify-indie-sort"
```

## Observe first

Before starting or restarting a worker, inspect LaunchAgent and process state.
Duplicate API workers previously caused a long Spotify 429 ban.

```bash
ps -axo pid,ppid,%cpu,%mem,etime,command | \
  grep -E 'enrichment_daemon|prepare_cloud_audio|follow_local|cloud_production|runpod_full'

launchctl print gui/$(id -u)/com.jakub.local-dj-enrichment
launchctl print gui/$(id -u)/com.jakub.music-db-cloud-full-prep
launchctl print gui/$(id -u)/com.jakub.music-db-essentia-full
launchctl print gui/$(id -u)/com.jakub.music-db-rhythm-full
launchctl print gui/$(id -u)/com.jakub.music-db-cloud-production
```

The local Essentia and rhythm labels are intentionally disabled. Do not enable
them during cloud production unless the owner explicitly requests an offline
fallback.

Do not launch a script manually when its LaunchAgent already owns it.

## Standard status

```bash
./.venv/bin/python coverage_report.py
./.venv/bin/python sync_status.py
./.venv/bin/python audio_enrichment_status.py
tail -100 data/enrichment_supervisor.log
```

Full-audio counters:

```bash
find data/cloud_full/clips -type f | wc -l
tail -n +2 data/cloud_full/manifest.csv | wc -l
wc -l data/cloud_full/local-essentia-results.jsonl
wc -l data/cloud_full/local-rhythm-results.jsonl
cat data/cloud_full_shards/orchestrator_status.json
```

Temporary differences between clip, manifest, JSONL and DB counts are expected.
The important invariant is monotonic progress with no repeated permanent error.

## RunPod safety and monitoring

```bash
~/.local/bin/runpodctl user
~/.local/bin/runpodctl pod list
cat data/cloud_full_shards/shard-0001/runpod_state.json
tail -100 data/cloud_production.log
tail -100 data/cloud_production.error.log
```

Rules:

- never fund, upgrade or change billing;
- never create a pod manually while the orchestrator is live;
- hourly price must be <= USD 0.40;
- local orchestrator waits below USD 1.00 balance;
- each pod has server-side stop and terminate timestamps;
- verify deletion against RunPod, not only local JSON;
- if a pod is orphaned after a client crash, retrieve any result first if safe,
  then delete the pod using the existing cleanup code/CLI.

Production shard lifecycle is:

`ready -> created -> ssh_ready -> uploaded -> analysis_complete ->
results_downloaded -> terminated -> imported`.

Results are append-only; re-running an incomplete shard skips successful
track/stage pairs. A completed shard has every pair listed in its manifest's
`required_stages`; already imported stages are intentionally omitted.

Before launching a newly generated shard format, verify that every manifest
`clip_path` exists both locally and inside `tar -tf bundle.tar`, and run a tiny
bounded cloud smoke/benchmark across rhythm, MAEST, Essentia and CLAP. Do not
run heavy preflights on the laptop. A checksum alone proves bundle integrity,
not that its internal paths/import dependencies are correct.

## Pause and resume

The menu-bar app is the preferred user control for the general sync supervisor.
CLI fallback:

```bash
./.venv/bin/python sync_control.py pause-all
./.venv/bin/python sync_control.py resume-all
./.venv/bin/python sync_control.py check-disk
```

Important: the dedicated full-track LaunchAgents are separate from
`com.jakub.local-dj-enrichment`. `pause-all` currently controls the general
supervisor, not necessarily every full-track/cloud agent. If a true emergency
stop is needed, explicitly stop each relevant LaunchAgent and document why.

## Disk guard

```bash
df -h .
./.venv/bin/python sync_control.py check-disk
```

The owner wants processing to continue on the internal disk until only 50 GiB
remains, then be notified. Do not silently move the active corpus to an SSD
before the user supplies and identifies it. A future move must update:

- `sync_control.output_root`;
- audio scan roots in `.env`;
- LaunchAgent arguments/working paths if required;
- DB paths or symlinks in one atomic migration plan;
- Traktor paths as appropriate.

## Reinstalling LaunchAgents

Only do this when a source plist changed or an agent is missing:

```bash
cp com.jakub.music-db-cloud-full-prep.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jakub.music-db-cloud-full-prep.plist
```

Use the matching label/path for other agents. `launchctl bootout` before
re-bootstrap when replacing a loaded agent. Verify exactly one resulting process.

## Network outage behavior

- Catalog workers test connectivity and wait 60 seconds while offline.
- Heavy Essentia/rhythm inference remains disabled locally.
- SCP/RunPod commands can fail; shard state persists and the orchestrator retries.
- Never treat one timeout as a permanent no-match.

## Credential/access verification

```bash
./.venv/bin/python verify_handoff_access.py
./.venv/bin/python verify_handoff_access.py --live
```

The live mode performs safe read-only Spotify, Last.fm, MusicBrainz and RunPod
checks. It never prints key values and does not spend a FreqBlog lookup.

After connectivity returns, confirm counters progress. Do not start duplicate
workers to “help” a waiting supervisor.

## Sleep/restart behavior

LaunchAgents start at login/reboot. Append-only results and DB checkpoints mean
completed tracks are not lost. After wake/reboot:

1. inspect all agent states;
2. inspect disk free space;
3. inspect RunPod for orphaned paid resources;
4. confirm result/manifest counters resume;
5. only intervene if the same error repeats without progress.

## Database integrity and backup

Read-only quick checks:

```bash
sqlite3 data/music.db 'PRAGMA quick_check;'
sqlite3 data/music.db 'PRAGMA journal_mode;'
```

For a consistent live backup, use SQLite's backup API. Avoid copying
`music.db` alone while `music.db-wal` is active. Before schema work, create a
verified backup and ensure no destructive command touches unrelated user data.

## Logs and failure interpretation

| Log/state | Meaning |
|---|---|
| `data/enrichment_supervisor.log` | All general provider worker cycles |
| `data/cloud_full_prep*.log` | FFmpeg full-track preparation |
| `data/essentia_full*.log` | Local supervised follower/importer |
| `data/rhythm_full*.log` | Local rhythm follower/importer |
| `data/cloud_production*.log` | Production orchestrator and shard runner |
| `data/cloud_full_shards/*/runpod_state.json` | Per-shard cloud lifecycle |
| `data/cloud_full_shards/orchestrator_status.json` | Current production phase |

One failed item should be recorded and skipped/retried. A worker is considered
stuck only when timestamps, output counts and logs remain unchanged while its
process is alive and the external dependency is healthy.

## Quality audit after full batch

Do not declare success from coverage alone. Select a stratified audit including:

- afro/organic/ritual/ecstatic music;
- indie rock/pop/folk and acoustic songs;
- techno/house/trance and melodic electronic music;
- beatless ambient and beatless intros;
- four-on-the-floor, broken beat and mixed-meter examples;
- vocals/instrumentals and sparse/dense arrangements;
- underground Tebra-adjacent material;
- long tracks with changing mood/genre.

Review canonical and candidate tags separately, rhythm timeline, mood timeline,
BPM/key conflicts and nearest-neighbor quality. Calibrate thresholds from this
audit without deleting raw predictions.

## Common recovery cases

### RunPod pod exists but local runner died

Inspect pod and shard state. Resume `runpod_full_shard.py --shard ...` only when
the production LaunchAgent is not already doing so. The runner reuses saved SSH
state, skips uploaded/analyzed stages when valid and deletes in `finally`.

### Result JSONL exists but DB count did not increase

Run `import_full_audio_results.py` with the corresponding manifest/results only
after confirming no live follower is importing the same file. The importer is
idempotent by track/stage/model keys.

### Spotify returns a long `Retry-After`

Do not retry aggressively. `spotify_client.py` refuses automatic sleeps longer
than 120 seconds. Stop duplicates and wait until the exact retry time.

### FreqBlog 429

A 429 can mean monthly quota or concurrency/rate limit. Inspect response/state.
Do not buy more quota. Allow the job's retry/quota-wait state to handle it.

### Low disk

Pause, notify the user and wait for the SSD decision. Do not delete analysis
assets or source audio to recover space without explicit approval.
