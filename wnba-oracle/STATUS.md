# Status

Last verified: 2026-09-27T03:45:00Z

## Next-slate readiness (#453)  -  2026-09-27 ~03:40Z

| Check | Result |
|-------|--------|
| Slate | `2026-09-26`; first tip `2026-09-27T18:00:00Z`; freeze target `2026-09-27T17:20:00Z` |
| Serving health | API `/health` ok; frontend HTTP 200; watchdog `status=ok`, `ready_for_freeze=true` |
| Dual-fire | Live `wnba-oracle` cron schedules **null**; mono schedules armed (job1 `0 13`, job1-late `*/30 16-23`, job2 `*/5 14-23,0-3`, dayclose `0 6`) |
| DATA_PLANE_MATCH | Same live Postgres (`acela.proxy.rlwy.net:51730`, password hash match) and Redis (`altaria.proxy.rlwy.net:13969` = live redis TCP proxy); mono uses `sslmode=require` |
| DB freshness | `wnba_game_logs` seasons **2017-2026** present (49756 rows; 2026 max game_date `2026-09-24`) |
| Job2/API knobs | `PAYOUT_REGIME=top_1`, `OPTIMIZER_OBJECTIVE_MODE=total_draft_value`, `OPTIMIZER_MAX_VALUE_OWNERSHIP_FADE=0.001`, `LIVE_OWNERSHIP_CAPTURE_ENABLED=true` (api+job2 process env verified) |
| QUEUED | Cleared stuck QUEUED deploys via `deploymentCancel` |
| Residual | Advisory `config_drift` clears after this PR merges+redeploys; advisory `rotowire_empty` until Sunday ~13:00Z job1 |

## Serve Tier-0 -> EB primary + vegas/boost (#523)  -  2026-09-27

Code on branch (not yet production-verified on mono):

- Serve ladder default is `WNBA_SERVE_PRIMARY=eb`: Tier-0 uses
  `EBHierarchicalBaseline` with optional `team_pace` / `opp_pace` /
  `vegas_total` / `card_boost` from `head_features` + pool row.
  Starter confirmation remains a serve-time multiplier.
  Minutes blend / player-history / heuristic remain cold-start only.
- LightGBM quantile heads stay in the train artifact and fire only when
  `WNBA_SERVE_PRIMARY=heads` (rollback without removing train code).
