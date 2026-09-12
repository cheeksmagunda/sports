# Status

Last verified: 2026-09-08 20:40 CT, Codespace cleanup checkpoint for issue #115.

This file records application state only. Re-verify auth and coverage before
treating any row as production truth.

## Day-close infrastructure generalized to oracle-core; full-field capture added (issue #146)

Builds on issue #140. Three changes:

- The catch-up sweep (grade a target day, retry a bounded window of earlier
  ungraded days, isolate one day's failure from the rest) is now generic
  orchestration in `oracle_core.dayclose.run_sweep`, shared by every future
  sport's day-close job. `nfl_oracle.recommendations.dayclose.run` supplies
  only the NFL-specific `close_one_day` callback; its top-level JSON stdout
  keys and CLI exit-code mapping (only `"failed"` is non-zero) are unchanged.
  One real behavior change: `outcomes` now lists every day the sweep visited
  in the catch-up window, not only days that had a freeze - a normal run now
  shows several `"no_freeze"` entries alongside the graded day.
- Both `nfl-dayclose.yml` and `nfl-corpus-backup.yml` now gate on
  `nfl-oracle/scripts/nfl_dayclose_gate.py`, a session-free public-nflverse
  check for whether the day-close sweep window contains any slate. A day
  with no slate anywhere in that window (not just "yesterday") skips real
  work silently and posts nothing to the results ledger; `workflow_dispatch`
  always bypasses the gate. Ledger-post/escalate boilerplate is now the
  shared `.github/actions/dayclose-ledger` composite action.
- The `dayclose_grade` artifact (schema_version 2) now also captures the
  whole field, not just our five picks: contest-level facts, the visible
  leaderboard, and every player's draft stats for the entire slate, via the
  existing `contests.parse.load_contest`. `backup_corpus.py` gains a fourth
  CSV table, `player_results.csv`, derived from the same artifacts (no
  Postgres schema change).

**Still not yet live.** Both workflows remain inert until the operator
provisions `NFL_DAYCLOSE_DATABASE_URL` (write-capable Postgres),
`REALSPORTS_STORAGE_STATE_B64GZ` (the derived Real Sports session, shared
across every sport's day-close workflow, base64+gzip), and
`NFL_BACKUP_DATABASE_URL` (read-only Postgres). This secret name changed
from the prefixed `NFL_REALSPORTS_STORAGE_STATE_B64GZ` used at #140's merge
to the unprefixed, portfolio-shared `REALSPORTS_STORAGE_STATE_B64GZ` - see
root `README.md`. Nothing needed migrating: neither workflow had ever run
with the secret configured. Until secrets exist, `nfl-dayclose.yml` fails
cleanly with a `not_configured` message and posts nothing beyond that to the
results ledger; `nfl-corpus-backup.yml` errors before touching the database.
No credential was created by this work.

## Railway worker activated as sole primary writer (2026-09-09 18:55 UTC, issue #129)

This checkpoint supersedes the two sections below for tonight's live status.
Per operator direction ("get it to run for real, without needing the local
fallback"), the hosted `nfl-oracle-worker` service is now the sole writer for
the 2026-09-09 SEA at NE slate (contest 2141, kickoff 2026-09-10T00:20:00Z,
T-40 2026-09-09T23:40:00Z). The local `run_t40_worker.sh` process crashed
around 18:07 UTC (PostgreSQL tunnel drop cascading into the audit-write
failure this checkpoint's retry fix addresses) and was not restarted; the
operator was told not to restart it, to avoid a double-writer race.

Sequence, each step independently verified:

1. PR #131 (`_record_worker_failure`, the retry-crash fix, plus
   `test_worker_retry.py`) merged to main at `f12c150`. Required CI green
   (secret-scan, devcontainer-smoke, test-and-quality, integration-and-container).
2. `nfl-oracle-worker` auto-rebuilt from `f12c150`; confirmed via SSH
   (`$RAILWAY_GIT_COMMIT_SHA`) that the running container is that exact
   commit, not an older cached image.
3. Corpus G (3,342 files, 513,980,989 bytes) and the one context snapshot
   confirmed present post-rebuild via a fresh SSH read, matching the prior
   upload counts exactly.
4. A read-only `SELECT 1` against `NFL_DATABASE_URL` from inside the worker
   container confirmed the private-network path to production Postgres works;
   this path had never been exercised by any prior worker deployment (every
   earlier run exited at the `recommendations_disabled` gate).
5. `NFL_RECOMMENDATIONS_ENABLED` set to `1` via `railway variable set
   --skip-deploys` (the `railway environment edit --service-config` dot-path
   form no-ops on this field specifically, for both this value and
   `deploy.startCommand`, regardless of target value; the working path for
   `startCommand` remains the Railway dashboard).
6. The operator applied the dashboard change restoring
   `deploy.startCommand` to `sh -c 'exec nfl-pipeline worker'`. Deployment
   `ebb4c9d1` went live at 18:55:25 UTC.
7. First log line: `[INFO] status="waiting_or_locked"` at 18:55:25 UTC. In
   `_worker_once`, `store.record_run(day, status="waiting", ...)` commits to
   Postgres before this line prints, so it proves auth derivation, live
   provider read, and a committed production write in one signal.
8. Independently confirmed via the local read-only tunnel: production table
   `nfl_recommendation_runs` rows 71 and 72, `checked_at` 18:55:24.97Z and
   18:55:55.47Z (30s apart, matching `--poll-seconds 30`), both
   `{"status": "waiting", "detail_code": "waiting_for_t40", "details":
   {"next_freeze": "2026-09-09T23:40:00+00:00", "cutoff_at":
   "2026-09-10T00:20:00+00:00"}}`. Rows 68-70 (checked_at 18:05-18:06Z) are
   the local worker's last writes before its crash; no writer was polling
   between roughly 18:07 and 18:55 UTC, but no freeze was due in that window.

Remaining to verify before this is closed out: the worker keeps polling
`waiting_or_locked` without crashing through T-40 (23:40 UTC), then actually
executes `publish()`/freeze against production Postgres at T-40, producing
the correct five-pick, descending-slot-order lineup with no contest
submission, through kickoff (00:20 UTC 2026-09-10).

## Hosted provisioning and retry recovery (2026-09-09, issue #129)

This checkpoint supersedes the provisioning blocker recorded below. The
operator applied `sleep infinity`; the hosted container is accessible and
recommendations remain disabled while preflight runs. The operator has since
authorized making Railway the primary worker for tonight, without the Mac
fallback, provided only one worker is active.

The local worker exited around 18:07 UTC after a PostgreSQL tunnel connection
failure. Its tunnel and watchdog processes remained, but the worker did not.
The operator was informed; no local process or tunnel was restarted by the
agent. A failed operator restart attempt did not restore the worker. Do not
continue claiming the local fallback is active without a fresh process and log
check.

The mounted Corpus G upload is verified byte-for-byte: 3,342 files,
513,980,989 bytes, directory digest
`3d7ccfa2eb237b376fc9e5dd27f849ee1fa8a4657e0806ccde6b55178427da63`
(SHA256 over sorted relative paths, NUL, file SHA256, newline). The latest
context snapshot listed below also matches its local SHA256. Only that latest
snapshot was uploaded, avoiding old snapshots being chosen by upload time.
Volume runtime directories are owned by UID 10001, and the worker user can
write data and read `/app/nfl-oracle/config/NFLconfigvenues.json` in the hosted
image. This verifies the venue path correction from PR #130 at runtime.

`REALSPORTS_STORAGE_STATE_B64GZ` is verified sealed on the worker only. A
read-only hosted authentication check, executed as UID 10001, successfully
derived fresh headers. The value was sent through native CLI JSON stdin,
never command arguments or logs. Configuration read-back confirmed
`isSealed=true`, `sleep infinity`, and recommendations disabled.

The worker now tolerates a second database failure while recording a failed
poll. It emits only the audit-failure code and exception type, then continues
its bounded polling delay. It preserves nonzero failure for `worker --once`.
Regression tests cover recovery after ordinary poll errors and no-slate
errors when the audit database is also unavailable, plus one-shot failure
and secret-free logging. Three focused tests, lint, and types pass. The full
local suite reports 266 passed, one skipped, and one Docker smoke failure
because the Docker daemon is unavailable.

A hosted rehearsal using an isolated in-memory SQLite store is in progress;
production Postgres is not used by that rehearsal. Primary activation and a
real T-40 freeze remain pending verified rehearsal and single-worker checks.

## Railway worker continuation (2026-09-09, issue #129)

Verified from the operator Mac using the native Railway CLI. The local
`run_t40_worker.sh` process remains the active path for tonight's freeze;
`/tmp/nfl_t40_worker.log` was updating with `waiting_or_locked` during this
checkpoint. Its process, SSH tunnel, and production database were not modified.
Kickoff supplied for contest 2141 is `2026-09-10T00:20:00Z`, with T-40 at
18:40 America/Chicago on September 9. A completed production freeze has not
yet been verified.

The hosted worker service `a4e05931-fd02-4dd0-b998-d8ecfdbcc355` in project
`dc2d3b51-2551-4df1-981e-c2c1440dc992`, environment
`21c8b1a2-6648-4535-8a26-b65da96d8ed1`, had
`NFL_RECOMMENDATIONS_ENABLED=1` when inspected. It has been set to `0` and
read back as `0` to avoid enabling a second writer before the local freeze.
`NFL_DATABASE_URL` is present; `REALSPORTS_STORAGE_STATE_B64GZ` is absent.
The API and Postgres services report Online in Railway; this is a service
status observation, not a new database health or freeze-content check.

`nfl-oracle-worker-volume` (`9cb6374a-f47b-4401-ba35-b6131f9d30e5`) is attached
at `/app/nfl-oracle/data`. Deployment
`c7c08dcf-564b-40f5-b677-77dc4e6d79a5` reports Crashed after completing its
build; runtime logs confirm `recommendations_disabled` on each startup.
Volume listing fails with an SFTP initialization timeout. A native CLI
start-command edit to `sleep infinity` returned without applying a change;
a subsequent attempt explicitly reported `No changes to apply`, and read-back
still showed `sh -c 'exec nfl-pipeline worker'`. The operator was asked to
set the temporary start command and deploy through the dashboard. No data or
session upload has been completed in this continuation.

The local inputs exist: Corpus G is approximately 500 MB, and seven context
JSON snapshots total approximately 1.1 GB. The latest snapshot is
`f70ae53d793d2dc84a9e967dc3509fb4c1ca61c90c2addbb1c0728fd2384334e.json`,
file SHA256 `85569b590ee476c04a3b5effcd40c8a6d1609b9dada0596ffa8fadd38590fa80`.
The local session is structurally valid JSON with mode `0600`; this is not
proof of hosted authentication.

The production Dockerfile now copies venue configuration explicitly to
`/app/nfl-oracle/config/`, matching the worker's default lookup. Previously
it copied to `/config/` before setting the runtime working directory, which
would leave the default worker lookup missing its venue file. Local image
verification could not run because the Docker daemon socket was unavailable.

Remaining acceptance: obtain a running provisioning container, upload and
verify Corpus G and context on the volume, seal the worker-only session,
verify runtime paths and permissions, restore the worker start command, and
only enable recommendations after confirming tonight's local freeze. A
natural subsequent slate must demonstrate hosted refresh, model preparation,
T-40 waiting, and a five-player freeze before claiming weekly self-sufficiency.
Rollback during provisioning is recommendations disabled with the local
runner left intact. References: issues #129 and #124.

## Current operational readiness

- GitHub `main` remains `66955746f76af3a024489606e37620bd43f0d5ac`.
  The recommendation pipeline and frontend are branch work on
  `chat/115-nfl-live-pipeline`, not a production deployment. The canonical
  Codespace `orange-system-4jx77wj6jvg6cq4gq` is on that branch, clean after
  cleanup commit `31968386d7488b1252ada04534be730efdf60c8b`, and
  `make write-path-check` passed there. The Mac Copilot worktree is synced to
  the same commit.
- The service scope is five recommended players with committed slot order for
  the operator to enter manually. Contest submission remains hard-denied.
- The controlling objective is expected Total Value:
  `sum(expected Real value * (player boost + slot multiplier))`, with slot
  multipliers `2.0, 1.8, 1.6, 1.4, 1.2` and player boosts from `0` through `3`.
  There is no validated production winning strategy or whole-field win probability.
- Saved contest `2141` targets September 9, 2026: NE at SEA, Real game `19457`,
  kickoff `2026-09-10T00:20:00Z` (September 9 at 19:20 America/Chicago).
  The intended T-40 freeze is September 9 at 18:40 America/Chicago, subject
  to a fresh provider lock/kickoff check. Correctness takes precedence over
  that first slate.
- The latest saved slate was captured `2026-09-08T22:46:23.045249Z`: 161
  observed candidates, one game, and all observed boosts zero. The branch now
  fails closed if a freeze sees a partial candidate pool or a boost-regime
  declaration that does not match the candidate boost table.
- The local Corpus G loader yields 37,710 player-games from 570 validated
  games across 2024 and 2025, excluding 98 preseason games and one missing
  value. These ignored local artifacts are not transported by a git checkout.
- Saved historical daily-contest evidence is one finalized contest, `870`
  (September 15, 2025), with 20 saved leaders out of 20,841 reported entrants.
  Full Corpus C collection and audit remain incomplete.
- Release blockers include unsafe context identity fallbacks, incomplete final
  context refresh, missing calibrated media/role evidence, incomplete
  contest-level decision evaluation, active-artifact/readiness API checks, and
  no Railway deployment yet. Passing unit tests alone does not resolve these
  operational risks.
- The full session requirements, strategy decisions, audit findings, artifact
  paths, validation results, and continuation instructions are maintained in
  [issue #115](https://github.com/cheeksmagunda/sports/issues/115).

## Corpus C landed: the historical contest archive (2026-09-09 UTC)

The daily-draft contest archive now exists. `nfl-contest-backfill` walked the
global `playerratingcontest` id space 1-2141 and saved every NFL contest it
found. Read-only; the package has no submit path.

- **92 NFL contests saved, 91 finalized**, spanning **2024-11-24 to 2026-02-08**,
  plus the live pregame contest 2141. Fields run 12,049 to 62,457 entrants
  (median 23,380).
- Each finalized contest yields the top-20 human lineups with per-card slot,
  boost, Real value, score and finalized value rank; a 45-row `draftStats`
  block with per-player boosts and draft counts; the payout table; and the Rax
  side-pool terms.
- `/entries` serves **at most 20 rows and exposes no pagination parameter**
  (page/offset/limit/cursor all return the same 20). Every field statistic is
  therefore conditioned on reaching the visible top twenty. The median entry is
  never observed and must not be claimed.

### Scoring law, verified not assumed

`score = value * (slot_multiplier + card_boost)` reconciles on every card of
every saved entry across all 91 finalized contests. `parse_entries` checks the
decomposition per row and refuses a payload that fails it, so a rule-era change
surfaces instead of being averaged in. `payoutinfo.entryPayoutText` describes a
different, rank-distance game and contradicts the leaderboard; the arithmetic
is authoritative over that copy.

### Card boosts are provider-assigned and absent in week 1

Boosts are set by the provider from the player's pre-game Real ranking, never
chosen by the entrant. They are **absent for the whole of NFL week 1** and
switch on at week 2 Thursday:

| Contest | Day | Boost table |
| --- | --- | --- |
| 839 | 2025-09-04 (W1 Thu) | all 0.0 |
| 843 | 2025-09-05 (W1 Fri) | all 0.0 |
| 849 | 2025-09-07 (W1 Sun) | all 0.0 |
| 851 | 2025-09-08 (W1 Mon) | all 0.0 |
| 857 | 2025-09-11 (W2 Thu) | full 0.1-3.0 spread |

Contest 2141 (2026-09-09) reads all-zero live, consistent with the same rule.
An all-zero table is shape-identical to a real one, and an optimizer fed zeros
silently degenerates into "take the five highest projected values", discarding
the leverage dimension. `observe_boosts` detects the state explicitly and
`nfl-boost-watch` records the publication clock; a zero-boost slate must be
gated as a deliberate regime, never optimized as if boosts were merely small.

### What the archive says about winning

Pooled over 91 finalized contests, conditioned on the visible top twenty:

- Winners captured a mean **79.9%** of the hindsight-best legal lineup.
- Only **3.2%** of visible top-20 lineups committed their five cards in the
  optimal slot order (median 0%). Mean slot regret **1.45** points.
- Winners averaged **3.4 of 5** cards inside the finalized Real-value top ten.

In the four **zero-boost week-1 contests**, which are the exact rule analog for
2026-09-09, the picture sharpens:

- Winners captured **97.5%** of hindsight best. Without boosts there is little
  leverage variance left, so the ceiling is nearly reachable.
- Visible lineups averaged **4.59 of 5** cards inside the Real-value top ten;
  59 of 80 had all five.
- Ordering optimality was still only **6.2%**, mean regret 0.44.
- Contest 839 is the clearest case: 23,880 entrants, all twenty visible lineups
  drafted the **identical five players**, and 1st (30.27) beat 20th (29.98) by
  **0.29 points** on slot order alone.

The operational reading for a zero-boost single-game slate: player selection
converges across the serious field and is table stakes, while committed slot
order is a free deterministic lever that roughly 94% of the visible field fails
to take. Total score decomposes into an order-invariant part and a
rearrangement part, so the optimal commitment is strictly descending projected
value. The edge is projection accuracy at the margin, expressed through order.

Recurring winning archetype on single-game zero-boost slates: **both starting
quarterbacks, the top skill producers, and the kicker.** 843 (KC at LAC) ran
Herbert, Mahomes, Johnston, Allen, Kelce. 851 (MIN at CHI) ran McCarthy,
Williams, Jones, Jefferson, Reichard. This is a described pattern from four
contests, not a fitted or validated policy.

### Payout structure, stated plainly

Leaderboard prizes are 100/80/60/40/20 Rax for ranks 1-5 and 10 Rax for 6-10.
Against a field of 20,000-plus that is a negligible expected return. The
material payouts are the optional Rax side pools: top 50% pays 1.7x, top 20%
pays 3.5x, top 10% pays 7x on a 100 Rax wager, tiebreak by earliest entry.
Maximising expected Total Value is the objective the operator set and is what
the optimizer maximises; it is not the same objective as maximising
`P(top 10%)`. Both are exposed, the difference is documented, and no claim of a
validated winning edge is made from either.

### Commands

```sh
uv run --package nfl-oracle nfl-contest-backfill --start 1 --end 2141 --descending
uv run --package nfl-oracle nfl-boost-watch --contest-id 2141 --day 2026-09-09 --once
```

Payloads land under `data/raw/corpus_c/` (gitignored, redacted, sha256
provenance sidecars, mode 0600) with the resume cursor in
`data/catalog/corpus_c_cursor.json`.

## Historical application baseline (September 6, 2026)

- Package: `nfl-oracle` workspace member
- Scope live now: Corpus G ingest boundary + season resume CLI + redaction tests + Real `value` label schema + offline walk-forward baselines + observation-only data/strategy/feature/calendar/identity scaffolds + read-only research service routes + **offline contest dry-run** (shadow slate; hard-deny submit)
- Wired into root `make test-nfl` / `lint` / `typecheck` / `build`; `make -C nfl-oracle strategy-schema`
- Not started: Corpus C contests, verified five-card provider contract (#91), production deploys,
  contest submission, Railway production secret injection, in-repo Railway deploy source

## Auth

- Pattern: `headers_or_capture` in `nfl_oracle.ingest.realsports`
- Session source: operator-seeded `scraper/storage_state.json`,
  `NFL_REALSPORTS_STORAGE_STATE` / `REALSPORTS_STORAGE_STATE_PATH`, or
  `REALSPORTS_STORAGE_STATE_B64GZ` (same Real Sports account mechanics as WNBA,
  without importing WNBA domain code)
- Device identity for header harvest: `NFL_DEVICE_UUID` and `NFL_DEVICE_NAME`
  (see `realsports.py`). Not `NFL_REALSPORTS_DEVICE_*`.
- Railway staging (`nfl-oracle-staging` / `nfl-oracle`): placeholders include
  storage-state keys plus additive `NFL_DEVICE_*`; legacy
  `NFL_REALSPORTS_DEVICE_*` names may remain present and unused by code.
  No deploy source connected (0/1 online by design). No contest code.
- Railway operations use the authenticated local native Railway CLI. Do not
  perform Railway operations in cloud sessions or mint/copy an additional
  token to bypass the boundary recorded in issue #109. Recheck authentication
  locally before any authorized Railway action.
- Secrets stay local under ignored `scraper/` / `.secrets/`; never committed

## Train vs live

- Training may use post-game Real `value` as labels after finalization
- Live / prospective decisions use only pre-lock features (strategy playbook
  clocks + leakage blacklist)
- No contest entry code in this package

## Corpus G proof

- Target: season 2002, game id 126323 (2002-09-08)
- Seed catalog: `data/catalog/season_game_ids.json`
- Raw payloads and coverage matrices are gitignored; fixtures under
  `tests/fixtures/` are redacted/synthetic for CI


## Value labels + baselines (observation only)

- Schema: `nfl_oracle.labels.schema` (`real_value_label` v1)
- Extract: `nfl_oracle.labels.extract` from Corpus G `stats.json` + clocks
- Baselines: `global_mean`, `position_mean`, `position_median` via
  `nfl_oracle.baselines.walk_forward` (OOS by season)
- Optional: `player_mean`, `feature_ridge` (leakage-safe prior-feature ridge)
- CLI: `nfl-value-baselines` (offline; `--schema-only` / `--root` / `--json` / `--methods`)
- **Eval report:** `nfl-walk-forward-report` / `make walk-forward-report` — baselines vs
  `feature_ridge` on fixtures → `artifacts/walk_forward_fixture_sample.{json,md}`
  ([sample MD](artifacts/walk_forward_fixture_sample.md))
- Metrics: pooled MAE / RMSE / bias on held-out season anchors
- Still out of scope: contest submission, live entry


## Week / slate resolution (2026-09-06 CT)

- `nfl_oracle.calendar.slate` — resolve games + opponents from date or season+week
  (dense offline schedules; exact gameday or week span; no invented weeks)
- Research: `GET /research/schedule/slate?season=&week=` or `?date=YYYY-MM-DD` (+ optional `team`)
- Dry-run optional: `include_schedule_slate` / `--include-schedule-slate` attaches schedule slate
- **Hardened attach** (`resolve_dry_run_schedule_slate`): priority explicit date → week →
  label `event_time` → week-1 fallback; `dry_run_attach` meta; optional `schedule_team`
- Contest entry unchanged (`contest_entry=false`; submit hard-deny intact)

## Coverage gaps

- Catalog still holds Corpus G **seed anchors** (3-5 ids/season); schedule census is separate
- Offline nflverse/nfldata schedules now provide **continuous full-season slates**
  (2002–2025 slim CSV under `data/schedule/schedules.csv`; CC BY 4.0)
- Tracked seasons 2002–2025 still need denser Corpus G ingest beyond seeds
- Contest-era Corpus C is explicitly deferred


## Coverage matrix statuses

Season rows in `data/catalog/coverage_matrix.json` (gitignored; regenerated by
backfill) use:

- `known` — ≥1 Corpus G game ingested
- `unknown` — tracked season with no discovered/ingested game ids yet
- `blocked` — auth/storage missing/stale or provider systematically refused

Each season carries a Real `value` presence note. Seed game ids that *are*
committed live in `data/catalog/season_game_ids.json`.

## Clock fields

Provenance + manifests carry `event_time`, `source_available_at`, `captured_at`,
and `decision_at` (null on historical backfill). See README train/live section.



## Data / strategy / feature scaffolds (2026-09-06 CT)

Observation-only modules on branch `codex/nfl-data-schemas-scaffold` (no contest entry):

- `nfl_oracle.data` — seed catalog loader, coverage row vocabulary, data path helpers
- `nfl_oracle.strategy` — clock gates, five-card structural legality, shadow snapshot + `nfl-strategy-schema` CLI
- `nfl_oracle.features` — FeatureSpec v1 registry (pre-lock priors vs same-slate finals)
- `nfl_oracle.calendar` — season label helper (week unresolved without schedule)
- `nfl_oracle.identity` — Real-primary identity map + Corpus G players hydrate
- `nfl_oracle.service` — oracle-core FastAPI research routes for schema/catalog JSON only
- `nfl_oracle.baselines.player_priors` — walk-forward player/position/global prior scaffold
- `nfl_oracle.strategy.scoring` — observation-only weighted five-card shadow score
- `nfl_oracle.data.coverage_matrix` — load/save helpers for catalog coverage_matrix.json
- baselines CLI `--methods` includes optional `player_mean`
- `nfl_oracle.calendar.schedule` — offline nflverse schedules.csv parser (public data)
- `scripts/hydrate_identity_fixtures.py` — offline identity summary from fixtures
- GitHub push from box blocked (PAT Contents write 403); commits local on `codex/nfl-data-schemas-scaffold`

Still deferred: Corpus C ingest, provider-verified slot/boost/lock contract, Railway deploy source.


## Provider stubs (#91) (2026-09-06 CT)

- `nfl_oracle.providers.auth_status.probe_realsports_auth` — presence-only probe (no secret values)
- `nfl_oracle.providers.five_card.FiveCardProviderStub` — shadow preview / hard-deny submit+inventory
- CLI: `nfl-provider-status` / `make -C nfl-oracle provider-status`
- Research: `GET /research/provider/status`
- Box auth still missing; status expected `auth_missing`
- GitHub push/MCP write still 403; see `/workspace/codex-nfl/HANDOFF.md`



## Research service path (2026-09-06 CT)

Runnable offline research HTTP (observation only; no contest entry; no deploy):

- CLI: `nfl-research-serve` / `make -C nfl-oracle research-serve` (needs `--extra serve` / uvicorn)
- Routes: schemas (labels/strategy/features/**scoring**), catalog, provider status + posture,
  `POST /research/shadow/preview` (contest algebra + optional best ordering),
  `POST /research/shadow/rank-orderings` (top-k of 120),
  `GET /research/gates/entry` (always `contest_entry=false` + package hard-deny),
  `GET /research/coverage/summary`, `GET /research/features/live-ok`,
  `GET /research/status` (`include_gates` query; Railway presence flags; auth presence only),
  `/health` (auth degraded OK)
- Strategy: contest scoring algebra (`OBSERVED_DEFAULT_SLOT_MULTIPLIERS`),
  `ordered_five_card_actions` (120) + `best_shadow_ordering` / `rank_shadow_orderings`,
  entry gates checklist, `posture_from_readiness`
- Data: `research_data_summary` over season catalog + coverage_matrix
- Features: `player_prior_mean` + `live_ok_feature_names()`; prior feature rows helper
- daily_shadow artifact includes provider_status (presence only)
- Circular-import fix: `posture`/`gates` lazy-import provider stubs (strategy package exports safe)
- Box verification: pytest **66 passed**; ruff + mypy clean on touched paths
- **Still deny real submit** — `FiveCardProviderStub.submit` raises; gates never flip `contest_entry`

## Railway config presence (document only; do not deploy)

- **In-repo:** no `nfl-oracle/railway.toml`, no `nfl-oracle/Dockerfile` (unlike wnba-oracle).
- **External:** Railway project `nfl-oracle-staging` / service `nfl-oracle` exists as
  offline placeholders (0/1 online by design). No deploy source connected from this package.
- Research status route reports `railway.in_repo_config=false` and staging names only.
- Do not create Railway services, inject production secrets, or connect a deploy source
  from this overnight pass.

## Codespace live-wire (2026-09-05 CT)

Executor attempt from Ben's Mac worktree `/private/tmp/sports-nfl-oracle-89`.

- Scaffold landed on branch `chat/89-nfl-real-corpus`: `nfl-oracle/scripts/daily_shadow.py`
  + `make -C nfl-oracle daily-shadow` (coverage matrix refresh -> `nfl-value-baselines` ->
  `data/artifacts/daily_shadow_*.json`). Observation / #91 shadow only. No contest entry.
- Mac Railway CLI: `railway whoami` OK; linked `nfl-oracle-staging` / service `nfl-oracle`
  (environment labeled `production` on staging project). Service offline by design.
- **Blocked:** Mac `gh` token lacks `codespace` scope, so cannot SSH/list Codespaces.
  Ben (already in `/workspaces/sports`) should paste the CS command block from the
  strategy playbook dated note to finish checkout + `RAILWAY_TOKEN` presence check +
  CS railway link + `make install` / `make -C nfl-oracle daily-shadow`.
- Never echo `RAILWAY_TOKEN` values.

## Codespace checkout (2026-09-06 03:28 UTC)

PR #92 `chat/89-nfl-real-corpus` branch confirmed:

- [x] Branch checked out from `main`
- [x] `RAILWAY_TOKEN` environment variable present (not printed)
- [x] `uv sync --all-extras` succeeded; all workspace deps installed
- [x] `make -C nfl-oracle test` passed (22 tests, 1.17s)
- [x] Lint/typecheck/build wired; ready for daily shadow ops
- [x] Root Codespaces smoke passes after `daily_shadow.py` lint cleanup and
  includes NBA/NHL scaffold checks.
- Railway CLI installed in Codespace (`railway 5.49.2`), but auth returns
  Unauthorized with the current `RAILWAY_TOKEN`; `railway link` / `status`
  stay blocked until a refreshed token has project access.
- Local Railway auth cache was cleared (`railway logout` + config cleanup) and
  `railway whoami` still returns Unauthorized, so this is token access/scope,
  not stale local CLI state.
- No contest entry code or credentials staged.

## Box Real Sports auth (2026-09-06 CT)

Executor box `/workspace/sports` on branch `codex/nfl-data-schemas-scaffold`:

- [x] Offline `scripts/auth-check nfl-oracle --offline` passed
- [ ] No `REALSPORTS_STORAGE_STATE_B64GZ` / path env on box
- [ ] No `nfl-oracle/.secrets/*.sops.env` or age private key on box
- [ ] No registered local machines via ListMachines for pulling scraper state
- Live Corpus G backfill blocked until Ben seeds storage_state (SOPS decrypt via
  `scripts/with-secrets wnba-oracle -- …`, Codespaces secret, or local
  `nfl-oracle/scraper/storage_state.json` mode 0600)
- Never print token / storage_state values

## Codespace daily ops (planned)

**HOLD** until Ben confirms Codespaces secret `RAILWAY_TOKEN` is set for
`cheeksmagunda/sports`. Prep/docs only until then. Do not create/start
Codespaces, mint tokens, set secrets, or deploy from this checklist.

Org-wide default: Codespaces is the long-term home for **every** app's daily
processes in this monorepo (Mac is not the standing ops host). NFL is the first
concrete slice.

Checklist (execute only after HOLD clears):

- [ ] Confirm `RAILWAY_TOKEN` Codespaces secret present (Ben dashboard mint +
      `gh secret set RAILWAY_TOKEN --app codespaces --repo cheeksmagunda/sports`)
- [ ] Keep existing sports Codespace; refresh checkout to `chat/89-nfl-real-corpus`
      (PR #92) or a dedicated daily branch (do not recreate blindly)
- [ ] Set Real env key names as Codespace secrets only (never git):
      `NFL_DEVICE_UUID`, `NFL_DEVICE_NAME`, plus storage-state keys as needed.
      Do not rely on `NFL_REALSPORTS_DEVICE_*` (code does not read those).
- [ ] Daily shadow pipeline (America/Chicago clocks; no contest entry; #91 shadow):
      Corpus G coverage refresh → label/baseline recompute → status artifact
- [ ] Record run timestamps + clock fields (`event_time`, `source_available_at`,
      `captured_at`, `decision_at`) on artifacts / strategy notes
- [ ] Optional parallel: denser Corpus G census only when Ben picks it up

## Codespace secret inventory (2026-09-06 CT)

- Codespaces secret `RAILWAY_TOKEN` is present (name-only check via `gh secret list --app codespaces`).
- No Real Sports storage-state secrets in repo or Codespaces secret lists.
- Repo secrets include Railway workspace token and DB-related keys (WNBA); none are NFL storage_state.

## GitHub publish blocker (2026-09-06 CT)

- Branch `codex/nfl-data-schemas-scaffold` is local-only (ahead of `main`; push 403).
- Tracking: GitHub issue #94. Box PAT lacks Contents:Write.
- Codespace has `/tmp/nfl-schemas.bundle` + `/tmp/cs-push-bundle.sh` (cp OK); SSH from box hangs — run push inside CS.
- No Railway deploy; nfl-oracle has no railway.toml.


## Overnight research hardening (2026-09-06 01:18 CT)

Local-only on `codex/nfl-data-schemas-scaffold` (push blocked; do not retry):

- Verified contest scoring algebra scaffold: `nfl_oracle.strategy.algebra`
  (`score = value * (slot_multiplier + multiplierBonus)` non-negative branch;
  observed defaults `[2, 1.8, 1.6, 1.4, 1.2]`; negative branch refused)
- Entry gates: `nfl_oracle.strategy.gates.evaluate_entry_gates` — checklist always
  keeps `contest_entry=False`; `FiveCardProviderStub.submit` still hard-denies
- Research API: `GET /research/schemas/scoring`, `GET /research/gates/entry`,
  `POST /research/shadow/rank-orderings`; shadow preview gains contest algebra +
  best ordering; `/research/status` includes entry_gates + auth presence
- Features: `week`, `prior_n_games`, `card_boost_post_settlement` (live_ok=false);
  `nfl_oracle.features.rows` walk-forward prior feature rows
- Box state (honest): Real Sports auth missing; GitHub Contents write 403; no
  in-repo Railway Dockerfile/railway.toml; staging names only; no deploy
- Verification: pytest **66 passed**; ruff + mypy clean on `nfl-oracle/src`


## Identity / coverage density + research integration (2026-09-06 ~01:23 CT)

Local-only on `codex/nfl-data-schemas-scaffold` (push blocked; do not retry):

- Offline density helpers: `nfl_oracle.identity.density`, `nfl_oracle.data.density`
- Dense fixtures: `tests/fixtures/identity/dense_players.json`,
  `tests/fixtures/coverage/dense_{catalog,matrix}.json`,
  `tests/fixtures/offline_research/data/catalog/*` for research TestClient roots
- Identity hydrate composes `firstName`+`lastName`; `hydrate_identity_fixtures` emits density
- `research_data_summary` includes `density` block (seed means + matrix status ratios)
- Integration: `tests/integration/test_research_routes.py` (full route surface, dense coverage,
  shadow/rank, gates hard-deny, validation 422s)
- Box verification: pytest **78 passed**; ruff + mypy clean on `nfl-oracle/src`
- **Still deny real submit**; Real Sports auth missing on box; GitHub Contents write 403

## Denser fixtures + draft readiness honesty (2026-09-06 ~01:30 CT)

Local-only on `codex/nfl-data-schemas-scaffold` (push blocked; do not retry):

- Denser offline fixtures: 8 seasons / 36 catalog seeds; coverage matrix 6 known / 1 unknown / 1 blocked (18 matrix games); identity ~41 players (≥36 complete)
- Offline research root now includes `data/identity/players.json`
- Extra value_labels fixtures: 2022/1002, 2025/5001
- Research API: `GET /research/identity/density`; `/research/status` adds `identity` + `draft_readiness` (submit_hard_denied, railway_deploy_ready=false, deny_by_default_entry_gates)
- `research_data_summary` includes `identity` block
- Integration tests cover denser coverage/identity, draft_readiness honesty, provider submit/inventory hard-deny
- Entry gates: `package_submit_hard_deny` remains ok=False; `contest_entry` never flips
- Box verification: pytest **81 passed**; ruff + mypy clean on `nfl-oracle` paths
- **Still deny real submit**; Real Sports auth missing on box; GitHub Contents write 403; no Railway Dockerfile/railway.toml


## Strategy posture vocabulary (2026-09-06 CT)

Observation-only `nfl_oracle.strategy.schema.Posture` / `posture_from_readiness`:

| Posture | When | Contest entry |
|---------|------|---------------|
| `blocked` | Real auth missing, or defensive if readiness ever claims `contest_entry=true` | never |
| `shadow_only` | Provider stub status with auth present | never |
| `ready_pending_contract` | Auth present, contract still `#91` unverified | never |
| `capture_only` | Contract marked verified; package still denies submit | never |

Box / CI default without storage_state → `blocked` via `auth_missing`.
`evaluate_entry_gates` always keeps `contest_entry=false`; `package_submit_hard_deny` stays `ok=false`.
Research `/research/status` and `/research/provider/status` expose posture for honesty only.

## Schedule + denser coverage fixtures (2026-09-06 ~01:40 CT)

Local-only on `codex/nfl-data-schemas-scaffold` (push blocked; do not retry):

- Schedule helpers: `summarize_schedule_density`, `load_schedules_csv`, `week_for_gameday`,
  `catalog_vs_schedule_density`; `season_week_for_date(..., schedule=)` resolves week offline
- Fixture: `tests/fixtures/schedule/dense_schedules.csv` (3 seasons / ≥24 games / ≥8 week-slots)
- Coverage denser: 10 seasons / 45 catalog seeds; matrix 8 known / 1 unknown / 1 blocked (26 matrix games)
- Offline research root mirrors denser catalog/matrix
- Script: `scripts/research_client_smoke.py` / `make -C nfl-oracle research-smoke` (TestClient offline)
- STATUS posture table above documents deny-by-default strategy posture
- Box verification: pytest **94 passed**; ruff + mypy clean on `nfl-oracle` paths
- **Still deny real submit**; Real Sports auth missing on box; GitHub Contents write 403; no Railway Dockerfile/railway.toml

## Draft readiness densify (2026-09-06 ~01:50 CT)

Local-only on `codex/nfl-data-schemas-scaffold` (push blocked; do not retry):

- Coverage denser: **12 seasons / 56 catalog seeds**; matrix **10 known / 1 unknown / 1 blocked** (32 matrix games); known_ratio ≈ 0.833
- Identity denser: **~57 players** (≥50 complete) mirrored into offline research root
- Schedule denser: **4 seasons / ≥36 games / ≥12 week-slots** (`tests/fixtures/schedule/dense_schedules.csv`)
- Research API tests expanded (`tests/unit/test_research_api_draft_edges.py`); smoke hits GET routes + shadow preview + rank-orderings via TestClient (`scripts/research_client_smoke.py` / `make research-smoke`)
- Box verification: pytest **103 passed**; ruff + mypy clean on `nfl-oracle` paths
- **Still deny real submit** — `FiveCardProviderStub.submit` raises; entry gates `package_submit_hard_deny` ok=false; `contest_entry` never flips
- Honest gaps unchanged: Real Sports auth missing on box (posture `blocked`); GitHub Contents write 403; branch local-only; no Railway Dockerfile/railway.toml

## Research-smoke polish + denser matrix (2026-09-06 ~01:40 CT)

Local-only on `codex/nfl-data-schemas-scaffold` (push blocked; do not retry):

- Coverage denser: **14 seasons / 70 catalog seeds**; matrix **12 known / 1 unknown / 1 blocked** (40 matrix games); known_ratio ≈ 0.857
- Offline research root mirrors denser catalog/matrix (`tests/fixtures/coverage/dense_{catalog,matrix}.json`)
- `make research-smoke` polish: strip `DATABASE_URL`/`REDIS_URL` like `make test`; `SMOKE_ARGS` passthrough; smoke asserts density floors + `package_submit_hard_deny`
- **Still deny real submit** — entry gates hard-deny; `contest_entry` never flips
- Honest gaps unchanged: Real Sports auth missing on box (posture `blocked`); GitHub Contents write 403; branch local-only; no Railway Dockerfile/railway.toml

## Offline census + identity aliases + feature depth (2026-09-06 ~01:45 CT)

Local-only on `codex/nfl-data-schemas-scaffold` (push blocked; do not retry):

- **Schedule/coverage census:** denser offline schedules (8 seasons / ≥120 games /
  ≥60 week-slots; 2023–2025 full weeks 1–18). Helpers: `try_load_schedules_csv`,
  `resolve_schedule_csv_path`, `build_gameday_week_index`, `season_week_census`,
  `coverage_schedule_census`, `research_schedule_summary`. Research routes:
  `GET /research/schedule/summary`; coverage summary embeds schedule + census.
- **Identity aliases:** `identity.aliases` (`upsert_with_aliases`,
  `apply_alias_table`, `reconcile_alias_collisions`); density tracks
  `n_with_external_alias` / `alias_ratio`. Fixture ~89 players with gsis/espn
  aliases + intentional display-name collision pair.
- **Feature registry depth:** pre-lock live_ok features expanded (calendar /
  matchup / identity / prior tiers incl. median + team prior + days_rest +
  kickoff_slot); `features_document` reports group/live counts.
- **research-smoke:** documented in README; TestClient subset asserts schedule
  census floors + `provider_contract_verified` ok=false + package hard-deny.
- **Still deny real submit** — entry gates hard-deny; `UNKNOWN_PROVIDER_RULES`
  unchanged (offline notes only for slot weights / negative branch).
- Box verification: pytest **116 passed**; ruff + mypy clean; research-smoke OK
- Honest gaps: Real Sports auth missing (posture `blocked`); GitHub Contents
  write 403; branch local-only; no Railway Dockerfile/railway.toml; Claude gap #3 feature_ridge landed (optional); #91 live contract still open.

## Claude gap #1 — full-season schedule census (2026-09-06 ~01:55 CT)

Local-only on `codex/nfl-data-schemas-scaffold` (push blocked; do not retry):

- Public **nflverse/nfldata** `games.csv` cached/slimmed (CC BY 4.0; see `DATA_ATTRIBUTION.md`)
- Committed continuous slates: `data/schedule/schedules.csv` — **24 seasons / 6499 games**
  (REG+post); fixture `tests/fixtures/schedule/dense_schedules.csv` — **8 seasons / 2227 games**
- Loaders: `resolve_schedule_csv_path`, `try_load_schedules_csv`, `summarize_season_slate`,
  `season_week_census`, `coverage_schedule_census`, `research_schedule_summary`
- Continuous REG discovery: weeks 1..17 (legacy) / 1..18 (modern) without holes;
  smoke reports `schedule_seasons=24 schedule_games=6499`
- Refresh: `scripts/cache_nflverse_schedules.py` / `make cache-schedules`
- Research: `GET /research/schedule/summary` + coverage summary embeds schedule census
- **Still deny real submit**; Real Sports auth optional/missing; no GitHub push

## Claude gaps #2 / #4 / #5 offline (2026-09-06 ~02:15 CT)

Local-only on `codex/nfl-data-schemas-scaffold` (push blocked; do not retry):

- **Gap #4 identity:** `normalize_display_name` / `name_match_keys` / soft
  nickname bridges beyond first+last; `suggest_dedup_candidates` (never
  auto-merges). Fixtures ~115 players with Jr/III collisions, nickname soft
  keys, intentional shared-gsis alias collision. Tests cover collisions.
- **Gap #5 features:** injury / weather / pace / opponent-adjusted
  FeatureSpecs with `offline_stub=True` and clear live_ok flags;
  `offline_stub_feature_row` emits null/false placeholders;
  `live_ok_feature_names()` ≥24 including injury/weather/pace/opp-adj.
- **Gap #2 provider rules:** `OFFLINE_RULE_NOTES` now covers all 7
  `UNKNOWN_PROVIDER_RULES` (best-effort public/playbook notes). Notes do
  **not** remove keys or enable submit. Research:
  `GET /research/provider/rules-offline`; docs
  `src/nfl_oracle/providers/RULES_OFFLINE.md`.
- **Still deny real submit** — entry gates hard-deny; `submit()` raises;
  `provider_contract_verified=false`.
- Box verification: pytest **122 passed**; ruff + mypy clean; research-smoke OK
- Honest gaps unchanged: Real Sports auth missing; GitHub Contents write 403;
  no Railway Dockerfile; value model beyond mean/median still deferred; #91 live
  contract still open.


## Claude gap #3 — feature-driven value model (2026-09-06 ~02:05 CT)

Local-only on `codex/nfl-data-schemas-scaffold` (push blocked; do not retry):

- Built on peer HEAD `a802bc5` (gaps #2/#4/#5). Optional walk-forward method
  **`feature_ridge`**: stdlib ridge on live_ok prior features
  (`player_prior_mean`, position mean/median, global/team priors,
  `prior_n_games`, position one-hots). No numpy/sklearn required.
- Modules: `nfl_oracle.baselines.ridge`, `nfl_oracle.baselines.value_model`,
  `nfl_oracle.strategy.value_preds` (shadow `values_by_player` wiring)
- CLI: `nfl-value-baselines --methods feature_ridge` (optional). **Default**
  path unchanged: `global_mean` / `position_mean` / `position_median` only.
- Leakage proofs: train seasons strictly earlier than test; design matrix never
  includes label/`same_slate_*`; mutating held-out y does not change OOS preds.
- Box verification: pytest **132 passed**; ruff + mypy clean on touched paths
- **Still deny real submit**; Real Sports auth optional/missing; no GitHub push


## Shadow value-model flag (2026-09-06 ~02:10 CT)

Local-only on `codex/nfl-data-schemas-scaffold` (push blocked; do not retry):

- Wired optional **`feature_ridge`** into research shadow preview / rank-orderings
  via request flag **`use_feature_value_model`** (default **`False`** = offline-safe
  explicit `values_by_player` path; no model fit unless opted in).
- Opt-in requires `player_positions`, `decision_season`, and inline `train_labels`
  (seasons strictly earlier than decision). Response includes `value_model` meta
  (`value_source` = `explicit` | `feature_ridge`).
- Status exposes `value_model.shadow_flag` / `shadow_flag_default=false`.
- E2E TestClient: schedule summary + shadow rank (explicit + flag) + provider
  rules-offline (`tests/integration/test_research_routes.py`).
- `make research-smoke` remains the offline smoke entry (hard-deny; strips DB/redis).
- Box verification: pytest **136 passed**; ruff + mypy clean on touched paths;
  `research-smoke` OK.
- **Still deny real submit** — entry gates hard-deny; `submit()` raises;
  `provider_contract_verified=false`.
- Honest gaps unchanged: Real Sports auth missing on box (posture `blocked`);
  GitHub Contents write 403; branch local-only / unpushed; no Railway
  Dockerfile/railway.toml; draft readiness gates deny by default; #91 live
  contract still open.

## Research OpenAPI tags + readiness score (2026-09-06 CT)

- OpenAPI tags split: `research-schemas`, `research-provider`, `research-shadow`,
  `research-data`, `research-status` (legacy flat `research` tag removed)
- `GET /research/health/readiness-score` — 0–100 observation-only density score
  (`nfl_oracle.strategy.readiness_score`); also optional on `/research/status`
- High score does **not** authorize contest entry; auth missing expected on box
- pytest: 144; branch still local-only (push 403)


## Offline contest dry-run (2026-09-06 ~02:10 CT)

Local-only on `codex/nfl-data-schemas-scaffold` (push blocked; do not retry):

- `nfl_oracle.strategy.dry_run` — builds a five-card shadow slate from offline
  value-label fixtures (`tests/fixtures/value_labels`); default values =
  walk-forward player/position priors; optional **`feature_ridge`**
- Labels: `mode=dry_run`, `dry_run=true`, `observation_only=true`,
  `contest_entry=false`; `submit_proof` calls stub.submit and records hard deny
- CLI: `nfl-contest-dry-run` / `make -C nfl-oracle contest-dry-run`
- Research: `GET /research/shadow/contest-dry-run` (`use_feature_ridge`,
  `decision_season`, `top_k` query params)
- pytest: **155**; still **no push**; real contest entry remains hard-denied


## Contest dry-run × week/slate harden (2026-09-06 ~02:30 CT)

Local-only on `codex/nfl-data-schemas-scaffold` (push blocked; do not retry):

- `resolve_dry_run_schedule_slate` — priority: explicit `schedule_date` →
  `schedule_week` → label `event_time` → week-1 fallback; records `dry_run_attach`
- Optional `schedule_team` on dry-run CLI / research route for opponent lookup
- Tests: unit priority + CLI text attach; integration date/auto/422
- pytest: **172**; gates unchanged (`contest_entry=false`; submit hard-deny)


## Walk-forward eval report (2026-09-06 ~02:15 CT)

Local-only on `codex/nfl-data-schemas-scaffold` (push blocked; do not retry):

- Offline **baselines vs `feature_ridge`** walk-forward report on fixture labels
- Modules: `nfl_oracle.baselines.eval_report` + CLI `nfl-walk-forward-report`
- Make: `make -C nfl-oracle walk-forward-report`
- Checked-in sample: [`artifacts/walk_forward_fixture_sample.md`](artifacts/walk_forward_fixture_sample.md)
  (+ `.json`); generated `walk_forward_latest.*` gitignored
- Tests: `tests/unit/test_eval_report.py`
- **Dry-run / submit gates unchanged** — `contest_entry=false`; hard-deny intact
- Fixture-scale ranking (illustrative): `position_mean` best MAE; `feature_ridge`
  does not beat classical priors on the tiny fixture set
- Box verification: pytest **160 passed**; ruff + mypy clean on baselines eval paths
- Still **no push**; Real Sports auth optional/missing

## Value law decoded and replay harness verified (2026-09-09 ~00:50 UTC)

Local, uncommitted at time of writing, on `chat/115-nfl-live-pipeline`. New
package `nfl_oracle.valuelaw` and new package `nfl_oracle.replay`, both with
unit tests; full suite green (**251 passed, 1 skipped**, up from 240; ruff and
mypy --strict clean on every new module).

### The Real `value` label is not a pure function of the box score, but is close

Across 47,209 finalized Corpus G player-games, 2,246 distinct (position, exact
stat line) groups occur more than once; only 430 have an identical `value` in
every occurrence, 1,816 differ. So `value` carries roughly 5% variance the box
score cannot explain (`nfl_oracle.valuelaw.boxstats`'s `purity` check:
`unexplained_variance_share` 0.0496 on 47,206 labelled rows, 17,810 groups,
2,246 with more than one row). The remaining ~95% is recoverable: a plain
ridge fit (`nfl_oracle.valuelaw.model.fit_all`, alpha 1e-6, effectively OLS)
trained on season 2024 and tested out-of-sample on season 2025, per position,
regular season only:

| pos | train | test | OOS R2 | OOS MAE | position-mean MAE | lift |
|-----|-------|------|--------|---------|--------------------|------|
| QB  |  732  |  723 | 0.965  | 0.233   | 1.603              | 85.5% |
| RB  | 1698  | 1743 | 0.989  | 0.084   | 1.489              | 94.4% |
| WR  | 2599  | 2677 | 0.985  | 0.077   | 1.146              | 93.3% |
| TE  | 1282  | 1350 | 0.983  | 0.056   | 0.795              | 92.9% |
| DL  | 3410  | 3446 | 0.903  | 0.138   | 0.666              | 79.3% |
| LB  | 3162  | 3385 | 0.920  | 0.120   | 0.797              | 85.0% |
| DB  | 4236  | 4362 | 0.949  | 0.084   | 0.763              | 89.0% |
| K   |  571  |  569 | 0.918  | 0.328   | 1.465              | 77.6% |
| P   |  551  |  559 | 0.965  | 0.078   | 0.537              | 85.5% |

OL and LS both fit R2 ~0 (near-constant near-zero label: OL mean 0.028,
91.6% exact zero; LS mean 0.047, 93.8% exact zero) -- they are correctly
near-undraftable, not a modelling failure. Recovered defensive coefficients
read like clean rules: solo tackle ~0.20, forced fumble ~0.4-0.6, sack
~0.7-0.8, interception ~2.0, fumble recovery ~1.9, consistent across DL/LB/DB.
Persisted fit: `nfl-oracle/data/artifacts/valuelaw/value_model.json`.
Modules: `nfl_oracle.valuelaw.boxstats` (dataset + label characterisation,
`nfl-oracle/data/artifacts/valuelaw/box_stats.jsonl` + `_schema.json` +
`_label_report.json`), `nfl_oracle.valuelaw.model` (fit/predict/persist),
`nfl_oracle.valuelaw.candidates` (live slate load, Corpus G history join,
live re-collect, slate diff -- already exercised against the real contest
2141 slate, see below).

**Honest caveat on the achievable ceiling.** The box-score-to-value map being
solved does not mean *projecting the box score* is solved. A walk-forward
replay over all 668 games (prior-game EWMA per player, decay 0.9, minimum 3
games, falling back to position mean) predicting the next game, then scoring
a single expected-value-maximizing 5-card lineup under the verified law:
mean capture of the legal hindsight-best lineup is **61.1%**, median 63.4%
(decile spread 35%/48%/63%/76%/84%). Kicker value is NOT predictable from a
kicker's own history (player EWMA MAE 1.53 worse than position-mean MAE
1.48) -- it is opportunity-driven, not skill-driven, and must be projected
from team context, not the kicker's own line. Defenders are only marginally
more predictable than their position mean. This 61% single-entry figure is
not in tension with the archive's 79.9%/97.5% winner-capture numbers below --
those are the **argmax of 12,000-62,000 entries**, not the expectation of
one entry. Conflating the two would overstate what a single recommended
lineup is likely to achieve.

### Replay harness: STATUS.md's own headline claims are now code-derivable

New `nfl_oracle.replay` package (`harness.py`, tests in
`tests/unit/test_replay_harness.py`) replays all 91 finalized Corpus C
contests via the already-existing, already-verified
`nfl_oracle.contests.parse.iter_contests`. It does not re-parse or
re-verify the scoring law; it consumes `ParsedContest` records directly.

Running it over the real archive today reproduces the "Corpus C landed"
section above almost exactly, independently, in code:

| slice | contests | optimal-order rate | mean slot regret | mean winner capture |
|-------|----------|---------------------|-------------------|----------------------|
| overall | 91 | 3.19% | 1.452 | 79.9% |
| zero-boost | 4 | 6.25% | 0.443 | 97.5% |

(STATUS.md's prose above says 3.2% / 6.2%, 1.45 / 0.44, 79.9% / 97.5% --
matches to the stated precision.) 6 of 91 finalized contests fail the
additive scoring-law check (5, 851, 880, 892, 893, 979) -- these are already
surfaced by `iter_contests`'s `law_verified` flag and excluded from any
"law reconciles" claim; they are not silently averaged in here either.

**Bug found and fixed during this build, worth recording:** the first
version of `hindsight_best_lineup` selected the top-k players by raw
finalized value and only applied boosts when scoring the total. That is
correct only when every boost is equal (e.g. the zero-boost regime), and it
produced impossible results in boosted contests (some `winner_capture_ratio`
values above 1.0, i.e. the visible rank-1 entry scoring higher than the
computed "hindsight best", which is a contradiction). The fix: because the
score decomposes into an order-invariant `sum(value*boost)` term and a
rearrangement term `sum(value*slot)` that for any FIXED five players is
maximized by descending-value slot assignment (rearrangement inequality)
regardless of boost, selecting the optimal five reduces to a linear-time
DP over the value-sorted pool (`hindsight_best_lineup` in
`nfl_oracle/replay/harness.py`). After the fix, max observed capture ratio
across all 91 contests is 0.999, as it must be by construction, and the
zero-boost numbers were unaffected (boost is uniform there, so naive
selection was already exact) -- confirming the bug did not touch the number
that matters for tomorrow's zero-boost slate, but would have corrupted any
general-regime claim if left in.

### Freeze-path audit: the pipeline is further along than earlier entries assumed

A read-only audit of `nfl_oracle.recommendations` and `nfl_oracle.strategy`
found most of the seven required T-40 gates already enforced, contrary to
this file's earlier "release blockers" note:

- **Already enforced:** locked/finalized contest refusal
  (`recommendations/schema.py:140`), per-source clock freshness via
  `assert_prelock(max_age_seconds=900)` (`schema.py:138-153`), player identity
  by exact provider id with no name-based fallback (`provider.py:233-270`),
  model staleness and training-fingerprint validation
  (`pipeline.py:54-60,110-112`), contest-lock-refresh consistency
  (`validate_lock_refresh`, `pipeline.py:81-87`), and a structural submit
  hard-deny (`FiveCardProviderStub.submit()` unconditionally raises,
  `providers/five_card.py:185-189`; recommendations code never calls it).
- **Real gaps, confirmed, not yet closed:** (1) pool completeness --
  `pool_roster_count`/`pool_unmatched_ids` are recorded
  (`schema.py:111-113`) but nothing gates on `pool_unmatched_ids == ()`; a
  partial pool would currently pass silently. (2) boost-regime declaration --
  `nfl_oracle.contests.boosts.BoostObservation.all_zero` exists and is
  correct but is never imported by `recommendations/`; the optimizer accepts
  whatever `card_boost` values a candidate carries with no explicit
  zero_boost-vs-published classification recorded on the frozen artifact.
- Store backend is SQLite-or-Postgres via `NFL_DATABASE_URL`
  (`recommendations/store.py`, `cli.py:48-58`); a `sqlite:///...` URL works
  fully locally, append-only enforced by a BEFORE UPDATE/DELETE trigger on
  both backends. No Postgres requirement blocks a local T-40 run.
- Entry point is `nfl-pipeline {serve,migrate,train,worker}`
  (`recommendations/cli.py`); `worker` runs collect -> context -> model ->
  `pipeline.prepare()` -> `pipeline.publish()` end to end, waiting for T-40
  internally.
- The optimizer (`recommendations/optimizer.py:38-46`) implements
  `score = value * (slot + boost)` exactly and uses `scipy.optimize.milp`
  exact search when available (bounded beam search fallback otherwise), but
  does not emit a rearrangement-inequality proof alongside its output --
  the *result* is provably optimal by construction whenever milp runs, but
  the artifact does not say so.

### Slate truth for contest 2141, confirmed twice independently

Two independent live reads tonight (this session's manual check at
00:16 UTC, and a live re-collect via `nfl_oracle.valuelaw.candidates`
saved to `data/artifacts/slate_2141_live_20260909T002548Z.json` at
00:25:48 UTC) agree exactly: 161 candidates, pool method
`roster_exact_id_search` with `pool_roster_count == pool_search_matched_count
== 161` and `pool_unmatched_ids == []` (a legitimate, stated-denominator
completeness proof), all 161 `card_boost` values 0.0, contest not locked or
finalized. 141 Active, 18 Out (including both listed backfield starters:
TreVeyon Henderson for NE and Zach Charbonnet for SEA -- NE's clear starter
is now Rhamondre Stevenson, SEA's backfield has no clear starter among
Holani/Jones/Wilson/Wright/Price), 2 Questionable (Tory Horton, Nick
Emmanwori). The boost watcher launched this session
(`nfl-boost-watch --contest-id 2141 --day 2026-09-09 --interval 900 --until
2026-09-09T23:40:00Z`, still running) has logged all-zero every 15 minutes
since 22:46 UTC.

### Cleanup checkpoint after failed subagents

Commit `31968386d7488b1252ada04534be730efdf60c8b` on
`chat/115-nfl-live-pipeline` closes the two concrete freeze-path gaps found
above: `Slate.assert_prelock()` now refuses incomplete pools, and every slate
declares `zero_boost` or `provider_boosts_present` with checked counts and max
boost. `NFLReader.collect()` passes those declarations from the provider
capture, and regression tests cover complete, partial, zero-boost, and boosted
slates.

The branch also adds small, explicit research helpers for the failed projection
and backtest subagents: `nfl_oracle.valuelaw.project` projects candidates from
Real-id Corpus G history and returns zero-boost slot recommendations in
descending projected value; `nfl_oracle.replay.backtest` replays zero-boost
games from prior player history and reports capture ratio summaries. These are
not a claim of a calibrated production edge. They are executable scaffolds for
the one-game week-1 decision path and for honest historical capture reporting.

Frontend status after `7b208f8`: the served page renders five cards in slot
order as player name plus team, position, and opponent. It intentionally omits
numeric projections and repeats that entries are never submitted
automatically.

Checks run in the canonical Codespace after `3196838`: `make write-path-check`,
`make test-app APP=nfl-oracle` (257 passed, 1 skipped), `make -C nfl-oracle
lint`, `make -C nfl-oracle typecheck`, `make check-boundaries`, and `make
codespaces-smoke`. Docker is not installed in that Codespace, so the Docker
smoke targets skip there by design. The Mac Docker production smoke passed
after `.dockerignore` was updated to include `nfl-oracle/config/`.
