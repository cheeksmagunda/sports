#!/usr/bin/env bash
# Full dev startup script. Sources .env, verifies every credential, prints
# status, updates STATUS.md timestamp. Designed for interactive runs.
# The lightweight subset for the SessionStart hook lives in verify-creds.sh.

set -u
set -o pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [ ! -f .env ]; then
  echo "[FATAL] .env missing at repo root."
  exit 1
fi

set -a
# shellcheck disable=SC1091
source ./.env
set +a

ok()   { printf "  [OK]   %s\n" "$1"; }
warn() { printf "  [WARN] %s\n" "$1"; }
fail() { printf "  [FAIL] %s\n" "$1"; }

printf "wnba-oracle credential check (%s)\n" "$(date -u +%FT%TZ)"

# GitHub
if [ -z "${GITHUB_TOKEN:-}" ]; then
  fail "GITHUB_TOKEN missing"
else
  # gh auth status exits non-zero if ANY known account is stale, even when our
  # env token works. Capture the output first (pipefail otherwise kills the
  # pipeline before grep runs) and look for "Logged in ... (GH_TOKEN)".
  gh_out=$(GH_TOKEN="$GITHUB_TOKEN" gh auth status 2>&1 || true)
  if printf '%s\n' "$gh_out" | grep -q "Logged in to github.com .* (GH_TOKEN)"; then
    ok "GITHUB_TOKEN (gh recognizes env token)"
  else
    fail "GITHUB_TOKEN present but gh did not accept it"
  fi
fi

# Railway. CLI rejects workspace tokens; smoke via GraphQL projects query
# (NOT `me`, which fails on workspace tokens). See DECISIONS.md.
if [ -z "${RAILWAY_TOKEN:-}" ]; then
  fail "RAILWAY_TOKEN missing"
else
  resp=$(curl -sS -X POST https://backboard.railway.com/graphql/v2 \
    -H "Authorization: Bearer $RAILWAY_TOKEN" \
    -H "Content-Type: application/json" \
    -d '{"query":"query{projects{edges{node{id name}}}}"}' \
    --max-time 10 || true)
  if echo "$resp" | grep -q 'wnba-oracle'; then
    ok "RAILWAY_TOKEN (workspace token reaches GraphQL, wnba-oracle visible)"
  elif echo "$resp" | grep -q '"data"'; then
    warn "RAILWAY_TOKEN GraphQL ok but wnba-oracle project not in listing"
  else
    fail "RAILWAY_TOKEN GraphQL probe failed"
  fi
fi

# The Odds API. Free /v4/sports endpoint; no quota burn.
if [ -z "${ODDS_API_KEY:-}" ]; then
  fail "ODDS_API_KEY missing"
else
  http_code=$(curl -sS -o /dev/null -w '%{http_code}' \
    "https://api.the-odds-api.com/v4/sports?apiKey=$ODDS_API_KEY" --max-time 10)
  if [ "$http_code" = "200" ]; then
    ok "ODDS_API_KEY (sports endpoint 200)"
  else
    fail "ODDS_API_KEY probe got HTTP $http_code"
  fi
fi

# Real Sports. No lightweight check exists. Deferred to Playwright run.
if [ -z "${REAL_SPORTS_USERNAME:-}" ] || [ -z "${REAL_SPORTS_PASSWORD:-}" ]; then
  fail "REAL_SPORTS_USERNAME / REAL_SPORTS_PASSWORD missing"
else
  warn "REAL_SPORTS_* present (verification deferred to first Playwright run)"
fi

# Claude Code OAuth token. Empty is acceptable; warn only.
if [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
  warn "CLAUDE_CODE_OAUTH_TOKEN empty (human runs interactively; not fatal)"
else
  ok "CLAUDE_CODE_OAUTH_TOKEN present"
fi

# Database / Redis. Empty until Railway provisioning completes.
if [ -z "${DATABASE_URL:-}" ]; then
  warn "DATABASE_URL empty (populate after Railway Postgres provisioning)"
else
  ok "DATABASE_URL set"
fi
if [ -z "${REDIS_URL:-}" ]; then
  warn "REDIS_URL empty (populate after Railway Redis provisioning)"
else
  ok "REDIS_URL set"
fi

# Tooling presence
command -v claude >/dev/null 2>&1 && ok "claude CLI present" || warn "claude CLI missing"
command -v uv >/dev/null 2>&1 && ok "uv present" || warn "uv missing"
command -v gh >/dev/null 2>&1 && ok "gh present" || warn "gh missing"

# Credential rotation reminder. Tracks ages in .credential-ages.json.
AGES_FILE=".credential-ages.json"
if [ -f "$AGES_FILE" ]; then
  python3 - <<'PY'
import json, datetime, pathlib, sys
p = pathlib.Path(".credential-ages.json")
try:
    data = json.loads(p.read_text())
except Exception:
    sys.exit(0)
today = datetime.date.today()
for name, iso in data.items():
    try:
        d = datetime.date.fromisoformat(iso)
    except Exception:
        continue
    age = (today - d).days
    if age > 90:
        print(f"  [WARN] credential {name} is {age} days old; consider rotation")
PY
fi

# Update STATUS.md last-verified timestamp if file exists.
if [ -f STATUS.md ]; then
  ts="$(date -u +%FT%TZ)"
  if grep -q '^last_verified:' STATUS.md; then
    if [ "$(uname)" = "Darwin" ]; then
      sed -i '' -E "s/^last_verified:.*/last_verified: ${ts}/" STATUS.md
    else
      sed -i -E "s/^last_verified:.*/last_verified: ${ts}/" STATUS.md
    fi
  fi
fi

echo "Done."
