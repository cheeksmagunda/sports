status: BUILD_COMPLETE
last_verified: 2026-05-27T03:30:00Z
phase: ready_for_2026_05_27_slate

# Build status

Set by the build automation. Allowed values: `IN_PROGRESS`,
`BLOCKED_NONFATAL`, `BUILD_COMPLETE`.

The 7-day shadow run + watchdog drill are wall-clock operational phases.
All code paths are unit-tested; the manual fire path has been exercised
end-to-end via `scripts/manual_fire.py --fixtures`. The operator starts
the live shadow window via `oracle-rotate-check --window-days 7` after
the live collector has accumulated >= 7 slate labels in `slate_labels`.

## Live services (verified 2026-05-27)

- api:       https://api-production-7033.up.railway.app/health -> 200
- api:       https://api-production-7033.up.railway.app/lineup -> 200
- frontend:  https://frontend-production-a739.up.railway.app/ -> 200
- postgres:  internal, alembic head = 20260527_0002
- redis:     internal, password-protected
- cron-job1: `0 13 * * *` UTC, oracle-cron --job job1
- cron-job2: `*/15 21-23,0-3 * * *` UTC, oracle-cron --job job2
- cron services seeded with REALSPORTS_STORAGE_STATE_B64GZ + WNBA_DEVICE_UUID
- env-tunable knobs set: CONTRARIAN_STRENGTH=0.2, CONTRARIAN_ENABLED=true,
  OPTIMIZER_MAX_PER_TEAM=2, PAYOUT_REGIME=top_20

## Strategy ports from basketball-main (2026-05-27)

Six patterns ported across two rounds. See DECISIONS D27-D33.

Round 1 (commit 65cef5b):
- D27 **Anti-popularity contrarian tilt.** Late-season alpha source;
  basketball-main measured -0.457 popularity-vs-boost correlation and
  ~24-26% value uplift in the least-drafted half.
- D28 **`max_per_team=2`** in the optimizer. Skips ~30% of combos early
  so the constraint is also a speedup.
- D29 **Injury-cascade minutes redistribution** module.

Round 2 (commit 797ceac):
- D30 **Game-script tier multipliers, WNBA-calibrated.** Vegas total
  drives a real_score multiplier; blowout penalty fires only in
  track_meet games with |spread| >= 8.
- D31 **Env-tunable contrarian strength + max_per_team.** Operator
  tunes via Railway env vars without a code deploy.
- D32 **Inject Vegas total + spread into job1_enrichment.features_json.**
  Single Odds API hit per slate; the signals flow to all downstream
  consumers without re-fetching.
- D33 **Wire injury_cascade into build_slate_features.** Operator
  action item 5 complete.

## Tomorrow's slate (2026-05-27)

Cron-job1 fires at 13:00 UTC (9am ET) tomorrow:
1. Headless re-auth via REALSPORTS_STORAGE_STATE_B64GZ + WNBA_DEVICE_UUID
2. /home/wnba/next + /players/sport/wnba/search a..z pool fetch
3. The Odds API basketball_wnba pull (vegas signals -> features_json)
4. RotoWire WNBA lineups scrape
5. UPSERT into job1_enrichment

Cron-job2 fires every 15 min from 21:00 UTC through 04:00 UTC:
1. Load slate from job1_enrichment + slate_labels (drafts if available)
2. Compute per-player heuristic real_score
3. Apply game_script_multiplier (Vegas-driven tier weights)
4. Apply anti-popularity contrarian adjustment
5. Optimize lineup (top-30 -> C(30,5), max_per_team=2)
6. Freeze via Redis SET NX + Postgres UPSERT

The frontend (https://frontend-production-a739.up.railway.app/) auto-
fetches the frozen lineup from /lineup/2026-05-27.

## Quality gates

- 77 unit tests pass.
- ruff + mypy strict on `src/` clean.
- 57 source files in `src/wnba_oracle/`.
- 6 basketball-main patterns ported with zero new external dependencies.

The eval/ bundle is seeded with placeholder JSON. It auto-populates once
the live collector accumulates enough slates (Part 0.4 deliverable list).
