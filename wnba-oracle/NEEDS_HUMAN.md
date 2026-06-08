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

3. **[DONE 2026-06-07]** Stand up corpus + train + deploy. 13,002-row corpus
   built from wnba_game_logs with team_pace + opp_dvp enrichment (D77).
   Heads trained on cohort F, artifact picker_e2ced9ec (SHA 94f8e860...) deployed
   to all three services (D79 manual promotion). `oracle-rotate-check` runs
   against shadow rows as they accumulate; next retrain when corpus grows
   materially or a new feature set is validated.

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

11. **[AWARENESS 2026-06-05, D61]** New self-issued credentials + one caveat.
    - `oracle_ro` Postgres role (SELECT-only) password lives in local `.env`
      (DATABASE_PUBLIC_URL) only. Rotate at will: `ALTER ROLE oracle_ro
      PASSWORD '...'` then update .env + the GH secret.
    - Postgres TLS keypair in `.pgssl/` (gitignored) and Railway env
      `PG_SSL_CERT_B64` / `PG_SSL_KEY_B64`. Self-signed, 10y.
    - The nightly `corpus-backup` GitHub Action needs two repo secrets:
      `BACKUP_DATABASE_URL` (oracle_ro URL, sslmode=verify-ca) and
      `PG_SSL_ROOT_CERT` (the .pgssl/server.crt contents). Set this session.
    - CAVEAT: the public TCP proxy host:port (acela.proxy.rlwy.net:NNNNN) can
      change if the proxy is recreated. If laptop/CI connections start failing,
      re-read it from Railway and update .env + the `BACKUP_DATABASE_URL` secret.

11. **[DONE 2026-06-06, D69]** Wire trained model into serving. job2 Tier-0
    path batch-runs the LightGBM heads via PickerArtifact.predict_real_score;
    confirmed-starter multiplier (D71) and prop-signal multiplier (D78) applied
    on top. Artifact committed by gitignore exception; loaded at startup.

12. **[SHIPPED D55/D63-D78] Prediction-quality lever -- live.**
    Minutes model live (D55), decomposed heads trained and serving Tier-0 (D69),
    confirmed-starter multiplier (D71), prop-signal multiplier (D78), availability
    model calibrated (D73). Remaining deferred items:
    a. LIVE CALIBRATION. Tune MinutesConfig starter/bench anchors against
       accumulated live results. Watch job1 `n_minutes_matched` + job2
       `n_minutes_predicted`.
    b. Real ownership ingestion from the Real Sports Daily Draft Stats panel
       (true field ownership -> leverage term + field simulation). See D59.
    c. Multi-entry VOLUME. Verify whether Real Sports allows >1 entry per
       contest; if so, portfolio of differentiated lineups is the biggest EV
       multiplier (D54).
    d. [DONE 2026-06-05, D60] Dayclose cron wired on Railway.

13. **[PARTIAL, D56] Two follow-ups from the freeze outage:**
    a. VECTORIZE `picker.payout.expected_payout`. Loops over samples in Python;
       vectorizing would let n_samples return to 5000 without cron-window risk.
       Verify numerical equivalence before shipping. (Deferred -- current knobs
       fit in the 15-min window.)
    b. **[DONE 2026-06-07, D74]** RotoWire URL fixed (/basketball/ -> /wnba/).
       Watch job1 `n_matched` to confirm lineup data flows again.

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

15. **[LIVE, D57]** GAME_SCRIPT_MINUTES_ENABLED=true on cron-job2. Role-aware
    blowout bench-minutes redistribution + regime-switching copula. Priors
    (blowout ramp soft=8/hard=18 pts, starter_trim_fraction=0.18,
    redistribution_rate=0.70) are empirical starting points; tune against live
    results once Vegas spread data accumulates in corpus.

16. **[LIVE, D57/D58]** LINEUP_ANCHOR_FLOOR=2 on cron-job2. Forces >= 2
    confirmed-minutes anchors in every frozen lineup. Monitor
    `optimizer_stage2` keys (`skipped_anchor_floor`, `effective_min_anchors`)
    in job2 logs.

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

18. **[NEW 2026-06-08, D81] cron-job1-late service added.** A clone of cron-job1
    (id `2b0cd5aa-8793-45a5-bca0-e81c6d8455ff`) fires `35 22 * * *` UTC to refresh
    enrichment with RotoWire CONFIRMED lineups before the 23:00 job2 re-freeze.
    Env is set via cross-service references to cron-job1, so re-seeding
    REALSPORTS_STORAGE_STATE_B64GZ on cron-job1 (item 6) automatically covers it.
    NOTE: destructive Railway ops are denied at the settings layer, so this
    service cannot be deleted with the project token -- to retire it, clear its
    cron schedule or pause it in the dashboard. Monitor at 22:35 UTC: job1_done
    log line + `rotowire_confirmed > 0` in job1_enrichment for the slate.

19. **[NEW 2026-06-08, D80] Player-prop credit budget.** fetch_player_props now
    spends ~1 Odds API credit per game per run (slate-scoped, player_points
    only). Two job1 runs/day (13:00 + 22:35) x ~3 games ~= 180-300 credits/mo
    against the 500 free-tier cap, plus game odds. If the slate grows or a third
    daily run is added, watch `x-requests-remaining` in job1 `player_props_quota`
    logs; props degrade to empty (no crash) on quota burn.
