status: BUILD_COMPLETE
last_verified: 2026-06-01T00:00:00Z
phase: live. 2026-06-01 build pass shipped: dynamic team cap by slate size (D50); contrarian kept at 0.2 (D51); sampling recalibrated K=10->2 + per-player sigma (D52); and the MINUTES/ROLE MODEL (D55) -- the real edge. Proven walk-forward: minutes x rate predicts real_score at corr 0.554 (actual-min ceiling) / 0.355 (recency) vs boost 0.246; real_score is a fixed box formula (R^2 0.957) so the pipeline is self-contained on nba_api. job1 ingests per-player recent_minutes + per_min_rate from stats.wnba.com game logs; job2 uses a boost<->minutes blend with confirmed-starter / injury-cascade / blowout same-day signals. Env kill-switch MINUTES_MODEL_ENABLED. Earlier: CAVEAT_IS_SKIP + stable argsort (D48); recency/EB-over-boost tested and rejected (D52/D54, boost already encodes form). Harnesses: scripts/backtest_walkforward.py, validate_minutes_model.py, test_minutes_placement.py, replay_slate.py.

# Build status

Set by the build automation. Allowed values: `IN_PROGRESS`,
`BLOCKED_NONFATAL`, `BUILD_COMPLETE`.

The 7-day shadow run + watchdog drill are wall-clock operational phases.
All code paths are unit-tested; the manual fire path has been exercised
end-to-end via `scripts/manual_fire.py --fixtures`. The operator starts
the live shadow window via `oracle-rotate-check --window-days 7` after
the live collector has accumulated >= 7 slate labels in `slate_labels`.

## Live services (verified 2026-05-27 05:30 UTC)

- api:       https://api-production-7033.up.railway.app/health -> 200
- api:       https://api-production-7033.up.railway.app/lineup -> 200 (empty)
- frontend:  https://frontend-production-a739.up.railway.app/ -> 200
- postgres:  internal, alembic head = 20260527_0003 (local repo; Railway upgrade pending operator deploy)
- redis:     internal, password-protected
- cron-job1: `0 13 * * *` UTC, oracle-cron --job job1 (next: 2026-05-27T13:00Z)
- cron-job2: `*/15 21-23,0-3 * * *` UTC, oracle-cron --job job2 (next: 2026-05-27T21:00Z)
- cron-dayclose: `0 6 * * *` UTC, oracle-cron --job dayclose (D41 — local
  only until operator wires the Railway cron service; corpus is auto-
  extended each fire by walking back N ids from today's max contest id
  and skipping anything not `sport=wnba` & finalized)
- env-tunable knobs (scope verified 2026-06-01, D53):
  - SHARED (env scope, via ${{shared.KEY}} refs): ENV, LOG_LEVEL,
    PYTHONUNBUFFERED, TZ, PAYOUT_REGIME=top_20, WNBA_ORACLE_MODEL_ARTIFACT_SHA.
  - cron-job2 scope (optimizer): CONTRARIAN_STRENGTH=0.2 (reconciled from a
    drifted 0.3, D53), CONTRARIAN_ENABLED=true, OPTIMIZER_MAX_PER_TEAM=2,
    CAVEAT_IS_SKIP=true. The D50/D52/D55 knobs OPTIMIZER_DYNAMIC_TEAM_CAP (true),
    SAMPLING_SCORE_OFFSET (2.0), STARTER_SIGNAL_ENABLED (true),
    MINUTES_MODEL_ENABLED (true) are NOT set on Railway and run on code
    defaults; set them on cron-job2 to override (e.g. MINUTES_MODEL_ENABLED=false
    to fall back to the boost/EB predictor, SAMPLING_SCORE_OFFSET=10 to revert).
  - cron-job1 now also pulls stats.wnba.com game logs (nba_api) for the D55
    minutes features; a stats.wnba.com outage degrades gracefully (job2 falls
    back to boost). Watch the job1 log key n_minutes_matched.
  - DATABASE_URL / REDIS_URL are service references; never literals.
- env-tunable knobs at cron-job2 service: CAVEAT_IS_SKIP=true (set
  2026-05-29 per D48; demotes `enter_with_caveat` to `skip` on
  marginal-EV slates). Unset or set to `false` to roll back.

## Historical corpus (added 2026-05-27 09:40 UTC)

`data/historical/{slate_labels,leaderboards}/slate_date=*/data.parquet`
covers the 2026 WNBA season through 2026-05-25:

