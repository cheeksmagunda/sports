status: BUILD_COMPLETE
last_verified: 2026-05-27T03:00:00Z
phase: late_season_alpha_ported

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

## Strategy ports from basketball-main (2026-05-27)

Three patterns ported from the sibling NBA Real Sports product the
operator used to win late-season drafts. See DECISIONS D27 / D28 / D29.

- **Anti-popularity contrarian tilt** (D27). Late-season alpha source;
  basketball-main measured -0.457 popularity-vs-boost correlation and
  ~24-26% value uplift in the least-drafted half. Wired into Job 2's
  `_build_specs`. `picker/popularity.py` + `ContrarianConfig`.
- **`max_per_team=2`** (D28). Optimizer hard cap; skips ~30% of combos
  early so it is also a speedup. `picker/optimize.py`.
- **Injury-cascade minutes redistribution** (D29). Bench-weighted
  cohort-aware redistribution from OUT starters.
  `features/injury_cascade.py`. Wiring into `build_slate_features`
  pending the RotoWire `injury_status` flow-through.

## Quality gates

- 73 unit tests pass.
- ruff + mypy strict on `src/` clean.
- 56 source files in `src/wnba_oracle/`.
- 3 patterns ported with zero new external dependencies.

The eval/ bundle is seeded with placeholder JSON. It auto-populates once
the live collector accumulates enough slates (Part 0.4 deliverable list).
