status: BUILD_COMPLETE
last_verified: 2026-05-27T02:30:00Z
phase: step_10_validated

# Build status

Set by the build automation. Allowed values: `IN_PROGRESS`,
`BLOCKED_NONFATAL`, `BUILD_COMPLETE`.

The 7-day shadow run + watchdog drill are wall-clock operational phases.
Both code paths are unit-tested and the manual fire path has been
exercised end-to-end via `scripts/manual_fire.py --fixtures`. The
operator starts the live shadow window via `oracle-rotate-check
--window-days 7` after the live collector has accumulated >= 7 slate
labels in `slate_labels`.

## Live services (verified 2026-05-26)

- api:      https://api-production-7033.up.railway.app/health -> 200
- api:      https://api-production-7033.up.railway.app/lineup -> 200
- frontend: https://frontend-production-a739.up.railway.app/ -> 200
- postgres: internal, alembic head = 20260527_0002
- redis:    internal, password-protected
- cron-job1: `0 13 * * *` UTC, oracle-cron --job job1
- cron-job2: `*/15 21-23,0-3 * * *` UTC, oracle-cron --job job2

## Live verifications (2026-05-26 probe)

- /home/wnba/next?cohort=0           -> 5 games today
- /players/sport/wnba/search?query=Q -> 20 rated players per prefix
- /games/playerratingcontest/1840    -> WNBA contest 1840 (day 2026-05-27)
- The Odds API basketball_wnba       -> 7 games, totals 164-172,
                                       497/500 monthly credits remaining

## Quality gates (post-audit, 2026-05-27)

- 55 unit tests pass.
- ruff + mypy strict on `src/` clean.
- 7 unused deps removed (~80MB image trim, no functional change).
- 3 dedup'd code locations consolidated under `common.db_utils` +
  `features.build.team_key_from_full_name`.
- One real bug caught and fixed: `slate_date` was being written into
  the slate feature matrix by `build_slate_features` but was not in the
  `PREGAME_FEATURES` allowlist, so every non-empty live call would have
  raised `FeatureLeakageError`. Now allowlisted (see DECISIONS D26) and
  covered by `tests/unit/test_features_build.py`.

The eval/ bundle is seeded with placeholder JSON. It auto-populates once
the live collector accumulates enough slates (Part 0.4 deliverable list).
