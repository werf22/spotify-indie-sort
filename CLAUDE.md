# CLAUDE.md — <project-name>

<!-- This file is PROJECT LAW. The global ~/.claude/CLAUDE.md handles method and persona
     (spec → verifier → environment, guardrails, learning loop); THIS file holds everything
     project-specific: stack, architecture, conventions, phases, budgets, commands.
     The doc filenames referenced below are this project's convention — adapt the names
     to taste, but keep the roles (tasks / context / lessons / done-log / documentation
     map / file structure, plus architecture when it earns its own file). -->

@LESSONS.md
<!-- Adjust to this project's lessons filename so lessons auto-load every session (core §3, §6). -->

## Project

- **Goal:** <one sentence — what this product does and for whom>
- **Target users:** <who exactly; their context>
- **Success metric:** <the one number or observable outcome that means "working">
- **Current phase:** <phase id — see Phases below>

## LOCKED STACK

| Layer | Tech | Notes |
|---|---|---|
| <frontend> | <tech + version> | <why chosen / constraints> |
| <backend> | <tech + version> | |
| <database> | <tech> | |
| <hosting/deploy> | <platform> | |
| <auth / payments / other> | <service> | |

**Rule:** any new dependency requires written justification why this stack cannot solve it. Never change the stack without explicit permission (core §5, ASK FIRST).

## Tooling map

<!-- Concrete servers/CLIs behind the generic tool classes in ~/.claude/rules/tool-routing.md.
     Fill in what THIS project actually has connected; drop rows that don't apply. -->

| Tool class | This project uses | Notes |
|---|---|---|
| Library/API docs | <docs MCP / web fetch> | |
| E2E user-flow testing | <browser/E2E tool> | |
| DB operations & migrations | <DB MCP / CLI> | <which database/instance> |
| Production errors | <error tracker + project name> | |
| Repo/PR management | <platform CLI> | |
| UI components | <component-registry MCP, if any> | |

**Rule:** a job class needed but not mapped/connected → say so and propose connecting it; never silently degrade (`rules/tool-routing.md`, Missing tools).

## Architecture & boundaries

- **Main components:** <component A — role>; <component B — role>; <component C — role>
- **Data flow:** <one line, e.g. "client → API → queue → worker → DB → client poll">
- **Boundary rules:** <which module may import/call which — keep one-way; enforcement under Import & dependency rules below>

## Key patterns

<!-- The house patterns of THIS project, per technology — these beat any generic habit (core §3: conventions
     come from the project). Format: <Technology> — <pattern name>: <files involved> · <rules> · <failure behavior>. -->

- **<Technology> — <pattern name>:** <files involved> · <rules> · <behavior on failure>
- **<Technology> — <pattern name>:** <files involved> · <rules> · <behavior on failure>
- **<Technology> — <pattern name>:** <files involved> · <rules> · <behavior on failure>

<!-- Example: "DB client — 3 clients, never an ORM: client.ts (browser, anon key) · server.ts (SSR, cookies) ·
     admin.ts (service role); migrations NNN_desc.sql, never edit already-run; row-level security on EVERY table."
     Example (AI integration): "All LLM prompts centralized in one prompts/ dir — never hardcoded in routes;
     AI never fabricates domain data (prices/stock/reviews) — only data from API/DB context;
     retry 3x with backoff → fallback message in the user's language; bounded history." -->

## Import & dependency rules

- **Path aliases:** <alias → target, e.g. `<@alias>/*` → `<src/*>`> — always aliases; no relative imports across feature boundaries.
- **One-way domain rule:** <feature-B> NEVER imports from <feature-A>; reads its data via DB/API only.
- **Enforcement:** lint rule over convention — wire the boundary into <lint tooling>. A rule living only in this file gets broken.

## Conventions

- **Naming:** <files, branches, DB tables/columns, env vars>
- **Error responses:** <exact shape, e.g. { error: { code, message, details } } + status codes used>

### API conventions

