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
