# WNBA Oracle

Real Sports WNBA daily-draft picker. It scrapes the slate pool, builds
pre-tip features, predicts player distributions, optimizes a five-player
lineup, and freezes the result to Redis plus Postgres.

The source of truth is code plus Postgres. Historical handoff logs and
research dumps were removed because they had become stale and hard to audit.

## Current State

- Production model: `models/picker_e2ced9ec_1780873338.pkl`
- Active model SHA: `94f8e8606dab4d48652929bb3884fb9152e1abc766eeb2c2d86559f4318676cd`
- Training command: `uv run oracle-train --corpus-mode both`
- Serving path: Job 1 enrichment, Job 2 tip-relative freeze, FastAPI read surface
- Canonical data: Postgres tables read through `src/wnba_oracle/db/reads.py`

## Local Commands

```sh
make install
make test
make lint
make typecheck
make dev
make migrate
```

`scripts/dev.sh` checks local credentials. Railway config, database URL,
Redis URL, and the served model SHA live in Railway.

## Operations

AGENTS.md is the operating manual: credential layers (local Claude Code,
Railway production, cloud routines), Railway service IDs and schedules, the
Real Sports session recovery procedure, and the two scheduled monitoring
routines (pre-freeze guard at 13:30 UTC, dayclose verify at 07:00 UTC).
Production state and troubleshooting live in STATUS.md. Escalations and the
results ledger live in GitHub issues labeled `ops-guard` and `ops-results`.

## Runtime Shape

- `oracle-cron --job job1`: scrape pool, odds, lineups, props, and features.
- `oracle-cron --job job1late`: credit-free starter refresh before freeze.
- `oracle-cron --job job2`: run prediction, optimization, and freeze.
- `oracle-cron --job dayclose`: ingest finalized contests, refresh game logs,
  record placements, and run retention cleanup.
- `GET /lineup/{date}`: latest frozen lineup.
- `GET /lineup/{date}/history`: all freezes for a slate.
- `GET /slate/{date}`: first-tip and freeze timing metadata.

## Data

There are two distinct training frames.

| Frame | Grain | Source | Consumer |
| --- | --- | --- | --- |
| Gamelog corpus | player-game | `wnba_game_logs` | LightGBM minutes and rate heads |
| Label corpus | player-slate | `slate_labels` | EB baseline, blend, calibration |

Local parquet snapshots are not required. Refresh or inspect data through the
Postgres helpers in `src/wnba_oracle/db/reads.py`.

## Layout

```text
src/wnba_oracle/api/        FastAPI app and read endpoints
src/wnba_oracle/ingest/     Real Sports, WNBA stats, odds, RotoWire
src/wnba_oracle/features/   Feature builders and rolling windows
src/wnba_oracle/train/      LightGBM heads, EB baseline, artifact CLI
src/wnba_oracle/predict/    Prediction and availability logic
src/wnba_oracle/picker/     Field model, payout, optimizer
src/wnba_oracle/scheduler/  Cron jobs, freezes, placements, watchdog
src/wnba_oracle/db/         SQLAlchemy reads and engine helpers
frontend/                   Vite React UI
migrations/                 Alembic migrations
tests/                      Unit and contract tests
```

## Cleanup Policy

Keep documentation short and current. Prefer tests, schema, code comments,
and Postgres facts over narrative logs. Do not reintroduce long handoff files,
research dumps, local parquet snapshots, or markdown ledgers.
