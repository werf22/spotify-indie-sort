---
name: session-start
description: Orients inside a project at the start of a work session — discovers project docs, reads lessons and context, finds the next task, checks git state, and briefs the user. Use at the start of any session in a project directory, when the user asks "where were we", "what's the status", "pokračujeme", or types /session-start.
---

# session-start — orient before touching anything

Implements core §3. The goal: within a minute, know what this project is, where it stopped, and what comes next — without the user re-explaining anything. Never start coding from a cold prompt.

## Procedure

### 0. Convergence check — vendor the AI layer (local machine only)
If this repo lacks `.claude/rules/core-portable.md`, every CLOUD session on it runs blind — fix that FIRST, before any other work:
1. Run `"/Users/jakub/Appky Claude/claude-code-system/install-into-repo.sh" "$PWD"`.
2. Commit (`chore: vendor AI layer`) and push — autopilot, no question needed: the installer is additive (it never overwrites project files; it only syncs its own `core-portable.md` + `learned-rules.md` snapshot).
3. If the repo HAS the layer, still let the installer refresh the two sync files when learned rules changed recently (same command, idempotent).
Skip this step inside cloud sandboxes — there the layer either came with the repo or this step cannot help (`rules/capability-map.md`, cloud caveat). Also promote any `[global-candidate]` entries found in the project lessons file (learn skill §5).

### 1. Discover the project's docs
- Read the project's own `CLAUDE.md` if present.
- Glob the repo root and `docs/` (and any obvious planning directory) for planning docs under **any** naming: task lists, context, lessons, PRD, idea, architecture, done-log, file-structure, roadmap, spec — names vary per project (`TASKS.md`, `todo.md`, `PLAN.md`, `prd.md`, `notes/…`).
- List what was found in one line. **Never assume a fixed set of files exists** — discover, don't expect.

### 2. Read state, in this order
1. **Handoff file first** (`HANDOFF.md`; legacy `CONTEXT.md`) — the designated entry point: Snapshot, DO-THIS-NOW, state of the world. If it's stale (older than the last commits), flag that immediately and rebuild it from git + the other docs before doing anything else — a stale handoff is a broken project.
2. **Lessons file** — known mistakes in this codebase must be loaded before any work, or they get repeated. (Global learned rules are already auto-imported by the core.)
3. **Task file** — what's checked, what's next, what's blocked; cross-check against the handoff's DO-THIS-NOW.
4. **Every other planning doc discovered in step 1** — PRD, architecture, file-structure, documentation map, roadmap: at least skim each. A discovered-but-unread doc is how conventions get violated on the first edit.

### 3. Detect the stack & scan the structure
- Stack from evidence only: lockfiles, manifests, config files, the code itself. There is no global stack and no carry-over from other projects (core §3.4). Note the detected `<stack>` in one line; if ambiguous, say so rather than guessing.
- **Scan the codebase structure**: glob the source tree two to three levels deep and absorb how it's organized — where features, shared code, and config live. If the project keeps a file-structure doc, diff reality against it and flag drift. Starting a task without having seen the tree is how files land in the wrong place.
- **Verify the Tooling map**: read the project CLAUDE.md's Tooling map and check the mapped tool classes are actually connected (`rules/tool-routing.md`). A mapped-but-disconnected tool follows the Missing-tools rule — say so, don't silently degrade.

### 4. Check git
- `git status` — **uncommitted work is the first thing to surface**; it means the last session ended mid-task or dirty.
- Current branch — a non-default branch usually names the task in flight.
- `git log` (last ~5 commits) — what actually landed, versus what the docs claim.
- If docs and git disagree, trust git and flag the drift.

### 5. Brief the user — 5 to 10 lines
- **Current state:** one-line project status, branch, dirty/clean tree.
- **Last completed:** most recent finished task or commit.
- **Next task candidate:** next unchecked item in the task file, with its id.
- **Open risks / blockers:** uncommitted changes, failing checks, stale docs, unresolved questions from context.

No essays. The brief exists so the user can say "go" with full information.

### 6. Confirm and hand off
- Propose the target task in one line and ask to confirm.
- On confirmation — or if the user already said "just keep working" / "pokračuj" — pick the next unchecked task and switch to the `task-loop` skill (core §4).

## Anti-patterns
- Starting to code before the brief.
- Assuming doc names or a stack from a previous project.
- Ignoring a dirty working tree because the task file looks clean.
- A 40-line brief — if it doesn't fit in 10 lines, it's a report, not a briefing.
