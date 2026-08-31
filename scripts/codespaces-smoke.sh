#!/bin/sh
set -eu

echo "Checking required developer tools"
command -v uv >/dev/null
command -v make >/dev/null

echo "Checking workspace imports"
uv run --package oracle-core python -c 'import oracle_core; assert oracle_core.Dossier'
uv run --package wnba-oracle python -c 'import wnba_oracle'

if [ "${CODESPACES:-}" = "true" ] || [ "${REMOTE_CONTAINERS:-}" = "true" ]; then
    echo "Checking PostgreSQL and Redis services"
    ready=0
    i=0
    while [ "$i" -lt 30 ]; do
        if pg_isready -h db -U postgres -d sports_dev >/dev/null 2>&1 \
            && redis-cli -h redis ping 2>/dev/null | grep -qx PONG; then
            ready=1
            break
        fi
        i=$((i + 1))
        sleep 2
    done
    [ "$ready" -eq 1 ] || {
        echo "developer services did not become ready" >&2
        exit 1
    }
else
    echo "Skipping container service checks outside Codespaces"
fi

echo "Checking repository contracts"
make check-boundaries
make check-applications
make lint
make typecheck

echo "Codespaces smoke check passed"
