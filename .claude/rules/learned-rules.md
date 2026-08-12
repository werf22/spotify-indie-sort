# Learned Rules

Auto-imported into every session via `@rules/learned-rules.md` in the core CLAUDE.md — this file is always in context, so keep it terse: one rule per line, format `- [YYYY-MM-DD] rule — why`.
New rules are appended under "Learned rules" by the Learning protocol (core §6). A candidate that matches an existing rule — in ANY section, including Seed rules — sharpens that rule in place; never append a second copy.
Store every rule in English, regardless of the language it was stated in — translate, and optionally keep the original phrase in the why. One storage language is what keeps grep-based dedupe working.
When the file exceeds ~40 rules (seed rules count and may be merged like any other), propose a consolidation pass: merge near-duplicates, drop stale ones. Consolidation is propose-only — present the merged file as a before/after diff, get explicit approval before writing, and never drop a rule without it.

## Seed rules

<!-- One example entry demonstrating the format — replace it with your first real rule.
     Don't restate what the always-loaded core already mandates; rules here must ADD signal. -->

- [2026-06-09] (format example) never run a schema migration without a dated backup of the data store first — restoring after a bad migration costs hours; a dated backup makes rollback a copy, not a forensic project.

## Learned rules

<!-- Append here. Format: - [YYYY-MM-DD] rule — why -->

- [2026-06-10] all work — the main session and every subagent — runs on the top-tier model at maximum effort (currently Fable 5, `claude-fable-5`); downgrading anything to a cheaper model is ASK-FIRST, never silent — user explicitly requires uniform flagship quality ("všetko musí byť spravené pomocou Fable 5 najväčším effortom"); cost is managed by fewer agents, not weaker ones.
- [2026-06-10] every repo must carry the vendored AI layer: at local session start (and in /new-project), if `.claude/rules/core-portable.md` is missing, run `claude-code-system/install-into-repo.sh`, commit, push — autopilot, no asking — cloud sessions (iPhone/web/desktop-cloud) load ONLY the committed repo, so an unvendored repo means a cloud session with no system; user requires automatic cloud parity on every repo.
- [2026-06-16] when synthesizing from the user's knowledge base, always draw from the ENTIRE corpus — raw notes, concepts, entities, journals, tags, AND existing syntheses — never only from finished syntheses; distillations are lossy (they drop exact techniques, verbatim phrasing, raw material the synthesis needs); user corrected this explicitly ("nemáš čerpať len zo syntézy… čerpaj zo všetkých poznámok aj raw").
- [2026-06-18] after EVERY change to code/files, commit AND push to GitHub automatically — every time, no exceptions, without being asked and without the user checking; never end a turn with uncommitted work — user demanded it emphatically ("ZA KAŽDÝM a v KAŽDOM PRÍPADE… automaticky"); enforced by the Stop hook `auto-commit.sh` (global `~/.claude/hooks/` + vendored `.claude/hooks/` in every repo), because CLAUDE.md text is only a request.

## Declined

<!-- Candidates the user said to never propose again. Format: - [YYYY-MM-DD] declined: rule
     The dedupe grep (core §6, learn skill §3) searches this section too — a hit here kills the candidate. -->
