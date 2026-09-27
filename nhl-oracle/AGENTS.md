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
into `oracle-core` or another sport package. **Frontend is separately owned
per sport** (`frontend/`); backend PRs must not change frontend source,
dependencies, styling, components, tests, or build configuration.

**Train / backtest target (when implemented):** Real Sports Highest Total
Value boards (`highestBoostedValuePlayers`), five-player contest pick,
pre-slate features to post-slate HV results — never winning drafts. Gap:
draftStats used for contract/boost audit only; no HV train/backtest path yet
(`STATUS.md`). Early-season boost regime may be none until every franchise
has 1 GP.

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
is the read-only API default; `nhl-pipeline worker` is an idle
observation-only heartbeat until a real pipeline exists. Credentials never
enter the image. No contest entry. API must not migrate on startup (no
schema yet).

## Verification bar

- Start with focused tests and run `make test`.
- Keep live-provider behavior out of this scaffold until explicitly added.
- Never commit secrets, browser sessions, or token material.