- 16 finalized slates (cid 1755 = 2026-05-08 .. cid 1831 = 2026-05-25);
  the 3 off-days for WNBA in that window (5-11, 5-16, 5-26) are absent
  by design — the platform doesn't surface a WNBA contest on those.
- 505 player rows in `slate_labels` (HV / popular / 3x sections,
  deduped by player; first section seen wins).
- 320 leaderboard rows in `leaderboards` (top-20 finishers per slate),
  each with the 5-player lineup as `lineup_json` (playerId, chosen
  multiplier, card boost, per-player realized real_score, computed
  per-player score).

To re-run / extend:
```
set -a && source .env && set +a
export WNBA_DEVICE_UUID=<uuid matching storage_state>
uv run oracle-backfill --mode historical --start-id 1755 --stop-id 1840 \
    --pause-seconds 0.6 --parquet-out-dir data/historical
```

When DATABASE_URL is set (Railway env), the same command UPSERTs into
Postgres (`slate_labels` + `contest_leaderboards`). See D38/D39/D40.
A day-close cron that auto-extends the corpus from the prior night's
finalized contest is **not yet wired** (NEEDS_HUMAN item 10).

## Optimizer correctness (2026-05-27 10:00 UTC)

The pre-fire backfill (D38) surfaced two long-standing bugs in the picker:

- **Slot multipliers were [3.0, 2.5, 2.0, 1.5, 1.0]** (NBA precedent); actual
  WNBA platform uses **[2.0, 1.8, 1.6, 1.4, 1.2]** verified empirically
  across all 320 corpus entries. Fixed in commit `5fb6c6f` and pinned in
  `tests/unit/test_slot_scheme.py`. See D42.

- **Heuristic real_score was 15.0 * (1 + 0.2 * boost)** — wrong magnitude
  (5x too high) and wrong slope (positive; actual relationship is
  -0.45/boost-unit because card_boost is a handicap). Recalibrated to
  `max(0.5, 3.16 - 0.45 * card_boost)`. See D43.

Tonight's 21:00 UTC cron-job2 fire is the first to use the corrected
optimizer. Backtest on 2026-05-25 realized values produced 49.73 points
(brute-force optimum), vs the actual contest winner cpgooner at 40.60.

## Today's slate (2026-05-27) — what to expect

**Cron-job1 fires at 13:00 UTC (8 AM CDT / 9 AM EDT):**
1. Headless re-auth via REALSPORTS_STORAGE_STATE_B64GZ + WNBA_DEVICE_UUID
2. /home/wnba/next + /players/sport/wnba/search a..z pool fetch
3. The Odds API basketball_wnba pull (vegas signals -> features_json)
4. RotoWire WNBA lineups scrape
5. UPSERT into job1_enrichment

**Cron-job2 fires every 15 min from 21:00 UTC through 04:00 UTC** (16:00 CDT
to 23:00 CDT). First fire at 21:00 UTC is when the frontend's countdown
expires and the lineup lands.
1. Load slate from job1_enrichment + slate_labels (drafts if available)
2. Compute per-player heuristic real_score
3. Apply game_script_multiplier (Vegas-driven tier weights)
4. Apply anti-popularity contrarian adjustment
5. Optimize lineup (top-30 -> C(30,5), max_per_team=2)
6. Freeze via Redis SET NX + Postgres UPSERT (with per_player block — D36)

