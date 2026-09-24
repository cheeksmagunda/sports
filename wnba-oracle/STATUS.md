# Status

Last verified: 2026-09-24T18:15:00Z

This file records live operational state only. Values marked unverified were
not exposed by the read-only checks available during this audit.

## Stopped using GitHub issues as permanent ledgers/incident trackers (2026-09-24, issue #283, PR #284)

`wnba-dayclose-verify.yml` and `watchdog-monitor.yml` previously used issues
as permanent application state: #2 (WNBA results ledger) was appended to
forever with no close path, and #243 (WNBA Oracle watchdog alert) had no
code path to close itself even after a healthy run; the two workflows also
silently shared one issue by label only (`ops-guard`, no title check), so a
day-close report could land in what was meant to be the watchdog's own
alert issue and vice versa.

Fixed via the shared `dayclose-ledger` composite action (NFL already used
it; WNBA's inlined copy of the same logic was replaced with it for parity):
results digests now post to the job's step summary, not an issue; the guard
issue is matched on label and exact title together; it now closes itself
with a resolution comment on the next healthy run.
`watchdog-monitor.yml` also separates a probe *execution* failure from a
real *production* alert into two distinct, independently closeable
trackers, and captures the probe's stdout/stderr into its fallback report
instead of failing silently, in case it crashes again.

#2 was closed directly (nothing writes to it going forward). #243 will
close itself the next time `watchdog-monitor` runs clean under the new
logic; it does not need a manual close.

## 2026-09-24 update: billing outage recovery, T-40 readiness (issue #281)

GitHub billing-locked the account from 2026-09-20 to 2026-09-24, blocking
every Actions run and Codespace start; see `nfl-oracle/STATUS.md` for the
portfolio-wide incident detail (it is one GitHub account, not a WNBA-only
issue). Operator restored billing 2026-09-24. Re-checked live this session:

- All 9 `production` Railway services report a status; 8 `SUCCESS`, one
  known `FAILED` (`backfill-enrichment`, unchanged, see below). `api`,
  `cron-dayclose`, `cron-job1`, `cron-job1-late`, `cron-job2`, and `frontend`
  are all on the 2026-09-20T20:36:50Z deploy (`c20b54c`, the #268 fix); this
  superseded the 2026-09-19T08:xx deploys referenced below. `main` has since
  moved to `d44df18` (nfl-oracle-only artifact/doc change); not reverified
  whether that triggered a new WNBA redeploy.
- `/health`, `/watchdog/today`, and `/slate/2026-09-24` on the public API all
  responded clean: no watchdog events today, tonight's slate has
  `first_tip_utc=2026-09-24T23:00:00Z`, `freeze_target_utc=2026-09-24T22:20:00Z`,
  `picks_paused=false`.
- New, not yet root-caused: the `watchdog-monitor` GitHub Actions workflow's
  own probe script (`wnba-oracle/scripts/watchdog_monitor.py`) crashed (exit
  1, under 2s, no report) on today's rerun, which is why it still fails CI
  and why #243 stays open. That is a probe-script failure, not a live alert;
  the manual checks above are clean. Worth a fresh look before trusting the
  next scheduled run.

## Live operational snapshot (as of 2026-09-19T09:46:42Z; superseded in part above)

- Deployment state: 8 of 9 Railway services in the `production` environment
  report `SUCCESS` on their active deployment: `api`, `cron-job1`,
  `cron-job1-late`, `cron-job2`, `cron-dayclose` (all redeployed
  2026-09-19T08:06:34Z), `frontend` (2026-09-19T08:15:59Z), `redis`, and
  `postgres`. `backfill-enrichment` is `FAILED`: two consecutive build
  attempts at 2026-09-19T04:27Z on source `c1facd04530ef41099d4db0c6aa184220ecf060d`
  (2026-08-22, unchanged since its last successful build on that same
  commit) both failed at `uv sync --locked --no-dev --no-install-project`
  with `error: No interpreter found for Python >=3.11, <3.13 in managed
  installations or search path` (railpack/mise build path, "Python downloads
  are set to 'never'"). No matching GitHub Actions dispatch was found for
  `wnba-backfill-enrichment` around that time, so what triggered the rebuild
  is unverified. This service has no cron, source auto-deploy, or restart
  loop, so no live traffic is affected, but a manual dispatch right now would
  fail at build until this is fixed; do not redeploy it without addressing
  the interpreter resolution first. Still `FAILED`, unchanged, as of
  2026-09-24 (see update above). The public API at
  `https://api-production-7033.up.railway.app` responded to `/health` with
  `{"status":"ok","version":"0.1.0"}`.
- Active source commit: `1634ec1891ce29d9958ebdc927f459948ceda631` (#253) remains
  the last successful backend deployment. The newly merged documentation-only
  `ffddc7e052470186d204c2ef7a39b1c566e65da4` (#257) has Railway deployment
  records in `WAITING`/stopped state and is not yet a successful active
  deployment. The public API is therefore still serving the previous
  successful commit, while `main` is current at `ffddc7e`. The prior active
  commit `fe39f118c2b9c2e1078d730b34c3d55957d0d4c7` (#249) is in its ancestry.
  Railway recorded the new deployment attempt across the source-backed
  services, but the read-only service summary still reports the prior
  successful deployment as active. Recheck after Railway settles the
  deployment; do not describe `64faa87` as production-active yet.
  `de1d68a402f634e7a9978f4ce773693ea1b7e460` (#230, Real Sports access
  coordination) was itself briefly live before being superseded.
- Model artifact and SHA: production model SHA is still
  `7b06b6f98d0bb0cd69d4b12c49c5c97102b39eb30734c586f9d1f02ab69f1da2`
  (`wnba-oracle/models/picker_95264ce9_1788339935.pkl`), confirmed live as
  `WNBA_ORACLE_MODEL_ARTIFACT_SHA` on `cron-job2` (the only role that
  requires it per `_PRODUCTION_ROLE_REQUIREMENTS`). GitHub repository
  variable `WNBA_EXPECTED_MODEL_SHA` matches. This is a full-refit retrain on
  `main@6f466cf` (season_game_number train/serve parity fixed, causal
  point-in-time pace, pooled-F cohort, calibrators disabled at serving);
  incumbent architecture, selected over a challenger artifact after a paired
  104-slate tournament showed no statistically significant improvement. The
  season is live, not on break: frozen lineups for `slate_date=2026-09-17`
  (`frozen_at=2026-09-17T22:50:07Z`) and `slate_date=2026-09-18`
  (`frozen_at=2026-09-18T22:50:15Z`) both carry this `model_sha`, confirming
  live post-promotion freezes have run under this artifact. `slate_date=2026-09-19`
  has no frozen lineup yet as of this verification (2026-09-19T09:32Z),
  which is before the day's job1 (13:30 UTC) and job2 (14:20 UTC) deadlines.
- Rollback: two pre-refit artifacts are retained in the repository. Their
  sha256 hashes were independently verified against each file's own
  `.sha256` sidecar and via `shasum -a 256`, correcting a filename/hash
  pairing error carried forward in this file since 2026-09-02, sourced
  from issue #53's closing comment.
  `wnba-oracle/models/picker_e2ced9ec_1780873338.pkl` hashes to
  `94f8e8606dab4d48652929bb3884fb9152e1abc766eeb2c2d86559f4318676cd`; this
  is confirmed live as the `model_sha` on the pre-promotion 2026-08-30
  frozen lineup and its history, so this file, not
  `picker_bf3c8996_1780752059.pkl`, is the true previous production
  artifact.
  `wnba-oracle/models/picker_bf3c8996_1780752059.pkl` hashes to
  `2cc953b7fe86e8db8a21f7f9a594a2944c4ce9d98aa21d05a0a0b434d6efd985`. Issue
  #53 names it the tournament's pre-existing baseline against challenger
  `picker_e2ced9ec_1780873338.pkl`, consistent with
  `scripts/model_tournament.py`'s own `--baseline-artifact`/
  `--challenger-artifacts` usage example naming the same two files in the
  same roles; no `tournament_results.json` remains in the repository to
  confirm this exact invocation produced the reported 104-slate results.
  Railway's per-service deployment history (checked for
  `api`, `cron-job1`, `cron-job1-late`, `cron-job2`,
  `cron-dayclose`) retains the prior commits `de1d68a4` (#230, `REMOVED`,
  2026-09-19T07:25:55Z) and `ca6a43d4` (#244, `REMOVED`, 2026-09-19T06:19:09Z)
  as entries in the deployment list; whether a `REMOVED` deployment can be
  redeployed with one click was not verified. Specific rollback deployment
  IDs are not restated here since they change on every redeploy; use
  Railway's live deployment history at time of need.
- Service and schedule state: watchdog `/watchdog/today` reports
  `status=ok`, no events, for `slate_date=2026-09-19`. `/slate/2026-09-19`
  currently 404s with "no slate timing for slate" (checked 2026-09-19T09:32Z,
  before today's job1 deadline; this does not establish whether games are
  scheduled today). The last two finalized slates both confirm the hard
  diversification policy is active: 2026-09-18 (3 games, 5 players, 5
  distinct teams, 2-1-2 split) satisfies the three-or-more-games cap of two
  per game. `/lineup/{date}`, `/lineup/{date}/history`, and `/dossier/{date}`
  were exercised live for 2026-09-17 and 2026-09-18 and returned correctly.
- Current incidents and production risks:
  - #243 (OPEN): watchdog `ALERT` at 2026-09-19T06:02Z, `cron-dayclose`
    `degraded` (`placement_capture` reason `missing_labels_or_leaderboard`
    for slate 2026-09-18, processed ~7 hours after freeze). Diagnosed live
    this session as the documented pre-catchup case
    (`_catch_up_missing_placements` only considers dates strictly before
    "yesterday," so 2026-09-18 is not yet eligible); expected to self-heal
    via the 2026-09-20 dayclose run, with the watchdog auto-closing once a
    clean probe runs. #233 (same alert class) closed at 2026-09-19T04:04Z
    with no active alert; this is a recurrence of that alert class a few
    hours later, not evidence that #229's fix regressed, but that has not
    been independently re-verified beyond the live diagnosis above.
  - `backfill-enrichment` build failure: see Deployment state above. Not yet
    filed as a tracked issue.
  - corpus-backup (#202, landed as #245 in `484db735`): every scheduled run
    from 2026-09-10 through 2026-09-18 ended red on the orphan-branch
    worktree-restore `Post Run` step. Verified live this session via
    workflow_dispatch run `35427434241` (2026-09-19T06:44:47Z): fully green
    including `Post Run`. Also checked one prior red run
    (`35341487312`, 2026-09-18 schedule): export and the actual snapshot
    commit/push both succeeded; only the `Post Run` cleanup step failed,
    confirming these were red-run/cleanup failures, not backup-data gaps.
    The first *scheduled* (non-manual) run under the fix has not happened
    yet as of verification time.
  - #230 (Real Sports access coordination, closed): migration
    `20260919_0011_external_access_windows` and its consumer
    (`scheduler/access_coordination.py` + `scheduler/realsports_access.py`)
    landed in `de1d68a4`. `REALSPORTS_ACCESS_COORDINATION_ENABLED` confirmed
    absent (default-off) on `cron-job1`, `cron-dayclose`, and
    `backfill-enrichment` via live variable reads this session; no
    production behavior or schedule change from landing it. Alembic ran
    during the latest `api` deployment startup (confirmed in deploy logs),
    consistent with the migration path executing automatically; the specific
    `20260919_0011` revision was not independently confirmed as the current
    head against production Postgres. See `AGENTS.md`'s Jobs and production
    operations for the enable decision and the known `nfl-oracle-worker`
    coordination gap.
  - Known residual limitation: the offline model tournament used a
    documented offline feature-reconstruction path
    (`--game-logs-csv`/`--game-identity-csv`) rather than the live DB read
    path, which has a separate, pre-existing schema mismatch
    (`read_game_identity()`/`index_game_identity()`) not touched by recent
    pushes; see issue #53's final comment for detail.

Development plans, branch history, check output, decisions, and completed work
belong in GitHub Issues and Pull Requests, not this file.
