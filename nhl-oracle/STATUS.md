# Status

Last verified: 2026-09-24 (Week 2 live Real Sports contract audit #299)

This file records application state only.

## Application state

- Package: `nhl-oracle` workspace member
- Scope live now: Week 2 live, read-only Real Sports contract audit complete
  (#299). Contested fields were resolved from historical NHL contest **1901**
  (no NHL contests on the current home slate at audit time) plus current-slate
  game player cards and contest `/stats` draftStats.
  - `contract/`: `NhlContestContract` defaults now reflect live evidence:
    `five_card_ordered`, lock `per_contest`, boost `flat`, score label
    `"value"`, roster size 5, slot multipliers `(2.0, 1.8, 1.6, 1.4, 1.2)`,
    `goalie_eligible=True`. `contract.discovery` infers these only from
    explicit payload fields; `contract.gates` passed on the redacted live
    fixture (`contest_entry: False`).
  - `ingest/`: NHL-owned `realsports` client (adapted from the NFL pattern;
    no cross-sport import), `redact`, live `audit` CLI
    (`nhl-live-contract-audit`), and `NhlCorpusStore` provenance. Live
    redacted corpus seeded under `data/raw/` (gitignored) with coverage
    denominators. Auth uses Codespace secret `REALSPORTS_STORAGE_STATE_B64GZ`
    only; no new credential type; no contest entry.
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
- Not started: chronological baselines / walk-forward predictions, contest-law
  optimizer, hosted API, frontend, deployment

## Boundaries

- NHL domain behavior stays in `nhl-oracle`
- Shared technical abstractions may move to `oracle-core` only after proven
  provider-neutral use across multiple sports
- No contest entry code in this package. `contract.gates.NhlAuditReport` and
  `scheduler.freeze.FreezeCycleRecord` both carry an explicit
  `contest_entry: False`. Live audit records also set `contest_entry: False`.

## Roadmap progress

Plan: `README.md` Roadmap section. Moved off the issue tracker 2026-09-24
(#135 and #148 closed; per root `AGENTS.md`, roadmaps live in app docs).

- **Week 1 (contract and corpus skeleton): done.** #136, PR #137. Scaffold
  under Application state (pre-audit).
- **Week 2 (live contract audit, real corpus seed): done for the contract and
  corpus-seed slice (#299).** Live read-only Real Sports contact used the
  existing shared session (`REALSPORTS_STORAGE_STATE_B64GZ`); no new credential
  type; no contest entry; no Railway for NHL.
  Verified facts (historical contest 1901 + current slate players/stats):
  - format: `five_card_ordered` (lineupSize=5, defaultMultipliers length 5)
  - lock_scope: `per_contest` (contest-level `isLocked`)
  - boost_regime: `flat` (nonzero `multiplierBonus` on draftStats cards)
  - score_value_label: `value` (contest draftStats)
  - goalie_eligible: `True` (position `G` on live player cards)
  - slot_multipliers: `(2.0, 1.8, 1.6, 1.4, 1.2)`
  Coverage at audit: games captured/scheduled 11/11; players resolved/seen from
  the scored contest pool (draftStats). Gates passed on the redacted fixture.
  Still not started in Week 2: chronological baselines adapted from NFL
  `baselines/` + walk-forward (`observation_only: True`).
- **Weeks 3+ (roadmap steps 3 to 6): not started.**
