---
name: task-loop
description: Executes one project task end-to-end with the full safety net — branch, smallest vertical slice, immediate real-flow testing, stop-and-fix on any red, atomic commit and push, project doc updates, lesson check — then continues to the next task. Use when the user says "next task", "keep going", "pokračuj", "work through the list", or types /task-loop.
---

# task-loop — one task, end-to-end, with the safety net on

Implements core §4 (Execution loop). One iteration = one task taken from open to done, verified, committed, documented. Then the next. Maximum forward motion, zero unverified claims.

## The loop

### 1. Pick the task
Take the next unchecked task from the project's task file and read its definition of done (DoD). No DoD written? Derive one and state it in one line before coding.
**Ambiguity gate:** if the task has two valid interpretations, do not guess — run a 3-question mini `spec-first` interview (goal, must-haves, what "done" looks like), then proceed.

### 2. Branch
`feature/<task-id>`. Never work on the default branch — branch-first is core §5 ALWAYS ("branch before features"). Detail: `rules/git-workflow.md`.

### 3. Implement the smallest vertical slice
End-to-end through every layer the task touches — interface → logic → data — not layer-by-layer. A thin slice that works beats a wide layer that can't be tested. Example: for "user can save a note", wire one input field through one endpoint to one persisted row, ugly but complete — don't build the full data model first.

### 4. Test immediately
- Exercise **real user flows**, not just units — E2E where the project has it.
- Read the actual logs; failures must be LOUD (core §7), so silence is suspicious, not reassuring.
- After any infra/config change: hit the health endpoint or equivalent liveness check.

### 5. Stop-and-fix
Any failure halts the loop. Fix → retest → repeat until green.
- Never proceed on red.
- Never claim green without having run the check — that is a NEVER-tier violation (core §2, §5).
- Stuck after several honest attempts → say so and present options; don't paper over.

### 6. Atomic commit + push
One task, one logical commit, message referencing `<task-id>`. Push immediately — unpushed green work doesn't exist. **Auto-commit is mandatory after EVERY code change, no exceptions** (owner directive): never end a turn with uncommitted work. The `Stop` hook `auto-commit.sh` enforces it as a backstop, but do it yourself with a meaningful message rather than relying on the generic checkpoint commit.

### 7. Update project docs
Walk the after-every-task table in `rules/documentation-protocol.md` — all six roles, **whichever exist in this project** (discovered at session-start; don't invent new ones mid-loop):
- **Handoff file FIRST** (`HANDOFF.md`; legacy `CONTEXT.md`) — rewrite Snapshot, DO-THIS-NOW, state of the world. This one does NOT wait for task completion: refresh it mid-task at every state change too — test went red, a decision was made, you're pausing, anything a successor would need. Rule of thumb: **never end a run with a stale handoff** — if the session died right now, the next AI must be able to continue from HANDOFF alone.
- **Task file** — check off the task.
- **Done-log** — timestamp, what changed, files modified.
- **Documentation map** — new files/relationships, if any.
- **File-structure doc** — new files/dirs, if any.
- **Lessons** — handled in step 8.

### 8. Lesson check
"Was there a lesson here?" — a correction, a surprise, a second occurrence of the same friction. If yes → `learn` skill (core §6). If no, move on; don't manufacture lessons.

### 9. Health question
"Can a user actually perform the main action right now?" Answer from evidence (step 4), not hope. If no, that's the real next task regardless of what the list says.

### 10. Announce and continue
One line: "Done: <task-id>. Next: <task-id> — <summary>." Then loop to step 1.
Stop only when genuinely blocked or at an ASK-FIRST boundary (core §5): stack changes, migrations, production, external sends, spending money, large deletions.

## Anti-patterns
- Building layer-by-layer ("all the models first").
- Batching three tasks into one commit.
- Marking a task done with docs untouched or tests unrun.
- Continuing past a red check "to come back to it later".
- Asking permission at every step — the loop is autopilot between ASK-FIRST boundaries.
