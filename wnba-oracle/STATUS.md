# Status

Last verified: 2026-08-22

This file is a mutable operational snapshot. Verify service state, schedules,
repository commits, environment configuration, and artifact identity against
GitHub, Railway, PostgreSQL, and the running API before changing production.

## Monorepo cutover

- Completed 2026-08-21. Railway uses `cheeksmagunda/sports`, branch `main`, as
  the source for the API, four scheduled backend services, the isolated
  backfill service, and frontend.
- Backend services build from the workspace root with
  `wnba-oracle/Dockerfile`, so they can import `oracle-core`.
- The frontend builds from `wnba-oracle/frontend`; PostgreSQL and Redis remain
  the same managed Railway services.
- The previous WNBA repository is an archive only. Do not deploy from it.
- GitHub reports `main` as unprotected. Private-repository rulesets require an
  account-plan decision. Railway `Wait for CI` is enabled on the API, four
  scheduled backend services, and frontend, so source pushes do not deploy
  until the applicable GitHub checks succeed. Backfill source auto-deploy is
  disabled entirely. Treat every push to `main` as a production-source change
  even though the deployment boundary is gated.

## Production

- State: live (recovered 2026-08-18 from the 08-15..08-18 trial-expiry
  outage; see Incident history below)
- Model artifact: `picker_e2ced9ec_1780873338.pkl`
- Model SHA: `94f8e8606dab4d48652929bb3884fb9152e1abc766eeb2c2d86559f4318676cd`
- Backend: FastAPI on Railway
- Frontend: Vite React on Railway
- Canonical store: Railway Postgres
- Serving state: PostgreSQL only
- Freeze coordination: Redis, required by Job 2 but not by the API
- Current production source commit: `c1facd04530ef41099d4db0c6aa184220ecf060d`
- 2026-08-22 T-40 freeze completed at 22:22:40 UTC with an `enter`
  recommendation and expected payout 1.4332. The served order was Breanna
  Stewart, Sabrina Ionescu, Kennedy Burke, Makayla Timpson, and Noemie Brochant
  at 2.0x, 1.8x, 1.6x, 1.4x, and 1.2x. The operator confirmed picks were
  received before first tip.

## Monitoring and ops record

- Production watchdog state is available at `/watchdog/today` and
  `/watchdog/jobs/today` on the API.
- Root GitHub Actions own backend CI, provider contracts, corpus backup,
  watchdog monitoring, pre-freeze checks, and day-close verification. The
  operational workflows retain manual dispatch and define portable repository
  schedules. The 2026-08-22 default-branch update activates those schedules;
  scheduled workflows run from the latest default-branch commit.
- Day-close records required and optional substeps separately. Discovery,
  historical backfill, label audit, placement capture, and enabled game-log
  refresh are required. Missing data or optional shadow/cleanup failures persist
  a degraded result; required execution failures persist a failed result.
- Operational history belongs in the corresponding GitHub issues and workflow
  logs. Keep this file to current state, known gaps, and recovery facts.
- Offline research tooling: `scripts/build_model_research_benchmark.py`
  (added 2026-08-26) replays stored slates through the production optimizer
  across a knob-ablation and sigma-temperature variant grid and writes
  `benchmark_results.json` plus a generated `MODEL_RESEARCH_BENCHMARK.md` to
  its `--output-dir`. It is read-only against production data; see the
  Model research benchmark section in `README.md`.
