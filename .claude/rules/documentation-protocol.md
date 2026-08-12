# Documentation Protocol

Deep reference for core §4 (update project docs) and §7 (scope discipline). Load at the end of every task and whenever files are added, moved, or deleted. Filenames are per-project — the project CLAUDE.md **Docs map** names them; the roles below are universal.

## The after-every-task update

A task whose docs are not updated is a task NOT done (core §4) — the box stays unchecked, same as a red test. After EVERY completed task, walk this table top to bottom:

| Doc role | What to update |
|---|---|
| **Handoff file** (`HANDOFF.md`; legacy name `CONTEXT.md`) | THE entry point for a cold session: Snapshot, DO-THIS-NOW, state of the world, direction. Overwrite it — it describes NOW, not history. Template: `templates/HANDOFF.md`. |
| **Task file** | Check off the task — only with the DoD met and checks green. An unchecked box with honest status beats a checked lie. |
| **Done-log** | Append one timestamped entry: what changed + files modified + how it was verified. Never edit past entries. |
| **Documentation map** | New files/modules, their relationships, any data flow touched — if the project keeps one. Template: `templates/DOCUMENTATION.md`. |
| **File-structure doc** | New files/dirs with one-line annotations — if the project keeps one. Template: `templates/FILE_STRUCTURE.md`. |
| **Lessons file** | Any mistake or learning from the task — via the learning protocol (core §6). None? Skip honestly; don't manufacture lessons. |

"If the project keeps one" is discovered at session start (core §3) from the Docs map — never invent new doc files mid-task. When a missing doc's absence bites, propose adding it as its own item.

## The handoff cadence — stricter than everything else

The handoff file does NOT wait for task completion. Update it after EVERY run: a step completed, a test gone red, a decision made, a pause — anything a successor would need. The session may die at any moment (cloud timeout, closed laptop, crashed terminal); the handoff is what makes that survivable. **Never end a run with a stale handoff.** The acceptance test, always: *could a brand-new AI, reading HANDOFF.md alone, continue this project right now?* If the honest answer is no, fixing the handoff IS the next action — before code, before anything.

## File-structure discipline

- Creating ANY file outside the documented structure without updating the file-structure doc **in the same task** is a violation — not a style nit.
- Moving and deleting count the same as creating.
- The file-structure doc is authoritative: when doc and disk disagree, fixing the disagreement is the immediate next action, not background debt. A stale structure doc is worse than none.

## Naming consistency

- One concept, one name, across the ENTIRE codebase: names, keys, types, constants. The data column, the API field, and the UI variable for the same thing share one name (modulo case convention).
- ALWAYS check existing code before creating any new name — match the established pattern; never introduce a second convention (`rules/coding-standards.md` → Structure).
- If the existing convention is wrong, propose a rename as its own task — don't fork conventions inside a feature.

## Code documentation

Standards live in `rules/coding-standards.md` → Comments and docs — apply them, don't restate them. The contract in one breath: comments explain WHAT / WHY / HOW-TO-TWEAK for a non-coder owner; every module header carries purpose / inputs / outputs; just enough to understand and tweak, never overwhelming.
