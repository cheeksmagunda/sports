# nhl-oracle

NHL Oracle application scaffold.

Portfolio product goal: root `../README.md` (Product goal). The hook graph,
including the hosted-freeze gap, is in `CONNECTORS.md`. Current NHL serve
knobs and readiness facts are in `STATUS.md`.

Current scope (verified facts in `STATUS.md`): Week 2 live read-only Real
Sports contract audit, corpus seed, and contest-range discovery are done.
Week 3 chronological baselines (`labels/`, `baselines/`) run on synthetic
labels; HV train/backtest wiring prefers HV-tagged rows when present and
reports a corpus gap when they are not. Contest algebra and a T-40 coherence
check exist in code. There is no Real-corpus fit, no contest-law optimizer,
and no contest entry. `nhl-pipeline worker` on sports-oracle `nhl-staging`
runs the hosted T-40 runner (#675) and `nhl-pipeline serve` reads its
lineups (`nhl-api`, `nhl-worker`, `nhl-frontend`). Frontend scaffold:
`frontend/` (#462). Structural outline: root `../OVERVIEW.md`.

## Win stack

Inline contract. Live staging facts stay in `STATUS.md`. The roadmap below
keeps the contest-law detail; this table is the map.

| Piece | Code |
|---|---|
| HV label | `labels.hv` / `TRAINING_LABEL_SECTION` = `highestBoostedValuePlayers`. `report_hv_corpus_gap` when durable boards are missing |
| Contest score | `nhl_oracle.contest`: ordered five, slots `(2.0, 1.8, 1.6, 1.4, 1.2)`, `value * (slot_multiplier + effective_card_boost)` |
| Boost | `contract.boost_gate`: multiplier 0 until every club has at least 1 GP |
| T-40 runner | `nhl-pipeline worker` (#675): `scheduler.live_cycle` collects the Real day (`/home/nhl/next`), contest, games, and every game's pool; `scheduler.runner` projects and runs `evaluate_win_freeze_readiness`; `service.lineup_store` writes `nhl_t40_lineups` (preview, then frozen once inside `lock_at - 40m`; frozen rows never change). `nhl-api` serves `GET /lineup/{date}` and `GET /readiness` from that table. Lock proxy is the earliest game start on the Real day. `nhl-pipeline cycle` prints one cycle without persisting. Kill switch `NHL_T40_RUNNER=0` |
| Projection v0 | `rankings.primaryValue` (Real's season total value) divided by public prior-season GP, shrunk toward the pool's forward/D/G mean over 10 pseudo-games. Real player ids are NHL ids. No prior GP gets the position mean; `injuryStatus` Out gets 0. `NHL_PRIMARY_VALUE_SEASON_ID` overrides the GP season |
| Own model | `features.own_model_map` routes pre-slate history to priors / ridge-valuelaw. No LightGBM primary |
| Ollama | Portfolio helper on the same boards (`../OVERVIEW.md`). Not an NHL serve model |
| Serve knobs | None. No `OPTIMIZER_*` / profile env contract |
| HV export | `scripts/export_hv_board.py` exits 78 |
| Connectors | Real Sports read-only client (`ingest/realsports.py`, audit and T-40 pool); public NHL API via `history_loader.py` and `nhl-history-nightly.yml`; Railway staging shell in `STATUS.md` |

## Connection surfaces

Use root `../ENTRY_POINTS.md` for the portfolio-wide Codespace, agent, auth,
and cloud project rules. For NHL work, open or rejoin the repo's GitHub
Codespace, read root `../AGENTS.md`, this app's `AGENTS.md`, this `README.md`,
and `STATUS.md`, then run from the monorepo root:

```sh
make test-app APP=nhl-oracle
scripts/auth-check nhl-oracle --offline
```

NHL staging lives under the sports-oracle Railway mono-project environment
`nhl-staging` (see root `ENTRY_POINTS.md` / #457). Do not mint provider
credentials, contest entry paths, or per-agent PATs unless a scoped issue
authorizes that work. Cloud projects must include the root snapshot bundle
plus `nhl-oracle/AGENTS.md`, `nhl-oracle/README.md`, and
`nhl-oracle/STATUS.md`, then verify against live `main` before material work.

### Frontend (scaffold)

```sh
cd frontend
npm ci
npm run dev          # local Vite
npm run test
npm run build        # requires VITE_API_URL=https://... for Docker/serve CSP
```

The UI is NHL-branded (dark ice), with `/`, `/slate/:date`, and `/health`
routes plus stub clients for `/health`, `/slate/{date}`, and `/lineup/{date}`.
Hosted API responses are not required for the static shell to deploy.

## Commands

From this directory:

```sh
make test
make lint
make typecheck
make history-load   # uses NHL_DATABASE_URL / DATABASE_URL
```

From the repository root:

```sh
make test-app APP=nhl-oracle
make check-applications
make check-boundaries
```

Historical load CLI:

```sh
cd nhl-oracle
NHL_DATABASE_URL=postgresql://... \
  uv run --frozen --package nhl-oracle --extra dev \
  nhl-history-load --start-season 2021 --end-season 2024 --game-types 2,3
```

For Railway staging, use the Codespace tunnel flow in `../ENTRY_POINTS.md`
rather than printing or copying connection strings locally.

## Roadmap

Training and backtest product target: each slate's Real Sports **Highest
value / Total Value** board (`highestBoostedValuePlayers`). Objective is a
**5-player** ordered contest pick under slot multipliers
`(2.0, 1.8, 1.6, 1.4, 1.2)`, graded and fit on HV boards. Never use winning
drafts. Pre-slate features map through `features.own_model_map` into the
priors / future ridge-valuelaw path (**no LightGBM primary**). T-40 freeze
policy: `scheduler.t40` (`lock_at - 40m`, per-contest lock). **Corpus gap:**
durable multi-contest HV ingest is not landed yet; `labels.hv.report_hv_corpus_gap`
documents it (#526). Models stay in this app; `frontend/` is separately
owned. Backend PRs must not edit it. Verified milestone progress lives in
`STATUS.md`.

The approved plan from the current scaffold to a verified, autonomous
recommendation product (planned under #135, 2026-09-10; moved here from the
issue tracker 2026-09-24). Milestone progress lives in `STATUS.md`. The plan
itself authorizes no provider collection, service provisioning, credentials,
or deployment; each milestone gets its own scoped issue when it starts.

Working product hypothesis, pending operator confirmation: open the NHL app
and see five ordered Real Sports recommendations for manual entry. Week 2
live audit (#299) plus pre-boost correction (#325) confirmed five-card-ordered
format, per-contest lock, score label "value", goalie eligibility, and slot
multipliers (2.0/1.8/1.6/1.4/1.2). Boost regime is **none** (pre-boost) until
every NHL team has played.

**Hard gate (#501):** `contract.boost_gate` keeps boost multiplier at **0**
through the early-slate gap (games starting before all 32 clubs have ≥1 GP).
That gap is the strategy window: exploit field mispricing; never arm boost /
ownership-fade / leverage early. Fail closed when team-GP coverage is missing.
T-40 win-freeze readiness (`scheduler.readiness`) refuses a five-card freeze
unless that gate holds, the slate pool is larger than five and matches its
denominator, and the clock is inside `lock_at - 40m`. The no-boost picker is
`select_no_boost_five_from_full_pool`. The hosted runner is
`nhl-pipeline worker` (Win stack table). `nhl-oracle/scripts/nhl_t40_watchdog.py`
(`nhl-t40-watchdog` on Actions) is a public-schedule alert only.
Historical contest 1901 draftStats may show flat `multiplierBonus` from a
later window and must not override the gate.

1. **Product and provider contract.** Audit current and historical contest
   identities, exact score/value labels, candidate completeness, goalie
   eligibility, slot multipliers, boosts, and whether lock applies to a
   contest or to individual games. Deliver redacted fixtures and executable
   contracts. Do not assume NFL or WNBA routes or scoring apply.
2. **Historical corpora.** Build NHL-owned historical game/player and contest
   corpora. Reconcile source IDs, retain provenance and capture/event/
   availability clocks, report coverage with denominators, and separate
   pregame evidence from finalized outcomes. Official hockey statistics may
   provide features but do not substitute for authoritative Real value or
   contest outcomes.
3. **Predictions.** Start with named player and position baselines, then test
   skater and goalie approaches where eligible. Candidate inputs: expected
   ice time, even-strength and power-play role, shot volume, opponent, rest,
   scratches, starting-goalie evidence. Chronological evaluation with actual
   pre-decision availability; report uncertainty, cold starts, and input
   gaps. Added complexity needs out-of-sample evidence. Week 3 skeleton
   started (#456): NHL-owned priors + season walk-forward
   (`observation_only`); next is fit on seeded Real value corpus.
4. **Optimization under the verified contest law.** Compare candidate
   selection and committed slot assignment against exhaustive small
   fixtures. Replay frozen decisions against finalized outcomes, with
   explicit uncertainty/censoring for incomplete contest archives. No payout
   probabilities from synthetic fields.
5. **Hosted lifecycle.** Retained validated model before freeze; pregame
   pool/context refresh; prediction and optimization; lock recheck;
   append-only freeze; read-only API and mobile frontend; postgame
   reconciliation. One active writer, durable private runtime inputs,
   bounded retries, recoverable checkpoints, prior artifacts retained for
   rollback.
6. **Verified autonomous delivery** on a natural NHL slate. A healthy service
   is not sufficient: source freshness, active model, committed freeze, API
   payload, and actual five-card mobile rendering must all be verified.

Operational lessons carried over from the NFL 2026-09-09 run:

- Model training/validation must finish before the time-critical freeze job.
- Expose meaningful phases and safe failure codes; no single "waiting" state
  covering collection and model work.
- Define a measured publication-latency target and pre-deadline readiness
  checks. T-40 is a candidate policy, subject to NHL lock behavior and late
  lineup evidence.
- Failures must preserve previous valid freezes; stale or blocked states must
  be explicit.

Open decisions (operator): first product scope, initial target slate/date,
usable historical coverage depth beyond the Week 2 seed, and the publication
target after a measured hosted rehearsal. Contest law and lock semantics were
verified in the Week 2 live audit (#299); boost regime corrected to pre-boost
`none` in #325. See STATUS.md.