- Local calibration recovery on the fixed benchmark path was completed in an
  isolated worktree (`~/.codex/worktrees/b88c/sports`) on top of `df5b3b3`
  without changing production state. Checkpoint `5e02b89` contained six
  WNBA-only files; its `db.reads` game-identity changes were already present
  in inherited `df5b3b3`, so they required no new diff. The reapplied code
  delta was the missing benchmark surface only: `OPTIMIZER_COMMITTED_ORDER_OBJECTIVE`
  wiring plus local `--extra-variant` support and validation. Reproducibility
  for the local measurements:
  corpus identity: `/private/tmp/bench-corpus/slate_labels.csv`
  `sha256=f1ea1e438852cdaa15d5d8aff6dc31489324c334605f896f56c2b8a0d512876b`,
  `/private/tmp/bench-corpus/contest_leaderboards.csv`
  `sha256=6da928411d352e33c4299d999947aca1f3c09cb83dd51f9789edbab167619cac`,
  `/private/tmp/bench-corpus/game_identity.csv`
  `sha256=d95ea6a8755223e4ad16a643c09e8fce5548435f472ee7f16da2640db59615a9`.
  These `/private/tmp` files are ephemeral local inputs and outputs, not a
  persistent store; rerun the commands below if they are absent. At the time
  these commands ran, `committed_order_objective` still defaulted to `false`
  in `EXPECTED_PROD_CONFIG`, so `baseline` below means committed-order-off.
  Phase 1 command: `python wnba-oracle/scripts/build_model_research_benchmark.py
  --output-dir /private/tmp/bench-sweep/shardN --labels-csv
  /private/tmp/bench-corpus/slate_labels.csv --leaderboards-csv
  /private/tmp/bench-corpus/contest_leaderboards.csv --game-identity-csv
  /private/tmp/bench-corpus/game_identity.csv --n-samples 400
  --temperature-variants 0 --shard-count 7 --shard-index N --variant baseline
  --variant knob:field_same_game_boost_off --variant
  knob:field_same_team_boost_off --variant knob:dynamic_team_cap_off --variant
  knob:duplication_aware_payout_on --variant knob:leverage_weight_0.2 --variant
  knob:ceiling_weight_0.2 --variant knob:committed_order_objective_on
  --extra-variant sweep.lev0.1:leverage_weight=0.1 --extra-variant
  sweep.lev0.35:leverage_weight=0.35 --extra-variant
  sweep.ceil0.1:ceiling_weight=0.1 --extra-variant
  sweep.ceil0.35:ceiling_weight=0.35 --extra-variant
  bundle:leverage_weight=0.2,ceiling_weight=0.2,duplication_aware_payout=true,committed_order_objective=true`,
  observed phase-1 merge payload `sha256=8a348abae1f38f627aa22d41f529c59f536376a11b2fa7c749b7a4f55e0c25e3`.
  Coverage was 101 eligible slates, 0 dropped, `n_samples=400`, optimizer
  errors 0, optimizer infeasible 0 for the cited variants. Against baseline,
  `knob:leverage_weight_0.2` improved paired mean score by +4.861 and paired
  mean payout capture by +0.1683 over 101 shared slates, with wins/losses
  65/17, sign-test `p<1e-6`, `t=5.585`. `knob:committed_order_objective_on`
  improved paired mean score by +2.673 and paired mean payout capture by
  +0.0891, with wins/losses 66/33, sign-test `p=0.001185`, `t=3.209`.
  The all-on bundle improved baseline but underperformed leverage-only on
  payout capture, so ceiling and duplication additions were not promoted from
  Phase 1 alone.
  Phase 2 command: `python wnba-oracle/scripts/build_model_research_benchmark.py
  --output-dir /private/tmp/bench-sweep2/shardN --labels-csv
  /private/tmp/bench-corpus/slate_labels.csv --leaderboards-csv
  /private/tmp/bench-corpus/contest_leaderboards.csv --game-identity-csv
  /private/tmp/bench-corpus/game_identity.csv --n-samples 400
  --temperature-variants 0 --shard-count 7 --shard-index N --variant baseline
  --extra-variant sweep.lev0.28:leverage_weight=0.28 --extra-variant
  sweep.dup1:duplication_weight=1 --extra-variant sweep.dup5:duplication_weight=5
  --extra-variant pair.lev.committed:leverage_weight=0.28,committed_order_objective=true
  --extra-variant pair.lev.ceil:leverage_weight=0.28,ceiling_weight=0.2
  --extra-variant pair.lev.dup:leverage_weight=0.28,duplication_weight=1
  --extra-variant pair.lev.committed.dup:leverage_weight=0.28,committed_order_objective=true,duplication_weight=1`,
  reconstructed phase-2 merge payload from all seven ephemeral shard JSONs
  `sha256=41ce2da27d855ec8f6ac6f6c70ad05c1dde9d975edd23ef13566c7df6da87a3b`.
  Coverage was again 101 eligible slates with `n_samples=400`; the leading
  pair `pair.lev.committed` had optimizer errors 0 and optimizer infeasible 0.
  Versus baseline it improved paired mean score by +4.890 (95% paired CI
  +3.101 to +6.678) and paired mean payout capture by +0.1980 over 101 shared
  slates, with wins/losses 71/29, sign-test `p=0.000032`, `t=5.358`.
  `sweep.lev0.28` alone was +5.103 score (95% paired CI +3.369 to +6.837)
  and +0.1386 payout, wins/losses 66/23, sign-test `p=0.000006`, `t=5.767`.
  `pair.lev.ceil` was weaker than `pair.lev.committed`, and the duplication
  variants were identical to their non-duplication counterparts on this
  corpus, so there is no evidence here to enable duplication penalties.
  Current-source confirmation rerun used the same corpus and `--n-samples 400`
  with `--temperature-variants 0`, baseline, `sweep.lev0.28`,
  `pair.lev.committed`, and `pair.lev.ceil` in one unsharded output. Its
  observed artifact hash was
  `sha256=b9ae24edeba78ccd972932b4e557f2786554209661fe444e2601f13f3c403c6e`;
  it again produced 101 eligible slates, 0 drops, and zero optimizer errors
  or infeasible results.
  Decision from these measurements: the committed-order objective outperforms
  the off baseline both alone (+2.673 score) and combined with
  `leverage_weight=0.28` (+4.890 score, +0.1980 payout capture, the strongest
  pair measured), so on 2026-08-30 `optimizer_committed_order_objective` was
  promoted to `true` in `EXPECTED_PROD_CONFIG` (code state only -- see the
  production-rollout note below). The benchmark script's registered
  `knob:committed_order_objective_*` ablation was renamed from `_on` to `_off`
  to match: now that `true` is the baseline, the forward-looking re-measurement
  question is what turning it back off costs, not what turning it on gains.
  That `_off` ablation has not itself been re-executed against the new
  baseline; the promotion rests on the `_on`-vs-old-baseline measurement above,
  which is what was actually run. `leverage_weight=0.28` remains the leading
  follow-up candidate for any separately authorized production-config proposal.