- `models.yaml` documents EB weight 1.0 / LGBM 0.0 (serve never applied
  the old 70/30). Train/grade labels remain Highest-value boards (#505).
- RS field matrix: `features.rs_field_map`; key-dump scaffold
  `scripts/rs_corpus/` (durable HV corpus: #526 / PR #532).
- Production mono job2: unverified until merge + redeploy. Rollback:
  set `WNBA_SERVE_PRIMARY=heads` on `wnba-cron-job2` / `wnba-api` and
  redeploy (cron variable changes need a real redeploy).

## Training target: Total Value Daily Leaderboard (#453 / #505 / #523)  -  2026-09-27

Locked: train / optimize on Real Sports **Highest value / Total Value Daily
Leaderboard** (`draftStats.sectionName=highestBoostedValuePlayers`) for every
slate - Amihere / Copper / Aubrey-style boards down the list.
**Do not train on prior users' winning drafts** (`contest_leaderboards` /
`leaderboard_lineup`); those are a reference bar to beat, not fit targets.
Popularity sections are excluded from the EB label corpus. Backtests grade
each slate against that slate's Highest value players, not winning drafts.
Portfolio goal: root `../README.md` (Product goal). Current serve knobs live
in the mono / Win-draft sections below. Existing EB / ridge surface only; no
new model stacks (#523).

## Multi-year `wnba_game_logs` accuracy (#509 / #492 / #498 / #453)  -  2026-09-27T03:03Z

Read-only verify via Codespace `fluffy-zebra-g4gqq746477q2jg` +
`scripts/codespace-railway-env` against `sports-oracle` / `wnba-production`.
App `DATABASE_URL` / `DATABASE_PUBLIC_URL` on `wnba-api` and
`wnba-cron-dayclose`: host `acela.proxy.rlwy.net:51730`, `sslmode=require`,
`sha256[:8]=088a0da2` (no secrets printed).

### `wnba_game_logs` per season

| Season | Rows | Min date | Max date | Flag |
|--------|------|----------|----------|------|
| 2017 | 4747 | 2017-04-29 | 2017-10-04 | ok |
| 2018 | 4824 | 2018-05-06 | 2018-09-12 | ok |
| 2019 | 4697 | 2019-05-09 | 2019-10-10 | ok |
| 2020 | 2796 | 2020-07-25 | 2020-10-06 | ok (COVID bubble; below prior-season median 4771 but above 50% floor) |
| 2021 | 4102 | 2021-05-05 | 2021-10-17 | ok |
| 2022 | 4771 | 2022-04-23 | 2022-09-18 | ok |
| 2023 | 5215 | 2023-05-05 | 2023-10-18 | ok |
| 2024 | 5249 | 2024-05-03 | 2024-10-20 | ok |
| 2025 | 6275 | 2025-05-02 | 2025-10-10 | ok |
| 2026 | 7080 | 2026-04-25 | 2026-09-24 | current season (partial) |
| **Total** | **49756** | | | matches #498 expected |

No season 2017-2025 underfilled relative to a 50% prior-season-median floor.
Missing seasons: none.

### Enrichment freshness

- `job1_enrichment`: 14491 rows / 252 distinct slates; max `captured_at`
  `2026-09-27T02:49:12Z` on slate `2026-09-26` (pool 124).
- Last 14d: `empty_feat=0`, `blank_opponent=0`, `starters=299` / 1837 rows.
- Tip-weekend gap (known #441 / RotoWire): slate `2026-09-25` and
  `2026-09-26` have `starters=0`; game-day `2026-09-24` has `starters=48`.
- `features_json` includes `head_features` on most recent-pool rows
  (e.g. 119/124 on `2026-09-26`).
- `slate_labels` latest durable slate: `2026-09-24` (dayclose product;
  09-25/09-26 not labeled yet at check time).

### Nightly / ops health

- Mono API `/health` ok; `/watchdog/today` `status=ok`, live `events=[]`,
  slate `2026-09-26`; freeze advisory still lists `rotowire_empty`
  (observation-only); `job1_last_status=success`.
- `wnba-cron-dayclose` latest SUCCESS deploy `822fa2f4` at
  `2026-09-27T02:45:25Z` (schedule `0 6 * * *`, next ~3h at check).
- Actions `wnba-dayclose-verify` last success
  [run 36240844716](https://github.com/cheeksmagunda/sports/actions/runs/36240844716)
  (2026-09-26T12:05Z).
- Actions `watchdog-monitor` still failing: workflows hardcode
  `WNBA_API_BASE=https://api-production-7033.up.railway.app` (legacy cold
  standby). Mono serving URL is healthy; Actions probe URL drift is residual
  cutover debt (also `wnba-pre-freeze-guard`, `wnba-backfill-enrichment`).

## Sports-oracle cutover (serving) (#453 / #457)  -  2026-09-27 ~02:00Z

Operator-authorized Sunday-path cutover to Railway project **`sports-oracle`**
(`cca6b03f-…`) / environment **`wnba-production`**. Codespace
`fluffy-zebra-g4gqq746477q2jg` via `scripts/codespace-railway-env`. No secrets
printed.

### Active serving plane

| Resource | Verified fact |
|----------|---------------|
| Project / env | `sports-oracle` / `wnba-production` |
| Source SHA | `70ea992` on `main` (tip-day `4c7c959` ancestor; newer than tip-day floor) |
| API health | `https://wnba-api-wnba-production.up.railway.app/health` → `{"status":"ok","version":"0.1.0"}` |
| Frontend | `https://wnba-frontend-wnba-production.up.railway.app/` → HTTP 200 |
| Domains | Generated `*.up.railway.app` only (live had no custom domains to move). CLI domain move N/A. Old live URLs (`api-production-7033`, `frontend-production-a739`) remain on `wnba-oracle` until callers switch. |
| Data plane (cutover-time) | App URLs then hash-matched live `wnba-oracle` / `api` (`DB sha256[:8]=0cffc88e`, `REDIS sha256[:8]=b0421c4c`, `DBPUB sha256[:8]=42376805`). Mono Railway Postgres service stayed empty. |
| Data plane (re-verified 2026-09-27T03:00Z) | `wnba-api` / `wnba-cron-dayclose` `DATABASE_URL` + `DATABASE_PUBLIC_URL` → `acela.proxy.rlwy.net:51730` `sslmode=require` `sha256[:8]=088a0da2` (full `wnba_game_logs` corpus; see #509). Mono Railway `Postgres` service still separate/internal. |
| Cron schedules (mono) | job1 `0 13 * * *`; job1-late `*/30 16-23 * * *`; job2 `*/5 14-23,0-3 * * *`; dayclose `0 6 * * *` (GraphQL `serviceInstanceUpdate`) |
| Live old project crons | `wnba-oracle` / `production` cron-job1, job1-late, job2, dayclose schedules set to **null** (no dual-fire). Project **not** deleted. |
| Frontend API URL | Mono `VITE_API_URL=https://wnba-api-wnba-production.up.railway.app` |

### Rollback

1. Re-arm live `wnba-oracle` cron schedules to the values above (GraphQL
   `serviceInstanceUpdate` / CLI).
2. Null mono `wnba-cron-*` schedules (or leave mono idle).
3. Point any callers / bookmarks back to
   `https://api-production-7033.up.railway.app` and
   `https://frontend-production-a739.up.railway.app`.
4. Live Postgres/Redis unchanged throughout; no data restore required for this
   cutover shape.

### Residual

- Mono empty Postgres/Redis retained for a later true migrate (not tonight).
- Railway domain `update --port 4173` for frontend hit CLI rate limit; frontend
  still returned HTTP 200. Retry port pin when rate limit clears if needed.
- Old `wnba-oracle` api/frontend still online as cold standby (crons disarmed).

## Mono URL / data-plane note (#457 / #453)

- Canonical mono URLs are in the cutover table above.
- Legacy `wnba-oracle-production.up.railway.app` → HTTP 404; old
  `api-production-7033` / `frontend-production-a739` may remain until
  callers switch. Data-plane must use the **public TCP proxy** form of
  Postgres/Redis (not `*.railway.internal`). Design on #457.


## Win-draft knobs on mono (verified) (#453)  -  2026-09-27

- `PAYOUT_REGIME=top_1` on `wnba-cron-job2` + `wnba-api` (was `top_20`; rollback: restore `top_20`).
- `OPTIMIZER_OBJECTIVE_MODE=total_draft_value` on `wnba-cron-job2` + `wnba-api` (process env verified; rollback: `payout`).
- `OPTIMIZER_MAX_VALUE_OWNERSHIP_FADE=0.001` on those services.
- `LIVE_OWNERSHIP_CAPTURE_ENABLED=true` on those services.
- `EXPECTED_PROD_CONFIG["optimizer_objective_mode"]` synced to `total_draft_value` so job2 watchdog does not warn `config_drift` against the live flip.
- Under TDV, job2 skips contrarian sampler fade and floor-tilt (cash/median mid-slot blend); ownership preference is only the fade tiebreaker.
- Data plane: public Postgres `acela.proxy.rlwy.net:51730` with `sslmode=require` (not verify-ca — missing `root.crt` in container); Redis `altaria.proxy.rlwy.net:13969`.
- Live old crons nulled; mono crons armed. Watchdog hist match LIVE=MONO.

## Optional total_draft_value optimizer objective (#433 / #453)  -  2026-09-27

- `"total_draft_value"` selects by E[committed-order lineup score] and skips
  payout/leverage/ceiling/duplication additives; ownership-fade tiebreaker
  remains. Serving flip is live on mono `wnba-cron-job2` (see Win-draft knobs).
- Unit tests in `tests/unit/test_total_draft_value_objective.py`.

This file records live operational state only. Values marked unverified were
not exposed by the read-only checks available during this audit.

## Tip-day RotoWire fix live (#441 / #454 / #453)  -  2026-09-27

Historical note: prior to the sports-oracle cutover above, tip-day deploys
were verified on Railway project **`wnba-oracle`**. Serving is now mono.

- Merged #454 (`4c7c9598`) into `main` (replaces closed #445 after branch
  rename for issue-link enforcement). Follow-up #465 regenerated `FILES.md`.
- Railway (Codespace CLI session as Cheeks Magunda), production:
  - `api` SUCCESS deploy `b6980bde` on `4c7c9598`
  - `cron-job1` SUCCESS `95353809` on `4c7c9598`
  - `cron-job1-late` SUCCESS `f3dfb782` on `4c7c9598`
  - `cron-job2` SUCCESS `cc2a7a0a` on `4c7c9598`
  - `cron-dayclose` SUCCESS deploy `cd69934d-1aa5-4068-ab39-d7e9526f96e9`
    on `1adb1250530a` (from-source after tip-day; tip-day `4c7c9598` is an
    ancestor). Verified 2026-09-27T01:43Z via Codespace Railway CLI.
- Live API at 2026-09-27T01:36Z:
  - `/health` -> `status=ok`
  - `/watchdog/today` slate `2026-09-26` -> `status=ok`, `events=[]`
    (historical `rotowire_empty` rows remain under `history` only)
  - `/slate/2026-09-26` -> first tip `2026-09-27T18:00:00Z`, freeze target
    `2026-09-27T17:20:00Z`; `/lineup/2026-09-26` -> no freeze yet
  - `freeze_readiness` still observation-only / blocked with advisory
    `rotowire_empty` and `job1_last_status=failed` from the 2026-09-26 false
    alarms; next clean job1 is the Sunday ~13:00Z run
- Root cause (unchanged): on 2026-09-26 job1/job1late failed with
  `rotowire_empty_near_tip` inside the 30h lead while RotoWire free page
  had `no_games_scheduled` (lists only today's Eastern games).
- Fix: `ingest/rotowire.starters_expected` requires the 30h lead and the
  tip's Eastern date; job1, job1-lite, and watchdog share it.

## Scheduled WNBA checks report through their Actions runs, not issues (#442)  -  2026-09-26

- Per the issue rule in root `AGENTS.md` (Documentation and state),
  `watchdog-monitor.yml`, `wnba-dayclose-verify.yml`, and
  `wnba-pre-freeze-guard.yml` no longer open, comment on, label, or close
  issues, and none holds `issues: write`. Each posts its report to the run's
  job summary through `.github/actions/dayclose-ledger` and fails the run
  under the same conditions that previously escalated.
- `watchdog-monitor.yml` reports a probe crash under the `WNBA watchdog probe
  failure` heading and a completed probe under `WNBA Oracle watchdog`; both
  fail the run when warranted, and the heartbeat forwarding is unchanged.
  `wnba-pre-freeze-guard.yml` now writes a job summary on healthy runs too.
- The `ops-guard`, `ops-guard-probe`, and `ops-results` labels have no
  writer. #441 (`WNBA Oracle watchdog alert`, filed by `watchdog-monitor` at
  2026-09-26T19:58Z) was the last issue this channel filed; it reported
  dayclose `degraded` and job1/job1late `failed`. Older entries below that
  describe `ops-guard` or incident issues record past behavior only.

## Optional total_draft_value optimizer objective (#433 / #453)  -  2026-09-27

- `"total_draft_value"` selects by E[committed-order lineup score] and skips
  payout/leverage/ceiling/duplication additives; ownership-fade tiebreaker
  remains. Serving flip is live on mono `wnba-cron-job2` (see Win-draft knobs).
- Unit tests in `tests/unit/test_total_draft_value_objective.py`.

This file records live operational state only. Values marked unverified were
not exposed by the read-only checks available during this audit.

## WNBA race corpus builder (#337 under #332)  -  2026-09-25

- **Code:** `scripts/build_race_corpus.py` and `scripts/seasons_common.py`
  (PR #337); offline unit tests in
  `tests/unit/test_seasons_and_race_corpus.py`.
- **Operator build:** run from the Codespace with read-only
  `BACKUP_DATABASE_URL`, emit parquet under a temp dir, publish to the orphan
  `backups` branch (CSV corpus backup pattern; dedicated race workflow
  unverified until first dispatch).
- **Research scripts:** walk-forward, pipeline, counterfactual, knob
  calibration, and model-research benchmark accept `--seasons` (default
  `2025,2026`) instead of a hard `2026-` slate filter.

## rotowire_empty + enrichment_stale (#319)  -  2026-09-25

- **Symptom:** `/watchdog/today` warn with `rotowire_empty` (124-player pool,
  zero `is_starter`) and `enrichment_stale` (last capture 13:07 UTC vs old
  13:30 floor) for slate `2026-09-25` whose `first_tip_utc` is Sunday
  `2026-09-27T17:00:00Z` (freeze target 16:20 UTC / 11:20 AM CT).
- **Root cause:** Real Sports opened the Sunday contest on Friday. RotoWire
  correctly SSRs "no games on the WNBA schedule today," so `fetch_lineups()`
  returned [] and job1_lite nooped all day. Watchdog treated that as scrape
  or join failure. Separately, `enrichment_stale` used a 13:30 UTC floor while
  every healthy job1 finishes ~13:04-13:08, and did not skip when freeze was
  still days away.
- **Live evidence (2026-09-25 ~4:45 PM CT):** `cron-job1` deploy `48d3ba01`
  logged `n_rotowire=0` / `n_lineups=0` / pool 124 / capture 13:07:04Z then
  `watchdog_event trigger=rotowire_empty`. Public
  `https://api-production-7033.up.railway.app/watchdog/today` still returns
  those historical warns plus `enrichment_stale` (floor still 13:30 on the
  pre-fix image). Live RotoWire HTML classifies as `no_games_scheduled`
  (327471 bytes, 0 parsed lineups). Slate tip/freeze unchanged.
- **Code fix:** classify empty RotoWire HTML (`no_games_scheduled` /
  `subscriber_paywall` / `parse_empty`); gate `rotowire_empty` until ~30h
  before tip; fail closed (`rotowire_empty_near_tip`) inside that window;
  move freshness floor to 13:00 UTC and skip when freeze is >6h away.
- **API clear path:** `/watchdog/{slate_date}` and `/watchdog/today` now
  drive `events`/`status` from a live `evaluate_watchdog()` re-check (no
  persist). Historical rows remain under `history` for forensics, so tip-
  window false positives cannot sticky-warn the phone curl after the gates
  deploy.
- **Sunday residual:** starters still depend on Sunday ~13:00 UTC job1 (and
  job1_lite) seeing same-day RotoWire lineups for the tip-day slate_date.
  New fires of `rotowire_empty` / `enrichment_stale` stay suppressed outside
  the tip / freeze windows after deploy. Parser DOM still matches sister
  sports with live games; WNBA page is empty only because there are no games
  today.
- **Real Sports session (2026-09-25 ~4:50 PM CT):** `REALSPORTS_STORAGE_STATE_B64GZ`
  present on `cron-job1`, `cron-job1-late`, `backfill-enrichment`, and
  `cron-dayclose` (len=9248 each). `auth-check-live`: derived session payload
  structure valid; live checks passed. Names/presence only; value not logged.

## optimizer_leverage_weight sweep decision (#317) - 2026-09-25

- The leak-free GitHub Actions benchmark run [36133177919](https://github.com/cheeksmagunda/sports/actions/runs/36133177919) succeeded at about 2026-09-25 07:31 CT. Its `model-research-benchmark-merged` artifact contains `MODEL_RESEARCH_BENCHMARK.md` and `benchmark_results.json` covering 109 slates.
- The compiled production baseline uses `optimizer_leverage_weight=0.28`. The only leverage challenger in the default grid was `knob:leverage_weight_0.2`: paired score W/T/L was approximately 9/92/8 versus baseline, mean score delta was approximately -0.036, and payout was flat. This provides no flip signal.
- Decision: keep `optimizer_leverage_weight=0.28`. No Railway variable change is needed, and `EXPECTED_PROD_CONFIG["optimizer_leverage_weight"]` already remains `0.28`, so no config code update is needed. Live Railway `cron-job2` confirms `OPTIMIZER_LEVERAGE_WEIGHT=0.28`.
- The dedicated E1 leverage matrix (`0.0`, `0.14`, `0.28`, `0.40`) was not run. It remains an optional follow-up; picker-knob work is proceeding in parallel under #280 and #37. Full matrix is ~86 CPU-hours at default samples; not justified pre-Sunday given flat default-grid signal.

## optimizer_leverage_weight evidence gate (#289)  -  2026-09-25

- **Live knob:** `EXPECTED_PROD_CONFIG["optimizer_leverage_weight"]` remains
  `0.28` (no production knob change; public API had no slate timing for
  2026-09-25 at verification; standing authorization for justified picker-knob
  changes is documented in commit `3ec2bad` and issue #37. Railway
  `OPTIMIZER_LEVERAGE_WEIGHT` was not mutated in this fix.
- **Root cause:** `scripts/build_model_research_benchmark.py`
  `_precompute_slates` (shared by `model_tournament.py`) patched
  `job2._load_measured_drafts` to each slate's own post-lock `slate_labels.drafts`.
  Live freezes never see those drafts. The 2026-08-30 promotion evidence is
  therefore not transferable.
- **Code fix:** benchmark/tournament default to prior-slate
  (`wnba_oracle.eval.point_in_time.causal_drafts_for_slate`); optional
  `--leak-same-slate-ownership` keeps the old path for diagnostics only.
  Unit tests pin the guard. Walk-forward already had the same rule.
- **Decision (via #317):** default-grid leak-free challenger
  `knob:leverage_weight_0.2` showed no flip vs 0.28 (see sweep section above).
  Keep `0.28`. Dedicated E1 matrix (`0.0/0.14/0.28/0.40`) remains optional;
  Railway `OPTIMIZER_LEVERAGE_WEIGHT` unchanged at `0.28`.


## backfill-enrichment recovery (#279 / #310 / #312)  -  2026-09-25

Live verification from Codespace Railway CLI (`scripts/codespace-railway-env`,
CLI session as Cheeks Magunda):

- **Root cause (#279):** image-reuse `railway redeploy` of an older deployment
  kept `serviceManifest.builder=RAILPACK` even though `wnba-oracle/railway.toml`
  declares `builder = "DOCKERFILE"`. Railpack/mise then ran `uv sync` with
  `UV_PYTHON_DOWNLOADS=never` and failed looking for Python >=3.11,<3.13.
  Fix path: `railway redeploy --from-source` or `serviceInstanceDeployV2`
  (docs in `railway.toml` / README via PR #309, merge `cc2d553`).
- **Dockerfile builds:** confirmed. Deploy `215229c9` on merge `f0acf412`
  (#311 / #310) used `builder=DOCKERFILE`, `dockerfilePath=wnba-oracle/Dockerfile`,
  startCommand `sh -c 'python .../seed_storage_state.py && oracle-cron --job backfill'`.
  Earlier smoke redeploy `2012c79a` also reached Railway `SUCCESS` on a Dockerfile
  image.
- **Runtime TypeError (#310):** fixed and merged (`f0acf412`). Prior crash was
  `if not game_logs` on a Polars DataFrame; now `len(game_logs) == 0`. Deploy
  `215229c9` logs show **no** TypeError / DataFrame-ambiguity
  (`backfill_game_logs_loaded n_rows=18504`, then opp-DvP built).
- **AttributeError (#312):** root cause was the #310 mypy follow-up calling
  `slate_date.isoformat()` in `job_backfill.main` while
  `slate_labels.slate_date` is VARCHAR (psycopg returns `str`). That raised
  `AttributeError: 'str' object has no attribute 'isoformat'` for all 226
  slates on deploy `215229c9`. Fix: normalize DATE and VARCHAR values to ISO
  text via `_as_iso_slate_date` so head-feature builds and the
  existing-enrichment membership check share one type. Unit coverage in
  `test_job_backfill_slate_dates.py`. Merged as `e6a40ab` (PR #314).
- **Post-fix redeploy (#312):** Dockerfile `--from-source` deploy
  `5d1f20d9` on `e6a40ab` reached Railway `SUCCESS` then `STOPPED` after the
  one-shot job. Logs: `seed_storage_state` materialized, game logs
  `n_rows=18504`, `serving_head_features_built` for all 226 slates,
  `failed_feature_builds=0`, `failed_slates=0`, `job_completed status=success
  exit_code=0` (~98s). No `AttributeError` / `backfill_head_feats_failed`.
  `inserted=0` / `updated=0` (no enrichment rows needed write this run).
- **Real Sports session on backfill-enrichment:** copied
  `REALSPORTS_STORAGE_STATE_B64GZ` from `cron-job1` (name only; value not
  logged). Seed path materialized the derived session. Cron dispatch still
  reported `has_realsports_creds=false` (that flag tracks username/password,
  not the B64GZ session blob). Full historical backfill remains an authorized
  one-shot via `wnba-backfill-enrichment.yml`, not a routine auto-deploy.

## Configuration audit, layers 2-5 (2026-09-24 ~20:30 UTC, issue #239)

Names and `sha256[:8]` only, read-only against production. Open production
risks, none changed by this audit:

- Project shared variable `GITHUB_TOKEN` exists (40 characters, consistent
  with a classic PAT) and no service references it. Unaccounted credential
  with unknown expiry.
- Project shared variable `WNBA_ORACLE_MODEL_ARTIFACT_SHA` hashes `bd0ba39a`
  and no service references it; `cron-job1`, `cron-job1-late`, and `cron-job2`
  hold literal copies hashing `2e894c6c`, which matches the Actions variable
  `WNBA_EXPECTED_MODEL_SHA`. The shared copy is stale.
- `ODDS_API_KEY`: Railway shared variable (referenced by `cron-job1` and
  `cron-job1-late`) hashes `93571b1a`; the Actions secret hashed `d6798b68`
  in `secret-audit` run 35426281058 (2026-09-19; secret last updated
  2026-08-20). Two different keys; both currently authenticate.
- `WATCHDOG_PING_URL` (read by `scheduler/watchdog.py`) is not set on any
  service, so app-side critical events do not ping an external monitor.
- `ENV`, `LOG_LEVEL`, `TZ`, `PYTHONUNBUFFERED` are `${{shared.*}}` references
  on `api`, `cron-job1`, `cron-job2` but equal-valued literals on
  `cron-job1-late`, `cron-dayclose`, `backfill-enrichment`. `api`
  `DATABASE_PUBLIC_URL` is a literal, not a reference.

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
logic (title and label match verified); it does not need a manual close,
but it cannot run clean until the dayclose fix below is deployed.

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
- Corrected 2026-09-24T20:30Z: the `watchdog-monitor` run at 17:40Z was not
  a probe crash. `watchdog_monitor.py` exits 1 for a legitimate
  `status=alert` finding and prints nothing to stdout, so exit 1 in under
  2s with no console output is its normal alert shape; the 18:17Z and
  19:19Z runs (after PR #284 and `4212880`) completed the probe, wrote a full
  report, and routed it to #243 correctly. No `ops-guard-probe` issue has
  ever been opened. The live alert is real (see next bullet).
- Root cause of #243 (every dayclose `degraded` since at least 2026-09-19,
  verified from `cron-dayclose` structured logs 2026-09-21 to 2026-09-24):
  `job_dayclose.run()` walked contest ids from `top_cid - 1`, but at the
  06:00Z dispatch `top_cid` is yesterday's own contest (2180, 2185, 2187,
  2192 were each the processed slate's contest). Yesterday's labels and
  top-20 board were therefore never ingested on its own night, so
  `placement_capture` returned `missing_labels_or_leaderboard` every run and
  `placement_catchup` recorded it one day late. Fix (walk from `top_cid`
  inclusive) is drafted, pending a PR against #243, together with a
  finalization guard: the walk now skips (`skip_not_finalized`) any contest
  whose payload lacks `isFinalized: true`, so pre-game labels are never
  written. Until it deploys to `cron-dayclose`
  before a 06:00Z dispatch, every dayclose stays `degraded` and #243 stays
  open. Unverified: whether yesterday's `/entries` board is already
  populated at 06:00Z (the next night's walk has always found 20 entries).

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
