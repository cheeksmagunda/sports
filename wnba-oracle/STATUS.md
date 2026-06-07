status: BUILD_COMPLETE
last_verified: 2026-06-07T05:30:00Z
phase: live. 2026-06-07 (D72, R6 from research/00_GAP_ANALYSIS.md): MENU-SCRAPE GAP CLOSED. fetch_pool_for_date now runs a targeted-search fallback after the a..z prefix sweep -- for each per-game-union player not yet rated, query the ASCII-folded first 3 chars of their last name (cap 50 per slate). The audit (scripts/research/menu_scrape_gap.py) against the LIVE collector window showed 8 of 13 slates (61.5%) had >= 1 winning-lineup pick the optimizer could not pick, including the 2026-06-01 rank-1 lineup (M. Akoa Makani, pid 4322738) and the 2026-06-02 rank-2 lineup (C. McMahon, pid 4322864). Recurring victims (A. Stevens, S. Sabally, J. Jocyte, M. Akoa Makani, C. McMahon, K. Bell) all draftable per Real Sports leaderboards. fetch_pool_fallback log line surfaces n_added per slate. New `oracle.ingest.realsports` log channel. 4 unit tests in test_realsports_pool_fallback.py exercise: recovery by last-name, ASCII-fold for accented names (Jocyte), missing first+last skip-not-crash, no a..z requery. Commit e340350 on main, pushed. No env change; pure code, takes effect on cron-job1's next 13:00 UTC fire. Earlier 2026-06-07 (D71, R5): RotoWire confirmed-starter signal now wired into the D69 head Tier-0 path. The trained heads learned without `is_confirmed_starter` (the gamelog corpus doesn't compute it, so `train/pipeline.py:240` drops it from feature_subset_per_head — verified against picker_bf3c8996_*.pkl), so the head was silently blind to today's confirmed lineups. job2._build_specs Tier-0 now calls `_starter_multiplier` (the same Tier-3 helper) and scales p10/p50/p90 symmetrically by 1.10 (confirmed starter), 0.82 (confirmed bench), or 1.00 (unmatched). Tier-1 blend deliberately stays unchanged (blended_real_score handles role signals internally). Tests grow 4 -> 7 in test_head_tier0.py. No env change; reverse via STARTER_SIGNAL_ENABLED=false or revert commit aa39806. Earlier: 2026-06-06 (D70, R2+R3+R4 from research/00_GAP_ANALYSIS.md): three picker hardening knobs SHIPPED on cron-job2. R2 lineup boost caps (OPTIMIZER_BOOST_SUM_CAP, OPTIMIZER_MAX_SINGLE_BOOST) refuse lineups whose sum-of-card-boost or per-pick boost exceeds the configured ceiling; relax to 0 (with a warning) only when the team cap + boost caps are jointly infeasible. Armed at 9.0 / 2.5 — median rank-1 winner total boost is 7.5 (research/internal/01_winners_anatomy.md), the 2.5-3.0 boost bucket has 8.2%/Sharpe-1.21 vs (2.0,2.5] at 50.4%/2.01 (research/internal/04_boost_economics.md), and the 2026-06-04 ~6000th bust was driven by five high-boost cards. R3 game-stack bonus (OPTIMIZER_GAME_STACK_BONUS, armed at 0.005) adds a tiny per-stack-pair EV bias since 87% of top-20 lineups include a 2+ same-game stack. R4 audited the slot assignment — already optimum under the rearrangement inequality (`optimize.py:309-316`); winners' low-slot-0 boost is a player-selection effect, not a slot-assignment bug. Pinned by tests/unit/test_boost_cap.py (8) + test_game_stack.py (7). Commits 7386f71 (R2) and 5395585 (R3+R4) on main, pushed. Env vars set on cron-job2 (service id 4a511ed2-10ad-441f-bf9a-3748c1e6b929). All three reverse via env with no redeploy: unset the OPTIMIZER_BOOST_SUM_CAP / OPTIMIZER_MAX_SINGLE_BOOST / OPTIMIZER_GAME_STACK_BONUS env vars (or set to 0.0). Earlier same day: 2026-06-06 (D69): Phase 2b SHIPPED — D63 trained heads now serve job2 live. job1 persists the full causal head-feature row into features_json.head_features (build_head_feature_lookup, mirrors features/corpus.build_gamelog_corpus); job2._build_specs now batch-runs the (minutes, F) + (real_score_per_min, F) heads via PickerArtifact.predict_real_score in a new Tier-0 path above the existing blended_real_score -> EB -> history -> heuristic ladder. Purely additive: any pid without a head prediction falls through unchanged (4 unit tests in test_head_tier0.py pin all four branches). Per research/internal/03_theoretical_ceiling.md, wiring alone is projected to lift top-500 rate 33% -> 61%. New artifact SHA: 2cc953b7fe86e8db8a21f7f9a594a2944c4ce9d98aa21d05a0a0b434d6efd985 (picker_bf3c8996_1780752059.pkl, 6 heads trained on cohort F, training_rows=11205). Deploy: set WNBA_ORACLE_MODEL_ARTIFACT_SHA=2cc953b7fe86e8db8a21f7f9a594a2944c4ce9d98aa21d05a0a0b434d6efd985 on Railway after the commit lands. Watch job2 logs for head_predict n_in/n_out and predictor_mix n_head_predicted. Earlier: 2026-06-05 (D63): decomposed projection ACTIVATED offline. The multi-task heads were coded but never trained (the 7-column slate_labels corpus lacked their target columns), so job2 served a career-average heuristic for ~85% of players, the root cause of the 06-04 ~6000th/8317 bust. New features/corpus.py builds a 12,981-row feature+target corpus from the 13,435 game-logs (targets via the locked box_to_real_score); the minutes + per-minute heads now train (low_data_mode cleared, 0 -> trained). New PickerArtifact.predict_real_score recomposes E[real_score]=E[min]xE[rate] as a lognormal product; TRUE walk-forward (train pre-2026, predict 2026, n=1776) corr 0.554 (matches the actual-min ceiling, D55) vs the boost heuristic's 0.246, P10-P90 coverage 0.81. Also Phase 0: CV embargo leak fixed (3d -> window-covering 70d), player_id tree-categorical footgun removed (was latent), eval/multiple_comparisons.py CPCV + deflated-edge guard above the rotation gate. LIVE SERVING UNCHANGED: the deployed artifact (SHA 6182a29d) still has 0 heads and job2 still serves the heuristic ladder; the trained heads are dormant until Phase 2b wires job1 feature persistence + a job2 Tier-0 path. Commits 01a1d15/241b6b5/d792127 on main. Phases 2b-6 remain (see DECISIONS D63). Training command is now `oracle-train --corpus-mode both`. 2026-06-02: Tier 3 built behind GAME_SCRIPT_MINUTES_ENABLED (default OFF, D57) -- role-aware game-script bench-minutes redistribution (features/game_script_minutes.py) + regime-switching same-team copula correlation (picker/sample.py), wired into job2 behind the kill-switch; live freeze byte-identical with the flag off. This is Tier 3 of the D57 draft-winning strategy, built first at operator direction; it rides on the Tier 2 availability engine (not yet built) and currently only moves KNOWN rotation bench players, so it does NOT by itself fix the 06-01 all-longshot bust. 2026-06-01 22:23Z: today's slate frozen with real names + entry=enter (Shepard/Holmes/Siegrist/Horston/McCowan) after fixing a prod OUTAGE (D56): the optimizer's prod defaults (5000 samples x 1000 field x C(30,5)) could not finish in the 15-min cron window, so job2 was killed before freezing every tick -- no picks, and earlier freezes showed "Player <id>" (optimizer picked blank-name boost-3 rookies). Fixed by reducing optimizer knobs to the validated range (~85s). 2026-06-01 build pass also shipped: dynamic team cap (D50); contrarian kept at 0.2 (D51); sampling K=10->2 + per-player sigma (D52); and the MINUTES/ROLE MODEL (D55) -- the real edge (today's freeze matched 48/49 players to nba_api minutes). Proven walk-forward: minutes x rate predicts real_score at corr 0.554 (actual-min ceiling) / 0.355 (recency) vs boost 0.246; real_score is a fixed box formula (R^2 0.957) so the pipeline is self-contained on nba_api. job1 ingests per-player recent_minutes + per_min_rate from stats.wnba.com game logs; job2 uses a boost<->minutes blend with confirmed-starter / injury-cascade / blowout same-day signals. Env kill-switch MINUTES_MODEL_ENABLED. Earlier: CAVEAT_IS_SKIP + stable argsort (D48); recency/EB-over-boost tested and rejected (D52/D54, boost already encodes form). Harnesses: scripts/backtest_walkforward.py, validate_minutes_model.py, test_minutes_placement.py, replay_slate.py.


