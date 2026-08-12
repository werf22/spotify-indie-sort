# Coding Standards

Deep reference for core §7 (Quality bar). Load when writing or reviewing code.

## Simplicity

- Boring, elegant, smallest correct diff. The clever solution loses to the obvious one every time.
- Make it work first. Measure. Only then optimize — and only what the measurement points at.
- No premature optimization: no speculative abstraction layers, no "we might need this later" generics, no hand-rolled caching before a measured bottleneck exists.
- If a diff touches more lines than the task requires, shrink it before presenting it.
- Radical simplicity at the architecture level too: bias toward one language, one framework, one database. Every additional moving part — a second database, a queue service, a separate cache — must justify itself against the spec. This applies to existing projects as much as to new-project stack selection.

## Structure

- Files under ~250 lines. Approaching the limit is the signal to split into modules — split *before* it becomes a monolith, not after.
- Centralized constants, types, and schemas: one source of truth, imported everywhere. Never redefine the same shape, magic number, or enum in two places.
- DRY: before writing a function, check whether the codebase already has it (or 80% of it).
- Naming consistency: before naming anything new — file, function, variable, route, table — check how existing code names similar things and match the pattern. Never introduce a second convention.
- When the project keeps a file-structure doc, update it in the same task that adds, moves, or deletes files. A stale structure doc is worse than none. Full discipline: `rules/documentation-protocol.md`.

## Comments and docs

- Comments explain **WHAT** the code does, **WHY** it does it that way, and **HOW TO TWEAK** it — written for a non-coder owner who will adjust values and behavior without rewriting logic.
- Every module starts with a header: purpose, inputs, outputs. Three lines is usually enough.
- Mark the knobs: where a value is safe to change (timeouts, limits, copy, thresholds), say so and say what happens when it changes.
- Not overwhelming — just enough to understand and tweak. Don't narrate trivial lines; do explain non-obvious decisions.

## Dependencies

- **Zero-setup rule (core §4):** delivered code checks for and installs its own dependencies on first run. The owner does nothing manually — no "first run `<install command>`" instructions in chat.
- **Research-first (core §7):** before building anything, do two searches — (1) is there a quality, maintained open-source solution? (2) does this codebase already do something similar? Use and tweak rather than reinvent. Reinventing is the exception and needs a stated reason.
- Any NEW dependency must be justified: state explicitly why the existing stack cannot do it. "It's popular" is not a justification; "the stack has no <capability> and building it would take longer than auditing this library" is.
- Any new dependency or external service must also pass the portability test: "could we export the data and run on any Linux server tomorrow?" Prefer standard protocols (`DATABASE_URL`-style connections) over proprietary SDKs — see `rules/production-readiness.md` §15 (zero vendor lock-in).
- Never change the tech stack without permission — ASK FIRST tier (core §5). Swapping a library for its competitor counts as a stack change.

## External APIs

- ALWAYS fetch current official documentation before coding against any library or external API — use the docs MCP, a context7-style tool, or web fetch. Training-data memory of an API is a guess, not a source.
- Never code against assumed API shapes: no guessed endpoint paths, parameter names, response fields, or auth flows. If the doc can't be fetched, say so and ask — don't improvise.
- Pin the version you coded against in a comment or the project's context doc when the API is known to move.
- Which tool to fetch docs with — and the routing rule for every other job class — lives in `rules/tool-routing.md`; route to the strongest connected tool before doing anything by hand.

## Scope discipline

- Do not modify working code outside the current task — not even "while I'm here" cleanups. Note the improvement, propose it, move on.
- Large refactors get their own spec and their own session (core §2, §5). They never ride along inside a feature task.

## Scalability awareness

- This is design awareness, not premature optimization: choices that are cheap on day 1 and brutally expensive to retrofit later.
- Connection pooling: never open a fresh connection per request when the platform supports pooling — use the pooled/managed path from the start.
- Caching: identify what is read often and changes rarely; design so a cache can be added behind the existing interface without rewriting callers. Add the actual cache only when measured.
- Indexing: any column or field used in lookups, joins, or sorts gets an index when the schema is created — not after the first slow-query incident.
- The line: structure for scale now, tune for scale when measured.
