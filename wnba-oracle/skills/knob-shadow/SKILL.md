---
name: wnba-oracle-knob-shadow
description: >
  Activate, review, and graduate a knob-shadow challenger in WNBA Oracle.
  A knob shadow runs the incumbent model's head predictions through a
  hypothetical picker-knob overlay on the same slate data, logs the ranking
  divergence (rbo_at_5, ndcg_at_5), and lets dayclose backfill the realized
  value delta once final scores arrive. Use this workflow to test a new default
  before committing it to production.
  Use when: operator wants to A/B test a picker knob change without deploying
  new code or changing the production freeze.
  Do not use: to change the actual production freeze result during a live contest.
license: proprietary
---

## Knob shadow architecture

A knob shadow does NOT change the production freeze. It:
1. Runs in job2 alongside the champion, using the same head predictions.
2. Logs a `model_shadow_runs` row with a synthesized challenger_sha derived
   from the overlay JSON hash.
3. After dayclose, the realized value delta is backfilled.

The challenger_sha for a knob shadow starts with `knob_` (vs `<sha64>` for
a model shadow). This lets the rotation gate distinguish between model and
knob comparisons.

## Step 1: Choose an overlay

Supported knob keys (from `scheduler/shadow_knobs.py:_KNOB_DEFAULTS`):

| Key | Default | Description |
|-----|---------|-------------|
| `starter_unknown_fade` | 0.75 | Fade for players with no RotoWire role |
| `picker_boost_tail_lift` | False | Whether to lift high-boost players |
| `boost_tail_lift_threshold` | 2.0 | Boost threshold for the tail lift |
| `boost_tail_lift_factor` | 1.5 | Lift multiplier above threshold |
| `starter_minutes_lift_enabled` | False | Lift starters whose recent minutes lag |
| `starter_minutes_norm` | 25.0 | Expected minutes for a starter |
| `starter_minutes_lift_weight` | 0.6 | Blend weight toward the norm |
| `starter_minutes_lift_cap` | 1.3 | Maximum lift factor |
| `floor_tilt_weight` | 0.0 | Penalty for low predicted floor |
| `floor_tilt_max_boost` | 2.0 | Ceiling on floor penalty |

Example: test whether the pre-2026-07-04 neutral unknown fade (1.0) has
lower realized value than the calibrated 0.75:

```json
{"starter_unknown_fade": 1.0}
```

## Step 2: Set the overlay env var on job2

In Railway, set `PICKER_KNOB_CHALLENGER_JSON` on the **cron-job2** service:

```
PICKER_KNOB_CHALLENGER_JSON={"starter_unknown_fade": 1.0}
```

The value must be valid JSON. Empty string disables the knob shadow.

To set via Railway CLI:

```sh
railway variables set PICKER_KNOB_CHALLENGER_JSON='{"starter_unknown_fade": 1.0}' \
  --service cron-job2 --environment production
```

Do not set this on the API or day-close services; they ignore it.

## Step 3: Verify the shadow logged on the next job2 run

After job2 completes, check `model_shadow_runs`:

```sh
uv run --frozen --package wnba-oracle python -c "
from wnba_oracle.common.clock import slate_date
from wnba_oracle.db.engine import get_engine
from sqlalchemy import text

sd = slate_date()
engine = get_engine()
with engine.connect() as conn:
    rows = conn.execute(text(
        '''SELECT challenger_sha, rbo_at_5, ndcg_at_5, realized_value_delta
           FROM model_shadow_runs
           WHERE slate_date = :sd AND challenger_sha LIKE 'knob_%' '''
    ), {'sd': sd}).fetchall()
    for r in rows:
        print(r)
"
```

A `knob_` prefix on challenger_sha confirms a knob shadow row.

## Step 4: Review accumulated delta after several slates

After 5+ slates, the realized_value_delta column has meaningful signal:

```sh
uv run --frozen --package wnba-oracle python scripts/analyze_strategy_gap.py --shadow-review
```

Or query directly:

```sh
uv run --frozen --package wnba-oracle python -c "
from wnba_oracle.db.engine import get_engine
from sqlalchemy import text

engine = get_engine()
with engine.connect() as conn:
    rows = conn.execute(text(
        '''SELECT challenger_sha,
                  COUNT(*) AS n_slates,
                  AVG(realized_value_delta) AS mean_delta,
                  SUM(realized_value_delta) AS total_delta
           FROM model_shadow_runs
           WHERE challenger_sha LIKE 'knob_%'
             AND realized_value_delta IS NOT NULL
           GROUP BY challenger_sha
           ORDER BY mean_delta DESC'''
    )).fetchall()
    for r in rows:
        print(f'{r.challenger_sha}: n={r.n_slates} mean={r.mean_delta:.4f} total={r.total_delta:.4f}')
"
```

- Positive mean_delta: the challenger knob config outperforms the incumbent
  on realized value.
- Negative mean_delta: the incumbent is better.

## Step 5: Graduate a winning challenger to production

If the challenger shows positive mean_delta over 5+ slates:

1. Update the relevant setting default in `common/settings.py` and
   add a calibration comment with the date and script.
2. Update `.env.example` with a description and the new default.
3. Clear `PICKER_KNOB_CHALLENGER_JSON` on Railway (set to empty string).
4. Open a PR with the change, run `make test lint typecheck`, merge.

Rollback: restore the previous Railway value, redeploy cron-job2, and verify the
running configuration before the next scheduled dispatch.

## Constraints

- Never change `PICKER_KNOB_CHALLENGER_JSON` between job1-late and the
  job2 freeze window; the shadow uses the same enrichment as the champion
  and a mid-slate change would produce a mismatched comparison.
- The knob shadow never touches `frozen_lineups`. Production freeze is
  always the champion.
- `frozen_lineups` is append-only. Do not reorder or delete entries.
