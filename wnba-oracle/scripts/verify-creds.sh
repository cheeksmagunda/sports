#!/usr/bin/env bash
# Lightweight credential probe for the SessionStart hook. Target: <2s.
# Sources .env, checks presence only (no network). Emits one JSON line.
# Network probes live in scripts/dev.sh.

set -u
set -o pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

[ -f .env ] || { echo '{"status":"no_env"}'; exit 0; }

set -a
# shellcheck disable=SC1091
source ./.env >/dev/null 2>&1
set +a

present () { [ -n "${!1:-}" ] && echo 1 || echo 0; }

cat <<JSON
{"status":"ok","ts":"$(date -u +%FT%TZ)","creds":{"GITHUB_TOKEN":$(present GITHUB_TOKEN),"RAILWAY_TOKEN":$(present RAILWAY_TOKEN),"ODDS_API_KEY":$(present ODDS_API_KEY),"REAL_SPORTS_USERNAME":$(present REAL_SPORTS_USERNAME),"REAL_SPORTS_PASSWORD":$(present REAL_SPORTS_PASSWORD),"DATABASE_URL":$(present DATABASE_URL),"REDIS_URL":$(present REDIS_URL)}}
JSON
