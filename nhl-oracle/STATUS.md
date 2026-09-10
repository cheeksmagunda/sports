# Status

Last verified: 2026-09-09 (Week 1 of the roadmap approved under #135; issue #136)

This file records application state only.

## Application state

- Package: `nhl-oracle` workspace member
- Scope live now: pre-provider-access scaffold, exercised only against
  synthetic fixtures and `oracle_core.testing` fakes. No live NHL provider
  has been contacted and no credential has been created.
  - `contract/`: candidate contest contract shape (format, lock scope, boost
    regime, slot multipliers, goalie eligibility) with every field defaulting
    to an explicit unknown state, plus an audit checklist (pool completeness,
    clock freshness, identity resolution, boost regime, lock scope) as
    executable gates. Contest format (five-card-ordered vs.
    roster-construction) and lock scope (per-contest vs. per-game) remain
    open questions pending a live audit.
  - `ingest/`: `Provenance` dataclass and `NhlCorpusStore` for redacted raw
    payload persistence with sha256 + sidecar provenance, adapted from
    nfl-oracle's Corpus G pattern. Root path is caller-supplied; no
    project-root auto-detection and no real corpus populated yet.
  - `identity/`: in-memory identity map plus a same-name collision
    reconciler that reports and never auto-merges, and
    `drop_ambiguous_identity_rows` to drop-and-audit ambiguous rows from a
    training set rather than weaken a validator (the NFL 508ee81 lesson,
    built in from the start).
  - `scheduler/`: `run_freeze_cycle` fixes the step order (collect, then read
    the decision clock, then load context, then check model freshness, then
    prepare, then publish) in code, and a `JobSpec` wired to
    `oracle_core.jobs`/`oracle_core.storage.LeaseStore` for single-active-writer.
    No real collector, model, or publisher is wired in; every step is an
    injected callable.
- Wired for root checks: test, lint, typecheck, build, boundary, and app contract
- Not started: live provider ingest, real historical corpus, model,
  contest-law-verified optimizer, hosted API, frontend, deployment

## Boundaries

- NHL domain behavior stays in `nhl-oracle`
- Shared technical abstractions may move to `oracle-core` only after proven
  provider-neutral use across multiple sports
- No contest entry code in this package. `contract.gates.NhlAuditReport` and
  `scheduler.freeze.FreezeCycleRecord` both carry an explicit
  `contest_entry: False`.
