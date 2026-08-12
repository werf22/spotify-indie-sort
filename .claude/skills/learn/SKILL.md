---
name: learn
description: Captures a user preference, correction, or lesson into persistent rules in real time. Use when the user states a preference ("always…", "never…", "from now on…", "vždy…", "nikdy…", "odteraz…"), corrects how something was done, says "remember this", "make this a rule", "zapamätaj si", "sprav z toho pravidlo", or "ulož to ako pravidlo", when the same mistake or friction appears a second time, during the end-of-task lesson check, or when the user types /learn.
---

# learn — capture a lesson into the system

Implements core §6 (Learning protocol). The system must get smarter every session; this skill is how a one-off correction becomes permanent behavior. When a signal fires, ask at the next natural pause — end of the current step or the end-of-task check, whichever comes first. Never more than one save question per pause (batch candidates, see §4). Only a rule preventing imminent damage justifies interrupting mid-step.

## Procedure

### 1. Phrase the candidate rule
One terse line + the why. A rule must be a **checkable behavior** — something a future session could violate and be caught violating. Vague rules ("be more careful", "write better code") are worthless; if it cannot be phrased as a checkable behavior, sharpen it until it can.

- Bad: "pay attention to migrations"
- Example: "Never run a schema migration without a dated backup of <data-store> first — restoring after a bad migration cost 2 hours on <project>."

### 2. Classify tier
- **global** — applies to every project (workflow, communication, tooling preferences).
- **project** — true only in this codebase (its conventions, quirks, fragile areas).
- **knowledge** — not a rule but a fact: narrative context (who/what/why) with nothing to violate → the matching `~/.claude/knowledge/` file (e.g. `personal/preferences.md`).
- **once** — situational; not worth persisting.

**Routing rule (rules vs knowledge):** checkable behavior a future session could violate → `learned-rules.md` / lessons file. Narrative context or facts with nothing to violate → `knowledge/`. Tool choices that constrain behavior (e.g. "use pnpm, never npm") are RULES, not knowledge.

Suggest a tier with one-line reasoning ("this is about how you like commits everywhere → global").

### 3. Dedupe BEFORE asking
Grep `~/.claude/rules/learned-rules.md` (ALL sections — Seed rules, Learned rules, Declined) and the project lessons file for keywords from the candidate rule. Rules are stored in English (§5), so translate the keywords to English before grepping. If an overlapping rule exists, skip the save question — say in one line that it's already covered and propose **updating or sharpening it in place** instead of adding a near-duplicate. Two rules saying almost the same thing is how rule files rot. A hit under `## Declined` kills the candidate outright: the user already said no — drop it without asking.

### 4. Ask in ONE line
> Save as a rule? [global / this project / knowledge / just this once]

**Multiple candidates pending** → one numbered list, one question:
> Save as rules? Answer per item (global/project/knowledge/skip): 1) … 2) … 3) …

Apply each answer independently and confirm all writes in one line.

**Exception:** if the user already explicitly said to save it ("add this as a global rule", "remember this for this project", "zapamätaj si", "sprav z toho pravidlo", "ulož to ako pravidlo"), skip the question — write it and confirm.

### 5. Write
- **Language:** store every rule in English, regardless of the language it was stated in — translate, and optionally keep the original phrase in the why. One storage language is what keeps grep-based dedupe (§3) working.
- **Cloud/ephemeral session check (BEFORE any global write):** if `~/.claude/rules/learned-rules.md` does not exist, this is not the user's machine (cloud sandbox) — a global write would evaporate with the sandbox. Save the candidate to the **project lessons file** instead, tagged `[global-candidate]`, and tell the user to promote it locally later. Local sessions: when the project lessons file contains `[global-candidate]` tags, propose promoting them to `learned-rules.md` at session start.
- **global** → append to `~/.claude/rules/learned-rules.md` under `## Learned rules`:
  `- [YYYY-MM-DD] rule — why`
  If §3 matched an existing rule under `## Seed rules`, edit it in place there — never append a near-duplicate under `## Learned rules`.
  Then run `"/Users/jakub/Appky Claude/claude-code-system/sync-global.sh"` (autopilot) — it pushes the updated rules to the canonical bundle repo, and the sync-ai-layer GitHub Action fans the fresh snapshot out to every repo, so cloud sessions learn the rule within minutes. (Not applicable in cloud sandboxes — the cloud check above already routed the save to project lessons.)
- **project** → append to the project's lessons file in the same format; if none exists, create it from `~/.claude/templates/LESSONS.md`. Then verify the project CLAUDE.md contains an `@LESSONS.md` import (adjusted to the actual filename); if the line is missing, add it; if no project CLAUDE.md exists, create a minimal one containing the import and say so. A lessons file without the import line does not load — confirm the import as part of the save confirmation (§6).
- **knowledge** → append to the matching `~/.claude/knowledge/` file (see routing rule, §2).
- **once** → apply now, persist nothing.
- **declined** → record it so no session ever re-asks: `- [YYYY-MM-DD] declined: rule` under a `## Declined` list at the bottom of `learned-rules.md` (global candidates) or the project lessons file (project candidates).

### 6. Confirm in one line
What was saved, verbatim, and where. Never save silently — the user must always know what entered the system.

### 7. Escalation paths
Check these after every save:

| Signal | Escalation |
|---|---|
| Path-based NEVER rule ("never touch <path>") | Add a pattern to `~/.claude/protected-paths.txt` (global) or `<project>/.claude/protected-paths.txt`, then verify the protect-paths hook is installed and active per `~/.claude/hooks/README.md` (run the manual test there) — the pattern file alone enforces nothing |
| Other safety-critical NEVER rule (core §5) that is mechanically checkable at the tool layer (a path, a command, a tool-call pattern) | Text is a request, not a rule — propose a hook to enforce it physically; see `~/.claude/hooks/README.md` |
| Safety-critical NEVER rule that is NOT tool-checkable (a code property, e.g. "failures are LOUD") | Stays text-enforced — add it to verification criteria (`verify-output`, tests) instead of proposing a hook |
| Same lesson saved in 2+ projects | Propose promoting it to global |
| Same multi-step procedure performed ~3 times | Propose creating a new skill for it |
| `learned-rules.md` beyond ~40 rules (seed rules count and may be merged like any other) | Propose a consolidation pass: merge overlaps, delete obsolete, sharpen vague. Propose-only — present the result as a before/after diff, write only after explicit approval, never drop a rule without it |

## Anti-patterns
- Saving silently — every write is announced.
- Saving a rule without its **why** — context-free rules get misapplied or deleted later.
- Adding a duplicate instead of sharpening the existing rule.
- Re-asking about a rule the user declined — in this session or any future one; declines are recorded (§5) precisely so this never happens.
- Interrupting mid-step with a save question — ask at the next natural pause (end of the current step or the end-of-task check, whichever comes first), one save question per pause, multiple candidates batched into one numbered list (§4). Only a rule preventing imminent damage justifies interrupting mid-step.
