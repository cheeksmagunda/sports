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

10. **[DONE 2026-06-05]** Day-close corpus extension. Logic landed
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

    **Wired 2026-06-05** (see D60): created Railway service `cron-dayclose`
    (id 606d950d) from cheeksmagunda/wnba-oracle, RAILPACK, start
    `sh -c 'python /app/scripts/seed_storage_state.py && oracle-cron --job
    dayclose'`, cron `0 6 * * *` UTC, restart NEVER. Secrets set as
    cross-service references to cron-job1 (DATABASE_URL,
    REALSPORTS_STORAGE_STATE_B64GZ, REAL_SPORTS_USERNAME/PASSWORD); device
    + non-secret vars literal. The alembic migration runs via the service
    pre-deploy command (`alembic upgrade head`, idempotent) so
    contest_leaderboards lands before the first write. WNBA_CORPUS_PARQUET_DIR
    intentionally unset (Postgres canonical; local parquet refreshed
    off-Railway on demand).

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

12. **[MINUTES MODEL SHIPPED 2026-06-01, D55] Prediction-quality lever.**
    The minutes/role edge is built and live: job1 ingests per-player
    recent_minutes + per_min_rate from stats.wnba.com game logs (real_score
    reconstructed from the box line, R^2 0.957), job2 blends boost<->minutes
    with confirmed-starter / injury-cascade / blowout signals. Validated
    walk-forward: minutes x rate corr 0.554 (actual-min ceiling) vs boost
    0.246. Kill-switch MINUTES_MODEL_ENABLED.
    **Remaining to maximise the edge (operator / next build):**
    a. LIVE CALIBRATION. The big same-day lift (toward the 0.554 ceiling)
       can't be backtested on the corpus (no historical RotoWire/Vegas).
       Tune the starter/bench anchors (MinutesConfig.starter_minutes 30 /
       bench_minutes 13 / confirm_weight 0.6) and the cascade
       redistribution_rate against live results as they accumulate. Watch
       the job1 `n_minutes_matched` and job2 `n_minutes_predicted` log keys.
    b. Field simulator stacks. `picker/field.py` samples opponents by
       independent ownership picks, so it never produces a stacked opponent;
       on <=2-game slates the real field stacks heavily, so EV/leverage is
       mispriced there. Add correlated (game-stack) field lineups.
    c. Payout regime. "Win a ~9k-entry field" is the convex top_1 shape, not
       the top_20 (20th-pct cash line) we run. Product decision (numBrawlers
       is 0 pregame, D48).
    d. Multi-entry VOLUME. If Real Sports allows >1 entry per contest, a
       portfolio of differentiated +EV lineups is the single biggest
       multiplier on the edge (D54). Verify the entry rules first.
    e. Wire the dayclose cron on Railway (item 10) so the minutes/rate
       history and slate_labels keep extending without manual backfills.

13. **[NEW 2026-06-01, D56] Two follow-ups from the freeze outage:**
    a. VECTORIZE `picker.payout.expected_payout`. It loops over samples in
       Python, which forced the emergency knob reduction (n_samples 5000->1000
       etc.) to fit the 15-min cron window. Vectorizing the rank/payout step
       (one numpy pass over the (n_field, n_samples) array) would let us
       restore high sample counts with no window risk. Verify numerical
       equivalence against the scalar version before shipping.
    b. RotoWire `wnba-lineups.php` returned 404 on 2026-06-01 (job1
       `job1_lineups_failed`). job1 degrades gracefully (no OUT filtering, no
       confirmed-starter signal -> minutes model uses the recency baseline),
       but that is HALF the minutes edge (same-day role). Check whether the
       RotoWire URL/markup changed and fix `ingest/rotowire.py`. Watch the
       job1 `n_matched` (RotoWire) and `n_minutes_matched` (nba_api) keys.

