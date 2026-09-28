# NHL Oracle agent instructions

Read the repository root `AGENTS.md` first. This file adds NHL-only rules and
does not weaken the portfolio contract.

## Purpose and ownership

NHL Oracle is an independent NHL application scaffold. NHL owns its calendar,
identity map, feature schema, model policy, scoring rules, provider adapters,
and operational gates. Do not import domain code from `wnba_oracle`,
`nfl_oracle`, or `nba_oracle`.

Shared work belongs in `oracle-core` only when the interface is provider-neutral
and proven by at least two sports with the same stable contract.

**Models stay in this app.** Do not move NHL model, feature, or scoring code
into `oracle-core` or another sport package. **Frontend is separately owned**
(`frontend/`); backend PRs must not change frontend source, dependencies,
styling, components, tests, or build configuration.

**Train / backtest target:** Real Sports Highest Total Value boards
(`highestBoostedValuePlayers` via `labels.hv` / `TRAINING_LABEL_SECTION`).
Five-player ordered pick + T-40 freeze (`contest/`, `scheduler.t40`). Own-model
path is priors / ridge-valuelaw (`features.own_model_map`); no LightGBM
primary. When durable RS contest HV ingest is missing, use
`report_hv_corpus_gap`. Do not invent labels. Early-season boost stays none
until every franchise has 1 GP (`contract.boost_gate`).

## Exact local commands

From the monorepo root:

```sh
make setup
make check-applications
make check-boundaries
make test-app APP=nhl-oracle
```

From this directory:

```sh
make test
make lint
make typecheck
```

## Production container boundary (staging scaffold)

`Dockerfile` and `railway.toml` are NHL-owned deployment source for
sports-oracle `nhl-staging`. One image, separate roles: `nhl-pipeline serve`
is the read-only API default; `nhl-pipeline worker` is an observation-only
heartbeat that reports T-40 win-freeze readiness and does not collect a live
slate. `nhl-pipeline readiness` prints the same fail-closed report. The public
T-40 runner is `scripts/nhl_t40_watchdog.py` (Actions `nhl-t40-watchdog`).
It reads the public schedule only and does not collect a contest pool.
Credentials never enter the image. No contest entry. API must not migrate
on startup (no schema yet). The root `.dockerignore` must allowlist
`nhl-oracle/src` or the Railway image build cannot see this package.

## Verification bar

- Start with focused tests and run `make test`.
- Keep live-provider behavior out of this scaffold until explicitly added.
- Never commit secrets, browser sessions, or token material.
