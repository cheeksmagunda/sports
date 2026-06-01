# Items requiring human action

Each entry: date, blocker, what was tried, what unblocks it. Empty list is
the desired state. Items here never block the build; the autonomous loop
proceeds with everything that does not depend on the blocked item.

(no open items)

---

## Operator action items

These are not strict NEEDS_HUMAN entries - the build works without them.

1. **Seed REALSPORTS_STORAGE_STATE_B64GZ on Railway.** [DONE 2026-05-27]
   Set on cron-job1 + cron-job2.

2. **Pin a stable WNBA_DEVICE_UUID env var on each cron service.** [DONE
   2026-05-27] Pinned to the UUID captured during first login.

3. **Stand up a corpus parquet from cumulative `slate_labels` rows once
   the live collector has ~30 slates of data** (~2-3 weeks). Then run
   `oracle-train` against that parquet, set the resulting SHA on
   `WNBA_ORACLE_MODEL_ARTIFACT_SHA`, and start the shadow window.
   **[PARTIAL 2026-05-27]** Historical corpus seeded via
   `oracle-backfill --mode historical --parquet-out-dir data/historical`
   for the 16 finalized 2026 WNBA slates (cid 1755..1831). Local parquet
   is ready; still need (a) Railway migration `20260527_0003` applied
   so the Postgres tables match the local schema and (b) the same
   backfill run with DATABASE_URL pointed at Railway to UPSERT into
   `slate_labels` + `contest_leaderboards` on prod. After that, the
   ~30-slate threshold is still a wall-clock blocker — 16 down, ~14
   to go at the live collector's accumulation rate. See D38.

4. **Tune `CONTRARIAN_STRENGTH` env var once you have 7-14 finalized
   slates.** Default 0.2 (basketball-main NBA value). [WIRED 2026-05-27]
   Operator can flip the value on Railway without a code deploy. Tune
   up to 0.3 in top-1 regime (variance is asset), down to 0.1 in
   cash games.

5. **Wire RotoWire `injury_status` into `features/build.py`.** [DONE
   2026-05-27] Hookup landed in commit `797ceac` per D33.

6. **Re-seed REALSPORTS_STORAGE_STATE_B64GZ when the JWT expires.**
   Real Sports JWTs last several months but eventually rotate. When
   cron-job1 starts logging StorageStateStale, re-run
   `scripts/realsports_login.py` locally, then re-encode + push:
   ```
   uv run python scripts/realsports_login.py
   B64GZ=$(gzip -c scraper/storage_state.json | base64 | tr -d '\n')
   # Update REALSPORTS_STORAGE_STATE_B64GZ on cron-job1 + cron-job2
   ```
   After hardening (D35) only cron-job1 needs this variable; cron-job2
   no longer authenticates and the var was dropped from its env.

7. **[DONE 2026-05-27]** Wire RotoWire injury_status into the live
   cron path. job1 now matches each Real Sports pool entry to
   RotoWire's lineup index by ``(team, normalized_name)`` and persists
   ``injury_status / is_out / is_starter / starter_slot /
   rotowire_confirmed`` into ``features_json``. job2 reads
   ``is_out`` and excludes those players from the optimizer pool
   before contrarian + game-script adjustments fire. The full D33
   minutes-redistribution cascade still needs ``mins_l10`` from
   game-log ingest (not yet on prod path); the binary
   drop-OUT-players is the highest-value half and is now active. See
   D37(a).

8. **[DONE 2026-05-27]** job2 freeze is now strictly idempotent. The
   ``frozen_lineups`` row is canonical state: an existence check by
   ``(slate_date, model_sha)`` short-circuits before Redis. Redis
   SETNX is now a fast soft-lock against intra-window races, not a
   freshness gate. ``INSERT ... ON CONFLICT DO NOTHING RETURNING id``
   means we never accidentally replace a frozen row. See D37(b).

