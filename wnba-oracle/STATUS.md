# Status

Last verified: 2026-09-02T09:30:00Z

This file records live operational state only. Values marked unverified were
not exposed by the read-only checks available during this audit.

## Live operational snapshot

- Deployment state: All 9 Railway services in the `production` environment
  (api, cron-job1, cron-job1-late, cron-job2, cron-dayclose,
  backfill-enrichment, frontend, redis, postgres) report `SUCCESS` on the
  latest deployment. The public API at
  `https://api-production-7033.up.railway.app` responded to `/health` with
  `{"status":"ok","version":"0.1.0"}`.
- Active source commit: `6f466cf9d17cae9ffac74732e33d7df9f374ea2` on GitHub
  `main`. Confirmed via Railway's own deployment record for every service
  above (each service's active deployment cites this commit).
- Model artifact and SHA: production model SHA is
  `7b06b6f98d0bb0cd69d4b12c49c5c97102b39eb30734c586f9d1f02ab69f1da2`
  (`wnba-oracle/models/picker_95264ce9_1788339935.pkl`), set as
  `WNBA_ORACLE_MODEL_ARTIFACT_SHA` on `cron-job2` (the only role that requires
  it per `_PRODUCTION_ROLE_REQUIREMENTS`) and confirmed applied via a real
  redeploy (not `--skip-deploys`). GitHub repository variable
  `WNBA_EXPECTED_MODEL_SHA` matches. This is a full-refit retrain on
  `main@6f466cf` (season_game_number train/serve parity fixed, causal
  point-in-time pace, pooled-F cohort, calibrators disabled at serving);
  incumbent architecture, selected over a challenger artifact after a paired
  104-slate tournament showed no statistically significant improvement. The
  WNBA season is on a break, so no live post-promotion slate freeze has run
  yet under this artifact; the most recent frozen lineup
  (`slate_date=2026-08-30`) correctly still shows the prior `model_sha`
  (`94f8e8606dab4d48652929bb3884fb9152e1abc766eeb2c2d86559f4318676cd`), since
  frozen lineups are immutable history and predate this promotion.
- Rollback: previous production artifact
  `wnba-oracle/models/picker_bf3c8996_1780752059.pkl` (sha256
  `94f8e8606dab4d48652929bb3884fb9152e1abc766eeb2c2d86559f4318676cd`) and the
  tournament-tested `wnba-oracle/models/picker_e2ced9ec_1780873338.pkl` are
  both retained in the repository. Previous `api` deployment
  `f83dd705-b9ca-47ee-a02f-aa166a346a0e` (source `6f466cf`, pre-model-SHA-swap)
  and the last known-good pre-this-push deployment on source `38ba732` remain
  available as rollback targets through Railway's deployment history.
- Service and schedule state: watchdog `/watchdog/today` reports
  `status=ok`, no events, for `slate_date=2026-09-02`. Verified live:
  `/slate/{date}`, `/lineup/{date}`, `/lineup/{date}/history`, and
  `/dossier/{date}` all return correctly for the last finalized slate
  (2026-08-30). That lineup's team/game distribution (5 players, 5 distinct
  teams, 4 distinct games, 2-1-1-1 split) matches the hard anti-stacking
  policy for a four-game slate, confirming the diversification policy is
  active in production. The WNBA season is on a break; no current slate
  exists, so a first post-break live freeze under the new artifact remains
  naturally pending.
- Current incidents and production risks: none open. The prior day-close
  degradation and watchdog failures noted in the previous snapshot
  (2026-09-01) predate this push's fixes and were not re-observed in this
  verification. Known residual limitation: the offline model tournament used
  a documented offline feature-reconstruction path
  (`--game-logs-csv`/`--game-identity-csv`) rather than the live DB read path,
  which has a separate, pre-existing schema mismatch
  (`read_game_identity()`/`index_game_identity()`) not touched by this push;
  see issue #53's final comment for detail.

Development plans, branch history, check output, decisions, and completed work
belong in GitHub Issues and Pull Requests, not this file.
