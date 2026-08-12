# Testing & Verification

Deep reference for core §2 (Verifier layer), §4 (Execution loop), §5 (Guardrails). Load when building or checking anything.

## Test as you build

- After EVERY feature, verify it immediately — before starting the next one.
- Never build 50 features to discover the first one is broken. Each task ends verified; errors never compound across unverified work.
- The smallest vertical slice (core §4) exists precisely so there is always something end-to-end to test.

## User flows over units

- Test what the user does, not what the code is.
- Example: do not test that a button renders; test that clicking "Sign Up" creates a user in the database and redirects to the dashboard.
- E2E flows with whatever tool the project uses (Playwright is typical for web; use the project's existing choice — never introduce a new test framework without asking, core §5).
- Unit tests still have a place for pure logic (calculations, parsers, validators) — but the flow tests are the ones that prove the product works.

## Stop-and-fix

- A failing test halts everything. Fix → retest → loop until green. Only then continue.
- Never proceed past a red test "to come back later". Never claim it works. Never hallucinate green output — report the actual result, verbatim if needed.
- If the fix exceeds the current task's scope, stop and say so — don't silently expand scope (see `rules/coding-standards.md`, Scope discipline).

## The verification layer (Karpathy layer 2)

- Define precise evaluation criteria BEFORE building. "The report must have three sections, each ending with a recommendation" — not "make it good". Criteria a critic can check mechanically, written down in the spec or task notes.
- After building, switch roles: stop being the builder, become the critic. Check the output against the spec item by item, looking for what fails — not for confirmation.
- Pull EXTERNAL signal — never rely on your own impression alone:
  - logs and structured output from an actual run
  - health endpoints and real responses
  - real data through the real flow, not synthetic happy-path data
  - past artifacts as a format reference ("does this match what good looked like last time?")
  - a second model as independent critic on complex or high-stakes builds (core §8)
- Never self-certify. "I read the code and it looks right" is not verification; an observed passing run is.

## Health checks

- After any infra change (config, deploy, env, dependencies): hit the health endpoint and confirm a healthy response before moving on.
- After each feature, answer concretely: **"Can a user actually perform the main action right now?"** If unsure, run the flow and find out — don't assume.

## Never claim verified when not

Claiming something was tested or verified when it wasn't is a NEVER-tier violation (core §5), same class as fabricating data. "Should work", presented as "works", is a lie with a delay. If something wasn't verified, the deliverable says so explicitly.

## Definition of Done

A task is done only when all three hold:

1. All tests pass — including existing tests, not just new ones.
2. The task's Definition of Done from the spec/task file is met, item by item.
3. Project docs are updated (task checked off, context/structure docs current).

Then commit and push per `rules/git-workflow.md`.
