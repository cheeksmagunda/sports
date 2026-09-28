# nba-oracle

NBA Oracle application scaffold.

Current scope is pre-product: package wiring, a health-only FastAPI process
for Railway mono staging, NBA season/coverage helpers, a public history
loader, and a Corpus G backfill gate that does not call the network.
Domain contests, provider HTTP ingest, models, T-40 freeze, and serve knobs
are not implemented. Structural outline: root `../OVERVIEW.md`.

## Win stack

This app is not on the freeze path.

| Piece | State in code |
|---|---|
| Model / serve knobs | None. `GET /health` only |
| T-40 runner | None |
| Ollama | Portfolio helper only (`../OVERVIEW.md`). Not an NBA model |
| HV board export | `scripts/export_hv_board.py` exits 78 (fail closed) |
| Game-stats append | `scripts/append_game_stats_matchup.py` uses `oracle_core.corpus_matchup` |
| Public history connector | `nba-history-load` / `history_loader.py` (`data.nba.com`). Observation only. Counts: `STATUS.md` |
| Real Sports connector | `nba-corpus-g-backfill` writes a blocked coverage matrix and exits non-zero when the process has no portfolio `REALSPORTS_*` material. It does not mint a session |
helpers, an auth-blocked Corpus G backfill gate, and an observation-only
T-40 freeze gate. Contest entry, provider HTTP ingest, models, and serving

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
  season label. The gate records every season as `blocked` and exits
  non-zero when portfolio `REALSPORTS_*` material is absent from that
  process. That is the gate's fail-closed behavior. It does not mint
  credentials and it does not claim historical rows loaded.

## Public history loader

Observation-only multi-year loader for staging Postgres (no Real Sports auth):

```sh
uv run --package nba-oracle nba-history-load --start-season 2021 --end-season 2024
```

Requires `DATABASE_PUBLIC_URL` (public TCP / `*.proxy.rlwy.net`, `sslmode=require`).

## Freeze gate

`nba_oracle.scheduler` is an observation-only T-40 gate. It is not mounted
on the health API and it does not submit a lineup. `contest_entry` stays
false.

- Pool completeness counts games whose tip is still ahead of the decision
  clock. A tipped game drops out of the denominator. An unobserved player
  on a still-draftable game fails closed.
- `run_freeze_cycle` collects, then reads the clock, then stamps one
  evidence epoch for that tick. Optional future feature rows are skipped.
  A required future row fails closed. Refusal reasons are on the job result.
- The job name is `nba_freeze_cycle`, role `worker` only, lease
  `nba:freeze_cycle`.
- Live pool, runner, and Railway gaps are in `STATUS.md`.