14. **[NEW 2026-06-02, D57] `make determinism-check` is silently broken (pre-
    existing, NOT Tier 3).** Two bugs: (a) `oracle-train` truncates `--commit`
    to 8 chars in the artifact filename (`dev_determ_1` -> `picker_dev_dete_*`),
    but the Makefile `find ... picker_*dev_determ_1*.pkl` looks for the full
    string, matches nothing, and `mv` errors before any comparison runs (both
    test commits even truncate to the same `dev_dete`). (b) The assertion
    compares pickle SHAs, but LightGBM Booster pickles are NOT byte-stable even
    when the trained model content is identical, so the check would FAIL on
    deterministic training. Fix: compare model CONTENT (per-array
    `np.array_equal` over heads + eb_baseline), not pickle bytes, and use commit
    prefixes that survive the 8-char truncation (or stop truncating in
    `train.pipeline.write_artifact`). Verified 2026-06-02 that training IS
    content-deterministic; only the gate is wrong.

15. **[ARMED 2026-06-02, D57] Tier 3 armed on cron-job2 (GAME_SCRIPT_MINUTES_ENABLED=true). Still tune the priors + validate; monitor the first fire.**
    `GAME_SCRIPT_MINUTES_ENABLED` is OFF by default. The constants (blowout ramp
    soft=8 / hard=18 pts, `starter_trim_fraction`=0.18, `redistribution_rate`
    =0.70, copula rhos +0.30 / -0.35 / -0.10) are PRIORS. Tune them once (a)
    historical Vegas spreads are in the corpus and (b) the availability/minutes
    engine (Tier 2) lands underneath. Tier 3 rides on that engine and currently
    only moves KNOWN rotation bench players (cold-start darts have no recent
    minutes so they are untouched, which is why this alone does not fix the
    2026-06-01 all-longshot bust). To turn on for a live A/B once validated: set
    `GAME_SCRIPT_MINUTES_ENABLED=true` on cron-job2 (also auto-disables the blunt
    team-wide blowout penalty). Reverse: unset it.

16. **[ARMED 2026-06-02, D58] Tier 1 anchor-floor seatbelt armed on cron-job2 (LINEUP_ANCHOR_FLOOR=2). Monitor the first fire (optimizer_stage2 keys).**
    Set `LINEUP_ANCHOR_FLOOR=2` on the cron-job2 Railway service (env, no
    redeploy, instant rollback by unsetting). This forces every frozen lineup to
    contain >= 2 confirmed-minutes anchors, so it can never again be 5 cold-start
    darts (the 2026-06-01 bust). It can never forfeit a slate (clamps + relaxes
    if infeasible). Built default-OFF only out of D56 caution (it changes the
    live optimizer enumeration); validated by unit tests but not yet on a live
    slate, so watch the first armed fire's `optimizer_stage2` log keys
    (`skipped_anchor_floor`, `effective_min_anchors`). CAVEAT: this forces a
    floor but does not pick the RIGHT ceiling darts (Kosu vs Holmes), which is
    Tier 2 (availability model). Necessary, not sufficient.

17. **[NEW 2026-06-02, D59] Deferred Tier 2 follow-ups (not blocking tonight).**
    The availability model (P(active), AVAILABILITY_MODEL_ENABLED) shipped;
    three Tier-2 pieces remain:
    a. REAL OWNERSHIP INGESTION from the Real Sports Daily Draft Stats panel
       (the in-app draft counts: 3k / 1k / 384 / 13 ...). Feed true field
       ownership into the field simulation (draw opponent lineups from real
       ownership, not a softmax over our own projections) and into a leverage
       term (ceiling x (1 - ownership)) to replace the flat contrarian penalty.
       Needs a new job1 scrape + parser; do NOT rush it live (RotoWire-404
       fragility class).
    b. WIN-EQUITY OBJECTIVE: optimize an upper-quantile / P(score >= winning
       threshold) term for the top-heavy payout, not just mean EV.
    c. MIXTURE-VARIANCE sampling: gate each player's copula draw by a seeded
       Bernoulli(P(active)) so the bimodal spike-at-zero is modeled, not just
       the mean (tonight uses the expectation form).
    North-star to measure all of this: realized leaderboard RANK on the corpus
    (build the replay harness on scripts/replay_slate.py).
