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

1. **Seed REALSPORTS_STORAGE_STATE_B64GZ on Railway.** [DONE 2026-05-27]
   Already set on cron-job1 + cron-job2.

2. **Pin a stable WNBA_DEVICE_UUID env var on each cron service.** [DONE
   2026-05-27] Pinned to the UUID captured during the first successful
   Real Sports login.

3. **Stand up a corpus parquet from cumulative `slate_labels` rows once
   the live collector has ~30 slates of data** (~2-3 weeks). Then run
   `oracle-train` against that parquet, set the resulting SHA on
   `WNBA_ORACLE_MODEL_ARTIFACT_SHA`, and start the shadow window.

4. **Tune `ContrarianConfig.strength` once you have 7-14 finalized
   slates.** Default is 0.2 (basketball-main NBA value). WNBA may
   warrant a different magnitude given the smaller player pool and
   higher chalk concentration. The picker exposes the parameter via
   `_build_specs` in `scheduler/job2.py`; the simplest first
   experiment is to run shadow with strength=0.3 and compare RBO@5
   against the default.

5. **Wire RotoWire `injury_status` into `features/build.py`** so the
   injury-cascade module (D29) starts injecting bonus minutes into the
   feature matrix. The pieces are already in place:
   `ingest.rotowire.LineupEntry.injury_status` exists, and
   `features.injury_cascade.redistribute_minutes` accepts
   `CascadeInput(is_out=True)`. The hookup is ~20 LOC in
   `build_slate_features`.