9. **[PARTIAL 2026-05-27]** Watchdog now ships with real checks +
   operator-facing API. ``run_watchdog(slate_date)`` evaluates four
   triggers (``no_job1_pool`` / ``pool_too_small`` /
   ``no_frozen_lineup`` / ``missing_per_player`` /
   ``zero_expected_payout``) after every cron-job2 fire, persists
   deduplicated events to ``watchdog_events``, and exposes them at
   ``GET /watchdog/today``. Operator can poll
   ``curl https://<api>/watchdog/today | jq .status`` from anywhere
   without log access. **Remaining work**: external push alerting
   (email / Slack / Discord webhook) is still manual — the operator
   must opt in by polling the endpoint or wiring a UptimeRobot
   monitor that watches ``.status != "ok"``. See D37(c).

10. **[CODE DONE 2026-05-27]** Day-close corpus extension. Logic landed
    in `scheduler/job_dayclose.py`, dispatched via
    `oracle-cron --job dayclose` (D41). Smoke-tested locally. **Operator
    action**: on Railway, create a third cron service `cron-dayclose`:
    - Start command: `oracle-cron --job dayclose`
    - Cron: `0 6 * * *` UTC
    - Env vars: inherit the same shared vars as cron-job1
      (REALSPORTS_STORAGE_STATE_B64GZ, WNBA_DEVICE_UUID for Playwright
      auth) plus the shared DATABASE_URL. `WNBA_CORPUS_PARQUET_DIR` is
      optional (only useful if you want a Railway-side parquet snapshot;
      Postgres is the canonical store).
    Also apply alembic upgrade head on prod Postgres so migration
    `20260527_0003_contest_leaderboards` lands before the first
    dayclose fires.

11. **[NEW 2026-05-27]** Wire the trained model artifact into the
    serving picker. D44 produced a working EB hierarchical baseline
    artifact (`models/picker_cfe5868_1779880756.pkl`, SHA
    `db18f6c9...`) trained on 121 slates / 2980 rows. D45 found
    `job2.run()` only uses `WNBA_ORACLE_MODEL_ARTIFACT_SHA` as a
    freeze tag, never loading the pickle. To make trained predictions
    actually serve tonight (or any future night), `_build_specs` needs
    to call `train.pipeline.load_artifact(...)` and use
    `art.eb_baseline.predict(player_id, cohort)` in place of
    `_heuristic_real_score`. The pickle also needs to be shipped with
    the deploy (currently `models/*.pkl` is gitignored — either
    un-ignore the production artifact or download from object
    storage at startup).

12. **[NEW 2026-06-01] Prediction-quality lever: wire the
    confirmed-starter / minutes signal into the live predictor.** D51
    found our leaderboard gap is dominated by prediction resolution
    (Spearman 0.37, top-5 recovers 2.44/5 of the realized top-8), not
    by the contrarian tilt or (now-fixed) stacking. job1 ALREADY
    persists `is_starter`, `starter_slot`, `rotowire_confirmed` into
    `features_json`, but job2's `_build_specs` reads only `is_out`.
    Minutes is the dominant driver of real_score. Proposed first step
    (cheap, data already present): a `starter_signal_multiplier` applied
    to `pred_real_score` in `_build_specs`, mirroring
    `game_script_multiplier` — confirmed starters up, confirmed bench
    down. Follow-ons: real box-score features from the `stats_wnba`
    (nba_api) ingest (recent real_score form, opponent defense, pace);
    per-player `sigma` instead of the flat 0.25 (starters lower-variance,
    boost/bench plays higher-variance) so ceiling plays are priced for
    the top-heavy payout; and softening the `K=10` log-offset in
    `sample.py` that compresses the right-skew where boom games live.
    **Why operator-gated, not shipped here**: honest measurement needs a
    walk-forward backtest (retrain EB on slates < N for each test slate
    N). The current 16-slate backtest has EB leakage (D45), so a
    prediction change cannot be validated offline on it. Build the
    walk-forward harness first (the `cv_splitter` + `oracle-train`
    pieces exist), then iterate the signals against it.
