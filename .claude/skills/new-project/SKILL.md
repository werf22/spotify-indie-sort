---
name: new-project
description: Scaffold a complete working environment for a new project — spec interview, stack decision, project docs from templates, git, guardrails, hooks. Use when starting a new project, app, or repo, or when the user types /new-project.
---

# new-project — from idea to working environment

Run the steps in order. Do not skip ahead: no code, no `git init`, no file scaffolding until step 1 is agreed. Each step ends with a one-line confirmation of what was decided or created.

## 1. Spec interview first

Invoke the `spec-first` skill. The interview must pin down, minimum:

- **Goal** — what the product does, in one sentence.
- **Target users** — who touches it, and how technical they are.
- **The decision it supports** — what does a user decide or do because this exists?
- **MVP vs nice-to-have** — explicit split. Nice-to-haves go to a backlog, not the plan.
- **Success metric** — one measurable signal that says "this works".

No scaffolding before the spec is agreed. A wrong foundation costs more than a slow start (core §2).

## 2. Stack decision — WITH the user, never silently

- **Research-first:** before proposing anything, look at what similar quality open-source products use. Cite 2–3 real examples. Don't invent a stack from taste.
- **Radical simplicity:** fewest moving parts that satisfy the spec. Ideal shape: one language + one framework + one database. Every extra service must justify itself against the spec, not against "best practice".
- **Zero vendor lock-in test:** ask out loud — *"Can we export the data and run this on any Linux server tomorrow?"* The answer must be YES. If a candidate component fails this test, name the lock-in and propose the portable alternative.
- **Production scope check:** if real users will touch this, ask whether full-stack production scope applies. If yes, schedule the `production-ready` skill for after scaffolding (core §7).
- Present the decision as a short table: component → choice → why → lock-in answer. Get explicit agreement before step 3.

## 3. Scaffold project docs from `~/.claude/templates/`

Create in the project root, filled in — not blank copies:

| File | Fill with |
|---|---|
| `CLAUDE.md` | Stack table from step 2, Tooling map (tool class → connected server/CLI, `rules/tool-routing.md`), conventions, budgets (cost/perf if known), project guardrails, Docs map naming all the files below |
| `TASKS.md` | Phased plan of **vertical slices** — each task is end-to-end usable, not a layer. Phase 0 = foundations (step 5) |
| `HANDOFF.md` | First snapshot: project one-liner, lifecycle = phase 0, DO-THIS-NOW = the first phase-0 task, spec summary + key decisions, doc/command map. From here on it's updated after EVERY run (`rules/documentation-protocol.md`) |
| `LESSONS.md` | Empty scaffold, ready for the learning protocol (core §6) |
| `DONE.md` | Empty scaffold |
| `DOCUMENTATION.md` | Codebase map for non-coders: modules, data flows, external services — seeded with the phase-0 skeleton |
| `FILE_STRUCTURE.md` | The scaffolded tree with one-line annotations — the authoritative map `rules/documentation-protocol.md` updates after every task |

Also generate per stack (no template — it depends on step 2's choices):

- `.env.example` — every env var the stack needs, with placeholder values and one-line comments.

Then vendor the portable AI layer — cloud sessions depend on it: run `"/Users/jakub/Appky Claude/claude-code-system/install-into-repo.sh" .` (adds `.claude/rules/` incl. `core-portable.md`, in-repo skills, the protect-paths hook, and the AI Layer import block in CLAUDE.md).

## 4. Git from day 0

1. `git init`, sensible `.gitignore` for the chosen stack (must cover `.env`).
2. Initial commit of the scaffold.
3. Create the remote: `gh repo create <name> --private --source=. --push` (confirm name and visibility first — creating a remote is external action, ASK-FIRST tier).
4. Verify the push landed. Everything recoverable from day 0; no work exists only locally.

## 5. Foundations before features — phase 0

Before any feature task, the skeleton must include:

- **Test harness** — runner installed, one trivial passing test, single command to run it.
- **Health endpoint** (or CLI equivalent) — "is it alive?" answerable in one call.
- **Structured logger** — wired at entry points; failures are LOUD (core §7).
- **Error tracking wiring** — at minimum a stub/env-var slot so it's a config change later, not a refactor.

These are phase 0 tasks in `TASKS.md`. Features start at phase 1.

## 6. Guardrails

- Create `.claude/protected-paths.txt` in the project: migrations, production config, `.env`, plus anything the spec marks as untouchable. One pattern per line.
- Offer to wire the `protect-paths` hook (`~/.claude/hooks/README.md`) so the NEVER tier is enforced at tool level, not just requested in text (core §5).

## 7. Hand off

Open the first phase-0 task and hand off to the `task-loop` skill. Confirm the loop: branch → slice → test → green → commit → push → docs → lesson check (core §4).
