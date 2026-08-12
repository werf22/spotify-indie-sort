---
name: sync
description: Synchronize the AI layer — install or refresh the portable layer in the current repo, or trigger the global fan-out that syncs ALL repos. Works on the local machine (from the canonical bundle) and in cloud sandboxes (by cloning the canonical GitHub bundle repo). Use when a repo lacks .claude/rules/core-portable.md, on freshly created or cloned repos, when the user says "spusti sync", "sync all", "synchronizuj", "nainstaluj AI layer", "chýba tu systém", or types /sync.
---

# sync — make THIS repo (or all repos) carry the current system

Two modes. Default is the current repo; "all/everywhere/všade" means the global fan-out. Additive and idempotent — never overwrites project files; only syncs the layer's own files (`core-portable.md`, `learned-rules.md` snapshot).

## Mode A — this repo (default)

### 1. Check
`.claude/rules/core-portable.md` present → already vendored. Say so in one line; refresh (steps 2–4) only if the user asked for a refresh. Missing → continue.

### 2. Locate the bundle source, in this order
1. **Local machine:** `/Users/jakub/Appky Claude/claude-code-system` — the canonical working copy.
2. **Anywhere else (cloud sandbox, other machine):** clone the canonical repo shallow:
   `git clone --depth 1 https://github.com/werf22/claude-code-system /tmp/ccs`
   (or `gh repo clone werf22/claude-code-system /tmp/ccs -- --depth 1`). Use whatever git credentials the environment already has.

### 3. Install
Run `<bundle>/install-into-repo.sh "$PWD"` and show its summary. It vendors rules (incl. `core-portable.md` + learned-rules snapshot), ALL personal skills, the protect-paths hook wired via `$CLAUDE_PROJECT_DIR`, `.mcp.json` (context7), and doc scaffolding (HANDOFF, TASKS, LESSONS, DONE, DOCUMENTATION, FILE_STRUCTURE) — plus the AI Layer import block in CLAUDE.md.

### 4. Commit + push
`chore(ai-layer): sync portable AI layer` — autopilot, no question: the change is additive (standing learned rule: every repo must carry the layer). Clean up any `/tmp/ccs` clone.

### 5. If the bundle repo cannot be cloned (no credentials in this sandbox)
Say so explicitly — do NOT silently continue without the layer. The sync-ai-layer GitHub Action vendors every repo automatically on its next run (≤6 h, or instantly via Mode B from a local session). Manual fallback for the owner, one paste: *"Clone werf22/claude-code-system and run its install-into-repo.sh on this repo, then commit and push."*

## Mode B — all repos ("sync all", "spusti sync všade")

Trigger the controller, preferring the lightest path that works:
1. `gh workflow run sync-ai-layer -R werf22/claude-code-system` — then watch it: `gh run watch <latest-run-id> -R werf22/claude-code-system --exit-status`.
2. If dispatching is not permitted in this environment, push any pending bundle change instead (e.g. run `sync-global.sh`) — the push trigger runs the same fan-out.
3. Report per-repo results from the run log (`synced` / `up to date` / failures), loudly naming any failures.

## Confirm
One line: what was synced and where — repo-level (files installed) or global (N repos synced, M up to date).