- The `optimizer_committed_order_objective=true` promotion above was deployed
  live on 2026-08-30: commit `b0ee474` pushed to `origin/main`, `cron-job2`
  redeployed from it (deployment `4501f53d`), and the Railway
  `OPTIMIZER_COMMITTED_ORDER_OBJECTIVE=true` env var was set, per explicit
  operator authorization ahead of the 2026-08-30 18:20 UTC freeze. GitHub
  Actions' "Wait for CI" gate was blocking the normal auto-deploy (a
  pre-existing, unrelated CI infrastructure failure -- see the CI note below),
  so the deploy was triggered manually from the Railway dashboard instead.
  Duplication remains the one deliberately non-promoted objective term.
- The latest scheduled watchdog workflow on the production source commit was
  GitHub run `32605850803` and completed successfully. Its application status
  was `warn`, not `ok`: `WATCHDOG_HEARTBEAT_URL` is not configured, and today's
  API watchdog retains one historical `enrichment_stale` warning because the
  13:07 UTC Job 1 capture preceded the monitor's 13:30 UTC freshness floor.
  Current durable Job 1, Job 1 late, Job 2, day-close, and backfill records are
  successful. External dead-man monitoring remains an explicit connector gap.
- 2026-08-30: GitHub Actions was broken repo-wide -- every recent run (push,
  schedule, and issue_comment triggers, including ones that predate the day's
  pushes) failed instantly with `startup_failure` against a `workflow_id` that
  matches none of the repo's current `.yml` files (`gh api
  repos/.../actions/workflows` lists none at that id). `backend-ci` itself
  never triggered for the `b0ee474` push (last successful run was two days
  prior). Because Railway's source triggers wait for CI, this blocked
  auto-deploy independent of the env var question above; the fix was a manual
  redeploy from the Railway dashboard's per-commit deployment history (find
  the commit under "History", not the auto-selected latest build, which
  Railway had already queued as a redeploy of the *previous* commit). Root
  cause not diagnosed further -- worth a follow-up issue since it silently
  defeats "Wait for CI" for every service.
- The live Railway deployment-trigger inventory has six normal source triggers:
  API, frontend, Job 1, Job 1 late, Job 2, and day-close. Each points to
  `cheeksmagunda/sports` on `main` with `Wait for CI`; backfill has no trigger.
  This manifest is checked before an explicitly requested backfill, but it is
  not polled by a scheduled workflow. Add continuous control-plane drift
  monitoring only after a dedicated read-only Railway credential exists;
  reusing the workspace mutation token would weaken the current trust boundary.
- The first scheduled day-close, corpus-backup, and live-provider contract
  cycles on the activated default-branch workflows have not all completed yet.
  Do not describe the nightly acceptance cycle as proven until their durable
  records and workflow results are verified.
- 2026-08-30 afternoon session (#32, #35, #38, #39, dossier reconciliation):
  reconciled three divergent worktrees onto main (14 commits), then continued
  same-day per explicit operator authorization ahead of the 18:20 UTC freeze.
  Summary, in commit order:
  - #32 fix: job1 opponent derivation now prefers Real Sports game_id over the
    corruptible Odds team_to_opp map (`job1.py`), plus a watchdog
    `opponent_non_reciprocal` check and a written-not-run
    `backfill_game_identity.py` for existing rows missing `game_id`.
  - DRY consolidation: `feature_payload.parse_feature_mapping`,
    `contest_score.committed_lineup_score`, shared postgres-URL
    normalization -- four and six call sites respectively collapsed to one
    implementation each.
  - Sport application contract (`scripts/check_applications.py`) added and
    wired into CI; `APPLICATION_GUIDE.md` documents the contract and the
    oracle-core promotion gate.
  - Dossier contract (oracle-core schema + wnba-oracle computation) merged
    from the isolated worktree that built it; the `_realized_oracle` top-26
    pruned brute force is now labeled `lower_bound`, not `exact` (it is not
    proven optimal under the team cap) -- and exposed read-only at
    `GET /dossier/{slate_date}` (#35 phase 3).
  - Watchdog dead-man's-switch fix: a non-2xx ping response no longer logs
    as delivered (`watchdog.py`).
  - `optimizer_committed_order_objective` promoted true and
    `optimizer_leverage_weight` promoted to 0.28 in `EXPECTED_PROD_CONFIG`
    (both explicitly authorized), deployed live on cron-job2 same-day (a
    manual Railway redeploy, since GitHub Actions' broken CI blocked the
    normal auto-deploy -- see the CI note above), verified via clean
    post-deploy watchdog runs.
  - `player_slate_ownership` (#38/F6) wired end-to-end: `job2.py` records
    projected ownership at freeze, `job_dayclose.py` records actual
    ownership from `slate_labels.drafts` (a computation that already
    existed for `contest_placements`'s JSONB blob, now also written to the
    dedicated per-player table), and `backfill_player_slate_ownership.py`
    backfills history (written, not run). A same-day live-capture attempt
    (`live_ownership.py`) exists behind `LIVE_OWNERSHIP_CAPTURE_ENABLED`
    (default off, left off this session) -- empirically confirmed
    2026-08-30 that Real Sports' `/stats` endpoint returns `draftStats == []`
    while a contest is pregame, so no pre-lock ownership signal is
    available from that endpoint today regardless.
  - F2 (immutable decision snapshot) and F5 (canonical player identity) are
    design-only: `drive/2026-08-30-immutable-decision-snapshot-design.md`
    and `drive/2026-08-30-canonical-player-identity-design.md`.
  - Player analysis (2026-08-29, on request): Han Xu, Shay Ciezki, Sami
    Whitcomb, and Rebekah Gardner (0.02-0.07% owned, near-max card_boost,
    bench/low-L5-production, both games at 8.5-9.5pt spreads) is the
    game-script blowout bench-minutes pattern -- the market, our model, and
    the boost mechanic all correctly priced them as long shots; this was a
    low-probability variance event, not an obvious missed signal. Zero
    player overlap between our frozen lineup and the winning entry that day.
  - Full offline suite green throughout (909 passed at last full run).

## Canonical Data

Use Postgres, not local parquet.

| Table | Purpose |
| --- | --- |
| `wnba_game_logs` | Player-game box scores and matchup fields for the heads corpus |
| `slate_labels` | Player-slate realized Real Sports labels |
| `contest_leaderboards` | Top-20 finisher lineups per contest |
| `job1_enrichment` | Pre-tip pool and feature snapshots |
| `frozen_lineups` | Append-only freeze history |
| `slate_meta` | First tip and lock metadata |
| `contest_placements` | Realized placement feedback |
| `watchdog_events` | Operational alerts |

Corpus size (read-only production query, 2026-08-22): 211 slates and 6,335 rows
in `slate_labels` (2025-05-16 through 2026-08-21); 17,444 player-games in
`wnba_game_logs` (2024-05-03 through 2026-08-21). The day-close cron extends
both nightly. All reads go through
`src/wnba_oracle/db/reads.py`.

## Live services

Recorded Railway identifiers:

| Resource | Identifier |
| --- | --- |
| Project | `ab83f44c-0bbc-4a58-931c-37d9fbfda73a` |
| Production environment | `d57a759e-e189-439b-a612-bd220ef59c39` |
| api | `f4750eda-fd6c-432b-b6f5-34254013c271` |
| frontend | `d56dccf4-85b3-4ba0-acaf-58ef0cced58c` |
| cron-job1 | `2e110589-9527-4541-a754-41c4719515ba` |
| cron-job1-late | `2b0cd5aa-8793-45a5-bca0-e81c6d8455ff` |
| cron-job2 | `4a511ed2-10ad-441f-bf9a-3748c1e6b929` |
| cron-dayclose | `606d950d-7d7d-4f5a-a049-b9fa69799169` |
| backfill-enrichment | `633aa1db-6c54-466d-8f89-39517a889fb4` |
| postgres | `5e827da3-6df6-4349-97ad-a800ece2716d` |
| redis | `bb131bec-4edd-4809-accd-e09e09aacbf6` |

Repository workflow schedules:

| Workflow | Schedule UTC |
| --- | --- |
| watchdog monitor | `23 * * * *` |
| provider contracts | `17 10 * * *` |
| corpus backup | `43 6 * * *` |
| WNBA pre-freeze guard | `30 13 * * *` |
| WNBA day-close verify | `0 7 * * *` |

- api: https://api-production-7033.up.railway.app (`/health`, `/lineup/{date}`,
  `/slate/{date}`, `/watchdog/today`)
- frontend: https://frontend-production-a739.up.railway.app/
  The app-owned `frontend/railway.toml` selects its Dockerfile; the package
  start command also generates the same assured static-server configuration if
  a Railpack fallback is selected. Verify the live builder path after release
  before describing the new CSP and HSTS headers as active.
- postgres: internal + public TCP proxy (TLS via start-command cert, D61);
  role `oracle_ro` for read-only laptop access
- redis: internal, password-protected
- cron-job1 `0 13 * * *` UTC: scrape Real Sports pool, minutes, odds,
  RotoWire, props; persist enrichment
- cron-job1-late `*/30 16-23 * * *` UTC: credit-free starter refresh
  (`oracle-cron --job job1late`; RotoWire + DB only, no Real Sports auth)
- cron-job2 `*/5 14-23,0-3 * * *` UTC: heads + optimizer, tip-relative T-40
  freeze to Redis + Postgres, late re-freeze when enabled
- cron-dayclose `0 6 * * *` UTC: ingest finalized contests, refresh game
  logs, record placements, retention cleanup
- backfill-enrichment: no cron, source auto-deploy disabled, restart policy
  `NEVER`, and source watch limited to the inert
  `/wnba-oracle/.manual-backfill-trigger` sentinel. Normal source pushes cannot
  run it. Use only the exact-commit manual workflow; never repoint a live cron
  at `--job backfill` (D103). The `c1facd0` source deployment ran backfill once
  before this isolation was applied and completed with zero inserted or updated
  rows.
- corpus-backup (GitHub Action) `43 6 * * *` UTC: nightly export to the
  off-main `backups` branch

Only the API and frontend have Railway HTTP domains. Redis and backfill have no
public HTTP domain. PostgreSQL retains one intentional public TCP proxy for the
TLS-verified read-only operator path; production services use private Railway
networking. Accidental HTTP domains created during the 2026-08-22 control-plane
audit were deleted immediately and verified absent.

## Active Railway env vars (cron-job2)

Production model SHA is set on cron-job1, cron-job1-late, cron-job2 as
`WNBA_ORACLE_MODEL_ARTIFACT_SHA`. The api reads frozen lineups from Postgres
and never loads the artifact, so it does not need the SHA.

| Var | Value | Decision |
|-----|-------|----------|
| PAYOUT_REGIME | top_20 | D48 |
| NEVER_SKIP | true (code default) | D67 |
| CONTRARIAN_ENABLED | true | D51 |
| CONTRARIAN_STRENGTH | 0.2 | D51/D53 |
| OPTIMIZER_MAX_PER_TEAM | 2 | D50 |
| OPTIMIZER_DYNAMIC_TEAM_CAP | true (code default) | D50 |
| OPTIMIZER_N_FIELD_LINEUPS | 500 | D76 |
| OPTIMIZER_BOOST_SUM_CAP | 9.0 | D70/R2 |
| OPTIMIZER_MAX_SINGLE_BOOST | 3.0 | 2026-07-04 sweep_max_boost.py (+75 aggregate) |
| OPTIMIZER_GAME_STACK_BONUS | 0.010 | Legacy rollback objective; ignored while contextual policy is enabled |
| OPTIMIZER_CONTEXTUAL_STACKING_ENABLED | true (code default) | contextual-stacking-v1 |
| OPTIMIZER_CONTEXTUAL_STACK_EV_MARGIN | 0.010 (code default) | Balance indifference band in objective units |
| OPTIMIZER_COMMITTED_ORDER_OBJECTIVE | true | 2026-08-30: promoted to true in EXPECTED_PROD_CONFIG and deployed live on cron-job2 (Railway env var set) ahead of the 2026-08-30 18:20 UTC freeze, per explicit operator authorization -- see decision above. Verified via a clean post-deploy watchdog run (no config_drift event) at 2026-08-30T15:05 UTC |
| MINUTES_MODEL_ENABLED | true (code default) | D55 |
| STARTER_SIGNAL_ENABLED | true (code default) | D71 |
| AVAILABILITY_MODEL_ENABLED | true | D73 |
| GAME_SCRIPT_MINUTES_ENABLED | true | D57 |
| LINEUP_ANCHOR_FLOOR | 2 | D57/D58 |
| LATE_REFREEZE_ENABLED | true | D75 |
| PROP_SIGNAL_SCALE | 0.3 | D78 |
| FIELD_MEASURED_OWNERSHIP_ENABLED | true (code default) | D86 |
| SAMPLING_SCORE_OFFSET | 2.0 (code default) | D52 |
| FIELD_SAME_GAME_BOOST | 3.0 | D88/D91 |
| FIELD_SAME_TEAM_BOOST | 2.0 | D88/D91 |
| OPTIMIZER_CEILING_SIGMA_BLOWOUT_BOOST | 0.15 | D89/D92 |
| OPTIMIZER_CEILING_SIGMA_LOW_HISTORY_BOOST | 0.20 | D89/D92 |
| OPTIMIZER_CEILING_TILT_SLOTS | true | D107/Phase 4 |
| OPTIMIZER_MIXTURE_VARIANCE_ENABLED | true | D107/Tier 2 |
| FREEZE_LEAD_MINUTES | 40 (code default) | D93 |
| STARTER_UNKNOWN_FADE | 0.75 | 2026-07-04 corpus calibration |
| PICKER_BOOST_TAIL_LIFT | false | 2026-07-04 rolled back after -93 counterfactual |
| STARTER_MINUTES_LIFT_ENABLED | true | 2026-07-10 Kuier/Harris fix; +12.5 suite counterfactual |
| PICKER_FLOOR_TILT_WEIGHT | 0.2 | 2026-07-10; cliff at 0.35, do not raise without re-sweep |
| PICKER_KNOB_CHALLENGER_JSON | pre-suite config (fade only) | 2026-07-10, measures the suite's marginal effect ex post |
| POOL_EXCLUDE_STARTED_GAMES | unset (code default false) | D109; operator-directed late-entry scope, see below |

All flags reverse via env with no redeploy: set `*_ENABLED=false` or unset
numeric knobs to revert to code defaults.

### Contextual stacking baseline, 2026-08-25

A read-only production aggregate over freezes since 2026-06-01 found 69
slates, of which 67 had complete legacy team/opponent structure. Twenty-one
complete multi-game slates selected more than two players from one game. The
placement table contained zero exact placement rows and 22 score-only,
censored rows, so this evidence measures lineup concentration only. It does
not establish that stacking or balancing improves contest results.

`contextual-stacking-v1` compares unrestricted and balanced candidates using
the same samples and seed. It prefers balance only inside the 0.010 objective
band and records any larger concentration advantage as
`contextual_ev_override`. Real Sports game IDs are primary; validated
reciprocal team/opponent pairs are the fallback. The complete rollback is
`OPTIMIZER_CONTEXTUAL_STACKING_ENABLED=false`.

`POOL_EXCLUDE_STARTED_GAMES=true` scopes the optimizer pool to games that
have not tipped, using the `game_start_utc` job1 writes per player. Before
the slate's first tip it is a no-op, so freeze semantics are unchanged; once
a game has started it appends one scoped freeze (`frozen_via =
job2_upcoming_games_only`) gated by the lock buffer against the next game.
It fails closed: a pool row with no known tip time is dropped, so enabling
it on a slate whose enrichment predates D109 empties the pool. Backfill
those rows first with `oracle-cron --job job1games`. Used live on
2026-08-19 (freeze_seq 2, GSV/MIN only, after TOR@WAS had tipped).

## Two corpora, two roles -- DO NOT CONFUSE

| Corpus | Grain | Source | Consumed by |
| --- | --- | --- | --- |
| Gamelog (heads) | player-game | `wnba_game_logs` | LightGBM minutes + per-min heads (D63) |
| Label (contest) | player-slate | `slate_labels` | EB baseline, blend, CQR calibration |

The label corpus carries `card_boost` and realized contest points; it is
not the heads' training corpus (the pre-D63 bug).

## Where to look if something goes wrong

| Symptom | First place to check |
|---|---|
| Frontend shows countdown past freeze time | Railway logs for cron-job2. Most likely `pool_too_small` (job1 wrote no rows) or `job2_failed` (DB / Redis hiccup) |
| Frontend shows ErrorState | `curl https://api-production-7033.up.railway.app/health`; if 200, check api Railway logs |
| Pool empty / 401s from web.realapp.com | Real Sports session died (they last ~3 weeks). Operator recovery only -- AGENTS.md, "Real Sports". Do NOT attempt a scripted/headless login; the site bot-blocks it |
| Odds API 429 / 401 | Quota or rotated key. Job1 degrades to empty odds; lineup still ships without the Vegas tilt |
| Watchdog `label_coverage_gap` | A contest player referenced in the top-20 leaderboard has no slate_labels row -- a real ingestion gap since 2026-07-03 (the check compares against leaderboard players, not the 3x-wider job1 pool) |
| No `slate_labels` rows for last night | Usually NOT a failure. `start_id = top_cid - 1` excludes the newest contest by design, so slates land late via window overlap. Measured lags: 07-12 +2d, 07-16 +5d, 07-19 +7d, 07-28 +5d, 07-29 +5d. Wait a week before investigating |
| Railway logs show no structured JSON (`kept`, `dayclose_walk`) | Known log-visibility gap since 2026-07-17, NOT a crash. Confirm the run actually worked by checking `ingested_at` in `slate_labels` / `wnba_game_logs`, not by log absence. This gap caused a false CRITICAL on #17 (2026-08-03) |

