#!/usr/bin/env bash
# Local dev startup: verify credentials from .claude/settings.local.json,
# check connectivity to GitHub/Railway/Odds API. Config values (DATABASE_URL,
# REDIS_URL, model SHA, etc.) live on Railway only and are not needed locally.

set -u
set -o pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Load credentials from Claude Code settings
SETTINGS_FILE=".claude/settings.local.json"
if [ ! -f "$SETTINGS_FILE" ]; then
  echo "[FATAL] $SETTINGS_FILE missing. Claude credentials not configured."
  exit 1
fi

# Extract credentials from settings.local.json using python
read -r GITHUB_TOKEN RW_WORKSPACE_TOKEN ODDS_API_KEY RS_USER RS_PASS < <(
  python3 -c "
import json
settings = json.load(open('$SETTINGS_FILE'))
env = settings.get('env', {})
print(
  env.get('GITHUB_TOKEN', ''),
  env.get('RAILWAY_WORKSPACE_TOKEN', ''),
  env.get('ODDS_API_KEY', ''),
  env.get('REAL_SPORTS_USERNAME', ''),
  env.get('REAL_SPORTS_PASSWORD', '')
)
" 2>/dev/null || echo "     "
)

ok()   { printf "  [OK]   %s\n" "$1"; }
warn() { printf "  [WARN] %s\n" "$1"; }
fail() { printf "  [FAIL] %s\n" "$1"; }

printf "wnba-oracle credential check (%s)\n" "$(date -u +%FT%TZ)"
printf "Architecture: Local credentials from settings.local.json, config on Railway\n\n"

# GitHub
if [ -z "$GITHUB_TOKEN" ]; then
  fail "GITHUB_TOKEN missing from settings.local.json"
else
  gh_out=$(GH_TOKEN="$GITHUB_TOKEN" gh auth status 2>&1 || true)
  if printf '%s\n' "$gh_out" | grep -q "Logged in to github.com .* (GH_TOKEN)"; then
    ok "GITHUB_TOKEN (gh recognizes env token)"
  else
    fail "GITHUB_TOKEN present but gh did not accept it"
  fi
fi

# Railway workspace token (GraphQL scripts: rwgql.sh)
if [ -z "$RW_WORKSPACE_TOKEN" ]; then
  fail "RAILWAY_WORKSPACE_TOKEN missing from settings.local.json"
else
  resp=$(curl -sS -X POST https://backboard.railway.com/graphql/v2 \
    -H "Authorization: Bearer $RW_WORKSPACE_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"query":"query{projects{edges{node{id name}}}}"}' \
    --max-time 10 || true)
  if echo "$resp" | grep -q 'wnba-oracle'; then
    ok "RAILWAY_WORKSPACE_TOKEN (GraphQL ok, wnba-oracle visible)"
  elif echo "$resp" | grep -q '"data"'; then
    warn "RAILWAY_WORKSPACE_TOKEN GraphQL ok but wnba-oracle not in listing"
  else
    fail "RAILWAY_WORKSPACE_TOKEN GraphQL probe failed"
  fi
fi

# Railway CLI / MCP (user OAuth from `railway login`, stored in ~/.railway)
rw_user=$(env -u RAILWAY_TOKEN -u RAILWAY_API_TOKEN railway whoami 2>/dev/null || true)
if [ -n "$rw_user" ]; then
  ok "railway CLI user login ($(echo "$rw_user" | tail -1))"
else
  warn "railway CLI not logged in (MCP tools unavailable; run: railway login)"
fi

# Odds API
if [ -z "$ODDS_API_KEY" ]; then
  fail "ODDS_API_KEY missing from settings.local.json"
else
  http_code=$(curl -sS -o /dev/null -w '%{http_code}' \
    "https://api.the-odds-api.com/v4/sports?apiKey=$ODDS_API_KEY" --max-time 10)
  if [ "$http_code" = "200" ]; then
    ok "ODDS_API_KEY (sports endpoint 200)"
  else
    fail "ODDS_API_KEY probe got HTTP $http_code"
  fi
fi

# Real Sports
if [ -z "$RS_USER" ] || [ -z "$RS_PASS" ]; then
  fail "REAL_SPORTS_USERNAME / REAL_SPORTS_PASSWORD missing from settings.local.json"
else
  warn "REAL_SPORTS_* present (verification deferred to first Playwright run)"
fi

# Tooling
command -v claude >/dev/null 2>&1 && ok "claude CLI present" || warn "claude CLI missing"
command -v uv >/dev/null 2>&1 && ok "uv present" || warn "uv missing"
command -v gh >/dev/null 2>&1 && ok "gh present" || warn "gh missing"

echo ""
echo "Config values (DATABASE_URL, REDIS_URL, WNBA_ORACLE_MODEL_ARTIFACT_SHA, etc.)"
echo "live on Railway and are not needed locally. Run 'make dev' to start."
echo ""
