# Status

Last verified: 2026-09-28 UTC (#601 T-40 win-freeze readiness; continues #535
HV train/backtest wiring, #501 zero-boost gate, #482 nhl-staging image)

## Win stack index (#594)

Pointer only. Not a new live check.

- Code contract (HV label, zero-boost gate, T-40 skeleton, no serve knobs,
  export stub exit 78): `README.md` (Win stack).
- Staging health URLs and the corpus gap: sections below.
- Ollama is not an NHL model and there is still no hosted freeze publish.
  Role: root `../OVERVIEW.md`.

## Highest Total Value train + backtest path (#535 / #453 / #526)  -  2026-09-27

- **Train/backtest target:** Real Sports Highest value / Total Value board
  (`draftStats.sectionName=highestBoostedValuePlayers`). Never winning drafts.
  Executable path: `nhl_oracle.labels.hv` → `ValueLabel` / `oracle_core.high_tv`
  board; walk-forward prefers HV-tagged rows (`baselines.walk_forward`).
- **Contest algebra:** `nhl_oracle.contest` scores ordered five-card picks as
  `value * (slot_multiplier + effective_card_boost)` with slots
  `(2.0, 1.8, 1.6, 1.4, 1.2)`. Effective boost stays 0 under `boost_gate`.
- **T-40 freeze:** `scheduler.t40` + `scheduler.readiness` +
  `run_freeze_cycle(ensure_t40_coherent=...)` open at `lock_at - 40m` under
  per-contest lock. A winning five is ready only when the slate pool matches
  its denominator, effective card boost is 0 while the all-teams gate is
  closed, and the clock is inside the window. `GET /readiness` and
  `nhl-pipeline readiness` report that check. With no injected slate they
  stay `freeze_ready=false` and do not invent a lineup. **Hosted freeze
  publish is still unverified live** (no snapshot collector on the worker).
- **Own-model map:** `features.own_model_map` routes pre-slate history features
  into priors / future ridge-valuelaw (explicitly **no LightGBM primary**).
- **RS contest HV ingest gap (verified in-tree):** Week 2 audit seeds redacted
  contest `/stats` under `data/raw/corpus_nhl` (gitignored); there is **no**
  durable multi-contest HV train corpus yet. `report_hv_corpus_gap` reports
  that honestly. Closing the gap is #526 corpus work, not invented labels.
- Unit proof: `tests/test_hv_train_target.py`. Observation only;
  `contest_entry=False`.

## Hard zero-boost gate through all-teams-played gap (#501 / #453)  -  2026-09-27

- **Operator strategy:** the edge is the gap between early slate games starting
  and every NHL team having ≥1 GP this season. Through that entire gap:
  **ZERO BOOST**. Exploit field mispricing that assumes boosts; never arm
  boost / ownership-fade / leverage logic early.
- **Executable gate:** `nhl_oracle.contract.boost_gate` forces
  `boost_multiplier=0` (and discovery forces `BoostRegime.NONE` over flat /
  positional) until all 32 clubs have ≥1 GP. Fail closed on missing coverage.
  Audit checklist key: `zero_boost_until_all_teams_played`.
- **Unit proof:** `nhl-oracle/tests/test_boost_gate.py` keeps multiplier at 0
  while any team is still at 0 GP; discovery/gates tests cover flat-card
  override during the gap.
- **Current-season team GP coverage (verified 2026-09-26/27 CT via public NHL
  API, browser UA):**
  - `regularSeasonStartDate` = **2026-09-29** (`api-web.nhle.com/v1/schedule/now`)
  - seasonId **20262027** team summary (`gameTypeId=2`): **0** rows
  - Teams with ≥1 completed regular-season GP through 2026-09-26: **0 / 32**
  - Teams still at 0 GP: **32 / 32** (gate active; boost must stay off)
  - Note: `standings/now` still reflects completed **20252026** (32 teams @ 82
    GP) and must not be used as 2026-27 coverage.

## Total Value HV leaderboard corpus (#526)  -  2026-09-27

- Contest `draftStats` used for contract/boost audit only; no durable HV
  board corpus path yet.
- Stub only: `nhl-oracle/scripts/export_hv_board.py` exits 78 (fail-closed).
- Portfolio layout: `oracle_core.hv_board_corpus` + `hv-leaderboard-corpus.yml`.

## T-40 win-freeze readiness (#601)  -  2026-09-28

- **Runners:** GitHub still has `nhl-history-nightly` only (public NHL
  history, no Real Sports). There is no NHL T-40 Actions watchdog. Railway
  `nhl-worker` start command remains `nhl-pipeline worker`. The heartbeat
  now includes `readiness` and stays `freeze_ready=false` until a complete
  slate snapshot is injected inside T-40. It does not call Real Sports.
- **Pool:** `gate_pool_completeness` still accepts a roster-sized fixture
  when no slate denominator is set (Week 2 audit shape). A win freeze sets
  `expected_pool_size` and `games_scheduled` / `games_captured` and fails
  unless the observed pool equals that denominator and every scheduled game
  was captured. A five-player stub is not a complete slate.
- **Zero boost:** unchanged rule (#501). Effective card boost stays 0 until
  all 32 clubs have >=1 GP. Missing coverage fails closed. A flat contract
  label is forced to `none` for the freeze score while the gate is closed.
- **Code:** `nhl_oracle.scheduler.readiness`. Unit proof:
  `tests/test_win_freeze_readiness.py`. `contest_entry` stays false.

## Public 2026-27 coverage (verified 2026-09-28 UTC)

- `GET https://api-web.nhle.com/v1/schedule/now`:
  `regularSeasonStartDate=2026-09-29`.
- Team summary
  `https://api.nhle.com/stats/rest/en/team/summary` with
  `seasonId=20262027` and `gameTypeId=2`: **total 0**.
- `standings/now` is still seasonId **20252026**, 32 teams at 82 GP. That
  is not 2026-27 coverage. The zero-boost gate stays closed.
- Opening cluster on `schedule/2026-09-29` (`gameDate` was absent on the
  payload; identified by `startTimeUTC`): five regular-season games, all
  `gameState=FUT`, season **20262027**, `gameType=2`:
  FLA@CAR 2026-09-29T21:00Z, MTL@TOR 2026-09-29T23:00Z, NYR@BOS
  2026-09-30T00:00Z, VAN@EDM 2026-09-30T02:00Z, CHI@VGK 2026-09-30T02:30Z.
  Ten clubs. Not every franchise.

## Railway nhl-staging (#482 / #601)  -  2026-09-28

- Source: `nhl-oracle/Dockerfile` + `railway.toml`. `dockerfilePath` on
  `nhl-api` / `nhl-worker` is `nhl-oracle/Dockerfile`. `nhl-frontend` uses
  its own `Dockerfile` and `rootDirectory=nhl-oracle/frontend`.
- **Build blocker, verified:** commit `7f390cd` (#497) deleted the #494
  `nhl-oracle` allowlist from root `.dockerignore`. Subsequent main builds
  fail with `/nhl-oracle/src: not found`. Example: `nhl-api` deployment
  `9abecece-0fbe-435b-863d-27f1ad2c29a0` FAILED at build
  (2026-09-28T02:57Z, commit `e636040`). This change restores the allowlist.
  The image is not redeployed until this lands on `main`.
- Last SUCCESS still serving (verified 2026-09-28T03:00Z):
  - `GET https://nhl-api-nhl-staging.up.railway.app/health` returned
    `status=ok`, `observation_only=true`, `contest_entry=false`
    (`checked_at=2026-09-28T03:00:10Z`). Deployment
    `317c244d-c43c-4bf7-a905-e27524ffab60`, commit `4c6a225`
    (2026-09-27T02:44Z). That image does not yet serve `/readiness`.
  - `nhl-worker` SUCCESS `f2431eed-e07f-4f2d-ad2e-cea684f872c2`, commit
    `cf532a9` (2026-09-27T02:54Z). Idle heartbeat; no Real Sports loop.
  - `nhl-frontend` SUCCESS `e5aa846c-67f4-4f2a-9e6f-2fc9792f6592`. Not part
    of this change.
- Rollback if a post-merge `nhl-api` or `nhl-worker` deploy fails: api
  `317c244d-c43c-4bf7-a905-e27524ffab60`, worker
  `f2431eed-e07f-4f2d-ad2e-cea684f872c2`. Do not redeploy `nhl-frontend`
  for this change.
- No migrate-on-startup. No secrets in the image. **No contest entry.
  Staging only.**

## Railway mono-project shell (#457)  -  2026-09-27

- sports-oracle `nhl-staging` hosts `nhl-api`, `nhl-worker`, `nhl-frontend`,
  Postgres, Redis. Live WNBA/NFL traffic remains on prior projects through
  Sunday windows (#453) except as separately authorized.
- NHL app `DATABASE_URL` for staging services lives on **`nhl-staging`**, not
  `nfl-production`. A missing read against the NFL env is the wrong Railway
  environment, not absent auth.
- GitHub Actions repo secret `NHL_HISTORY_DATABASE_URL` is set to the existing
  `sports-oracle` / `nhl-staging` Postgres public TCP URL (Postgres-zZPV;
  host redacted `host_sha256[:8]=b1a88296`). No new credential minted.
  Verified 2026-09-27: `gh secret list` shows the name, and
  `nhl-history-nightly` run
  https://github.com/cheeksmagunda/sports/actions/runs/36297938962
  passed the `not_configured` gate (`conclusion=success`).

## Sunday readiness honesty (#453)  -  2026-09-27

- **Week 2 done** (contract/corpus/#325 boost=`none`; discovery/calendar #455).
- **Week 3 started** as an observation-only baseline skeleton (#456 / PR #459):
  `labels/` + `baselines/` with synthetic-label tests. **Not fitted on Real
  corpus. No contest entry.**
- Frontend scaffold landed (#462). Hosted API lifecycle (freeze/publish) still
  absent; #482 only unblocks the staging container shell.
- Optimizer / production NHL serving / contest path: **not started**.
- Contest discovery/calendar ops code: #455 landed on main.
- Do not treat NHL as Sunday live contest-ready.

## Application state

- Package: `nhl-oracle` workspace member
- Scope live now: Week 2 live, read-only Real Sports contract audit complete
  (#299). Contested fields were resolved from historical NHL contest **1901**
  (no NHL contests on the current home slate at audit time) plus current-slate
  game player cards and contest `/stats` draftStats.
  - `contract/`: `NhlContestContract` defaults now reflect live evidence:
    `five_card_ordered`, lock `per_contest`, boost `none` (hard zero-boost
    gate until every NHL team has ≥1 GP; #325/#501), score label `"value"`,
    roster size 5,
    slot multipliers `(2.0, 1.8, 1.6, 1.4, 1.2)`, `goalie_eligible=True`.
    `contract.boost_gate` + `contract.discovery` force multiplier 0 / regime
    `none` through the early-slate gap; historical contest draftStats
    `multiplierBonus` may be noted but does
    not override live pre-boost `none`. `contract.gates` includes
    `zero_boost_until_all_teams_played` and passed on the
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
- Staging container shell (#482 / #601): `nhl-pipeline serve`, `worker`, and
  `readiness`. Live deploy IDs and the dockerignore build blocker are in
  the Railway section above. No hosted freeze publisher yet.
- Not started: Real-corpus baseline fit / walk-forward report, contest-law
  optimizer, production NHL serving / contest entry. Any future
  picker/backtest must assume zero boosts until every NHL team has played
  (`contract.boost_gate` hard gate). The early-season gap between games
  starting (when boost fields may tempt the field) and every franchise
  completing one game is the edge: keep `boost_regime=none` and exploit
  mispricing while the field may assume boosts.

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
    boosts. #325 corrects #299/#308 `flat`. The early-season gap between
    games starting (when boost fields may tempt the field) and every
    franchise completing one game is the edge: keep `boost_regime=none`
    and exploit mispricing; `contract.boost_gate` enforces this in code.
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
