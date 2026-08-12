---
name: production-ready
description: Walk the full-stack production readiness checklist and turn gaps into tasks. Use when a product is meant for real users or production, before any launch, or when the user types /production-ready.
---

# production-ready — checklist to tasks, not vibes

Production readiness is a structured walk, not a feeling. The output is a classified gap list written into the project's task file — never a verbal "looks ready".

## 1. Confirm scope — one question

Ask exactly one question before anything else: **"Is this full-stack production-ready, or a prototype?"**

- **Prototype** → write "prototype — production checklist skipped on <date>" into the project's context doc and stop. Do not walk the checklist for throwaway work.
- **Production** → continue. From now on the checklist result gates the launch (step 5).

## 2. Walk the checklist in batches

Source of truth: `~/.claude/rules/production-readiness.md`. Walk it **category by category, in batches of 5–7 categories** so the user is never staring at forty questions at once.

For each category, classify with a one-line reason:

| Verdict | Meaning | Example reason |
|---|---|---|
| **NOW** | MVP-blocking — ship without it and real users get hurt | "no rate limit on auth endpoint — credential stuffing is free" |
| **LATER** | Real, but survivable past launch — goes to backlog | "single region is fine at <N> users" |
| **N/A** | Genuinely doesn't apply | "no user uploads, so no virus scanning" |

Rules of the walk:

- Every category gets a verdict. No category silently skipped.
- N/A requires a reason as much as NOW does — "N/A because lazy" is how gaps hide.
- End each batch with a 3-line recap, then continue. Pause for user input only when a verdict genuinely depends on a business call (budget, legal exposure, risk appetite).

## 3. Gaps become tasks — immediately

- Every **NOW** gap → a concrete task in the project's task file: what to build, where, and how it will be verified (the verifier is part of the task, core §2).
- Every **LATER** item → the backlog section of the same file, one line each.
- A gap that exists only in conversation does not exist. Writing the tasks is part of this skill, not a follow-up.

## 4. Flag the always-forgotten categories

Call these out explicitly even if the user waves them off — these are the ones that hurt:

- **Tested restore** — a backup that was never restored is a hope, not a backup. The task is "restore into a clean environment and verify", not "enable backups".
- **RPO/RTO** — how much data can we lose, how long can we be down? Numbers, agreed with the user.
- **Rollback strategy** — how does a bad deploy get undone, and has that path been exercised once?
- **Rate limiting** — on auth, on anything that sends, on anything that costs money per call.
- **Error tracking** — failures visible to the builder before users report them.
- **Legal docs** — terms, privacy policy, data-processing basics appropriate to the user base.

## 5. Re-run before launch — as a gate

Before any launch, re-run this skill against the same checklist. The launch decision must reference the result: **"all NOW items closed"** or an explicit, written user override naming what ships open and why. Record the outcome in the project's context doc. No checklist result, no launch call.
