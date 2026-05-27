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
