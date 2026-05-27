# WNBA Oracle

Real Sports daily-draft WNBA picker. Pre-tip ranker over the slate's
player pool, plus a lineup optimizer that maximizes expected payout
against a simulated field. Goal is contest-payout EV, not raw prediction
accuracy.

Status: see `STATUS.md`. Open human asks: see `NEEDS_HUMAN.md`. Build
decision log: see `DECISIONS.md`.

## Architecture

Two-phase fire:

- **Job 1 (morning):** scrape Real Sports player pool, headless re-auth,
  pull odds + RotoWire lineups, build features, persist enrichment.
- **Job 2 (near tip):** run models, run picker, freeze output to Redis +
  Postgres. Once frozen the lineup never re-rolls intra-day.

Single FastAPI surface exposes the frozen lineup.

Model stack: LightGBM multi-task heads (minutes, per-minute rates,
residual recompose) + EB-shrunk hierarchical baseline at 70/30 ensemble
weight. Mondrian conformal prediction by cohort and condition. Joint
sampling via Gaussian copula on log-residuals feeds the lineup optimizer.

## Local dev

```sh
make install          # uv sync + playwright install chromium
source scripts/dev.sh # verifies credentials, sets env
make test             # unit tests
make lint             # ruff
make typecheck        # mypy strict on src/
make dev              # uvicorn :8000 with reload
make migrate          # alembic upgrade head
```

Determinism gate (run before pushing any change to training code):

```sh
make determinism-check
```

## Shadow run (operator)

After the build completes, the 7-day shadow window is operator-started.

```sh
# Start shadow scoring on the challenger model. Reads from the same
# Job 1 enrichment as production but writes to model_shadow_runs.
oracle-rotate-check --start-window --challenger-sha <sha>
```

Rotation gate auto-evaluates each midnight; promote/demote decision lands
in `eval/rotation_<date>.json`. Operator approves the gate's recommendation
by flipping `WNBA_ORACLE_MODEL_ARTIFACT_SHA` on the Railway api + cron-job2
services.

## Deploy

Railway CLI rejects the workspace token (see DECISIONS D1). Use the
`use-railway` skill or hit GraphQL directly. `make deploy` prints the
hint.

## Layout

```
src/wnba_oracle/
  api/           FastAPI app + read-only frozen-lineup endpoints
  ingest/        Real Sports, stats.wnba.com (nba_api), odds, rotowire, bref
  features/      Allowlist, builders, cohort pooling, rolling windows
  schemas/       Pandera schemas at every module boundary
  train/         LightGBM heads, calibration, EB baseline, CLI, artifacts
  predict/       Inference, conformal, joint sampling
  picker/        Lineup optimizer: sample, field, payout, optimize
  scheduler/     Job 1, Job 2, cron, watchdog
  audit/         Rotation gate, adversarial validation, SHAP audit
  eval/          CRPS, reliability, conformal coverage, RBO@5, picker EV
  db/            SQLAlchemy models + helpers
  monitoring/    OpenTelemetry traces, structlog setup
frontend/        Vite + React app, teal+magenta tokens
migrations/      Alembic
scripts/         Dev startup, credential probe, manual fires
tests/           Pytest + hypothesis
```
