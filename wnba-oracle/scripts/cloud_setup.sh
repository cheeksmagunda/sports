#!/usr/bin/env bash
# Portable backend bootstrap for a fresh clone or ordinary cloud shell.

set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
portfolio_root="$(cd "$project_root/.." && pwd -P)"
cd "$portfolio_root"

if ! command -v uv >/dev/null 2>&1; then
  printf 'Installing uv\n'
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$HOME/.cargo/bin:$PATH"
fi

printf 'Installing workspace backend dependencies\n'
uv sync --all-packages --all-extras

printf 'Installing Playwright Chromium when the host supports it\n'
uv run --package wnba-oracle playwright install chromium --with-deps 2>/dev/null \
  || uv run --package wnba-oracle playwright install chromium 2>/dev/null \
  || printf 'Playwright browser install skipped; interactive session recovery needs a browser host\n'

"$portfolio_root/scripts/auth-check" wnba-oracle --offline

printf '\nBackend setup complete.\n'
printf '  make test-wnba\n'
printf '  make lint\n'
printf '  make typecheck\n'
printf '  scripts/with-secrets wnba-oracle -- make dev\n'