- **Routes:** <pattern, e.g. <verb> /api/<resource>/<id>; versioning scheme> · route list: <here or ARCHITECTURE.md>
- **Every route:** try/catch → structured `logger.error` → user-facing message in the product language → error tracker. Failures are LOUD (core §7).
- **Every boundary:** input validation on body/params/headers; rate limiting; strict CORS allowlist; security headers on ALL responses — `rules/security-baseline.md` §1–2.

### Frontend conventions

Generic floor (keep in any project) + this project's specifics:

- Error boundaries on every page · skeletons for async loads · empty states for zero results · toast feedback for actions.
- Respect `prefers-reduced-motion` · component-library-first: check <component library> before building custom.
- <state handling, data fetching, component organization>

## Cross-device & PWA

<!-- For user-facing web apps; delete this section otherwise. -->

- **Mobile-first:** when the traffic majority is mobile, design for the smallest target viewport first. Smallest viewport: <width — Example: 320px>.

| Breakpoint | Width | Targets |
|---|---|---|
| <name> | <px> | <device class> |
| <name> | <px> | <device class> |

- **Must-work matrix:** <browsers/devices, e.g. iOS Safari <ver>+, Android Chrome <ver>+, desktop Chrome/Firefox/Safari latest>
- **PWA checklist** (delete if not a PWA): manifest + full icon set · service worker with offline fallback message in the product language · iOS standalone meta · Lighthouse PWA pass.
- **Layout rules:**
  - <rule>
  - <rule>
  <!-- Example: "chat column max-w on desktop, full-width mobile; input sticky bottom with iOS safe-area padding." -->

## Performance budgets

| Metric | Target |
|---|---|
| <metric> | <target> |
| <metric> | <target> |
<!-- Example metrics: page load < 2s on mid-range device; API p95 < 300ms; Lighthouse mobile ≥ 90;
     AI time-to-first-token < 1.5s (if the product has AI); build < 90s; push-to-live < 10 min. -->

## Phases

- **Phase 0 — foundations:** <scope>
- **Phase 1 — MVP:** <scope>
- **Phase 2 — <name>:** <scope>

**Rule:** do NOT implement later-phase features early, even when "it's right there". Follow the task file order strictly (see Docs map).

## Project guardrails

Additions on top of global §5 — these are specific to THIS project:

- **ALWAYS:** <e.g. run <command> before commit; keep <doc> in sync with <thing>>
- **ASK FIRST:** <e.g. anything touching <billing module>; changing <public API shape>>
- **NEVER:** <e.g. write directly to <production resource>; touch <legacy dir>>

Hard-protected paths live in `.claude/protected-paths.txt` (hook-enforced — edits there are physically blocked, not just requested).

## Docs map

| File | Role |
|---|---|
| `<HANDOFF.md>` | Session entry point — Snapshot, DO-THIS-NOW, state of the world. Updated after EVERY run, read FIRST by every new session |
| `<TASKS.md>` | Ordered work queue — single source of truth for what's next |
| `<LESSONS.md>` | Project lessons — auto-imported above |
| `<DONE.md>` | Append-only completion log — timestamp + what changed + files + verified-by |
| `<DOCUMENTATION.md>` | Living codebase map for non-coders — modules, data flows, external services |
| `<FILE_STRUCTURE.md>` | Authoritative directory tree — updated in the SAME task that adds/moves/deletes files |
| `<ARCHITECTURE.md>` | Deeper system design, if/when the section above outgrows this file |

**Rule:** after EVERY completed task, walk the update table in `rules/documentation-protocol.md` — handoff rewritten, task checked off, done-log appended, documentation map and file structure current, lesson check done. A skipped update means the task is NOT done (core §4). The handoff additionally updates after every RUN, not just every task — never end a run with a stale handoff.

## Commands

- **Run:** `<command>`
- **Test:** `<command>`
- **Deploy:** `<command>`

## AI Layer (vendored)

@.claude/rules/core-portable.md
@.claude/rules/learned-rules.md

Vendored rules live in `.claude/rules/`, skills in `.claude/skills/`. Cloud sessions load ONLY this repo — keep this section and the lessons import intact.
