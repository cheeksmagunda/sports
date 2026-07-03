#!/usr/bin/env bash
# Railway GraphQL helper that uses the workspace-scoped token from
# .claude/settings.local.json (exported as RAILWAY_WORKSPACE_TOKEN). It is
# deliberately NOT named RAILWAY_TOKEN: the Railway CLI and MCP server treat
# that env var as a project token and it shadows the user OAuth login in
# ~/.railway/config.json. Scripts use this helper; interactive CLI/MCP use
# `railway login`. See AGENTS.md credentials section.
#
# Usage: scripts/rwgql.sh '<graphql query>' ['<variables-json>']

set -e

RW_TOKEN="${RAILWAY_WORKSPACE_TOKEN:-${RAILWAY_TOKEN:-}}"

if [ -z "$RW_TOKEN" ]; then
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$REPO_ROOT/.env"
    set +a
    RW_TOKEN="${RAILWAY_WORKSPACE_TOKEN:-${RAILWAY_TOKEN:-}}"
  fi
fi

if [ -z "$RW_TOKEN" ]; then
  echo '{"error":"RAILWAY_WORKSPACE_TOKEN missing"}' >&2
  exit 1
fi

if [ -z "$1" ]; then
  echo '{"error":"no query provided"}' >&2
  exit 1
fi

if [ -n "${2:-}" ]; then
  PAYLOAD=$(jq -n --arg q "$1" --argjson v "$2" '{query: $q, variables: $v}')
else
  PAYLOAD=$(jq -n --arg q "$1" '{query: $q}')
fi

curl -sS https://backboard.railway.com/graphql/v2 \
  -H "Authorization: Bearer $RW_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"
