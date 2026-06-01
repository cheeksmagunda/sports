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
# 1. Train a challenger artifact against the latest slate_labels corpus.
uv run oracle-train --corpus data/processed/training_corpus.parquet \
    --commit $(git rev-parse --short HEAD) \
    --metrics-path /tmp/train_metrics.json
# 2. Inspect the SHA-256 sidecar emitted by oracle-train.
ls -la models/picker_*_*.pkl.sha256
# 3. Set WNBA_ORACLE_MODEL_ARTIFACT_SHA on Railway (api + cron-job2 services)
#    to the new SHA. cron-job2 will start writing to model_shadow_runs with
#    that challenger_sha. The incumbent_sha is the prior value of the env var.
# 4. After >= 7 slate_labels rows accumulate for the challenger, evaluate:
uv run oracle-rotate-check --window-days 7
# 5. PROMOTE: leave WNBA_ORACLE_MODEL_ARTIFACT_SHA as the challenger.
#    BLOCK: revert to the prior SHA. Document the decision in DECISIONS.md.
```

The rotation gate uses RBO@5 + NDCG@5 + realized_value_delta with
1000-bootstrap CIs; defaults to BLOCK when fewer than 7 shadow rows are
available (underpowered promotion is worse than no promotion).

## Manual fire

Quick end-to-end smoke (fixtures, no network, no DB writes):

```sh
uv run python scripts/manual_fire.py --fixtures
```

Live fire (requires DATABASE_URL + REDIS_URL + a fresh Real Sports JWT
in `scraper/storage_state.json`):

```sh
uv run python scripts/realsports_login.py     # one-time, captures JWT
uv run python scripts/manual_fire.py          # Job 1 + Job 2 + watchdog
```

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
  audit/         Rotation gate, adversarial validation
  eval/          CRPS, reliability, conformal coverage, RBO@5, picker EV
  db/            SQLAlchemy engine + Redis client
  common/        Settings, structlog setup, db_utils
frontend/        Vite + React app, teal+magenta tokens
migrations/      Alembic
scripts/         Dev startup, credential probe, manual fires
tests/           Pytest
```

## Strategy: where the alpha comes from

**The core edge is the minutes/role model (D54/D55).** Real Sports is a
handicap market: `card_boost` is set so `boost x E[real_score]` is roughly
equal for everyone (within-slate corr(boost, realized value) = +0.016), so
boost level carries no edge and history/recency can't beat it (the boost
already encodes recent form). The one signal orthogonal to the boost is
tonight's MINUTES: `real_score = minutes x per-minute-rate`, the rate is
stable, and minutes is what same-day info (confirmed starters, injury
cascade, blowouts) reveals before the boost catches up. Walk-forward,
minutes x rate predicts real_score at corr 0.554 (if minutes known) vs the
boost's 0.246. `predict/minutes.py` + `ingest/minutes_features.py` ingest
per-game minutes from stats.wnba.com and blend a minutes prediction with the
boost prior; `predict/scoring.py` reconstructs real_score from the box line
(R^2 0.957) so the pipeline is self-contained on nba_api. Kill-switch
`MINUTES_MODEL_ENABLED`.

Three supporting patterns ported from `basketball-main` (the sibling NBA
Real Sports product the operator used to win late-season drafts):

1. **Anti-popularity contrarian tilt.** Draft popularity has a strong
   negative correlation with realized boost; the least-drafted half of
   the pool produces ~24-26% more total value than the most-drafted
   half. `picker/popularity.py` subtracts a popularity-scaled penalty
   from each player's predicted real_score before the optimizer reads
   it. Once `slate_labels.drafts` accumulates measured counts, the
   contrarian path uses real data; until then it falls back to an
   estimator (season ppg + big-market + slate size). Tunable via
   `ContrarianConfig.strength` (default 0.2).
2. **Dynamic team cap (was static `max_per_team=2`).** On 3+ game
   slates the optimizer still caps a lineup at 2 players per team: three
   from one team courts the negative same-team minutes-cannibalization
   correlation, and the corpus shows zero realized-oracle cost to the cap
   there. But on small slates the cap is wrong or impossible: on a 1-game
   slate, 5 players over 2 teams forces a 3-2 split, so a hard cap of 2
   admits no lineup at all (the optimizer shipped a 0.0 forfeit on
   2026-05-19). The effective cap now scales with distinct-team count: 2
   teams -> uncapped, 3-4 teams -> 3, 5+ teams -> 2. 100% of 1-game-slate
   winners and ~25% of 2-game-slate winners stack 3+. Env toggle
   `OPTIMIZER_DYNAMIC_TEAM_CAP` (default on). See DECISIONS D50.
3. **Injury-cascade minutes redistribution.** When a starter is OUT,
   their minutes get redistributed to same-cohort teammates inversely
   weighted by current minutes (bench players inherit more), with
   center-forward cross-sharing and a per-player cap. The largest
   upside in a WNBA slate is the backup who suddenly inherits 30
   starter minutes; the optimizer that knows about it beats the one
   that doesn't. Module: `features/injury_cascade.py`. Wiring into
   `features/build.py` lands once the RotoWire `injury_status` field
   flows through to the slate feature matrix.

See `DECISIONS.md` D27 / D28 / D29 for the full reasoning + reverse paths.

## Sustainability notes

- **Dependency hygiene.** `pyproject.toml` carries only what is imported
  in production code. A `# Deferred dependencies` comment lists each
  capability target that has been documented but not yet shipped (e.g.
  Optuna search, SHAP audit, OpenTelemetry traces). Re-add the dep when
  you implement the feature; log a DECISIONS entry to mirror the change.
- **No `_ = symbol` shims.** If an import is unused, delete it. Don't
  acknowledge it. The repo's audit history shows shims are a hazard:
  they hide real dead code under a layer of "intentional".
- **Postgres URL normalization, team-key mapping, JSON cache** each have
  one home. Adding a second copy is a code smell; route through
  `common.db_utils.normalize_postgres_url`,
  `features.build.team_key_from_full_name`, and `ingest.cache.*`
  respectively.
- **Tests are cheap insurance.** Every new module merits a smoke test
  that loads it and exercises one happy path. Coverage is not the goal;
  catching schema drift and import-time bugs is.