NEVER_SKIP policy active (default on, D67, formerly D49 in the originating PR): optimizer never recommends sitting out a slate; supersedes CAVEAT_IS_SKIP (a slate that would be demoted to 'skip' is promoted back to 'enter_with_caveat', with the EV signal preserved unchanged).

Player-name resolution hardened (D68, formerly D50 in the originating PR): slate_labels fallback in the freeze + contest-stats parser fallback, closing D49's two open loops so the frozen lineup never ships "Player <id>" placeholders.

# Build status

Set by the build automation. Allowed values: `IN_PROGRESS`,
`BLOCKED_NONFATAL`, `BUILD_COMPLETE`.

Live contest performance is tracked in `RESULTS.md`. First logged slate
(2026-05-28) sat Top 10% / 517th of 8,700 with 2 of 5 picks played.
Finalize a slate without a screenshot via `oracle-results --slate-date
YYYY-MM-DD` (reads frozen_lineups + slate_labels + contest_leaderboards).
DB stores only the top-20, so exact rank / field size still need a
screenshot. See D48.

The 7-day shadow run + watchdog drill are wall-clock operational phases.
All code paths are unit-tested; the manual fire path has been exercised
end-to-end via `scripts/manual_fire.py --fixtures`. The operator starts
the live shadow window via `oracle-rotate-check --window-days 7` after
the live collector has accumulated >= 7 slate labels in `slate_labels`.

