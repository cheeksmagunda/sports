# nba-oracle

NBA Oracle application scaffold.

Portfolio product goal is owned in this app's **Roadmap** below and current
state in `STATUS.md`.

Current scope is infrastructure only: package wiring, boundary-safe layout, a
health-only FastAPI process for Railway mono staging, and verification targets.
Domain behavior (providers, schemas, models, contests, and operations) is
intentionally not implemented yet.

## Roadmap

Product target when train/backtest exists: each slate's Real Sports **Highest
value / Total Value** board (`highestBoostedValuePlayers`). Objective is a
**5-player** NBA contest pick. Pre-slate features to post-slate HV results;
never winning drafts. **Current gap:** no HV ingest, label corpus, or
train/backtest entrypoint. Models stay in this app; frontend is separately
owned — backend PRs must not edit frontend when one exists. Progress in
`STATUS.md`.

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
```
