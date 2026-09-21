# Status

Last verified: 2026-09-20T12:15:00Z

This file records live operational state only. Values marked unverified were
not exposed by the read-only checks available during this audit.

## Read-only results endpoint (issue #34, 2026-09-20)

Added `GET /results/{slate_date}` (`wnba_oracle/api/results.py`) so
GitHub/ChatGPT/Claude/mobile surfaces without a terminal or a direct
read-only PostgreSQL session can answer "who were the highest realized-value
Real Sports players on a given slate" the same way `/lineup/{date}` already
answers "what did Oracle freeze." Reads only `slate_labels`; `real_score` is
returned verbatim (never recomputed). Returns `status: "pending"` (200, not
404) when a slate date has no ingested rows yet, matching the issue's
explicit "clear machine-readable pending state" requirement. The response
includes every ingested row plus a deterministic `top_value` view: top 5 by
`real_score`, deduped by player across Real Sports sections (a player can
appear in more than one section on the same slate), keeping each player's
best score and recording every section they appeared in for provenance.
Ties break by ascending `platform_player_id` for determinism; null
`real_score` (not yet graded) always ranks last. 15 new unit tests cover
pending/available status, verbatim `real_score`, cross-section dedup, the
top-5 cap with deterministic tie-breaking, and null-score ordering; the
existing OpenAPI contract test (`test_api_app.py`) now also asserts
`/results/{slate_date}` is present. No frontend changes, no Real Sports auth
added to the API, no change to `/lineup/{date}` behavior.

## Live operational snapshot

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
  the interpreter resolution first. The public API at
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

## 2026-09-20: durable day-close ALERT investigated (issues #2/#243 ledger)

The perpetual `ops-results` (#2) and `ops-guard` (#243) ledger issues (same
sticky-comment pattern as `nfl-oracle`'s #143/#144 -- intentionally left
open forever, updated by `wnba-dayclose-verify.yml` on every scheduled run)
showed `ALERT: Durable day-close: The durable run ended with status failed`
for the 2026-09-19 slate. Investigated live via `job_runs` in the WNBA
Postgres instance (queried through `railway ssh --service api`, since
`railway logs --service cron-dayclose` returns no output for a completed
cron run -- Railway does not retain post-exit logs for ephemeral cron job
instances via the CLI, only the durable `job_runs` row does):

- Root cause: the `game_log_refresh` substep (`_refresh_current_game_logs`
  in `wnba_oracle/scheduler/job_dayclose.py`, calling `refresh_game_logs()`
  in `wnba_oracle/ingest/minutes_backfill.py`) exhausted its bounded
  `nba_api`/stats.wnba.com retries and raised `GameLogRefreshError`. This
  substep is deliberately `required=True` (comment references D102: a
  silent staleness here previously caused the 2026-08-xx C. Leite
  head-features gap), so one required-substep failure correctly escalated
  the whole night's run to `status=failed` even though every other substep
  (contest discovery, label coverage, retention cleanup, historical
  backfill, placement catchup) succeeded.
- This is a legitimate transient upstream failure, not a code bug: `job_runs`
  history for the surrounding days (2026-09-16 through 2026-09-18) shows
  `game_log_refresh` succeeding normally. The retry window was thin,
  though -- only `(2.0, 5.0)` seconds, under 10 seconds of total retry time
  for a shared-cloud-IP-sensitive external API. Widened to
  `(3.0, 8.0, 20.0, 45.0)` in `minutes_backfill.py` so a genuinely transient
  blip has a fair chance to clear before escalating; a truly down upstream
  still fails and still escalates, unchanged.
- Also applied the same browser-leak fix `nfl-oracle` got this session:
  `wnba_oracle/ingest/realsports.py`'s `capture_live_headers()` and
  `discover_wnba_contest_id()` now use
  `oracle_core.browser.launch_chromium_session()` instead of manual
  `browser.close()` calls that only ran on some exit paths. WNBA's own
  disk usage was not independently confirmed to be under the same pressure
  NFL's was, but the leak was real and the fix is a narrow, low-risk,
  mechanical swap (see `nfl-oracle/STATUS.md`'s 2026-09-20 entry for the
  fuller incident writeup this mirrors).
- **#2 and #243 intentionally remain open** (same reasoning as NFL's
  #143/#144): they are the durable ops ledger, not one-off incident reports.
  This fix reduces how often a transient upstream blip pages as `ALERT`;
  it does not and should not make the ledger issues disappear.
- Verification: `make test-app APP=wnba-oracle` (993 passed, 7 deselected),
  `make lint`, `make typecheck` all pass for `wnba-oracle`.

## 2026-09-20: security dependency bump (issue #41)

- `starlette` 0.52.1 -> 1.6.0 and `pyarrow` 21.0.0 -> 25.0.1, resolving all
  6 known CVEs (`PYSEC-2026-161/248/249/2280/2281` on starlette,
  `PYSEC-2026-113` on pyarrow) that `pip-audit` flagged on 2026-08-30 and
  that had been deliberately deferred (major-version jumps landing inside a
  pre-freeze window).
- Compatibility check: installed FastAPI (0.141.1, the top of the app's
  existing `<0.142` pin) already declares `starlette>=0.46.0` with no upper
  bound, so no FastAPI bump was needed alongside the starlette major jump.
- `wnba-oracle/pyproject.toml` constraints widened to
  `starlette>=1.3.1,<2.0` and `pyarrow>=23.0.1,<26.0`; `uv.lock` regenerated.
- Verification: `pip-audit` against the resolved dependency set (excluding
  local workspace packages) reports no known vulnerabilities; full
  `make test-app APP=wnba-oracle` (993 passed, 7 deselected), API contract
  tests (`tests/unit/test_api_app.py`, 6 passed) covering `/health`,
  `/lineup/{date}`, `/slate/{date}`, `/watchdog/today`, `/dossier/{date}`
  and their security headers, `make lint`, `make typecheck` all pass.
- New (non-blocking) deprecation warning from the starlette bump: FastAPI's
  `TestClient` uses `httpx`'s deprecated starlette integration path,
  suggesting `httpx2`. Not acted on here -- purely a test-harness
  deprecation notice, no runtime behavior change; worth a follow-up if/when
  `httpx2` stabilizes.

## 2026-09-20: canonical Real Sports -> stats.wnba.com identity table landed locally (issue #30)

- Repository-local change only so far: Alembic head `20260920_0012` adds
  `canonical_player_identities`, keyed by Real Sports player id with the
  resolved stats.wnba.com id, provenance (`provider_nba_id`,
  `explicit_override`, `normalized_name_fallback`), first/last-seen
  timestamps, and audit-friendly name/team metadata.
- Ordinary Job 1 ingestion now attempts a nested-savepoint upsert into this
  table whenever the existing resolver resolves a player unambiguously. The
  write is isolated so a canonical-identity persistence failure cannot block
  the durable `job1_enrichment` promotion or change the frozen-lineup
  decision path.
- Historical backfill logic was added and tested only against synthetic
  fixtures. **No live backfill was run here. Separate operator authorization
  is still required before any production backfill execution.**
- Evaluation coverage reporting now prefers the canonical mapping for
  prediction-to-outcome joins and explicitly reports the fraction of
  predictions unresolved by the canonical map instead of silently name-matching
  everything.

Development plans, branch history, check output, decisions, and completed work
belong in GitHub Issues and Pull Requests, not this file.
