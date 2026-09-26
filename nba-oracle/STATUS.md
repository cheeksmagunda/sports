# Status

Last verified: 2026-09-26 (October 2026-27 readiness audit)

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