Railway dashboard:
https://railway.com/project/ab83f44c-0bbc-4a58-931c-37d9fbfda73a

## Known measurement gaps (2026-08-03)

Findings from an interactive research session; full detail and method in the
issue labeled `ops-results` (#15). No model change was made.

- **`contest_placements.entry_score` is inflated on every row written before
  2026-08-19** (and with it `entry_rank`, `finish_percentile`, `cashed`,
  `top_10pct`, `top_1pct`, all derived from it). Dayclose ranked the five picks
  by realized score before applying the slot multipliers, which awards the 2.0x
  base to whoever spiked; the slot order is committed before tip, so that is an
  upper bound, not our result. Measured against the corpus, the stored score
  matches the hindsight number on 11 of 18 slates and the correct committed-order
  number on 0 of 18, overstating by up to 2.4 points. Fixed and deployed in
  `4f73668`; rows written from 2026-08-20 onward are correct. Backfilled
  2026-08-19 via `scripts/backfill_placement_scores.py --apply`: **11 rows
  repaired** (mean -1.11, worst -2.45 on 2026-08-05; every row moved down, which
  is the expected direction since a committed order can never beat a hindsight
  one). **11 rows remain wrong and are not repairable** -- their picks have no
  `slate_labels` row, so the realized values needed to recompute do not exist.
  Those 11 also still carry the bogus `entry_rank = 21` sentinel. Treat any
  pre-2026-08-19 placement row with a 21 rank as unusable, not merely imprecise.

- **Automatic outcome measurement remains right-censored.** The current code
  records committed-order score and consumes `num_brawlers` as the full field
  size. It records an exact rank and percentile only when the lineup reaches
  the captured top 20; below that boundary it retains a lower-bound percentile
  in metadata and leaves rank and ROI unset. The production rows written after
  2026-08-20 were not re-audited from PostgreSQL during this update, so verify
  them before claiming KPI coverage.
- **`prediction_calibration_drift` was a false alarm for a month.** It
  correlates over the five optimizer-selected picks only, whose predicted
  spread is range-restricted, and compared that against the D77 full-corpus
  walk-forward 0.554, a different estimator. Reproduced pooled value is 0.408
  (n=95) with no trend. Alerts fired on 15-20 pairs where the 95% CI contains
  zero, 0.408 and 0.554 alike. Guarded 2026-08-03 by `DRIFT_MIN_PICK_PAIRS`.
- **Minutes intervals are symmetric by construction** (`predict/minutes.py`,
  `p50 +/- half`, half clamped to [2, 8]). 268 of 270 frozen intervals are
  exactly symmetric. Actuals land below p10 32.8% of the time against an
  expected 10%, worst in blowout wins (56.3%). Display-only: `pred_minutes_*`
  is read by the frontend and never by the optimizer, so this is a diagnostic.
- **The blowout path gates on a hard 24-minute recent-minutes threshold** in
  both `project_minutes_from_base` and `redistribute_game_script_minutes`. A
  confirmed starter below that line is classified bench and has projection
  *added* as a garbage-time recipient. This does reach the optimizer via
  `pred_real_scores`. Queued, not changed: needs a corpus counterfactual, and
  same-game counter-evidence exists (2026-08-02, Zandalasini fell, Stokes rose).
- **The two corpora share no player key.** `frozen_lineups` uses Real Sports
  pool ids, `wnba_game_logs` uses WNBA stats ids, zero overlap, and team codes
  differ (POR vs PDX). Prediction-to-outcome analysis must join on names, which
  hits 84.8%.

## Incident history

- 2026-08-15..08-18: three-day outage, issue #17. Railway trial expired;
  all services received a graceful stop at 2026-08-15T20:14Z and every
  redeploy attempt returned "Your trial has expired. Please select a plan".
  Billing is outside routine authorization, so the guard could only
  escalate. 08-16 was a full game day missed (no pool, no freeze, no
  ingest); 08-17 had no games. Recovered 2026-08-18: operator selected a
  paid plan, all services redeployed ~21:13 UTC. Redeploying a cron
  service only re-arms its schedule, so job1's missed 13:00 UTC fire was
  recovered by temporarily moving cron-job1's schedule to 21:54 UTC for a
  one-shot run, then restoring `0 13 * * *`. Recovery surfaced a second
  latent break: every backend service's builder had drifted to RAILPACK
  (ignoring railway.toml's DOCKERFILE), and Railpack's default Python moved
  to 3.13, outside pyproject's `>=3.11,<3.13` pin, so every fresh source
  build failed at `uv sync` while image-reuse redeploys kept succeeding.
  Fixed by setting config-file `railway.toml` + `Dockerfile` path on api,
  cron-job1, cron-job1-late, cron-job2, cron-dayclose, and
  backfill-enrichment. Frontend remained Railpack during incident recovery; its
  app-owned source configuration now selects the frontend Dockerfile and keeps
  an equivalent package start path.
  Durable lessons: a Railway billing lapse stops every service at once,
  crons do not catch up on their own after redeploy, and builder drift is
  invisible until the next cold build.

- 2026-06-27..07-03: five-day outage, issue #10. Root causes compounding:
  the Real Sports session died server-side (~3-week TTL) killing job1's
  pool, AND the cloud audit routine's bootstrap file
  (a legacy agent credential file) had been deleted in a cleanup commit, leaving
  the watcher blind with a stale Railway token. Recovered 2026-07-03:
  session re-seeded via the Playwright MCP login path, missed slates
  backfilled (labels + leaderboards for 06-27, 06-28, 06-30), routines
  rebuilt (see Monitoring above), credentials.env restored with minimal
  scope. Durable fixes: watchdog label-coverage check made
  leaderboard-grounded, session-death signature documented, scripted
  login marked broken.

## Quality gates

- Production source commit `c1facd04530ef41099d4db0c6aa184220ecf060d`
  passed backend CI run `32605402072`; all seven application services built and
  deployed successfully. API health and the exact T-40 lineup were then verified
  live. The latest watchdog workflow passed operationally but reported the two
  explicit warnings described above. `main` remains unprotected.
- Pre-release local verification, 2026-08-22: 694 WNBA tests passed with seven
  contract/integration tests intentionally deselected, and 48 oracle-core tests
  passed. Ruff, formatting, mypy, import boundaries, Bandit, and the Python
  dependency audit passed. Frontend lint, type checking, 33 tests, and the
  production build passed.
- The established Docker acceptance provisions PostgreSQL and Redis, upgrades
  both an empty database and the previous schema to Alembic head, verifies
  retained data, exercises all runtime roles, and starts the API and production
  frontend images. Four marked integration tests now cover these boundaries,
  including preservation of non-enrichment data during historical backfill.
  The latest tree's final local Docker rerun and npm audit were unavailable, so
  the exact pushed commit must pass the equivalent backend and frontend CI gates
  before deployment is treated as verified.
- Backend CI now repeats the PostgreSQL, Redis, migration, runtime-role, image,
  and API health acceptance path with pinned service images.
- Runtime dependency auditing is now a backend CI gate. Narrow ignores cover
  advisories whose affected APIs are not reachable in the current Linux API;
  each ignore is documented beside the CI command and must be removed if those
  assumptions change.
- `make determinism-check` compares model content, not pickle SHA (D93). The
  2026-08-22 live read-only run snapshotted 16,986 heads rows and 6,334 label
  rows once, trained twice from that identical snapshot, and passed with
  content-identical outputs.
- `src/wnba_oracle/scheduler/` was split 2026-08-21: `job1.py`, `job2.py`,
  `watchdog.py`, `placements.py`, and `shadow.py` (each 500-1700+ lines) were
  each broken into a handful of `<name>_<concern>.py` sibling modules (io/
  model/timing/freeze/specs for job2, rotowire/persist for job1, checks/
  drift for watchdog, calibration for placements, knobs for shadow). Every
  original module still exists and re-imports its moved names at the bottom
  of the file, so `from wnba_oracle.scheduler.job2 import _build_specs`
  (and every other pre-split import path) is unchanged. Behavior-preserving
  throughout; see the commit history from `0e3e613` to `bc4bbfc` for the
  per-slice verification each split ran. `frontend/src/styles/main.css`
  (1985 lines) was similarly split into `frontend/src/styles/partials/`,
  one file per numbered section (§1 through §15); verified byte-identical
  via the built CSS bundle's content hash before and after.
- `picker/optimize.py` was reorganized 2026-08-22 around typed filtering,
  simulation, constraint-scan, and recommendation boundaries. The public
  optimizer no longer carries an F-rated cyclomatic complexity score; its two
  most complex internal functions are C-rated at 17 and 14, with selection and
  random-call order preserved by focused behavior tests.
- Job 1 enrichment, Job 2 freeze orchestration, and player prediction were
  decomposed behind their existing public entry points. Their complexity fell
  from F47, F51, and F55 to D28, D22, and C12 respectively. No F-rated backend
  function remains. The Real Sports pool fetch and serve-time schema validator
  were also reduced from E32 and E36 to small orchestrators. The remaining
  E-rated offline backfill, model-lab, and loss-ledger scripts were decomposed
  as well. No E- or F-rated function remains in backend source or scripts, and
  Ruff enforces a maximum McCabe complexity of 20 so that boundary cannot
  silently regress.
- Dependabot is configured for weekly Python workspace, frontend npm, and GitHub
  Actions updates. The configuration becomes active from the default branch.
- App-owned runtime paths now resolve the WNBA checkout under both source and
  non-editable workspace installs. This closes a local operational gap where
  the served artifact, identity overrides, cache, payout archive, and watchdog
  checks could incorrectly look beneath `site-packages`. The pinned production
  artifact loads locally with 11,205 training rows and six trained heads.
- Backend Python source, tests, and operational scripts are Ruff-formatted, and
  the standard lint target now checks formatting so style drift fails locally
  and in backend CI.
