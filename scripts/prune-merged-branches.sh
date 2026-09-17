#!/usr/bin/env bash
# scripts/prune-merged-branches.sh
#
# Removes local worktrees/branches only when the branch's CURRENT tip is
# provably fully captured in origin/main, so codespace sprawl (stale
# worktrees, gone branches) never re-accumulates. Merged-but-dirty worktrees
# are skipped and logged, never force-cleaned — that preserves real
# uncommitted/staged work (see issue #220 background: chat/167-frontend-audit
# had 188 staged lines that would have been lost by a naive prune).
#
# Safety check has two independent paths, both false-negative-safe (they
# only ever say "yes, safe" when it's actually true — worst case they say
# "not sure, skip it"):
#   1. `git merge-base --is-ancestor branch origin/main` — true for regular
#      merge-commit PRs, since the original commits stay in main's history.
#   2. Exact tip-SHA match against a merged PR's recorded `headRefOid` —
#      needed for squash-merged PRs, where the original commit is never an
#      ancestor of main even though its content landed there.
# A branch whose merged PR exists but whose CURRENT tip differs from that
# PR's headRefOid (e.g. commits added locally after the PR merged, never
# pushed) matches neither path and is correctly left alone — this is exactly
# the failure mode a naive "any merged PR for this name" check misses.
set -u

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

cd "$(git rev-parse --show-toplevel)" || exit 1
current_branch=$(git branch --show-current)

is_safe_to_delete() {
  local branch="$1"
  git merge-base --is-ancestor "$branch" origin/main 2>/dev/null && return 0

  local tip merged_sha
  tip=$(git rev-parse "$branch" 2>/dev/null) || return 1
  merged_sha=$(gh pr list --head "$branch" --state merged --json headRefOid --jq '.[0].headRefOid // empty' 2>/dev/null)
  [ -n "$merged_sha" ] && [ "$tip" = "$merged_sha" ]
}

echo "=== Checking worktrees ==="
git worktree list --porcelain | awk '
  /^worktree / { path=$2 }
  /^branch /   { ref=$2; print path, ref }
' | while read -r path ref; do
  branch=${ref#refs/heads/}
  [ "$path" = "$(git rev-parse --show-toplevel)" ] && continue

  if ! is_safe_to_delete "$branch"; then
    echo "  keep (not confirmed merged at current tip): $branch ($path)"
    continue
  fi

  if [ -n "$(git -C "$path" status --porcelain)" ]; then
    echo "  SKIP (merged but dirty — needs human review): $branch ($path)"
    continue
  fi

  if [ "$DRY_RUN" = 1 ]; then
    echo "  would remove: $branch ($path)"
  else
    echo "  removing merged+clean worktree: $branch ($path)"
    git worktree remove "$path"
    git branch -D "$branch"
  fi
done

[ "$DRY_RUN" = 0 ] && git worktree prune

echo "=== Checking plain branches (no worktree) ==="
git for-each-ref --format='%(refname:short)' refs/heads/ | while read -r branch; do
  [ "$branch" = "$current_branch" ] && continue
  [ "$branch" = "main" ] && continue
  git worktree list --porcelain | grep -q "^branch refs/heads/$branch\$" && continue

  if is_safe_to_delete "$branch"; then
    if [ "$DRY_RUN" = 1 ]; then
      echo "  would delete merged branch: $branch"
    else
      echo "  deleting merged branch: $branch"
      git branch -D "$branch"
    fi
  fi
done

echo "=== Done ==="
