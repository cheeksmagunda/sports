# Status

Last verified: 2026-09-24 (roadmap progress section added; application state unchanged since 2026-09-09)

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

## Roadmap progress

Plan: `README.md` Roadmap section. Moved off the issue tracker 2026-09-24
(#135 and #148 closed; per root `AGENTS.md`, roadmaps live in app docs).

- **Week 1 (contract and corpus skeleton): done.** #136, PR #137. This is the
  scaffold described under Application state.
- **Week 2 (live contract audit, real corpus, baseline predictions): not
  started on `main`.** Operator authorized live, read-only Real Sports
  contact for NHL on 2026-09-12 using the existing shared session: no new
  credential type, no contest entry. Real Sports hosts NFL, WNBA, and NHL on
  one platform with contest IDs from one global sequence, so this is the
  existing session pointed at NHL's sport path. Scope when it starts:
  1. Read-only `nhl_oracle.ingest.realsports` client (new code adapted from
     the NFL pattern, no cross-sport import); resolve contest format
     (five-card-ordered vs. roster-construction), lock scope (per-contest vs.
     per-game), slot multipliers, boost regime, and goalie eligibility from
     live evidence; persist redacted fixtures via `NhlCorpusStore`; run
     `contract.gates` against the real fixtures and update
     `NhlContestContract` defaults to the resolved facts.
  2. Populate the raw NHL corpus with coverage denominators (games captured
     / scheduled, players resolved / seen).
  3. Chronological baselines adapted from NFL's `baselines/` + walk-forward
     pattern, `observation_only: True`.
  Exit check: contract facts recorded (or explicitly open with a reason),
  gates pass on at least one real redacted fixture, coverage report,
  nhl/nfl/wnba test suites plus lint, typecheck, and boundaries green.
  Must run from the Codespace (the only Mac-reachable home of the Real Sports
  session). Unlanded prior attempt: local worktree
  `.claude/worktrees/nhl-week2` (branch `chat/nhl-week2-live-audit`, tip
  7b3aad3, uncommitted discovery/redact/realsports ingest modules and a test);
  check it before starting over.
- **Weeks 3+ (roadmap steps 3 to 6): not started.**
