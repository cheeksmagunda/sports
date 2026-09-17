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
#
# A worktree can also be merged AND clean AND actively in use — a peer agent
# session mid-task that hasn't written anything yet. Merged+clean alone can't
# tell those apart, so worktrees additionally get a recency guard: skip
# anything whose git index was touched inside the last RECENT_ACTIVITY_MINUTES
# (any git command — status, add, checkout — refreshes the index's stat
# cache, so this catches "someone is here right now" even with zero diff).
#
# main is never a deletion candidate, worktree or not. is_safe_to_delete
# trivially says yes for it (it's always its own ancestor), and without an
# explicit exclusion a worktree checked out on main would eventually get
# `git worktree remove`'d and then `git branch -D main` — deleting the local
# main ref entirely, breaking every other worktree's fetch/merge-base target
# in this shared .git. The plain-branch loop already excludes main; the
# worktree loop needs the same exclusion.
set -u

DRY_RUN=0
[ "${1:-}" = "--dry-run" ] && DRY_RUN=1

RECENT_ACTIVITY_MINUTES=15

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

is_recently_active() {
  local path="$1"
  local gitdir
  gitdir=$(git -C "$path" rev-parse --git-dir 2>/dev/null) || return 1
  case "$gitdir" in
    /*) : ;;
    *) gitdir="$path/$gitdir" ;;
  esac

  local marker="$gitdir/index"
  [ -f "$marker" ] || marker="$gitdir/HEAD"
  [ -f "$marker" ] || return 1

  [ -n "$(find "$marker" -mmin "-${RECENT_ACTIVITY_MINUTES}" 2>/dev/null)" ]
}

worktree_list=$(git worktree list --porcelain)

echo "=== Checking worktrees ==="
echo "$worktree_list" | awk '
  /^worktree / { path=$2 }
  /^branch /   { ref=$2; print path, ref }
' | while read -r path ref; do
  branch=${ref#refs/heads/}
  [ "$path" = "$(git rev-parse --show-toplevel)" ] && continue
  [ "$branch" = "main" ] && continue

  if ! is_safe_to_delete "$branch"; then
    echo "  keep (not confirmed merged at current tip): $branch ($path)"
    continue
  fi

  if [ -n "$(git -C "$path" status --porcelain)" ]; then
    echo "  SKIP (merged but dirty — needs human review): $branch ($path)"
    continue
  fi

  if is_recently_active "$path"; then
    echo "  SKIP (merged+clean but active in the last ${RECENT_ACTIVITY_MINUTES}m — possible concurrent session): $branch ($path)"
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
  echo "$worktree_list" | grep -q "^branch refs/heads/$branch\$" && continue

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
