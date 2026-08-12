# Git Workflow

Deep reference for core §4 (Execution loop) and §5 (Guardrails). Load when doing any git work.

## Branch-first

- Before ANY new feature: create `feature/<task-id>` and work there.
- Never experiment on main. Never modify main directly. No exceptions for "tiny" changes — tiny changes are exactly how main breaks.
- One branch per task. If a second idea appears mid-task, it gets its own branch later, not a detour on this one.
- Branch names carry the task id so the branch, the commits, and the task file all point at each other.

## Atomic commits

- One logical chunk per commit: a commit should be describable in one sentence without using "and also".
- Message convention: `<type>(<task-id>): <what changed>`.
  - Example: `feat(T1-2): add product card component`
  - Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.
- Never batch unrelated changes into one commit. If the diff contains two stories, split it into two commits.
- Commit messages describe what changed and why it matters — not "updates" or "wip" on anything that gets pushed.

## Auto-commit — mandatory, every change, no exceptions

After EVERY change to code or files, commit AND push to GitHub automatically — every time, in every case, without being asked and without the owner having to check (owner directive 2026-06-18). Never end a turn with uncommitted changes. Text here is the intent; the `Stop` hook `auto-commit.sh` (`~/.claude/hooks/`, vendored into repos as `.claude/hooks/auto-commit.sh`) is the physical enforcement — it stages, commits, and pushes the current branch at the end of every turn. Do not disable or bypass it.

## Push discipline

- Commit AND push after every passing task. No work exists only locally — a laptop dying must never cost finished work.
- Commits are the safety net: commit before risky operations (migrations, large edits, dependency upgrades) so there is always a known-good point to return to.
- Frequent small pushes beat rare big ones. If it's green, it goes up.

## History is sacred

- Never delete or rewrite pushed history — NEVER tier (core §5). No force-push to shared branches, no rebase of anything already pushed, no history-editing commands on shared refs.
- Recovery on shared branches is `git revert` (a new commit that undoes the old one), never `git reset`. The mistake stays visible in history; the fix is a forward step.
- Local-only, never-pushed work may be amended or rebased freely — the line is the push.

## Done means

Tests green → commit → push → check off the task in the project task file. All four, in that order. A task with green tests but no push is not done. A pushed task not checked off in the task file is not done — the next session must be able to trust the task file (core §3).

## PRs

- When the project uses review, open PRs/MRs with the project's platform CLI (gh-class, `rules/tool-routing.md`; Example on GitHub: `gh pr create`): push the branch, then create the PR with a title matching the commit convention and a body stating what changed, why, and how it was verified.
- PR target is the project's default integration branch; merging follows the project's settings — never bypass required checks.
- Solo projects without review flow may merge feature branches directly after green tests, but the branch-first rule still applies.
