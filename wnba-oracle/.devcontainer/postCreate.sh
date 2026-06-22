#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Installing uv"
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"

echo "==> Installing Python deps + Playwright"
uv sync --extra dev
uv run playwright install chromium --with-deps

echo "==> Loading credentials from .claude/credentials.env"
if [[ -f ".claude/credentials.env" ]]; then
  set -a
  # Resolve REPO_ROOT token in DATABASE_PUBLIC_URL before sourcing
  eval "$(sed "s|REPO_ROOT|$REPO_ROOT|g" .claude/credentials.env | grep -v '^#' | grep -v '^$')"
  set +a
  echo "    Credentials loaded."
else
  echo "    WARNING: .claude/credentials.env not found -- set env vars manually."
fi

echo "==> Writing shell profile exports"
PROFILE="$HOME/.bashrc"
{
  echo ""
  echo "# WNBA Oracle -- auto-added by postCreate"
  echo "export PATH=\"\$HOME/.cargo/bin:\$PATH\""
  echo "export PGSSLROOTCERT=\"$REPO_ROOT/.pgssl/server.crt\""
  echo "if [[ -f \"$REPO_ROOT/.claude/credentials.env\" ]]; then"
  echo "  set -a"
  echo "  eval \"\$(sed 's|REPO_ROOT|$REPO_ROOT|g' $REPO_ROOT/.claude/credentials.env | grep -v '^#' | grep -v '^\$')\""
  echo "  export DATABASE_PUBLIC_URL=\"\${DATABASE_PUBLIC_URL//REPO_ROOT/$REPO_ROOT}\""
  echo "  set +a"
  echo "fi"
} >> "$PROFILE"

echo "==> Done. Open a new terminal or run: source ~/.bashrc"
echo "    Then: make dev      # start API"
echo "         cd frontend && npm install && npm run dev   # start frontend"
