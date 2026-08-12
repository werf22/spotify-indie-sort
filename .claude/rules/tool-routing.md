# Tool Routing

Deep reference for core §3 (Session start), §4 (Execution loop), §7 (Research-first). Load when deciding HOW to do a job — before doing anything by hand.

## Principle

Route every job to the strongest available tool BEFORE writing code by hand. Hand-rolling what a connected tool does better is the same mistake as reinventing an existing library (core §7): slower, blinder, and harder to verify.

Concrete MCP/server names vary per machine and per project — this file therefore names tool CLASSES, never specific servers (the named tools below are examples of a class, not requirements). At session start (core §3), discover what is actually connected; the concrete class → server mapping for each project lives in that project's CLAUDE.md under **Tooling map** (template: `~/.claude/templates/project-CLAUDE.md`).

## Routing table

| Job | Tool class | Rule |
|---|---|---|
| Library/API docs | Docs MCP (context7-class) or web fetch | **API RULE:** ALWAYS fetch current docs before coding with any library — never code against assumed API shapes. |
| Code examples & solutions | Web / code search | Search for proven solutions and quality examples before building from scratch — research-first (core §7). |
| E2E user-flow testing | Browser/E2E MCP (Playwright-class) | Test EVERY user flow after implementation — flows over units (`rules/testing-and-verification.md`). |
| DB operations, types, migrations | The project's DB MCP or CLI | Schema, generated types, and migrations go through the DB tool — never hand-typed from memory. Migrations stay ASK-FIRST (core §5). |
| Production errors | Error-tracker MCP (Sentry-class) | Check the tracker BEFORE debugging blind — real stack traces and frequencies beat reproduction guesses (`rules/logging-observability.md`). |
| Git operations | git CLI/MCP | Branch, atomic commit, push after every completed task (core §4, `rules/git-workflow.md`). |
| Repo/PR management | Platform CLI (gh-class) | Issues, PRs, reviews, CI status through the platform CLI — not guessed from memory or scraped from the web UI. |
| Complex problem decomposition | Plan mode / sequential-thinking tool | Decompose before executing anything multi-step — the thinking tool of the SPEC layer (core §2). |
| Filesystem operations | Built-in file tools (read/write/edit/glob/grep) | Project files go through the dedicated file tools, not shell `cat`/`sed` detours — better diffs, safer edits, hook coverage. |
| Endpoint & service verification | Web fetch / HTTP client | VERIFY a URL or live endpoint actually exists and responds as documented — external signal (core §2), never "it should work". |
| Current information | Web search | Anything time-sensitive (versions, pricing, status, news) gets searched, not recalled from training data. |
| Persistent context | Memory / knowledge base (`~/.claude/knowledge/`, learned rules) | Check it before asking what it already answers (core §9); write back only through the Learning protocol (core §6). |
| Analytics (if the product has them) | Analytics MCP / query CLI | Product metrics come from the analytics tool, never estimated — no fabricated numbers (core §5 NEVER). |
| UI component libraries | Component-registry MCP (shadcn-class) | Look up the registry component before hand-rolling any UI primitive — a hand-built twin of a registry component needs a stated reason. |

> **THE API RULE — worth repeating verbatim:** ALWAYS fetch current docs before coding with any library — never code against assumed API shapes. Training-data memory of an API is a guess, not a source: no guessed endpoint paths, parameter names, response fields, or auth flows. If the docs can't be fetched, say so and ask — don't improvise. Detail: `rules/coding-standards.md`, External APIs.

## Missing tools

When a needed tool class is NOT connected, say so and propose connecting it — never silently degrade to a weaker method (paraphrasing docs from memory, guessing schema shapes, "testing" by reading code). A degraded method is acceptable only after I explicitly decline the tool, and the deliverable then states which class was missing and what that cost in confidence.

## Per-project mapping

This file stays generic on purpose — there is no global stack (core §3). Each project's CLAUDE.md carries the concrete mapping in its **Tooling map** section: tool class → the actual connected server/CLI, plus project-specific notes (which DB, which tracker project, which component registry). At session start, verify the mapped tools are actually connected; a mapped-but-disconnected tool follows the Missing-tools rule above.

## This machine

The concrete inventory of skills, plugins, and MCP connectors installed on THIS machine — including the knowledge-system routing (graphify vs llm-wiki vs deep-research vs knowledge/) — lives in `rules/capability-map.md`. Class-level rules here; instance-level routing there.
