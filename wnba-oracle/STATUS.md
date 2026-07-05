# Status

Last updated: 2026-07-05

## Production

- State: live (recovered 2026-07-03 from the 06-28..07-02 outage; see
  Incident history below)
- Model artifact: `picker_e2ced9ec_1780873338.pkl`
- Model SHA: `94f8e8606dab4d48652929bb3884fb9152e1abc766eeb2c2d86559f4318676cd`
- Backend: FastAPI on Railway
- Frontend: Vite React on Railway
- Canonical store: Railway Postgres
- Cache/freeze coordination: Redis

## Monitoring and ops record

Two scheduled cloud routines watch production daily (details and design
rules in AGENTS.md, "Scheduled routines"):

- WNBA pre-freeze guard, 13:30 UTC: tonight's picks. Escalates to the
  GitHub issue labeled `ops-guard`; silent when healthy.
- WNBA dayclose verify, 07:00 UTC: corpus ingest + early Real Sports
  session-death warning + results digest to the issue labeled `ops-results`.

Operational history lives in those issues and in the routines' session
logs (https://claude.ai/code/routines), not in this file. The pre-2026-07
audit-log lines that used to accumulate here are preserved in git history.

## Canonical Data

Use Postgres, not local parquet.

| Table | Purpose |
| --- | --- |
| `wnba_game_logs` | Player-game box scores and matchup fields for the heads corpus |
| `slate_labels` | Player-slate realized Real Sports labels |
| `contest_leaderboards` | Top-20 finisher lineups per contest |
| `job1_enrichment` | Pre-tip pool and feature snapshots |
| `frozen_lineups` | Append-only freeze history |
| `slate_meta` | First tip and lock metadata |
| `contest_placements` | Realized placement feedback |
| `watchdog_events` | Operational alerts |

Corpus size (2026-07-03): 167 slates in `slate_labels` (2025-05-16 through
2026-07-02, ~4,900 rows); ~14,900 player-games in `wnba_game_logs`. The
day-close cron extends both nightly. All reads go through
`src/wnba_oracle/db/reads.py`.

## Live services

- api: https://api-production-7033.up.railway.app (`/health`, `/lineup/{date}`,
  `/slate/{date}`, `/watchdog/today`)
- frontend: https://frontend-production-a739.up.railway.app/
- postgres: internal + public TCP proxy (TLS via start-command cert, D61);
  role `oracle_ro` for read-only laptop access
- redis: internal, password-protected
- cron-job1 `0 13 * * *` UTC: scrape Real Sports pool, minutes, odds,
  RotoWire, props; persist enrichment
- cron-job1-late `*/30 16-23 * * *` UTC: credit-free starter refresh
  (`oracle-cron --job job1late`; RotoWire + DB only, no Real Sports auth)
- cron-job2 `*/5 14-23,0-3 * * *` UTC: heads + optimizer, tip-relative T-40
  freeze to Redis + Postgres, late re-freeze when enabled
- cron-dayclose `0 6 * * *` UTC: ingest finalized contests, refresh game
  logs, record placements, retention cleanup
- backfill-enrichment: cron=None, on-demand only; never repoint the live
  crons at `--job backfill` (D103)
- corpus-backup (GitHub Action) `43 6 * * *` UTC: nightly export to the
  off-main `backups` branch

## Active Railway env vars (cron-job2)

Production model SHA is set on cron-job1, cron-job1-late, cron-job2 as
`WNBA_ORACLE_MODEL_ARTIFACT_SHA`. The api reads frozen lineups from Postgres
and never loads the artifact, so it does not need the SHA.

