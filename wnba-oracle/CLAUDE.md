# WNBA Oracle

Full operating manual (credentials, Railway auth split, Real Sports rules,
routines, autonomy policy) is in AGENTS.md and is imported below. STATUS.md
holds current production state. Read both before touching anything.

@AGENTS.md

## Commands

- `make install` - uv sync + playwright chromium
- `make test` - full pytest suite (`uv run --extra dev python -m pytest -q`;
  bare `uv run pytest` lacks project deps and fails)
- `make lint` / `make typecheck` / `make fmt` - ruff check, mypy, ruff format
- `make dev` - uvicorn on :8000 with reload
- `make migrate` - alembic upgrade head
- `make determinism-check` - train twice, assert model content byte-equal
- Deploys go via GraphQL (`scripts/rwgql.sh`) or the use-railway skill,
  never `railway up` (workspace-token CLI mutations do not work)

## Verification bar

Before calling any code change done: `make test && make lint && make
typecheck`. For anything touching the prediction path, also confirm the
relevant contract tests (`make test-contract`).

## Project skills

- `/reseed-realsports` - recover a dead Real Sports session (operator-run)
- `/redeploy <service>` - redeploy a Railway service via GraphQL
