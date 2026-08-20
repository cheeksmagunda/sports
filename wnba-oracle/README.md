# WNBA Oracle

WNBA Oracle is the WNBA five-player daily-draft application. It collects the
available pool and pre-tip signals, builds WNBA-owned features, predicts player
distributions, optimizes a five-player lineup, freezes the result, and serves
read-only slate and lineup data.

Current deployment, model, service, schedule, corpus, incident, and measurement
facts are in `STATUS.md` and must be reverified before production work.

## Local backend setup

From the monorepo root:

```sh
uv sync --all-packages --all-extras
scripts/auth-check wnba-oracle --offline
make test-wnba
make lint
make typecheck
```

Commands requiring local backend credentials run through the in-memory loader:

```sh
scripts/with-secrets wnba-oracle -- make test
scripts/auth-check wnba-oracle --live
```

No plaintext `.env` file is needed. See root `README.md` and `.env.example` for
the portable SOPS and age contract. Frontend login passwords remain in iCloud
Passwords and are never backend environment variables.

## Runtime roles

- `oracle-cron --job job1`: collect pool, availability, odds, lineups, props,
  and WNBA feature inputs; persist enrichment.
- `oracle-cron --job job1late`: refresh late starter information without a
  Real Sports fetch.
- `oracle-cron --job job2`: run prediction and optimization, then append a
  lock-aware freeze.
- `oracle-cron --job dayclose`: ingest finalized contests and game logs, record
  placements, and perform application retention work.
- `GET /lineup/{date}`: return the latest valid freeze for a slate.
- `GET /lineup/{date}/history`: return all freeze sequences for a slate.
- `GET /slate/{date}`: return first-tip, lock, freeze, and pause metadata.

Exact production schedules are mutable and belong in `STATUS.md`.

## Canonical data

PostgreSQL is the durable source. Redis is a cache and coordination service.

| Frame | Grain | Source table | Primary consumer |
| --- | --- | --- | --- |
| Gamelog corpus | player-game | `wnba_game_logs` | Minutes and per-minute model heads |
| Label corpus | player-slate | `slate_labels` | Baseline, blend, and calibration |

These frames use different identifiers and are not interchangeable. WNBA-owned
identity resolution belongs in this application.

## Layout

```text
src/wnba_oracle/api/        WNBA routers and response contracts
src/wnba_oracle/ingest/     WNBA provider implementations and parsers
src/wnba_oracle/features/   Feature builders and rolling windows
src/wnba_oracle/train/      WNBA model training and artifact CLI
src/wnba_oracle/predict/    Prediction and availability logic
src/wnba_oracle/picker/     Field model, payout, and optimizer
src/wnba_oracle/scheduler/  WNBA job orchestration and watchdogs
src/wnba_oracle/db/         WNBA schemas, reads, and persistence adapters
migrations/                 WNBA-owned Alembic migrations
tests/                      Unit, integration, and contract tests
frontend/                   Separately owned Vite React application
```

Read `AGENTS.md` for exact commands, invariants, verification, provider rules,
and production recovery requirements.
