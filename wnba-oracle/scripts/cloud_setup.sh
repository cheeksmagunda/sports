#!/usr/bin/env bash
# One-shot bootstrap for a fresh cloud clone (Codespaces, cloud agent, etc.)
# Usage: bash scripts/cloud_setup.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Install uv if not present
if ! command -v uv &>/dev/null; then
  echo "==> Installing uv"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.cargo/bin:$PATH"
fi

echo "==> Installing Python deps"
uv sync --extra dev

echo "==> Installing Playwright Chromium"
uv run playwright install chromium --with-deps

echo "==> Loading credentials"
if [[ -f ".claude/credentials.env" ]]; then
  set -a
  eval "$(sed "s|REPO_ROOT|$REPO_ROOT|g" .claude/credentials.env | grep -v '^#' | grep -v '^$')"
  export DATABASE_PUBLIC_URL="${DATABASE_PUBLIC_URL//REPO_ROOT/$REPO_ROOT}"
  set +a
  echo "    OK -- credentials loaded from .claude/credentials.env"
else
  echo "    WARN -- .claude/credentials.env not found; set DATABASE_PUBLIC_URL etc. manually"
fi

echo "==> Setting PGSSLROOTCERT"
export PGSSLROOTCERT="$REPO_ROOT/.pgssl/server.crt"
echo "    PGSSLROOTCERT=$PGSSLROOTCERT"

echo "==> Installing frontend deps"
if command -v npm &>/dev/null; then
  (cd frontend && npm install)
else
  echo "    WARN -- npm not found; skipping frontend install"
fi

echo ""
echo "Setup complete. Quick reference:"
echo "  make dev          # start API on :8000"
echo "  make test         # run test suite"
echo "  make lint         # ruff"
echo "  make typecheck    # mypy"
echo "  cd frontend && npm run dev   # start frontend on :5173"
echo ""
echo "To persist env in this shell: source .claude/credentials.env && export DATABASE_PUBLIC_URL=\"\${DATABASE_PUBLIC_URL//REPO_ROOT/$REPO_ROOT}\" && export PGSSLROOTCERT=$REPO_ROOT/.pgssl/server.crt"
