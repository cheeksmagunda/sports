# Status

<<<<<<< HEAD
Last verified: 2026-09-27 (#482 Docker/Railway staging scaffold; continues #453/#457)
=======
Last verified: 2026-09-27 (#453 Sunday honesty; public NHL history staging load; discovery/calendar #455; frontend #462; baselines #456)
>>>>>>> 84ccf41b3 (docs(nhl-oracle): record staging history load (#453))

## Railway mono-project shell (verified non-serving) (#457)  -  2026-09-27

- Verified scaffold on `sports-oracle` / `nhl-staging`: `nhl-api`,
  `nhl-worker`, `nhl-frontend`, Postgres. **Non-serving** for NHL; no
  public NHL API/frontend domain claimed yet. Design + runbook on #457.
- Sibling mono public URLs already answering (other sports, #457/#453):
  - WNBA API `https://wnba-api-wnba-production.up.railway.app`
  - WNBA frontend `https://wnba-frontend-wnba-production.up.railway.app`
  - NFL API `https://nfl-api-nfl-production.up.railway.app`
- Legacy NFL `nfl-oracle-production.up.railway.app` still HTTP 200 until
  domain/cron cut completes; data-plane must use the public TCP proxy URL,
  not private Railway hostnames.

This file records application state only.

<<<<<<< HEAD
## Railway nhl-staging scaffold (#482)  -  2026-09-27

- Backend image source: `nhl-oracle/Dockerfile` + `nhl-oracle/railway.toml`
  (DOCKERFILE builder). Same image for `nhl-api` (default `nhl-pipeline serve`)
  and `nhl-worker` (`nhl-pipeline worker` start override). Observation-only;
  `contest_entry: false`. No migrate-on-startup; no secrets in the image.
- Minimal HTTP surface: `/health`, stub `/slate/{date}`, stub `/lineup/{date}`.
  Worker is an idle heartbeat only (no Real Sports calls yet).
- Frontend scaffold (#462 / PR #470): `nhl-oracle/frontend` with its own
  Dockerfile + `railway.toml`. Staging host under sports-oracle `nhl-staging`
  is non-contest; verify live deploy IDs after #482 landing.
- **No contest claims. Staging only. No live WNBA/NFL traffic touched.**
=======
## Public NHL history staging load (#453)  -  2026-09-27

- `sports-oracle` / `nhl-staging` Postgres now holds NHL public-history tables
  `nhl_history_games`, `nhl_history_player_games`, and
  `nhl_history_season_coverage`, loaded from the public NHL API with a
  browser-style User-Agent via `nhl-history-load`.
- Verified row counts in staging Postgres:
  - `nhl_history_games`: **5599**
  - `nhl_history_player_games`: **223901**
  - `nhl_history_season_coverage`: **4**
- Verified season coverage in staging:
  - 2021-22: games **1401/1401**, player rows **56020**, status `complete`
  - 2022-23: games **1400/1400**, player rows **55980**, status `complete`
  - 2023-24: games **1400/1400**, player rows **55988**, status `complete`
  - 2024-25: games **1398/1398**, player rows **55913**, status `complete`
- Scope note: this is official/public NHL game history only. It is useful for
  NHL-owned chronology, schedule, and stat features, but it is **not** the
  Real Sports value-label corpus and does not change the `contest_entry: False`
  posture.
>>>>>>> 84ccf41b3 (docs(nhl-oracle): record staging history load (#453))

## Sunday readiness honesty (#453)  -  2026-09-27

- **Week 2 done** (contract/corpus/#325 boost=`none`; discovery/calendar #455).
- **Week 3 started** as an observation-only baseline skeleton (#456 / PR #459):
<<<<<<< HEAD
  `labels/` + `baselines/` with synthetic-label tests. **Not fitted on Real
  corpus. No contest entry.**
- Frontend scaffold landed (#462). Hosted API lifecycle (freeze/publish) still
  absent; #482 only unblocks the staging container shell.
- Optimizer / production NHL serving / contest path: **not started**.
- Contest discovery/calendar ops code: #455 landed on main.
=======
  `labels/` + `baselines/` with synthetic-label tests. Public NHL multi-year
  history is now loaded in staging Postgres, but baselines are **not** yet
  fitted on the Real value corpus. Not serving. No hosted API. No contest
  entry.
- Frontend scaffold landed (#462) under `nhl-oracle/frontend` (Vite shell +
  Dockerfile). **Not hosted / not serving contests.** Hosted API still absent.
- Optimizer / production NHL serving / Railway live contest path: **not started**.
- Contest discovery/calendar ops code: #455 (this change) lands on main.
>>>>>>> 84ccf41b3 (docs(nhl-oracle): record staging history load (#453))
- Do not treat NHL as Sunday live contest-ready.

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
    (`nhl-live-contract-audit`), `ingest.discovery` slate probe + contest-ID
    range scan with identity-mismatch guard, and `NhlCorpusStore` that
    redacts before every write. Live redacted corpus under `data/raw/`
    (gitignored). Auth uses Codespace secret `REALSPORTS_STORAGE_STATE_B64GZ`
    only; no new credential type; no contest entry.
  - `calendar/`: season start-year label helper for corpus paths (#455).
  - `history_loader.py`: public NHL multi-year loader for staging Postgres.
    Current verified `nhl-staging` coverage is 2021-22 through 2024-25,
    complete for played regular-season + playoff games only, with
    `nhl_history_games` / `nhl_history_player_games` / `nhl_history_season_coverage`
    populated from official NHL boxscores.
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
- Frontend scaffold (#462): `nhl-oracle/frontend` Vite+React+TS shell with
  NHL dark-ice branding, `/health` client stub, slate placeholder page,
  Dockerfile + `railway.toml` matching the WNBA frontend deploy shape.
- Staging container shell (#482): root `nhl-oracle/Dockerfile` +
  `railway.toml`; `nhl-pipeline serve` / `nhl-pipeline worker` entrypoints.
  Stub API only; not a freeze/publish lifecycle. Railway `nhl-staging`
  services `nhl-api` / `nhl-worker` / `nhl-frontend` are configured to build
  from these paths after merge (verify deploy IDs live).
- Not started: Real-corpus baseline fit / walk-forward report, contest-law
  optimizer, production NHL serving / contest entry. Any future
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
  cross-sport import. No contest entry. Public NHL multi-year history is now
  staged in Postgres for chronology/stat features; Real value labels still
  need to be joined separately.
  **Next step:** fit priors / walk-forward on seeded Real value labels from
  the Week 2 corpus, joined where useful to the staged public NHL history,
  then publish an
  observation-only eval report, then expand skater/goalie approaches only
  with OOS evidence. Still not started after that: contest-law optimizer,
  hosted API, frontend, deployment (roadmap steps 4–6).