## Live services (verified 2026-05-27 05:30 UTC)

- api:       https://api-production-7033.up.railway.app/health -> 200
- api:       https://api-production-7033.up.railway.app/lineup -> 200 (empty)
- frontend:  https://frontend-production-a739.up.railway.app/ -> 200
- postgres:  internal + public TCP proxy (TLSv1.3, SSL enabled 2026-06-05 via
  start-command cert on stock postgres:16-alpine, D61); alembic head =
  20260605_0005 (D64: adds opponent/home_away/game_id matchup fields to
  wnba_game_logs). CANONICAL corpus store:
  slate_labels + contest_leaderboards (141 slates, 2025-05-16..2026-06-04,
  D64 adds 11 recovered 2025 playoff slates Sep 18..Oct 10) +
  wnba_game_logs (13,456 player-games, 2024-05-03..2026-06-05, with
  matchup fields populated at 97.8% -- the 295 NULL-opponent rows are
  exhibition/All-Star/preseason days where Real Sports correctly ran no
  contest). All training, backtest, and analysis scripts now read from
  Postgres via `db.reads` helpers; local parquet files retained as
  archival backups only. Laptop reads via `oracle_ro` (SELECT/INSERT/UPDATE
  on tables, sslmode=verify-ca), connection in gitignored .env
  DATABASE_PUBLIC_URL.
- cron-backup (GitHub Action `corpus-backup`): `43 6 * * *` UTC, exports the
  scraped corpus to the off-`main` `backups` branch (D61). 3-2-1 off-site copy.
- redis:     internal, password-protected
- cron-job1: `0 13 * * *` UTC, oracle-cron --job job1 (next: 2026-05-27T13:00Z)
- cron-job2: `*/15 21-23,0-3 * * *` UTC, oracle-cron --job job2 (next: 2026-05-27T21:00Z)
- cron-dayclose: `0 6 * * *` UTC, oracle-cron --job dayclose (D41; WIRED
  2026-06-05, service id 606d950d, see D60). Fires ~1h after the latest
  plausible WNBA finalization; auto-extends the canonical Postgres corpus
  each fire by walking back N ids from today's max contest id, skipping
  anything not `sport=wnba` and any pregame contest (empty draftStats).
