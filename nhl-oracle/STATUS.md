# Status

Last verified: 2026-09-26 CT (finish campaign #455 / parent #453)

This file records application state only.

## Application state

- Package: `nhl-oracle` workspace member
- Ready bar (honest): Week 2 live contract + corpus tooling is operational for
  **read-only** Real Sports work. Not a hosted prediction product.
  - `contract/`: `NhlContestContract` defaults reflect live evidence:
    `five_card_ordered`, lock `per_contest`, boost `none` (pre-boost until
    every NHL team has played; #325), score label `"value"`, roster size 5,
    slot multipliers `(2.0, 1.8, 1.6, 1.4, 1.2)`, `goalie_eligible=True`.
    `contract.discovery` prefers current-slate player-card boost fields;
    historical contest draftStats `multiplierBonus` may be noted but does
    not override live pre-boost `none`. `contract.gates` passed on the
    redacted live fixture (`contest_entry: False`).
  - `ingest/`: NHL-owned `realsports` client (adapted from the NFL pattern;
    no cross-sport import), `redact`, live `audit` CLI
    (`nhl-live-contract-audit`), `ingest.discovery` slate probe + contest-ID
    range scan with identity-mismatch guard, and `NhlCorpusStore` that
    redacts before every write. Live redacted corpus under `data/raw/`
    (gitignored). Auth uses Codespace secret `REALSPORTS_STORAGE_STATE_B64GZ`
    only; no new credential type; no contest entry.
  - `calendar/`: season start-year label helper for corpus paths.
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
- CI: `make test-nhl` runs in `backend-ci.yml`
- Railway: none (intentional; do not invent services without a scoped issue)
- Real Sports auth: shared portfolio session only; attach verified via Codespace
  secret presence (value never printed). Recovery is interactive browser login
  only, on explicit operator action.

## Next blockers (explicit)

- Chronological baselines / walk-forward (`observation_only: True`) not started
- Contest-law optimizer not started
- Hosted API / worker / frontend / Railway not started
- No backtest harness; any future picker must assume zero boosts until every
  NHL team has played
- Historical corpus depth beyond the Week 2 seed is operator-open (rescue
  branch `rescue/444-nhl-week2` holds local corpus JSON archive only; not
  merged as product code)

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

- **Week 1 (contract and corpus skeleton): done.** #136, PR #137.
- **Week 2 (live contract audit, real corpus seed): done for the contract and
  corpus-seed slice (#299, PR #308), with boost-regime correction (#325).**
  Finish slice #455 landed contest-range discovery + calendar season label
  from unfinished rescue work (unique non-data code only; raw corpus blobs
  stay gitignored / on rescue archive).
  Verified facts (historical contest 1901 for format/lock/scoring + current
  slate players for boost/goalie; last live re-audit 2026-09-25 CT under #325):
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
- **Weeks 3+ (roadmap steps 3 to 6): not started** (baselines through
  autonomous delivery).
