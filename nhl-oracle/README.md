# nhl-oracle

NHL Oracle application scaffold.

Portfolio product goal: root `../README.md` (Product goal). Current NHL serve
knobs and readiness facts are in `STATUS.md`.

Current scope (see `STATUS.md` for verified facts): Week 2 live read-only
Real Sports contract audit, corpus seed, and contest-range discovery are done; Week 3 chronological
baseline + prediction skeleton (`labels/`, `baselines/`) is started on
synthetic labels only. Package wiring includes contest contract and audit
gates (`contract/`), redacted ingest/provenance (`ingest/`), identity map
(`identity/`), and freeze-cycle job skeleton (`scheduler/`). No Real-corpus
baseline fit, contest-law optimizer, hosted API, or contest entry exists
yet. A lean Vite+React frontend scaffold lives at `frontend/` (#462).
Staging container shell (#482): root `Dockerfile` + `railway.toml` and
`nhl-pipeline serve` / `nhl-pipeline worker` (health + stub routes; idle
worker heartbeat). sports-oracle `nhl-staging` hosts `nhl-api` /
`nhl-worker` / `nhl-frontend` as non-contest staging only.

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
every NHL team has played; current-slate player cards lack card boost fields.
Do not design picker logic around boosts before that milestone. Historical
contest 1901 draftStats may show flat `multiplierBonus` from a later window.

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
4. **Optimization under the verified contest law.** Select five players that
   maximize Highest value / Total Value Daily Leaderboard capture (root
   `../README.md` Product goal), not cash/median finish. Compare candidate
   selection and committed slot assignment against exhaustive small
   fixtures. Replay frozen decisions against finalized Highest value boards,
   with explicit uncertainty/censoring for incomplete contest archives. No
   payout probabilities from synthetic fields. Keep zero-boost until every
   NHL team has played (#325 / #517).
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
