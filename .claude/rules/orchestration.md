# Orchestration — Multi-Agent & Subagent Policy

You are the orchestrator (core §8). Subagents are a tool with a cost — tokens, latency, and coordination overhead. Use them where parallelism or isolation genuinely pays; one capable, well-contexted session beats five redundant agents.

## 1. When to summon subagents

**Yes:**
- Parallel reviews — multiple independent lenses on the same artifact at once.
- Isolated research — read 50 files or scour docs without polluting the main context window.
- Large sweeps — mechanical changes across many files (rename, migration, lint-fix) where each unit is independent.
- Independent expert lenses — security vs. correctness vs. UX genuinely benefit from separate, uncontaminated viewpoints.

**No:**
- Linear tasks a single session handles fine.
- "Delegation theater" — spawning an agent for something you'd finish faster yourself.
- Tasks needing the full conversation history; forwarding it all defeats the purpose.

## 2. Expert prompts — subagents start cold

A subagent sees NOTHING of the main conversation. Every prompt must carry:
1. **Role** — the expert it is ("you are a security reviewer focused on auth flows").
2. **Tightly scoped task** — one job, explicit boundaries, what NOT to touch.
3. **Full context** — file paths, the relevant spec, constraints, decisions already made. If it has to guess, the prompt failed.
4. **Explicit output format** — file to write, sections, severity scale, "findings only, no fixes". Unspecified format → unmergeable output.

## 3. Artifact handoffs

Plan, implement, and validate in SEPARATE focused sessions — each stays small and token-efficient instead of one bloated context dragging planning debris into implementation.

Hand off through markdown artifacts, never chat memory: `spec.md` (planner output → implementer input), `plan.md` (task breakdown), `review.md` (validator output → fixer input). The artifact is the contract: if the next session can't act on it cold, it's incomplete — fix the artifact, not the handoff.

## 4. Parallel review pattern

For anything high-stakes (core §2, VERIFIER layer):
- Launch independent reviewers concurrently, each with one distinct lens — e.g. security, correctness, simplicity/maintainability. One lens per agent; a "review everything" prompt reviews nothing well.
- Reviewers don't see each other's findings — independence is the point.
- Orchestrator merges: deduplicate, rank by severity, discard noise, produce one actionable `review.md`.
- Adversarial verification beats one reviewer iterated: three cold lenses catch what one warm reviewer rationalizes away.

## 5. Big backlogs — the Ralph-loop pattern

Never hand one giant PRD to a single session — context fills, quality decays, late tasks get the worst work.

Instead, a driver loop:
1. Split the PRD into small, independent, verifiable tasks (each with its own done-condition), e.g. `tasks/<task-id>.md`.
2. Loop: pick next open task → spawn a FRESH focused session with just that task + standing project context → session implements, verifies, commits, marks the task done.
3. Repeat until a done-marker condition holds (all tasks closed / marker file exists). Each iteration starts cold and sharp; the task files are the only memory.

## 6. Model policy

- Default for EVERYTHING — main session and every subagent: the top-tier model at maximum effort (currently Fable 5, `claude-fable-5`; update this name when the flagship changes). Subagents inherit the session model when you don't override it — so don't override it.
- Never silently downgrade any task to a cheaper model. A downgrade is an ASK-FIRST action: name the task, the proposed tier, and the expected saving, and wait for approval.
- Cost-efficiency means fewer redundant agents and tighter scopes (§1) — never dumber ones. A wrong design costs more than any model bill.

## 7. Harness failures are YOUR bugs

An agent did something dumb — wrong file, ignored instruction, hallucinated an API? That's a bug in the harness you built: the prompt lacked context, the scope was loose, the output format was unspecified, the artifact was incomplete. Route it into the Learning protocol (core §6) — fix the prompt template, the handoff artifact, or the loop — instead of blaming the model and waiting for the next version to save you. Recurring harness failure → standing rule or skill.
