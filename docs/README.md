# Project documentation

This directory is the durable handoff package for the Spotify DJ Music
Intelligence Database. `../HANDOFF.md` is the entry point for a new agent.

## Reading order

1. [Handoff](../HANDOFF.md) — mission, safety invariants and immediate actions.
2. [Status](STATUS.md) — timestamped facts and commands for live truth.
3. [Architecture](ARCHITECTURE.md) — components, flows, processes and files.
4. [Data model](DATA_MODEL.md) — SQLite schema, provenance and trust hierarchy.
5. [Providers](PROVIDERS.md) — active/evaluated sources, costs and match rules.
6. [Operations](OPERATIONS.md) — start, stop, inspect, recover and verify.
7. [Decisions](DECISIONS.md) — binding technical/product decisions and rationale.
8. [Tasks](TASKS.md) — completed work, active work and backlog.
9. [History](HISTORY.md) — reconstruction of the full conversation/project arc.
10. [Playlists](PLAYLISTS.md) — known Spotify outputs and their purpose.
11. [Security](SECURITY.md) — credentials, spend and data handling.

## Source-of-truth precedence

When documents disagree, use this order:

1. explicit owner rules in `../HANDOFF.md`;
2. current code and live persisted state;
3. this `docs/` package;
4. root `README_MUSIC_DB.md` and `DATA_SOURCES.md`;
5. `PROJECT_STATUS_AND_SCALING.md` and the old git history, which may describe
   superseded experiments.

No document contains secret values. `.env` is intentionally ignored by git.