| Var | Value | Decision |
|-----|-------|----------|
| PAYOUT_REGIME | top_20 | D48 |
| NEVER_SKIP | true (code default) | D67 |
| CONTRARIAN_ENABLED | true | D51 |
| CONTRARIAN_STRENGTH | 0.2 | D51/D53 |
| OPTIMIZER_MAX_PER_TEAM | 2 | D50 |
| OPTIMIZER_DYNAMIC_TEAM_CAP | true (code default) | D50 |
| OPTIMIZER_N_FIELD_LINEUPS | 500 | D76 |
| OPTIMIZER_BOOST_SUM_CAP | 9.0 | D70/R2 |
| OPTIMIZER_MAX_SINGLE_BOOST | 3.0 | 2026-07-04 sweep_max_boost.py (+75 aggregate) |
| OPTIMIZER_GAME_STACK_BONUS | 0.010 | D70/R3, D98 |
| MINUTES_MODEL_ENABLED | true (code default) | D55 |
| STARTER_SIGNAL_ENABLED | true (code default) | D71 |
| AVAILABILITY_MODEL_ENABLED | true | D73 |
| GAME_SCRIPT_MINUTES_ENABLED | true | D57 |
| LINEUP_ANCHOR_FLOOR | 2 | D57/D58 |
| LATE_REFREEZE_ENABLED | true | D75 |
| PROP_SIGNAL_SCALE | 0.3 | D78 |
| FIELD_MEASURED_OWNERSHIP_ENABLED | true (code default) | D86 |
| SAMPLING_SCORE_OFFSET | 2.0 (code default) | D52 |
| FIELD_SAME_GAME_BOOST | 3.0 | D88/D91 |
| FIELD_SAME_TEAM_BOOST | 2.0 | D88/D91 |
| OPTIMIZER_CEILING_SIGMA_BLOWOUT_BOOST | 0.15 | D89/D92 |
| OPTIMIZER_CEILING_SIGMA_LOW_HISTORY_BOOST | 0.20 | D89/D92 |
| FREEZE_LEAD_MINUTES | 40 (code default) | D93 |
| STARTER_UNKNOWN_FADE | 0.75 | 2026-07-04 corpus calibration |
| PICKER_BOOST_TAIL_LIFT | false | 2026-07-04 rolled back after -93 counterfactual |
| PICKER_KNOB_CHALLENGER_JSON | knob-lift + fade | 2026-07-04, shadow-only for now |

All flags reverse via env with no redeploy: set `*_ENABLED=false` or unset
numeric knobs to revert to code defaults.

## Two corpora, two roles -- DO NOT CONFUSE

| Corpus | Grain | Source | Consumed by |
| --- | --- | --- | --- |
| Gamelog (heads) | player-game | `wnba_game_logs` | LightGBM minutes + per-min heads (D63) |
| Label (contest) | player-slate | `slate_labels` | EB baseline, blend, CQR calibration |

The label corpus carries `card_boost` and realized contest points; it is
not the heads' training corpus (the pre-D63 bug).

## Where to look if something goes wrong

| Symptom | First place to check |
|---|---|
| Frontend shows countdown past freeze time | Railway logs for cron-job2. Most likely `pool_too_small` (job1 wrote no rows) or `job2_failed` (DB / Redis hiccup) |
| Frontend shows ErrorState | `curl https://api-production-7033.up.railway.app/health`; if 200, check api Railway logs |
| Pool empty / 401s from web.realapp.com | Real Sports session died (they last ~3 weeks). Operator recovery only -- AGENTS.md, "Real Sports". Do NOT run `scripts/realsports_login.py` headless; the site bot-blocks scripted login |
| Odds API 429 / 401 | Quota or rotated key. Job1 degrades to empty odds; lineup still ships without the Vegas tilt |
| Watchdog `label_coverage_gap` | A contest player referenced in the top-20 leaderboard has no slate_labels row -- a real ingestion gap since 2026-07-03 (the check compares against leaderboard players, not the 3x-wider job1 pool) |

Railway dashboard:
https://railway.com/project/ab83f44c-0bbc-4a58-931c-37d9fbfda73a

## Incident history

- 2026-06-27..07-03: five-day outage, issue #10. Root causes compounding:
  the Real Sports session died server-side (~3-week TTL) killing job1's
  pool, AND the cloud audit routine's bootstrap file
  (.claude/credentials.env) had been deleted in a cleanup commit, leaving
  the watcher blind with a stale Railway token. Recovered 2026-07-03:
  session re-seeded via the Playwright MCP login path, missed slates
  backfilled (labels + leaderboards for 06-27, 06-28, 06-30), routines
  rebuilt (see Monitoring above), credentials.env restored with minimal
  scope. Durable fixes: watchdog label-coverage check made
  leaderboard-grounded, session-death signature documented, scripted
  login marked broken.

## Quality gates

- 435 unit tests pass (`uv run --extra dev python -m pytest -q`; the bare
  `uv run pytest` lacks project deps).
- ruff + mypy clean on `src/`.
- `make determinism-check` compares model content, not pickle SHA (D93).
