# Status

Last verified: 2026-09-27T02:55Z (repo + prior Railway disconnect evidence)

## Railway mono-project shell (verified non-serving) (#457 / #453)

- Scaffold on `sports-oracle` / `nba-staging`: `nba-api`, `nba-worker`,
  `nba-frontend`, Postgres. Non-serving. Design + runbook on #457.
- `nba-oracle/Dockerfile` + `railway.toml` are on `main` (merged #486).
- WNBA + NFL Sunday path is on mono production envs (#453/#457); NBA still
  has **no** live contest serving.

This file records application state only.

## Application state

- Package: `nba-oracle` workspace member
- Scope live now: contract-compliant scaffold + health-only FastAPI (`GET /health`)
- Deploy surface: `nba-oracle/Dockerfile` + `nba-oracle/railway.toml` (DOCKERFILE builder)
- Wired for root checks: test, lint, typecheck, build, boundary, and app contract
- CI: root `make test-nba` runs in `backend-ci.yml` alongside WNBA/NFL/NHL import smoke
- Calendar / TRACKED seasons: not started (NBA.com lists 2026-10-20 regular-season open; not recorded in-app)
- Multi-year history ingest scaffolding: open PR #489 (CONFLICTING as of
  2026-09-27T02:54Z). Not merged; no live DB load claimed.
- Not started: provider ingest on Railway, schemas beyond health, modeling,
  scheduling, contest logic

## Railway mono (`sports-oracle` / `nba-staging`, env `7ac1e6f8-…`)

Last Railway disconnect evidence: 2026-09-27 via Codespace
`fluffy-zebra-g4gqq746477q2jg` / `scripts/codespace-railway-env` (pre-#486
Railpack pause). **Reconnect / SUCCESS deploy after #486: unverified** this
pass.

| Service | Source | Last deploy | Notes |
| --- | --- | --- | --- |
| `nba-api` | **disconnected** (last verified) | FAILED (Railpack, pre-Dockerfile) | Reconnect to `cheeksmagunda/sports@main` + `--from-source` still required; post-#486 deploy status unverified. |
| `nba-worker` | **disconnected** | FAILED | No worker role yet; leave disconnected. |
| `nba-frontend` | **disconnected** | FAILED | No frontend package yet; leave disconnected. |
| `Postgres-6eeu` | n/a | SUCCESS / Online (last verified) | Empty DB; unused by health scaffold. |

No public domain claimed. No contest features. No Real Sports credential on NBA services.

## Boundaries

- NBA domain behavior stays in `nba-oracle`
- Shared technical abstractions may move to `oracle-core` only after proven
  provider-neutral use across multiple sports
- No contest entry code in this package
