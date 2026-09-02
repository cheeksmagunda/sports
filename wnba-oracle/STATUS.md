# Status

Last verified: 2026-09-02T06:39:21Z

This file records live operational state only. Values marked unverified were
not exposed by the read-only checks available during this audit.

## Live operational snapshot

- Deployment state: The public API at
  `https://api-production-7033.up.railway.app` responded to `/health` with
  `{"status":"ok","version":"0.1.0"}`. Railway service and deployment state:
  unverified because the Railway CLI had no linked project and no process
  authentication capability was configured.
- Active source commit(s): GitHub `main` is
  `0175764fff2a6df6a54e83cb2d581137014575bf` as of this verification. The
  source commit served by Railway is unverified.
- Model artifact and SHA: GitHub repository variable
  `WNBA_EXPECTED_MODEL_SHA` is set to
  `94f8e8606dab4d48652929bb3884fb9152e1abc766eeb2c2d86559f4318676cd`.
  The artifact loaded by the live API is unverified.
- Service and schedule state: The live watchdog endpoint reported `status=ok`
  with no events for slate date `2026-09-02`. The durable job endpoint reported
  no job1, job1late, job1games, job2, or backfill record; day-close for
  `2026-09-01` was `degraded` with `placement_capture` degraded and exit code
  `2`. GitHub workflows for watchdog, pre-freeze, day-close, and enrichment
  backfill are active. Railway schedules and service-level state are
  unverified.
- Current incidents and production risks: There is no current watchdog event
  in the live API response. The latest watchdog workflow succeeded, but the
  preceding five recorded runs failed between 2026-09-01 and 2026-09-02.
  Placement capture remains degraded for the latest day-close, and no current
  slate timing or frozen lineup was available from `/slate/2026-09-02` or
  `/lineup/2026-09-02`.

Development plans, branch history, check output, decisions, and completed work
belong in GitHub Issues and Pull Requests, not this file.
