#!/usr/bin/env bash
# auto-commit.sh — Stop hook. After EVERY Claude turn, automatically commit AND push any
# uncommitted changes, so code is ALWAYS saved to GitHub without the owner having to check.
# Owner directive (2026-06-18): "po každej zmene v kóde MUSÍ Claude spraviť commit na GitHub, automaticky."
#
# Behavior: runs in the project dir, commits all changes on the current branch, pushes if a
# remote exists. NEVER blocks the session — exits 0 on every path (push failure is logged, not fatal).
# TWEAK: change COMMIT_PREFIX for the message style; remove the push block to commit locally only.
set +e

COMMIT_PREFIX="chore(auto): checkpoint"

cd "${CLAUDE_PROJECT_DIR:-$PWD}" 2>/dev/null || exit 0

# Only act inside a git work tree.
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0

# Don't touch a repo mid-merge/rebase/cherry-pick — committing then would corrupt the operation.
GITDIR=$(git rev-parse --git-dir 2>/dev/null)
for marker in MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD rebase-merge rebase-apply; do
  [ -e "$GITDIR/$marker" ] && exit 0
done

# Nothing changed → nothing to do.
[ -z "$(git status --porcelain)" ] && exit 0

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
TS=$(date +"%Y-%m-%d %H:%M:%S")

git add -A
git -c user.name="Claude (auto-commit)" -c user.email="claude-auto@local" \
    commit -q -m "$COMMIT_PREFIX $TS [skip ci]" >/dev/null 2>&1

# Push to origin/<current-branch> if a remote is configured. Failure is non-fatal.
if git remote get-url origin >/dev/null 2>&1 && [ -n "$BRANCH" ] && [ "$BRANCH" != "HEAD" ]; then
  git push -q origin "$BRANCH" >/dev/null 2>&1 || echo "auto-commit: committed locally; push to origin/$BRANCH failed (offline or no upstream)" >&2
fi

exit 0
