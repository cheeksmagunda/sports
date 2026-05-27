# Items requiring human action

Each entry: date, blocker, what was tried, what unblocks it. Empty list is
the desired state. Items here never block the build; the autonomous loop
proceeds with everything that does not depend on the blocked item.

(no open items)

---

## Operator action items (not blockers, but worth doing)

These are not strict NEEDS_HUMAN entries — the build works without them —
but the operator may want to act on each within the first month of live
operation.

1. **Seed REALSPORTS_STORAGE_STATE_B64GZ on Railway.** The first cron-job1
   fire on Railway needs `scraper/storage_state.json` populated. Run the
   local login + encode flow once, then set the env var on cron-job1 and
   cron-job2.
   ```
   uv run python scripts/realsports_login.py
   gzip -c scraper/storage_state.json | base64 | tr -d '\n'
   # set the result on Railway cron-job1 + cron-job2 as REALSPORTS_STORAGE_STATE_B64GZ
   ```

2. **Pin a stable WNBA_DEVICE_UUID env var on each cron service.** Cold
   captures generate a fresh UUID each time; without a pinned value the
   Real Sports JWT 401s on the next fire. Use the UUID captured during
   the first successful login.

3. **Stand up a corpus parquet from cumulative `slate_labels` rows once
   the live collector has ~30 slates of data** (~2-3 weeks). Then run
   `oracle-train` against that parquet, set the resulting SHA on
   `WNBA_ORACLE_MODEL_ARTIFACT_SHA`, and start the shadow window.
