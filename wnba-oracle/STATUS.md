# Status

Last updated: 2026-07-01

## Production

- State: live
- Model artifact: `picker_e2ced9ec_1780873338.pkl`
- Model SHA: `94f8e8606dab4d48652929bb3884fb9152e1abc766eeb2c2d86559f4318676cd`
- Backend: FastAPI on Railway
- Frontend: Vite React on Railway
- Canonical store: Railway Postgres
- Cache/freeze coordination: Redis

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

## Active Runtime Jobs

- `job1`: scrape and persist slate enrichment.
- `job1late`: refresh starter signals without spending Odds API credits.
- `job2`: freeze the optimized lineup at the slate-specific T-minus window.
- `dayclose`: backfill finalized contest data, refresh game logs, record placements,
  and prune append-only operational tables.

## Current Cleanup Decision

The repo now keeps one short README and this status file. Removed files were
archival or stale: handoff logs, research markdown, research outputs, local
parquet snapshots, placeholder eval JSON, and the markdown results ledger path.

## Live services (verified 2026-06-13)

- api:       https://api-production-7033.up.railway.app/health -> 200
- api:       https://api-production-7033.up.railway.app/lineup -> 200
- frontend:  https://frontend-production-a739.up.railway.app/ -> 200
- postgres:  internal + public TCP proxy (TLSv1.3, SSL via start-command cert,
  D61). Alembic head = 20260613_0007 (D90: contest_placements + player_slate_ownership
  applied 2026-06-13). CANONICAL corpus store: slate_labels + contest_leaderboards
  (141+ slates, 2025-05-16..ongoing) + wnba_game_logs (13,456+ player-games,
  2024-05-03..ongoing). All reads via `db.reads` helpers; local parquet files
  are archival backups only.
- redis:     internal, password-protected
- cron-backup (GitHub Action `corpus-backup`): `43 6 * * *` UTC, exports corpus
  to off-`main` `backups` branch (D61). 3-2-1 off-site copy.
- cron-job1: `0 13 * * *` UTC -- scrape Real Sports pool, nba_api minutes,
  odds, RotoWire lineups, player props, persist features_json enrichment.
