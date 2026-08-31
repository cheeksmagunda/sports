#!/bin/sh
set -eu

echo "Checking required developer tools"
command -v uv >/dev/null
command -v make >/dev/null

echo "Checking workspace imports"
uv run --frozen --package wnba-oracle python -c 'import oracle_core, wnba_oracle; assert oracle_core.Dossier'

if [ "${SPORTS_DEVCONTAINER:-}" = "true" ]; then
    echo "Checking PostgreSQL and Redis services"
    uv run --frozen --package wnba-oracle python scripts/check_dev_services.py
else
    echo "Skipping service checks outside the project devcontainer"
fi

echo "Checking repository contracts"
make check-boundaries
make check-applications
make lint
make typecheck

echo "Codespaces smoke check passed"
