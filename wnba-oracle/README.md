# WNBA Oracle

WNBA Oracle is the WNBA five-player daily-draft application. It collects the
available pool and pre-tip signals, builds WNBA-owned features, predicts player
distributions, optimizes a five-player lineup, freezes the result, and serves
read-only slate and lineup data.

Current deployment, model, service, schedule, corpus, incident, and measurement
facts are in `STATUS.md` and must be reverified before production work.

## Local backend setup

See root `README.md` for workspace setup, authentication, and optional encrypted
file configuration. From the monorepo root:

```sh
uv sync --all-packages --all-extras
scripts/auth-check wnba-oracle --offline
make test-wnba
```

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

Day-close treats discovery, historical backfill, label coverage, placement
capture, and enabled game-log refresh as required work. A required failure makes
the durable job record fail. Optional shadow and cleanup failures remain visible
as degraded substeps without falsely marking required data work complete.

Normal production services deploy from `main` only after GitHub CI succeeds.
Historical enrichment backfill is isolated from source pushes: it has no cron,
source auto-deploy, or restart loop, and the manual workflow accepts only an
exact `main` commit with successful backend CI. The workflow then verifies a new
successful durable backfill record, while partial, empty-input, and write
failures return nonzero.

Scheduled watchdog, pre-freeze, and day-close verification steps retain a safe
report and escalate before failing their workflow. Corpus backup keeps database
credentials in its read-only export job and transfers a hash-verified artifact
to a separate repository-writing job, where the hashes are verified again.
Browser requests to the API and public score feed are no-store and time-bounded,
so a stalled connector reaches the existing retry/error state instead of
holding the interface open indefinitely.

## Model and infrastructure isolation

The model kernel owns policy, feature interpretation, prediction, sampling,
field simulation, payout, and optimization. Static import checks keep it free of
API, database, scheduler, provider, settings, HTTP, Redis, and assurance
dependencies. Infrastructure may call the model through typed inputs, but the
model cannot reach back into runtime state.

Job 2 captures its incumbent enrichment rows without changing their projection
or order, computes the recommendation, and only then creates observational
assurance metadata from copied rows. The durable freeze records the exact
sequence-sensitive enrichment hash, an order-independent canonical enrichment
hash, the finalized optimizer-input hash, model policy, artifact identity, and
serving-feature identity. Assurance failure is value-free and cannot change or
block the model decision.

`src/wnba_oracle/assurance/connectors.py` is the credential-free connector
catalog. Its smaller decision-input subset is fingerprinted separately from
delivery and control-plane connectors, so an API, frontend, GitHub, Railway, or
alerting change cannot masquerade as a model-input change. Source-quality V1
reports persisted aggregate evidence, not provider health; missing evidence is
degraded or unknown and must not be interpreted as proof that an upstream
service was available.

## Contextual lineup balance

The optimizer evaluates unrestricted, game-balanced, and team-balanced
candidates in one deterministic scan over the same simulated outcomes. On a
metadata-complete slate, it prefers the strongest balanced candidate when its
objective is within `OPTIMIZER_CONTEXTUAL_STACK_EV_MARGIN` of the unrestricted
winner. A larger modeled advantage may still justify concentration and is
recorded as `contextual_ev_override`.

The soft targets are slate-aware:

- One game: use the available matchup and prefer both teams.
- Two games: use both games, cap the preferred game count at three, and prefer
  all four teams when feasible.
- Three or more games: cap the preferred game count at two and prefer at least
  four teams.

Real Sports game IDs are the primary matchup identity. Reciprocal team and
opponent metadata is a validated fallback. Incomplete identity disables the
balance preference for that slate and records `metadata_incomplete`; it never
fabricates a matchup. Every freeze stores a versioned `stack_decision` with the
selected composition, balanced alternatives, objective sacrifice, threshold,
and reason. Set `OPTIMIZER_CONTEXTUAL_STACKING_ENABLED=false` to restore the
legacy fixed-bonus objective.

Use `scripts/analyze_stacking_decisions.py` for a read-only production summary.
The report separates exact, censored, and unknown outcomes and does not infer a
performance advantage from unresolved placements. The design and evidence
limits are documented in `../drive/2026-08-25-wnba-contextual-stacking.md`.

## Model research benchmark

`scripts/build_model_research_benchmark.py` replays stored 2026 slates through
the production optimizer under a deterministic variant grid: the validated
production knobs, one registered-knob ablation at a time, and sampling-sigma
temperature variants. It measures realized placement against the stored
leaderboards and payout capture under the top-20 curve, then atomically writes
`benchmark_results.json` and a generated `MODEL_RESEARCH_BENCHMARK.md` into
`--output-dir`. It requires `DATABASE_URL` in the process environment, is
read-only against production data, and its outputs are generated artifacts,
not committed documentation:

```sh
DATABASE_URL=$DATABASE_PUBLIC_URL uv run python \
    scripts/build_model_research_benchmark.py --output-dir /tmp/bench
```

## Canonical data

PostgreSQL is the durable source and the API's only state dependency. Redis is
restricted to Job 2 coordination, so a Redis outage cannot take already frozen
picks off the serving path. API and health database sessions are bounded and
enforced read-only; migrations and scheduled writers use separate job paths.

| Frame | Grain | Source table | Primary consumer |
| --- | --- | --- | --- |
| Gamelog corpus | player-game | `wnba_game_logs` | Minutes and per-minute model heads |
| Label corpus | player-slate | `slate_labels` | Baseline, blend, and calibration |

These frames use different identifiers and are not interchangeable. WNBA-owned
identity resolution belongs in this application.

## Layout

```text
src/wnba_oracle/api/        WNBA routers and response contracts
src/wnba_oracle/assurance/  Value-free connector and source-evidence manifests
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

## Acceptance commands

From the monorepo root, `make test-wnba` covers the default offline suite,
`make test-integration` exercises migrations plus PostgreSQL and Redis, and
`make test-contract` performs live provider checks. `make security` runs the
runtime dependency audit and the medium-severity Bandit gate. CI uses the same
targets before building the Docker image and probing all runtime roles.
