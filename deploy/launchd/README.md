# Supervised background jobs (macOS launchd)

These four agents make the pipeline run without a terminal, an AI session, or
anyone watching. Copy a plist to `~/Library/LaunchAgents/` and
`launchctl load` it; `launchctl kickstart -k gui/$(id -u)/<Label>` restarts one.

| Agent | What it guarantees |
|---|---|
| `com.jakub.podreaper` | No RunPod pod bills without proving it works. Died twice with the session that started it before it was supervised (D-064). |
| `com.jakub.music-db-cloud-production` | The orchestrator that builds shards and drives pods. Installed earlier; `pkill` does NOT stop it — use `launchctl unload`. |
| `com.jakub.music-db-prep` | The clip factory. Yields at 70 GiB free so the builder keeps its 45 GiB; skips absent sources, so unplugging T7 pauses only T7's tracks. |
| `com.jakub.music-db-gc` | Reclaims disk from finished work every 20 min. Without it the workspace grows until the builder falls below its floor and silently stops (D-066). |

The orchestrator's own plist is not copied here because it was installed before
this directory existed; export it with
`launchctl print gui/$(id -u)/com.jakub.music-db-cloud-production` if it is ever
lost.
