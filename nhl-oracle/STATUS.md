# Status

Last verified: 2026-09-26 CT (Week 3 baseline skeleton #456 under #453)

This file records application state only.

## Application state

- Package: `nhl-oracle` workspace member
- Scope live now: Week 2 live, read-only Real Sports contract audit complete
  (#299). Contested fields were resolved from historical NHL contest **1901**
  (no NHL contests on the current home slate at audit time) plus current-slate
  game player cards and contest `/stats` draftStats.
  - `contract/`: `NhlContestContract` defaults now reflect live evidence:
    `five_card_ordered`, lock `per_contest`, boost `none` (pre-boost until
    every NHL team has played; #325), score label `"value"`, roster size 5,
    slot multipliers `(2.0, 1.8, 1.6, 1.4, 1.2)`, `goalie_eligible=True`.
    `contract.discovery` prefers current-slate player-card boost fields;
    historical contest draftStats `multiplierBonus` may be noted but does
    not override live pre-boost `none`. `contract.gates` passed on the
    redacted live fixture (`contest_entry: False`).
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
  - `labels/` + `baselines/`: Week 3 prediction skeleton (#456). `ValueLabel`
    schema and transparent historical priors (`global_mean`, `position_mean`,
    `position_median`, `player_mean`) with season walk-forward evaluator.
    Reports set `observation_only: True`, `contest_entry: False`, and
    `boost_regime: none`. Goalie `G` is a first-class position bucket. No
    Real-corpus fit yet; tests use synthetic labels only.
- Wired for root checks: test, lint, typecheck, build, boundary, and app contract
- Week 3 started (#456): NHL-owned `labels/` + `baselines/` chronological
  prior skeleton (global/position/player means, season walk-forward,
  `observation_only: True`, `contest_entry: False`, boost regime `none`).
  Synthetic-label unit tests lock the acceptance contract. Not yet fitted on
  seeded Real corpus; no picker/optimizer.
- Not started: Real-corpus baseline fit / walk-forward report, contest-law
  optimizer, hosted API, frontend, deployment / Railway. Any future
  picker/backtest must assume zero boosts until every NHL team has played

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
  corpus-seed slice (#299, PR #308), with boost-regime correction (#325).**
  Live read-only Real Sports contact used the existing shared session
  (`REALSPORTS_STORAGE_STATE_B64GZ`); no new credential type; no contest
  entry; no Railway for NHL.
  Verified facts (historical contest 1901 for format/lock/scoring + current
  slate players for boost/goalie):
  - format: `five_card_ordered` (lineupSize=5, defaultMultipliers length 5)
  - lock_scope: `per_contest` (contest-level `isLocked`)
  - boost_regime: `none` (pre-boost). Live re-audit 2026-09-25 CT: current
    slate day `2026-09-25`, 4 games / **8** teams, **244/244** game player
    cards with **no** `multiplierBonus`/`cardBoost` fields; discovery notes
    pre-boost and ignores historical 1901 draftStats nonzero bonuses.
    Prior #299 corpus day `2026-09-24` was 11 games / 22 teams / 772/772
    cards without boost fields. Operator rule: until every NHL team has had
    a game, there are no card boosts; do not design picker logic around
    boosts. #325 corrects #299/#308 `flat`.
  - score_value_label: `value` (contest draftStats)
  - goalie_eligible: `True` (position `G` on live player cards)
  - slot_multipliers: `(2.0, 1.8, 1.6, 1.4, 1.2)`
  Coverage at #299 audit: games captured/scheduled 11/11; players
  resolved/seen from the scored contest pool (draftStats). Gates passed on
  the redacted fixture. Coverage at #325 live re-audit: games 4/4;
  players_resolved/seen 30/30 (scored contest pool); live cards inspected
  for boosts 244; `gates_ok=true`; `contest_entry=false`.
  Chronological baselines moved to Week 3 (#456); Week 2 contract/corpus
  slice is closed.
- **Week 3 (chronological baseline + prediction skeleton): started (#456).**
  NHL-owned `labels/` + `baselines/` landed with unit tests. No
  cross-sport import. No contest entry. No Railway.
  **Next step:** fit priors / walk-forward on seeded Real value labels from
  the Week 2 corpus (and any expanded historical capture), publish an
  observation-only eval report, then expand skater/goalie approaches only
  with OOS evidence. Still not started after that: contest-law optimizer,
  hosted API, frontend, deployment (roadmap steps 4–6).
