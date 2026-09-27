# nba-oracle

NBA Oracle application scaffold.

Current scope is pre-product: package wiring, boundary-safe layout, a
health-only FastAPI process for Railway mono staging, NBA season/coverage
helpers, and an auth-blocked Corpus G backfill gate. Domain contests,
provider HTTP ingest, models, and serving strategies are not implemented.

## Connection surfaces

Use root `../ENTRY_POINTS.md` for the portfolio-wide Codespace, agent, auth,
and cloud project rules. For NBA work, open or rejoin the repo's GitHub
Codespace, read root `../AGENTS.md`, this app's `AGENTS.md`, this `README.md`,
and `STATUS.md`, then run from the monorepo root:

```sh
make test-app APP=nba-oracle
scripts/auth-check nba-oracle --offline
```

NBA staging lives under Railway project `sports-oracle` environment
`nba-staging` (see `STATUS.md`). The API image is built from
`nba-oracle/Dockerfile` (`railway.toml` builder `DOCKERFILE`) and serves
`GET /health` only. Do not create provider credentials, contest entry paths,
or per-agent PATs unless a scoped issue explicitly authorizes that work. Cloud
projects must include the root snapshot bundle plus `nba-oracle/AGENTS.md`,
`nba-oracle/README.md`, and `nba-oracle/STATUS.md`, then verify against live
`main` before material work.

## Commands

From this directory:

```sh
make test
make lint
make typecheck
```

From the repository root:

```sh
make test-app APP=nba-oracle
make check-applications
make check-boundaries
docker build -f nba-oracle/Dockerfile -t nba-oracle .
uv run --package nba-oracle nba-corpus-g-backfill --dry-run
```

## Calendar and ingest gate

- Season labels are NBA-owned (`season_label_for_date`): October tip opens a
  new start-year label; January-June stay on the prior label.
- `NEXT_REGULAR_SEASON_OPEN` is `2026-10-20` (NBA.com public calendar fact).
- Tracked seasons for Corpus G planning: `2002` through the current Eastern
  season label. Until Real Sports auth is present on an authorized surface,
  every season is recorded as `blocked` in the coverage matrix.
- `nba-corpus-g-backfill` writes that matrix and exits non-zero when
  portfolio `REALSPORTS_*` material is absent. It does not mint credentials
  and does not claim historical rows loaded.

## Public history loader

Observation-only multi-year loader for staging Postgres (no Real Sports auth):

```sh
uv run --package nba-oracle nba-history-load --start-season 2021 --end-season 2024
```

Requires `DATABASE_PUBLIC_URL` (public TCP / `*.proxy.rlwy.net`, `sslmode=require`).
