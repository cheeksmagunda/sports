---
name: wnba-oracle-strategy-gap
description: >
  Run the WNBA Oracle strategy gap analysis. Compares the model's picks to
  realized outcomes, identifies systematic biases (archetype hit rates, starter
  signal accuracy, boost calibration), and surfaces knob candidates for the
  next shadow cycle. This is the primary tool for iterative model improvement.
  Use when: operator wants to know where the model is losing EV, which player
  types are systematically over- or under-weighted, or whether the current
  starter/boost configuration is tracking reality.
  Authoritative store: Postgres (wnba_game_logs, slate_labels, frozen_lineups,
  model_shadow_runs, player_pool).
license: proprietary
---

## Purpose

This skill wraps the research scripts that quantify the model's strategy gap.
It is the workflow equivalent of the "data interpretation and tactical analysis"
loop described in sports-analytics literature: measure the gap, hypothesize
a cause, shadow-test the fix, graduate if it wins.

## Pre-conditions

Requires at least 5 finalized slates (dayclose has run; `slate_labels`
has `real_score` populated). Check:

```sh
uv run --package wnba-oracle python -c "
from wnba_oracle.db.engine import get_engine
from sqlalchemy import text
engine = get_engine()
with engine.connect() as conn:
    n = conn.execute(text(
        'SELECT COUNT(DISTINCT slate_date) FROM slate_labels WHERE real_score IS NOT NULL'
    )).scalar()
    print('Finalized slates:', n)
"
```

## Step 1: Counterfactual backtest

Compare every past freeze to what the model would have picked under
alternative knob configurations:

```sh
# From wnba-oracle/
uv run --package wnba-oracle python scripts/backtest_counterfactual.py --recent 20
```

Produces a table of (slate_date, config_name, ev_estimate, realized_value,
rank_correlation). Read the output for:
- Configs that beat the incumbent on realized value
- Configs where rank_correlation (Spearman r) drops for specific player types

## Step 2: Walk-forward backtest

Evaluate the current production config on a rolling window without look-ahead:

```sh
uv run --package wnba-oracle python scripts/backtest_walkforward.py \
  --window 20 --step 5
```

This is the cleanest measure of in-production drift because it uses only
information available at each freeze time.

## Step 3: Analyze the strategy gap

Run the dedicated strategy gap script for a structured report:

```sh
uv run --package wnba-oracle python scripts/analyze_strategy_gap.py \
  --recent 20 --verbose
```

The report covers:
- Hit rate by archetype (Ceiling Anchor, Efficient Producer, Leverage Spike)
- Starter signal accuracy (how often confirmed starters outperformed unknowns)
- Boost tier calibration (does pred_real_score by card_boost quartile
  match actual real_score?)
- Top-5 slot accuracy (were high-value players correctly ranked into
  high-multiplier slots?)

## Step 4: Inspect loss ledger

The loss ledger shows the cumulative realized value delta relative to
alternative lineup constructions:

```sh
uv run --package wnba-oracle python scripts/loss_ledger.py --recent 20
```

If the ledger shows consistent loss from a specific player type (e.g.,
Leverage Spikes underperforming), that is a signal to add a new knob shadow
(see knob-shadow skill).

## Step 5: Calibrate knobs

If the analysis identifies a calibration gap (e.g., starter_unknown_fade is
wrong, boost_tail_lift hurts or helps), run the calibration script:

```sh
# Calibrate starter and boost parameters
uv run --package wnba-oracle python scripts/calibrate_starter_and_boost.py

# Calibrate contrarianstrength and optimizer settings
uv run --package wnba-oracle python scripts/calibrate_knobs.py
```

Record findings in `wnba-oracle/STATUS.md` and open a knob shadow via the
knob-shadow skill before changing any production default.

## Step 6: Replay a specific slate

If a particular slate had surprising results, replay it:

```sh
uv run --package wnba-oracle python scripts/replay_slate.py --date <YYYY-MM-DD>
```

This re-runs the optimizer on the stored enrichment and shows what the model
saw at freeze time vs what actually happened.

## Interpretation heuristics (WNBA-specific)

These heuristics are derived from the WNBA scoring formula (stl/blk/ast are
the highest-leverage stats per `predict/scoring.py:REAL_SCORE_WEIGHTS`):

- **Archetype miss rate > 30% for Ceiling Anchors**: the minutes floor
  assumption is wrong. Check if recent WNBA pace trends have changed the
  minutes distribution for the pool. May need a new minutes-model run.
- **Starter signal accuracy < 70%**: job1-late RotoWire enrichment may be
  arriving after the freeze window. Check `job_runs` for job1-late timing.
- **Boost calibration error > 20%**: the heuristic fallback
  (`modeling/scoring.py:_heuristic_real_score`) is being used for too many
  players. Check model artifact freshness in `STATUS.md`.
- **rbo_at_5 < 0.5 on shadow rows**: challenger and incumbent disagree
  substantially. The shadow is informative; check realized_value_delta
  before graduating.

## Constraints

- All analysis reads Postgres. Do not substitute local parquet or data/
  exports as the source of truth.
- Do not mutate `frozen_lineups`, `slate_labels`, or `wnba_game_logs`
  as part of this analysis. These are read-only from this skill's perspective.
- Calibration scripts may write to `runs/` (gitignored); those outputs
  are not canonical. Record findings in STATUS.md, not in runs/.
