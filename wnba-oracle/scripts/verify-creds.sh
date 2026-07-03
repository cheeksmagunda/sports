#!/usr/bin/env bash
# Lightweight credential probe for the SessionStart hook. Target: <2s.
# Checks presence in the session env (Claude Code exports the `env` block of
# .claude/settings.local.json), no network. Emits one JSON line.
# Network probes live in scripts/dev.sh.

set -u
set -o pipefail

present () { [ -n "${!1:-}" ] && echo 1 || echo 0; }

cat <<JSON
{"status":"ok","ts":"$(date -u +%FT%TZ)","creds":{"GITHUB_TOKEN":$(present GITHUB_TOKEN),"RAILWAY_WORKSPACE_TOKEN":$(present RAILWAY_WORKSPACE_TOKEN),"ODDS_API_KEY":$(present ODDS_API_KEY),"REAL_SPORTS_USERNAME":$(present REAL_SPORTS_USERNAME),"REAL_SPORTS_PASSWORD":$(present REAL_SPORTS_PASSWORD)}}
JSON
