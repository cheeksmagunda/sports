# Status

Last updated: 2026-08-20

This file is a mutable operational snapshot. Verify service state, schedules,
repository commits, environment configuration, and artifact identity against
GitHub, Railway, PostgreSQL, and the running API before changing production.

## Monorepo cutover

- Sports monorepo extraction: in progress; not yet the production source.
- Operational WNBA source commit observed 2026-08-20:
  `e82cd20806a117d407649b35f9b239f0faf1ae38`.
- The frontend contributor reported all eight frontend phases passing at that
  commit. The monorepo import still requires a mechanical commit import and
  frontend tree-hash verification before its source is repointed.
- Railway still requires sequential source repointing and a full acceptance
  cycle before the original private WNBA repository can become read-only.

## Production

- State: live (recovered 2026-08-18 from the 08-15..08-18 trial-expiry
  outage; see Incident history below)
- Model artifact: `picker_e2ced9ec_1780873338.pkl`
- Model SHA: `94f8e8606dab4d48652929bb3884fb9152e1abc766eeb2c2d86559f4318676cd`
- Backend: FastAPI on Railway
- Frontend: Vite React on Railway
- Canonical store: Railway Postgres
- Cache/freeze coordination: Redis

## Monitoring and ops record

At the last verified snapshot, two scheduled cloud routines watched production
daily:

- WNBA pre-freeze guard, 13:30 UTC: tonight's picks. Escalates to the
  GitHub issue labeled `ops-guard`; silent when healthy.
- WNBA dayclose verify, 07:00 UTC: corpus ingest + early Real Sports
  session-death warning + results digest to the issue labeled `ops-results`.