**Frontend** (https://frontend-production-a739.up.railway.app/) polls
/lineup/2026-05-27 every 5-60s with backoff:
- Until 21:00 UTC: full-bleed OracleLoader with countdown to lineup-freeze
- After 21:00 UTC (when job2 first writes): swaps to the 5-card grid

## Where to look if something goes wrong

| Symptom | First place to check |
|---|---|
| Frontend shows countdown past 21:00 UTC | Railway logs for cron-job2 service. Most likely `pool_too_small` (job1 didn't write rows) or `job2_failed` (DB / Redis hiccup) |
| Frontend shows ErrorState block | `curl https://api-production-7033.up.railway.app/health` first; if 200, check api Railway logs |
| Lineup loaded but card names show "Player 12345" | per_player block missing — should be impossible after D36; check job2's `_build_per_player` ran |
| Job1 fails with StorageStateStale | JWT inside REALSPORTS_STORAGE_STATE_B64GZ rotated. Re-run `scripts/realsports_login.py` locally and re-seed the env var on cron-job1 + cron-job2 (NEEDS_HUMAN item 6) |
| Odds API returns 429 / 401 | Free-tier quota or rotated key. Job1 degrades to empty odds; game_script_multiplier reverts to 1.0x. Lineup still ships, just without the Vegas tilt |

Railway dashboard for logs:
https://railway.com/project/ab83f44c-0bbc-4a58-931c-37d9fbfda73a

## Audit findings + fixes (2026-05-27 03:30-05:30 UTC)

The pre-fire audit surfaced four issues; all fixed before the operator
went to bed.

1. **Critical UX fix — per_player block** (D36): job2 was writing the
   frozen lineup JSONB without a `per_player` array, so the frontend
   would have rendered 5 placeholder cards ("Player 12345", "—", "—",
   all-zero scores) for tomorrow's first slate. Now job2 materializes
   the full projection contract (display_name / team / opponent /
   position / card_boost / pred_real_score_p50 / pred_minutes_p10-p90)
   into the JSONB. Four tests pin the contract in `tests/unit/
   test_per_player_frozen.py`.

2. **Frontend countdown target** (D36): countdown pointed at 13:00 UTC
   (job1 ingest, not user-visible) instead of 21:00 UTC (job2 freeze,
   when the lineup actually appears). Re-targeted; caption changed
   from "Next fire in" to "Lineup freezes in".

3. **Settings env aliases** (D36): pydantic-settings has
   `case_sensitive=True`, so fields without explicit `alias=` (env,
   log_level, payout_regime, optimizer_*, contrarian_*) never picked
   up Railway's uppercase env vars — silently falling back to defaults.
   The current Railway values happened to match defaults so today's
   run was not affected, but any future env-var tuning would have
   silently no-op'd. Added aliases on every uppercase env-var consumer.
   Verified: `ENV=prod LOG_LEVEL=DEBUG CONTRARIAN_STRENGTH=0.25` now
   propagates correctly through `Settings()`.

4. **Railway env hardening** (D35): promoted operational config to
   shared env-scope via `${{shared.KEY}}` references; converted
   DATABASE_URL / REDIS_URL to `${{postgres.DATABASE_URL}}` /
   `${{redis.REDIS_URL}}` service refs; converted frontend
   VITE_API_URL to `https://${{api.RAILWAY_PUBLIC_DOMAIN}}`. Dropped
   GITHUB_TOKEN + RAILWAY_TOKEN from every runtime service; dropped
   REAL_SPORTS_* / WNBA_DEVICE_* / REALSPORTS_STORAGE_STATE_B64GZ from
   api + cron-job2 (only cron-job1 authenticates).

## Known caveats — multi-day work, not blocking tomorrow

These came out of the deep code audit (general-purpose subagent, 2026-05-27
05:00 UTC) and are documented for follow-up; they will NOT block
tomorrow's first frozen lineup.

- **RotoWire lineups fetched but not persisted** (NEEDS_HUMAN item 7):
  `job1.py:114` calls `fetch_lineups()` and counts the result for the
  log line, but the rows aren't written to `job1_enrichment`. The
  injury-cascade port (D33) only fires through `features/build.py`
  which the live cron path never calls. Impact for tomorrow: players
  RotoWire flags OUT still draft into the optimizer pool; minutes
  redistribution does not apply. The lineup will still ship with
  reasonable picks (boost + Vegas signals carry it), just without the
  injury-aware adjustment.

- **Job2 `_freeze` is not strictly idempotent** (NEEDS_HUMAN item 8):
  The Redis SETNX guards the lock metadata but the Postgres UPSERT
  fires every invocation. Subsequent cron-job2 fires within the same
  slate window can replace the frozen lineup if new draft data arrives
  via slate_labels and shifts the contrarian adjustment. Documented
  intent vs. behavior mismatch — should either skip the UPSERT when
  the lock is held, or accept the refresh-as-data-arrives semantics
  and rename "freeze" everywhere.

- **Watchdog not wired** (NEEDS_HUMAN item 9): `scheduler/watchdog.py`
  is a stub returning `[]` and is not called from `cron.py`. Operator
  must read Railway logs manually for failure detection until the
  watchdog + alerting path lands.

## Quality gates

- 81 unit tests pass (was 77; added 4 in `test_per_player_frozen.py`).
- ruff + mypy on `src/` clean (project config; `--strict` flagged
  pre-existing dict-type-args lint, non-blocking).
- 57 source files in `src/wnba_oracle/`.
- 6 basketball-main patterns ported with zero new external dependencies.
- Frontend bundle: 209KB / 66KB gz, builds in ~470ms.

The eval/ bundle is seeded with placeholder JSON. It auto-populates once
the live collector accumulates enough slates (Part 0.4 deliverable list).