- cron-job1-late: `*/30 16-23 * * *` UTC (D103, was `35 22`, service id
  2b0cd5aa) -- runs `oracle-cron --job job1late`, the credit-free lite refresh
  (D102/#27): re-scrapes RotoWire and JSONB-merges ONLY the starter/confirmed
  fields onto existing enrichment (no Odds/props re-fetch). Fanned across the
  afternoon+evening so every slate gets confirmed starters before its T-40
  freeze. No Real Sports auth needed (RotoWire + DB only).
- cron-job2: `*/5 14-23,0-3 * * *` UTC -- run heads + optimizer, freeze lineup
  to Redis + Postgres (tip-relative T-40, D93). Changed from */15 to */5 on
  2026-06-22 to cut worst-case freeze lag from 15 min to 5 min after T-40.
  Late re-freeze when LATE_REFREEZE_ENABLED (D75).
- cron-dayclose: `0 6 * * *` UTC -- extend corpus from finalized contest ids
  (D41/D60, service id 606d950d) + nightly wnba_game_logs refresh (D102/#28,
  WNBA_DAYCLOSE_REFRESH_GAMELOGS).
- backfill-enrichment: cron=None (on-demand) -- the ONLY service that should run
  `oracle-cron --job backfill` (historical head_features). Never repoint
  cron-job1/late at it (D103).

## Active Railway env vars (cron-job2, verified 2026-06-13, D91)

Production model: `WNBA_ORACLE_MODEL_ARTIFACT_SHA=94f8e8606dab...`
(picker_e2ced9ec_1780873338.pkl, D77b). Set on api, cron-job1, cron-job2.

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
| OPTIMIZER_MAX_SINGLE_BOOST | 2.5 | D70/R2 |
| OPTIMIZER_GAME_STACK_BONUS | 0.010 | D70/R3, D98 (raised from 0.005; alignment 56.2%) |
| MINUTES_MODEL_ENABLED | true (code default) | D55 |
| STARTER_SIGNAL_ENABLED | true (code default) | D71 |
| AVAILABILITY_MODEL_ENABLED | true | D73 |
| GAME_SCRIPT_MINUTES_ENABLED | true | D57 |
| LINEUP_ANCHOR_FLOOR | 2 | D57/D58 |
| LATE_REFREEZE_ENABLED | true | D75 |
| PROP_SIGNAL_SCALE | 0.3 | D78 |
| FIELD_MEASURED_OWNERSHIP_ENABLED | true (code default) | D86 |
| CAVEAT_IS_SKIP | false | D48 (superseded by NEVER_SKIP) |
| SAMPLING_SCORE_OFFSET | 2.0 (code default) | D52 |
| FIELD_SAME_GAME_BOOST | 3.0 (D91 calibration, 12.1% beat-median) | D88 |
| FIELD_SAME_TEAM_BOOST | 2.0 (D91 calibration) | D88 |
| OPTIMIZER_DUPLICATION_AWARE_PAYOUT | false (no effect found, D91) | D88 |
| OPTIMIZER_LEVERAGE_WEIGHT | 0.0 (code default, synthesis: double-counts) | D87 |
| OPTIMIZER_CEILING_WEIGHT | 0.0 (code default, arm post-placement loop) | D87 |
| OPTIMIZER_DUPLICATION_WEIGHT | 0.0 (code default, arm post-placement loop) | D87 |
| OPTIMIZER_CEILING_SIGMA_BLOWOUT_BOOST | 0.15 (D89/D92, synthesis starting value, blowout signal active) | D89 |
| OPTIMIZER_CEILING_SIGMA_LOW_HISTORY_BOOST | 0.20 (D89/D92, synthesis starting value, post-D91 calibration) | D89 |
| FREEZE_LEAD_MINUTES | 40 (code default, D93) -- freeze at first_tip - 40min, tip-relative | D93 |

All flags reverse via env with no redeploy. Set *_ENABLED=false or unset numeric
knobs to revert to code defaults.

## Historical corpus (updated 2026-06-21)

All corpus data lives in Postgres (the canonical store). Local parquet
files under `data/historical/` and `data/processed/` are archival backups
only and are no longer read by any script.

### Raw Postgres tables

- `slate_labels`: 157 finalized slates (2025-05-16..2026-06-20), one row
  per player-slate, deduped by player per contest. ~4,500 rows.
- `contest_leaderboards`: top-20 finisher lineups per slate.
- `wnba_game_logs`: ~13.5k player-games across 2024-2026 seasons (454
  players), sourced from stats.wnba.com via nba_api.

### Two corpora, two roles -- DO NOT CONFUSE

The picker trains two distinct kinds of model on two distinct frames:

| Corpus | Builder | Grain | Target | Source | Consumed by |
| --- | --- | --- | --- | --- | --- |
| **Gamelog** (the heads corpus) | `features/corpus.build_gamelog_corpus()` | one row per player-GAME | per-game minutes + real_score-per-min | `wnba_game_logs` (~13k rows) | LightGBM heads (minutes + per-min rate, cohort F) -- the D63 keystone |
| **Label** (the contest corpus) | `features/corpus.build_label_corpus()` wrapping `db/reads.read_label_corpus()` | one row per player-SLATE | realized contest `real_score` | `slate_labels` (~4.5k rows) | EB baseline, real_score blend, CQR calibration |

The label corpus is *not* the training corpus for the heads. It is the
contest-platform corpus that carries `card_boost` and realized contest
points. The heads are starved if trained on it alone (the pre-D63 bug).

All reads go through `src/wnba_oracle/db/reads.py` (D62):
`read_label_corpus()`, `read_slate_labels()`, `read_leaderboards()`,
`read_game_logs()`, `read_player_history()`.

To re-run minutes backfill:
```
set -a && source .env && set +a
uv run python scripts/backfill_minutes.py
```

To re-run contest backfill:
```
set -a && source .env && set +a
export WNBA_DEVICE_UUID=<uuid matching storage_state>
uv run oracle-backfill --mode historical --start-id 1755 --stop-id 1900 \
    --pause-seconds 0.6
```

The day-close cron (`0 6 * * *` UTC) auto-extends the corpus nightly.

## Optimizer correctness (2026-05-27 10:00 UTC)

The pre-fire backfill (D38) surfaced two long-standing bugs in the picker:

- **Slot multipliers were [3.0, 2.5, 2.0, 1.5, 1.0]** (NBA precedent); actual
  WNBA platform uses **[2.0, 1.8, 1.6, 1.4, 1.2]** verified empirically
  across all 320 corpus entries. Fixed in commit `5fb6c6f` and pinned in
  `tests/unit/test_slot_scheme.py`. See D42.

- **Heuristic real_score was 15.0 * (1 + 0.2 * boost)** — wrong magnitude
  (5x too high) and wrong slope (positive; actual relationship is
  -0.45/boost-unit because card_boost is a handicap). Recalibrated to
  `max(0.5, 3.16 - 0.45 * card_boost)`. See D43.

Tonight's 21:00 UTC cron-job2 fire is the first to use the corrected
optimizer. Backtest on 2026-05-25 realized values produced 49.73 points
(brute-force optimum), vs the actual contest winner cpgooner at 40.60.

## Today's slate (2026-05-27) — what to expect

**Cron-job1 fires at 13:00 UTC (8 AM CDT / 9 AM EDT):**
1. Headless re-auth via REALSPORTS_STORAGE_STATE_B64GZ + WNBA_DEVICE_UUID
2. /home/wnba/next + /players/sport/wnba/search a..z pool fetch
3. The Odds API basketball_wnba pull (vegas signals -> features_json)
4. RotoWire WNBA lineups scrape
5. UPSERT into job1_enrichment

**Cron-job2 fires every 15 min from 21:00 UTC through 04:00 UTC** (16:00 CDT
to 23:00 CDT). First fire at 21:00 UTC is when the frontend's countdown
expires and the lineup lands.
1. Load slate from job1_enrichment + slate_labels (drafts if available)
2. Compute per-player heuristic real_score
3. Apply game_script_multiplier (Vegas-driven tier weights)
4. Apply anti-popularity contrarian adjustment
5. Optimize lineup (top-30 -> C(30,5), max_per_team=2)
6. Freeze via Redis SET NX + Postgres UPSERT (with per_player block — D36)

**Frontend** (https://frontend-production-a739.up.railway.app/) polls
/lineup/2026-05-27 every 5-60s with backoff:
- Until 21:00 UTC: full-bleed OracleLoader with countdown to lineup-freeze
- After 21:00 UTC (when job2 first writes): swaps to the 5-card grid

## Where to look if something goes wrong

| Symptom | First place to check |
|---|---|
| Frontend shows countdown past 21:00 UTC | Railway logs for cron-job2 service. Most likely `pool_too_small` (job1 didn't write rows) or `job2_failed` (DB / Redis hiccup) |
| Frontend shows ErrorState block | `curl https://api-production-7033.up.railway.app/health` first; if 200, check api Railway logs |
| Lineup loaded but card names show "Player 12345" | per_player block missing — should be impossible after D36; check job2's `_build_per_player` ran |
| Job1 fails with StorageStateStale | JWT inside REALSPORTS_STORAGE_STATE_B64GZ rotated. Re-run `scripts/realsports_login.py` locally and re-seed the env var on cron-job1 + cron-job2 (NEEDS_CLAUDE item 6) |
| Odds API returns 429 / 401 | Free-tier quota or rotated key. Job1 degrades to empty odds; game_script_multiplier reverts to 1.0x. Lineup still ships, just without the Vegas tilt |

Railway dashboard for logs:
https://railway.com/project/ab83f44c-0bbc-4a58-931c-37d9fbfda73a

## Audit findings + fixes (2026-05-27 03:30-05:30 UTC)

The pre-fire audit surfaced four issues; all fixed before the operator
went to bed.

1. **Critical UX fix — per_player block** (D36): job2 was writing the
   frozen lineup JSONB without a `per_player` array, so the frontend
   would have rendered 5 placeholder cards ("Player 12345", "—", "—",
   all-zero scores) for tomorrow's first slate. Now job2 materializes
   the full projection contract (display_name / team / opponent /
   position / card_boost / pred_real_score_p50 / pred_minutes_p10-p90)
   into the JSONB. Four tests pin the contract in `tests/unit/
   test_per_player_frozen.py`.

2. **Frontend countdown target** (D36): countdown pointed at 13:00 UTC
   (job1 ingest, not user-visible) instead of 21:00 UTC (job2 freeze,
   when the lineup actually appears). Re-targeted; caption changed
   from "Next fire in" to "Lineup freezes in".

3. **Settings env aliases** (D36): pydantic-settings has
   `case_sensitive=True`, so fields without explicit `alias=` (env,
   log_level, payout_regime, optimizer_*, contrarian_*) never picked
   up Railway's uppercase env vars — silently falling back to defaults.
   The current Railway values happened to match defaults so today's
   run was not affected, but any future env-var tuning would have
   silently no-op'd. Added aliases on every uppercase env-var consumer.
   Verified: `ENV=prod LOG_LEVEL=DEBUG CONTRARIAN_STRENGTH=0.25` now
   propagates correctly through `Settings()`.

4. **Railway env hardening** (D35): promoted operational config to
   shared env-scope via `${{shared.KEY}}` references; converted
   DATABASE_URL / REDIS_URL to `${{postgres.DATABASE_URL}}` /
   `${{redis.REDIS_URL}}` service refs; converted frontend
   VITE_API_URL to `https://${{api.RAILWAY_PUBLIC_DOMAIN}}`. Dropped
   GITHUB_TOKEN + RAILWAY_TOKEN from every runtime service; dropped
   REAL_SPORTS_* / WNBA_DEVICE_* / REALSPORTS_STORAGE_STATE_B64GZ from
   api + cron-job2 (only cron-job1 authenticates).

## Known caveats — multi-day work, not blocking tomorrow

These came out of the deep code audit (general-purpose subagent, 2026-05-27
05:00 UTC) and are documented for follow-up; they will NOT block
tomorrow's first frozen lineup.

- **RotoWire lineups fetched but not persisted** (NEEDS_CLAUDE item 7):
  `job1.py:114` calls `fetch_lineups()` and counts the result for the
  log line, but the rows aren't written to `job1_enrichment`. The
  injury-cascade port (D33) only fires through `features/build.py`
  which the live cron path never calls. Impact for tomorrow: players
  RotoWire flags OUT still draft into the optimizer pool; minutes
  redistribution does not apply. The lineup will still ship with
  reasonable picks (boost + Vegas signals carry it), just without the
  injury-aware adjustment.

- **Job2 `_freeze` is not strictly idempotent** (NEEDS_CLAUDE item 8):
  The Redis SETNX guards the lock metadata but the Postgres UPSERT
  fires every invocation. Subsequent cron-job2 fires within the same
  slate window can replace the frozen lineup if new draft data arrives
  via slate_labels and shifts the contrarian adjustment. Documented
  intent vs. behavior mismatch — should either skip the UPSERT when
  the lock is held, or accept the refresh-as-data-arrives semantics
  and rename "freeze" everywhere.

- **Watchdog not wired** (NEEDS_CLAUDE item 9): `scheduler/watchdog.py`
  is a stub returning `[]` and is not called from `cron.py`. Operator
  must read Railway logs manually for failure detection until the
  watchdog + alerting path lands.

## Quality gates

- 365 unit tests pass (D93; was 350). `uv run --extra dev python -m pytest -q`.
  Note: the global `uv run pytest` tool lacks the project deps -- use
  `--extra dev python -m pytest`.
- ruff + mypy on `src/` clean (D93 fixed pre-existing drift the docs had
  claimed clean: 3 ruff + 6 mypy).
- `make determinism-check` repaired (D93 / NEEDS_CLAUDE #14): compares model
  CONTENT via `pipeline.artifact_content_equal`, not pickle SHA.
- 72 source files in `src/wnba_oracle/`.
- 6 basketball-main patterns ported with zero new external dependencies.
- Frontend bundle: 209KB / 66KB gz, builds in ~470ms.

The eval/ bundle is seeded with placeholder JSON. It auto-populates once
the live collector accumulates enough slates (Part 0.4 deliverable list).

[2026-06-22 14:00 UTC audit] Status: OK. Pool: healthy (no watchdog pool/model events). Freeze target: 22:20 UTC. Issues fixed: none.
[2026-06-23 14:00 UTC audit] Status: OK. Pool: 28 players, 1 game. Freeze target: 01:20 UTC (Jun 24). Issues fixed: none. Notes: config_drift WARN from cron-job1 watchdog is the known false positive (#30) -- cron-job2 watchdog_clean confirms freeze knobs intact.
[2026-06-24 14:00 UTC audit] Status: OK. Pool: 120 players, 4 games. Freeze target: 22:50 UTC. Frontend: OK (toISOString=0, getFullYear=1, VITE_API_URL correct). Issues fixed: none. Notes: cron-job2 watchdog_clean at 14:16:48 UTC (optimizer evaluated 9777 lineups, expected_payout 1.2942, entry_flag enter); /watchdog/today still shows the known cron-job1 config_drift false-positive (#30). Odds quota 486 remaining.
[2026-06-25 14:00 UTC audit] Status: OK. Pool: 90 players, 3 games. Freeze target: 22:20 UTC. Frontend: OK (toISOString=0, getFullYear=1, VITE_API_URL correct). Issues fixed: none. Notes: api/cron-job1/cron-job2 deployed at HEAD (6b003e3); job1_done at 13:05:31 UTC (n_pool=90, n_lineups=44, persisted=90, head_features 85/90, rotowire 43/44, props 31 matched); cron-job2 fired clean at 14:00/14:05/14:10 UTC with watchdog_clean each time (optimizer evaluated 13744 lineups, expected_payout 1.2794, entry_flag enter, knobs effective anchors=2 / boost_cap=9 / max_single=2.5 / max_per_team=2); availability model dropped 18 of 90 to 72 active players. /watchdog/today still shows the known cron-job1 config_drift false-positive (#30). Odds quota 479 / props quota 476 remaining.
[2026-06-26 14:00 UTC audit] Status: OK. Pool: healthy (no watchdog pool/model/odds/rotowire events; pool_too_small fires <10, not fired). Freeze target: 22:50 UTC (first tip 23:30 UTC). Frontend: OK (toISOString=0, getFullYear=1, VITE_API_URL correct). Issues fixed: none. Notes: api/cron-job1/cron-job2 deployed at HEAD (a1c622f); model SHA 94f8e860... intact on cron-job2; cron-job2 schedule `*/5 14-23,0-3 * * *` and cron-job1-late `*/30 16-23 * * *` with `oracle-cron --job job1late` both correct; slate_meta first_tip=23:30 UTC populated by job1; /watchdog/today shows only the known cron-job1 config_drift false-positive (#30) at 13:05:46 UTC. DB public proxy (acela.proxy.rlwy.net:51730) unreachable from audit container (outbound TCP to non-HTTP ports blocked); checks 3/4/5/8/10 verified indirectly via /watchdog and /slate API endpoints rather than direct psql.
[2026-06-27 14:00 UTC audit] Status: OK. Pool: 93 players, 3 games. Freeze target: 17:20 UTC (first tip 18:00 UTC). Frontend: OK (toISOString=0, getFullYear=1, VITE_API_URL correct). Issues fixed: set 12 production knob env vars (PROP_SIGNAL_SCALE 0.3, LINEUP_ANCHOR_FLOOR 2, FIELD_SAME_GAME_BOOST 3.0, FIELD_SAME_TEAM_BOOST 2.0, LATE_REFREEZE_ENABLED true, OPTIMIZER_BOOST_SUM_CAP 9.0, AVAILABILITY_MODEL_ENABLED true, OPTIMIZER_GAME_STACK_BONUS 0.010, OPTIMIZER_MAX_SINGLE_BOOST 2.5, OPTIMIZER_CEILING_SIGMA_BLOWOUT_BOOST 0.15, GAME_SCRIPT_MINUTES_ENABLED true, OPTIMIZER_CEILING_SIGMA_LOW_HISTORY_BOOST 0.20) on cron-job1 and api so the watchdog drift check there now reads the same prod values as cron-job2; tomorrows 13:00 UTC job1 watchdog should emit no config_drift event, closing the #30 recurring false-positive at its source. Notes: api/cron-job1/cron-job2/cron-job1-late/cron-dayclose/frontend all deployed at HEAD (0baf944); model SHA 94f8e860... intact on cron-job2; cron-job2 schedule */5 14-23,0-3 * * * and cron-job1-late */30 16-23 * * * with oracle-cron --job job1late both correct; job1_done at 13:06:33 UTC (n_pool=93, n_games=3, n_rotowire=46 with 45 matched, n_head_features_matched=85 of 93, n_odds=5, persisted=93); cron-job2 fired clean at 14:00/14:05/14:10 UTC (n_pool=72 after availability dropout, expected_payout=1.183, entry_flag=enter); odds quota 467 / props quota 464 remaining; warn: team_name portland fire unmapped (RotoWire still matched 45/46). DB public proxy (acela.proxy.rlwy.net:51730) unreachable from audit container; checks 3/4/5/8/10 verified via Railway deployment logs and /watchdog //slate //lineup API endpoints rather than direct psql. The 24 variableUpsert calls (12 per service) triggered cascading Railway redeploys; latest queued at 14:11 UTC, API stayed 200 throughout.
[2026-06-29 14:00 UTC audit] Status: CRITICAL. Pool: 0 players, slate_meta empty -- /slate/2026-06-29 404, /lineup/2026-06-29 404, watchdog/today flags trigger=no_job1_pool severity=critical pool_size=0 at 14:00:13Z. Freeze target: unknown (no tip captured). Frontend: OK (200 reachable, toISOString=0, getFullYear=1, bundle index-ByL3nEom.js baked with https://api-production-7033.up.railway.app). Issues fixed: none -- audit blocked by same RAILWAY_TOKEN rejection that produced issue #10 yesterday; no Railway access means no logs, no variableUpsert, no redeploy. Yesterdays 06-28 freeze also never happened (watchdog: no_job1_pool at 13:03/19:05/01:05Z + no_frozen_lineup at 22:00Z); last successful freeze was 2026-06-27T17:22Z (5 players, expected_payout 1.183). Now a two-day freeze outage. Model SHA 94f8e860 still correct per last good freeze. DB public proxy (acela.proxy.rlwy.net:51730) unreachable from audit container as usual. Posted day-2 comment on production-critical issue #10 with current state and the same two unblock paths (rotate RAILWAY_TOKEN, or operator manual JWT refresh + variableUpsert REALSPORTS_STORAGE_STATE_B64GZ + serviceInstanceDeployV2 cron-job1).
[2026-07-02 14:00 UTC audit] Status: CRITICAL. Pool: 0 players. Freeze target: 22:50 UTC (first tip 23:30 UTC, WAS@ATL then DAL@CT 00:00Z and SEA@PHX 02:00Z per odds-api scores endpoint). Frontend: OK (200 reachable, toISOString=0, getFullYear=1, bundle index-ByL3nEom.js baked with https://api-production-7033.up.railway.app). Issues fixed: none -- day 5 of same RAILWAY_TOKEN blocker from #10. /watchdog/today fires no_job1_pool severity=critical pool_size=0 at 13:00:24Z plus the ongoing config_drift warn (12 knobs at default on cron-job1, unchanged since D107). /slate/2026-07-02 and /lineup/2026-07-02 both 404. Last successful freeze remains 2026-06-27T17:22Z (5 players, EP 1.183). Backlog since then: 06-28 game day missed, 06-29 off day, 06-30 game day missed, 07-01 off day, 07-02 game day at risk. Cross-check via odds-api /v4/sports/basketball_wnba/scores?daysFrom=3 confirms 2026-07-02 has 3 real games. RAILWAY_TOKEN (aaa54228, 36 chars) still Not Authorized on Bearer/Project-Access-Token/Team-Access-Token/X-Railway-Token; introspection works so rejection is auth-layer. DB public proxy (acela.proxy.rlwy.net:51730) still TCP timeout. Model SHA still 94f8e860 on the last good freeze. Odds quota 498 remaining. Posted day-5 comment on #10 confirming game day + unchanged blocker; unblock paths still (1) rotate RAILWAY_TOKEN so next audit can self-recover, or (2) operator one-shot recovery from a workstation (realsports_login.py + variableUpsert REALSPORTS_STORAGE_STATE_B64GZ on cron-job1 + serviceInstanceDeployV2). Ideally before ~22:00 UTC to leave the 22:50 freeze target a margin.