Operational history lives in those issues and in the routines' session
logs (https://claude.ai/code/routines), not in this file. The pre-2026-07
audit-log lines that used to accumulate here are preserved in git history.

The monorepo migration adds equivalent WNBA-owned GitHub Actions. Do not disable
the old routines or enable new schedules until manual runs and the required
production acceptance cycle succeed.

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

Recorded Railway identifiers:

| Resource | Identifier |
| --- | --- |
| Project | `ab83f44c-0bbc-4a58-931c-37d9fbfda73a` |
| Production environment | `d57a759e-e189-439b-a612-bd220ef59c39` |
| api | `f4750eda-fd6c-432b-b6f5-34254013c271` |
| frontend | `d56dccf4-85b3-4ba0-acaf-58ef0cced58c` |
| cron-job1 | `2e110589-9527-4541-a754-41c4719515ba` |
| cron-job1-late | `2b0cd5aa-8793-45a5-bca0-e81c6d8455ff` |
| cron-job2 | `4a511ed2-10ad-441f-bf9a-3748c1e6b929` |
| cron-dayclose | `606d950d-7d7d-4f5a-a049-b9fa69799169` |
| postgres | `5e827da3-6df6-4349-97ad-a800ece2716d` |
| redis | `bb131bec-4edd-4809-accd-e09e09aacbf6` |

Recorded legacy routine identifiers:

| Routine | Trigger | Schedule UTC |
| --- | --- | --- |
| WNBA pre-freeze guard | `trig_01FzJJAJ89ggeMgkgoPRTEzg` | `30 13 * * *` |
| WNBA day-close verify | `trig_015HXQzUQjAgVFwfv6b7q8y6` | `0 7 * * *` |

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
| OPTIMIZER_CEILING_TILT_SLOTS | true | D107/Phase 4 |
| OPTIMIZER_MIXTURE_VARIANCE_ENABLED | true | D107/Tier 2 |
| FREEZE_LEAD_MINUTES | 40 (code default) | D93 |
| STARTER_UNKNOWN_FADE | 0.75 | 2026-07-04 corpus calibration |
| PICKER_BOOST_TAIL_LIFT | false | 2026-07-04 rolled back after -93 counterfactual |
| STARTER_MINUTES_LIFT_ENABLED | true | 2026-07-10 Kuier/Harris fix; +12.5 suite counterfactual |
| PICKER_FLOOR_TILT_WEIGHT | 0.2 | 2026-07-10; cliff at 0.35, do not raise without re-sweep |
| PICKER_KNOB_CHALLENGER_JSON | pre-suite config (fade only) | 2026-07-10, measures the suite's marginal effect ex post |
| POOL_EXCLUDE_STARTED_GAMES | unset (code default false) | D109; operator-directed late-entry scope, see below |

All flags reverse via env with no redeploy: set `*_ENABLED=false` or unset
numeric knobs to revert to code defaults.

`POOL_EXCLUDE_STARTED_GAMES=true` scopes the optimizer pool to games that
have not tipped, using the `game_start_utc` job1 writes per player. Before
the slate's first tip it is a no-op, so freeze semantics are unchanged; once
a game has started it appends one scoped freeze (`frozen_via =
job2_upcoming_games_only`) gated by the lock buffer against the next game.
It fails closed: a pool row with no known tip time is dropped, so enabling
it on a slate whose enrichment predates D109 empties the pool. Backfill
those rows first with `oracle-cron --job job1games`. Used live on
2026-08-19 (freeze_seq 2, GSV/MIN only, after TOR@WAS had tipped).

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
| Pool empty / 401s from web.realapp.com | Real Sports session died (they last ~3 weeks). Operator recovery only -- AGENTS.md, "Real Sports". Do NOT attempt a scripted/headless login; the site bot-blocks it |
| Odds API 429 / 401 | Quota or rotated key. Job1 degrades to empty odds; lineup still ships without the Vegas tilt |
| Watchdog `label_coverage_gap` | A contest player referenced in the top-20 leaderboard has no slate_labels row -- a real ingestion gap since 2026-07-03 (the check compares against leaderboard players, not the 3x-wider job1 pool) |
| No `slate_labels` rows for last night | Usually NOT a failure. `start_id = top_cid - 1` excludes the newest contest by design, so slates land late via window overlap. Measured lags: 07-12 +2d, 07-16 +5d, 07-19 +7d, 07-28 +5d, 07-29 +5d. Wait a week before investigating |
| Railway logs show no structured JSON (`kept`, `dayclose_walk`) | Known log-visibility gap since 2026-07-17, NOT a crash. Confirm the run actually worked by checking `ingested_at` in `slate_labels` / `wnba_game_logs`, not by log absence. This gap caused a false CRITICAL on #17 (2026-08-03) |

Railway dashboard:
https://railway.com/project/ab83f44c-0bbc-4a58-931c-37d9fbfda73a

## Known measurement gaps (2026-08-03)

Findings from an interactive research session; full detail and method in the
issue labeled `ops-results` (#15). No model change was made.

- **`contest_placements.entry_score` is inflated on every row written before
  2026-08-19** (and with it `entry_rank`, `finish_percentile`, `cashed`,
  `top_10pct`, `top_1pct`, all derived from it). Dayclose ranked the five picks
  by realized score before applying the slot multipliers, which awards the 2.0x
  base to whoever spiked; the slot order is committed before tip, so that is an
  upper bound, not our result. Measured against the corpus, the stored score
  matches the hindsight number on 11 of 18 slates and the correct committed-order
  number on 0 of 18, overstating by up to 2.4 points. Fixed and deployed in
  `4f73668`; rows written from 2026-08-20 onward are correct. Backfilled
  2026-08-19 via `scripts/backfill_placement_scores.py --apply`: **11 rows
  repaired** (mean -1.11, worst -2.45 on 2026-08-05; every row moved down, which
  is the expected direction since a committed order can never beat a hindsight
  one). **11 rows remain wrong and are not repairable** -- their picks have no
  `slate_labels` row, so the realized values needed to recompute do not exist.
  Those 11 also still carry the bogus `entry_rank = 21` sentinel. Treat any
  pre-2026-08-19 placement row with a 21 rank as unusable, not merely imprecise.

- **No placement has ever been recorded.** `contest_placements` holds 16 rows
  from one batch on 2026-06-13, all with `entry_rank = 21` (the "not in the
  top-20 leaderboard" sentinel) and `entry_count` / `finish_percentile` /
  `roi` fully NULL. Separate from the psycopg2 dialect bug fixed in `75f92f2`:
  even with the write path working, no percentile is computable without
  `entry_count`. The 2026-08-02 entry finished 16th of 7,400 and the system
  captured nothing.
- **`prediction_calibration_drift` was a false alarm for a month.** It
  correlates over the five optimizer-selected picks only, whose predicted
  spread is range-restricted, and compared that against the D77 full-corpus
  walk-forward 0.554, a different estimator. Reproduced pooled value is 0.408
  (n=95) with no trend. Alerts fired on 15-20 pairs where the 95% CI contains
  zero, 0.408 and 0.554 alike. Guarded 2026-08-03 by `DRIFT_MIN_PICK_PAIRS`.
- **Minutes intervals are symmetric by construction** (`predict/minutes.py`,
  `p50 +/- half`, half clamped to [2, 8]). 268 of 270 frozen intervals are
  exactly symmetric. Actuals land below p10 32.8% of the time against an
  expected 10%, worst in blowout wins (56.3%). Display-only: `pred_minutes_*`
  is read by the frontend and never by the optimizer, so this is a diagnostic.
- **The blowout path gates on a hard 24-minute recent-minutes threshold** in
  both `project_minutes_from_base` and `redistribute_game_script_minutes`. A
  confirmed starter below that line is classified bench and has projection
  *added* as a garbage-time recipient. This does reach the optimizer via
  `pred_real_scores`. Queued, not changed: needs a corpus counterfactual, and
  same-game counter-evidence exists (2026-08-02, Zandalasini fell, Stokes rose).
- **The two corpora share no player key.** `frozen_lineups` uses Real Sports
  pool ids, `wnba_game_logs` uses WNBA stats ids, zero overlap, and team codes
  differ (POR vs PDX). Prediction-to-outcome analysis must join on names, which
  hits 84.8%.

## Incident history

- 2026-08-15..08-18: three-day outage, issue #17. Railway trial expired;
  all services received a graceful stop at 2026-08-15T20:14Z and every
  redeploy attempt returned "Your trial has expired. Please select a plan".
  Billing is outside routine authorization, so the guard could only
  escalate. 08-16 was a full game day missed (no pool, no freeze, no
  ingest); 08-17 had no games. Recovered 2026-08-18: operator selected a
  paid plan, all services redeployed ~21:13 UTC. Redeploying a cron
  service only re-arms its schedule, so job1's missed 13:00 UTC fire was
  recovered by temporarily moving cron-job1's schedule to 21:54 UTC for a
  one-shot run, then restoring `0 13 * * *`. Recovery surfaced a second
  latent break: every backend service's builder had drifted to RAILPACK
  (ignoring railway.toml's DOCKERFILE), and Railpack's default Python moved
  to 3.13, outside pyproject's `>=3.11,<3.13` pin, so every fresh source
  build failed at `uv sync` while image-reuse redeploys kept succeeding.
  Fixed by setting config-file `railway.toml` + `Dockerfile` path on api,
  cron-job1, cron-job1-late, cron-job2, cron-dayclose, and
  backfill-enrichment (frontend stays Railpack; it is the Node app).
  Durable lessons: a Railway billing lapse stops every service at once,
  crons do not catch up on their own after redeploy, and builder drift is
  invisible until the next cold build.

- 2026-06-27..07-03: five-day outage, issue #10. Root causes compounding:
  the Real Sports session died server-side (~3-week TTL) killing job1's
  pool, AND the cloud audit routine's bootstrap file
  (a legacy agent credential file) had been deleted in a cleanup commit, leaving
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
