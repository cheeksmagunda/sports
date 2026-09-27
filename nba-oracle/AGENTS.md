# NBA Oracle agent instructions

Read the repository root `AGENTS.md` first. This file adds NBA-only rules and
does not weaken the portfolio contract.

## Purpose and ownership

NBA Oracle is an independent NBA application scaffold. NBA owns its calendar,
identity map, feature schema, model policy, scoring rules, provider adapters,
and operational gates. Do not import domain code from `wnba_oracle`,
`nfl_oracle`, or `nhl_oracle`.

Shared work belongs in `oracle-core` only when the interface is provider-neutral
and proven by at least two sports with the same stable contract.

**Models stay in this app** when modeling lands. **Frontend is separately
owned per sport**; backend PRs must not change frontend source, dependencies,
styling, components, tests, or build configuration when a frontend exists.

**Train / backtest target (when implemented):** Real Sports Highest Total
Value boards (`highestBoostedValuePlayers`), five-player contest pick,
pre-slate features to post-slate HV results — never winning drafts. Gap:
no HV ingest or train/backtest path yet (`STATUS.md`).

## Exact local commands

From the monorepo root:

```sh
make setup
make check-applications
make check-boundaries
make test-app APP=nba-oracle
```

From this directory:

```sh
make test
make lint
make typecheck
```

## Production container boundary

`Dockerfile` and `railway.toml` are NBA-owned deployment source for the
health-only API scaffold on `sports-oracle` / `nba-staging`. The image serves
`GET /health` via `uvicorn nba_oracle.api.app:app`. Do not add contest, provider,
or domain routes to that app until a scoped milestone authorizes them. Worker
and frontend Railway services stay source-disconnected until those packages
exist. Prefer `DOCKERFILE` builds; never recover a RAILPACK-failed deployment
with image-reuse redeploy (issue #279).

## Verification bar

- Start with focused tests and run `make test`.
- Keep live-provider behavior out of this scaffold until explicitly added.
- Never commit secrets, browser sessions, or token material.
