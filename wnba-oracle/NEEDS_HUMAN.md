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
   _Wall-clock blocker; depends on the cron pipeline accumulating
   data._

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

7. **Wire RotoWire lineups into the live cron path.** Surfaced by the
   2026-05-27 deep audit. `scheduler/job1.py:114` fetches RotoWire
   lineups but only logs the count; the rows are never written to
   `job1_enrichment`. The injury-cascade port (D33) lives inside
   `features/build.py::_build_cascade_inputs` which is never called
   from the cron path — only from `features/parity.py` and unit
   tests. Result: in production tomorrow, players RotoWire flags OUT
   still draft into the optimizer pool and the minutes redistribution
   has no effect. Likely fix: have job1 write a `rotowire_lineups`
   JSONB column (or a separate table), and have job2 call
   `build_slate_features` instead of going directly to `_load_enrichment`.
   Estimate: 3-5 hours including a parity test on a captured slate.

8. **Decide on job2 freeze semantics.** `scheduler/job2.py:_freeze`
   takes the Redis SETNX as advisory but unconditionally UPSERTs the
   Postgres row, so subsequent cron-job2 fires within the same slate
   window will replace the frozen lineup if any input (especially
   measured draft popularity from slate_labels) changes. Either: a)
   gate the UPSERT on `lock_acquired` so the first freeze sticks; or
   b) accept refresh-as-data-arrives and rename the column / logs to
   reflect intent. Tomorrow's first slate is fine with either choice.

9. **Add cron failure alerting.** `scheduler/watchdog.py` is a stub.
   Until the operator implements an alerting hook (Railway-native
   webhooks, email, Slack), cron failures must be detected by reading
   Railway logs by hand. Minimum viable: a 24h "lineup never frozen"
   email triggered by a small cron service that GETs /lineup at
   23:00 UTC and pages if 404.
