# Status

Last verified: 2026-09-27 (health-scaffold + nba-staging pause)

## Training target: Highest Total Value (gap) (#453 / #523 / #526)

Product target for when NBA train/backtest exists: each slate's Real Sports
**Highest value / Total Value** board (`highestBoostedValuePlayers`), a
**5-player** contest pick, pre-slate features to post-slate HV results —
never winning drafts. **Gap (verified):** no HV / draftStats ingest, no
`TRAINING_LABEL_SECTION` / `highest_value` eval, no train or backtest
entrypoint yet. Models stay in this app; frontend is separately owned
(backend PRs must not touch frontend when one exists). See `README.md`
Roadmap / `AGENTS.md`.

## Railway mono-project shell (verified non-serving) (#457)  -  2026-09-27

- Verified stub scaffold on `sports-oracle` / `nba-staging`: `nba-api`,
  `nba-worker`, `nba-frontend`, Postgres. Non-serving stubs; app has no
  Dockerfile yet. Design + runbook on #457.
- Live traffic for other sports remains on old projects through Sunday
  2026-09-27 (#453); NBA has no live Railway serving.

This file records application state only.

## Application state

- Package: `nba-oracle` workspace member
- Scope live now: contract-compliant scaffold + health-only FastAPI (`GET /health`)
- Deploy surface: `nba-oracle/Dockerfile` + `nba-oracle/railway.toml` (DOCKERFILE builder)
- Wired for root checks: test, lint, typecheck, build, boundary, and app contract
- CI: root `make test-nba` runs in `backend-ci.yml` alongside WNBA/NFL/NHL import smoke
- Calendar / TRACKED seasons: not started (NBA.com lists 2026-10-20 regular-season open; not recorded in-app)
- Not started: provider ingest, schemas, modeling, scheduling, contest logic

## Railway mono (`sports-oracle` / `nba-staging`, env `7ac1e6f8-…`)

Verified 2026-09-27 via Codespace `fluffy-zebra-g4gqq746477q2jg` /
`scripts/codespace-railway-env`. Non-serving scaffold only (#457 / #453).

| Service | Source | Last deploy | Notes |
| --- | --- | --- | --- |
| `nba-api` | **disconnected** | FAILED (Railpack, pre-Dockerfile) | Pause: GitHub source disconnected to stop Railpack loops. Reconnect after this Dockerfile lands on `main`, then `--from-source` redeploy. |
| `nba-worker` | **disconnected** | FAILED | No worker role yet; leave disconnected. |
| `nba-frontend` | **disconnected** | FAILED | No frontend package yet; leave disconnected. |
| `Postgres-6eeu` | n/a | SUCCESS / Online | Empty DB; unused by health scaffold. |

No public domain claimed. No contest features. No Real Sports credential on NBA services.

## Boundaries

- NBA domain behavior stays in `nba-oracle`
- Shared technical abstractions may move to `oracle-core` only after proven
  provider-neutral use across multiple sports
- No contest entry code in this package
