# Status

Last verified: 2026-09-26 (October 2026-27 readiness audit)

## Railway mono-project shell (verified non-serving) (#457)  -  2026-09-27

- Verified stub scaffold on `sports-oracle` / `nba-staging`: `nba-api`,
  `nba-worker`, `nba-frontend`, Postgres. Non-serving stubs; app has no
  Dockerfile yet. Design + runbook on #457.
- Live traffic for other sports remains on old projects through Sunday
  2026-09-27 (#453); NBA has no live Railway serving.

This file records application state only.

## Application state

- Package: `nba-oracle` workspace member
- Scope live now: contract-compliant scaffold only
- Wired for root checks: test, lint, typecheck, build, boundary, and app contract
- CI: root `make test-nba` runs in `backend-ci.yml` alongside WNBA/NFL/NHL import smoke
- Calendar / TRACKED seasons: not started (NBA.com lists 2026-10-20 regular-season open; not recorded in-app)
- Not started: provider ingest, schemas, modeling, scheduling, contest logic

## Boundaries

- NBA domain behavior stays in `nba-oracle`
- Shared technical abstractions may move to `oracle-core` only after proven
  provider-neutral use across multiple sports
- No contest entry code in this package
