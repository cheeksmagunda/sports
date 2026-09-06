# Status

Last verified: 2026-09-06 (initial scaffold)

This file records application state only.

## Application state

- Package: `nba-oracle` workspace member
- Scope live now: contract-compliant scaffold only
- Wired for root checks: test, lint, typecheck, build, boundary, and app contract
- Not started: provider ingest, schemas, modeling, scheduling, contest logic

## Boundaries

- NBA domain behavior stays in `nba-oracle`
- Shared technical abstractions may move to `oracle-core` only after proven
  provider-neutral use across multiple sports
- No contest entry code in this package
