#!/usr/bin/env bash
# Railway GraphQL helper that uses the workspace-scoped RAILWAY_TOKEN from
# .env. The use-railway skill's railway-api.sh expects a user OAuth token in
# ~/.railway/config.json; we don't have that. This script is the workspace-
# token equivalent. See CLAUDE.md credentials section.
#
# Usage: scripts/rwgql.sh '<graphql query>' ['<variables-json>']

set -e

if [ -z "${RAILWAY_TOKEN:-}" ]; then
  REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
  if [ -f "$REPO_ROOT/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$REPO_ROOT/.env"
    set +a
  fi
fi

if [ -z "${RAILWAY_TOKEN:-}" ]; then
  echo '{"error":"RAILWAY_TOKEN missing"}' >&2
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
  -H "Authorization: Bearer $RAILWAY_TOKEN" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"