- env-tunable knobs (scope verified 2026-06-01, D53):
  - SHARED (env scope, via ${{shared.KEY}} refs): ENV, LOG_LEVEL,
    PYTHONUNBUFFERED, TZ, PAYOUT_REGIME=top_20, WNBA_ORACLE_MODEL_ARTIFACT_SHA.
  - cron-job2 scope (optimizer): CONTRARIAN_STRENGTH=0.2 (reconciled from a
    drifted 0.3, D53), CONTRARIAN_ENABLED=true, OPTIMIZER_MAX_PER_TEAM=2,
    CAVEAT_IS_SKIP=true. OPTIMIZER_DYNAMIC_TEAM_CAP (true), SAMPLING_SCORE_OFFSET
    (2.0), STARTER_SIGNAL_ENABLED (true), MINUTES_MODEL_ENABLED (true) run on
    code defaults. ARMED on cron-job2 2026-06-02 for the D57 draft-winning
    overhaul: GAME_SCRIPT_MINUTES_ENABLED=true (D57 game-script bench-minutes +
    regime-switching copula), LINEUP_ANCHOR_FLOOR=2 (D58 require >=2
    confirmed-minutes anchors), AVAILABILITY_MODEL_ENABLED=true (D59 P(active)
    collapses cold-start darts). All three reverse via env with no redeploy:
    unset LINEUP_ANCHOR_FLOOR, set the *_ENABLED flags to false (or
    MINUTES_MODEL_ENABLED=false / SAMPLING_SCORE_OFFSET=10 to revert older
    knobs).
  - cron-job1 now also pulls stats.wnba.com game logs (nba_api) for the D55
    minutes features; a stats.wnba.com outage degrades gracefully (job2 falls
    back to boost). Watch the job1 log key n_minutes_matched.
  - DATABASE_URL / REDIS_URL are service references; never literals.
- env-tunable knobs at cron-job2 service: CAVEAT_IS_SKIP=true (set
  2026-05-29 per D48; demotes `enter_with_caveat` to `skip` on
  marginal-EV slates). Now superseded at runtime by NEVER_SKIP (D49):
  while NEVER_SKIP is on, no slate is demoted to `skip` regardless of
  CAVEAT_IS_SKIP. Operator may unset CAVEAT_IS_SKIP to avoid confusion.
- NEVER_SKIP=true is the new code default (D49). The optimizer never
  emits `skip`; sub-breakeven slates surface as `enter_with_caveat`.
  Set NEVER_SKIP=false to restore the D48 three-state behavior.

## Historical corpus (updated 2026-06-05)

All corpus data lives in Postgres (the canonical store). Local parquet
files under `data/historical/` and `data/processed/` are archival backups
only and are no longer read by any script.

- `slate_labels`: 130 finalized slates (2025-05-16..2026-06-04), deduped
  by player per contest.
- `contest_leaderboards`: top-20 finisher lineups per slate.
- `wnba_game_logs`: 13,435 player-games across 2024-2026 seasons (454
  players), sourced from stats.wnba.com via nba_api.

All reads go through `src/wnba_oracle/db/reads.py` (D62):
`read_training_corpus()`, `read_slate_labels()`, `read_leaderboards()`,
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
| Job1 fails with StorageStateStale | JWT inside REALSPORTS_STORAGE_STATE_B64GZ rotated. Re-run `scripts/realsports_login.py` locally and re-seed the env var on cron-job1 + cron-job2 (NEEDS_HUMAN item 6) |
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

- **RotoWire lineups fetched but not persisted** (NEEDS_HUMAN item 7):
  `job1.py:114` calls `fetch_lineups()` and counts the result for the
  log line, but the rows aren't written to `job1_enrichment`. The
  injury-cascade port (D33) only fires through `features/build.py`
  which the live cron path never calls. Impact for tomorrow: players
  RotoWire flags OUT still draft into the optimizer pool; minutes
  redistribution does not apply. The lineup will still ship with
  reasonable picks (boost + Vegas signals carry it), just without the
  injury-aware adjustment.

- **Job2 `_freeze` is not strictly idempotent** (NEEDS_HUMAN item 8):
  The Redis SETNX guards the lock metadata but the Postgres UPSERT
  fires every invocation. Subsequent cron-job2 fires within the same
  slate window can replace the frozen lineup if new draft data arrives
  via slate_labels and shifts the contrarian adjustment. Documented
  intent vs. behavior mismatch — should either skip the UPSERT when
  the lock is held, or accept the refresh-as-data-arrives semantics
  and rename "freeze" everywhere.

- **Watchdog not wired** (NEEDS_HUMAN item 9): `scheduler/watchdog.py`
  is a stub returning `[]` and is not called from `cron.py`. Operator
  must read Railway logs manually for failure detection until the
  watchdog + alerting path lands.

## Quality gates

- 81 unit tests pass (was 77; added 4 in `test_per_player_frozen.py`).
- ruff + mypy on `src/` clean (project config; `--strict` flagged
  pre-existing dict-type-args lint, non-blocking).
- 57 source files in `src/wnba_oracle/`.
- 6 basketball-main patterns ported with zero new external dependencies.
- Frontend bundle: 209KB / 66KB gz, builds in ~470ms.

The eval/ bundle is seeded with placeholder JSON. It auto-populates once
the live collector accumulates enough slates (Part 0.4 deliverable list).
