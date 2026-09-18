#!/usr/bin/env bash
# scripts/devcontainer-poststart.sh
#
# Runs on every codespace start/resume (postStartCommand). Two jobs, both
# read-only or safety-gated, both backgrounded so neither ever delays the
# terminal becoming usable and neither can make postStartCommand "fail":
#   1. check_dev_services.py — fast Postgres/Redis reachability ping.
#   2. prune-merged-branches.sh — auto-removes worktrees/branches whose
#      current tip is provably already merged into origin/main (see that
#      script for the safety rules). Keeps codespace sprawl from
#      re-accumulating without a manual sweep.
#
# Deliberately NOT the full quality gate (ruff+mypy across 5 packages) that
# was removed from container-creation time in #101 for being slow — this is
# the fast, standing alternative. Output goes to logs under /tmp rather than
# a terminal banner; check them by hand if something seems off.
set -u

cd /workspaces/sports || exit 0

# One GitHub identity per codespace (issue #235). Codespaces injects a
# repo-scoped GITHUB_TOKEN into VS Code/web terminals but not into
# `gh codespace ssh` sessions, and gh prefers an env token over the stored
# `gh auth login`. Without this, the two entry points act as different
# identities and the web one 401s once the injected token expires. Only
# interactive shells are touched; postStart/CI scripts keep their env.
for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
  [ -f "$rc" ] || continue
  grep -qF "# sports: one gh identity in this codespace (issue #235)" "$rc" && continue
  printf '\n%s\n[ -n "${PS1:-}" ] && unset GITHUB_TOKEN GH_TOKEN\n' "# sports: one gh identity in this codespace (issue #235)" >> "$rc"
done

(
  timeout 20s uv run --frozen --package wnba-oracle python scripts/check_dev_services.py \
    >/tmp/sports-dev-services-check.log 2>&1
) &
disown

(
  git fetch origin main --quiet 2>/dev/null
  bash scripts/prune-merged-branches.sh \
    >/tmp/sports-prune-merged-branches.log 2>&1
) &
disown

exit 0
