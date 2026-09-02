---
name: wnba-oracle-slate-review
description: >
  Pre-freeze slate review for WNBA Oracle. Reads player pool, archetype labels,
  stat-leverage scores, and streak quality from Postgres. Surfaces the lineup
  the model froze (or will freeze) with interpretable player context so the
  operator can confirm the picks before the contest lock.
  Use when: operator wants to review today's picks, understand why a player
  was slotted where they were, or compare production lineup to a challenger.
  Do not use: to place bets, to fetch live scores from ESPN, or to bypass the
  freeze rules. The authoritative store is Postgres; do not substitute ESPN
  public API data for production picks.
license: proprietary
---

## Data contract

All data for this skill comes from Railway Postgres. Do not use ESPN, web
scraping, or any source that bypasses Real Sports or the stored enrichment.

Authoritative tables:
- `frozen_lineups` -- committed picks, slot order, payload_json with archetype labels
- `player_pool` -- pool players, card_boost, is_confirmed_starter
- `player_features` -- features_json (starter signal, vegas lines, prop lines)
- `slate_labels` -- realized real_score (available only post-game)
- `model_shadow_runs` -- challenger vs incumbent comparison (rbo_at_5, ndcg_at_5)

## Pre-conditions

Before running this skill, verify that job1 and (optionally) job1-late have
completed for the target slate date:

```sh
# From wnba-oracle/
uv run --frozen --package wnba-oracle python -c "
from wnba_oracle.common.settings import get_settings
from wnba_oracle.db.engine import get_engine
from sqlalchemy import text
settings = get_settings()
engine = get_engine()
with engine.connect() as conn:
    rows = conn.execute(text(
        \"SELECT slate_date, first_tip_utc, contest_lock_utc FROM slate_meta ORDER BY slate_date DESC LIMIT 3\"
    )).fetchall()
    for r in rows:
        print(r)
"
```

If slate_meta is empty or stale, job1 has not run yet. Do not proceed.

## Step 1: Load the frozen lineup (or the current pool if pre-freeze)

```sh
uv run --frozen --package wnba-oracle python -c "
import json
from wnba_oracle.common.clock import slate_date
from wnba_oracle.db.engine import get_engine
from sqlalchemy import text

sd = slate_date()  # or pass a specific date string
engine = get_engine()
with engine.connect() as conn:
    # Try to load the freeze for today
    rows = conn.execute(text(
        '''SELECT player_ids, ev_estimate, recommendation, payload_json
           FROM frozen_lineups
           WHERE slate_date = :sd
           ORDER BY sequence DESC LIMIT 1'''
    ), {'sd': sd}).fetchall()

    if rows:
        r = rows[0]
        print('Recommendation:', r.recommendation)
        print('EV estimate:', r.ev_estimate)
        print('Player IDs (slot order):', r.player_ids)
        payload = r.payload_json or {}
        archetypes = payload.get('archetypes', {})
        print('Archetypes:', json.dumps(archetypes, indent=2))
    else:
        print('No freeze yet for', sd, '-- showing pool top-10 by card_boost')
        pool = conn.execute(text(
            '''SELECT player_name, card_boost, is_confirmed_starter, features_json
               FROM player_pool
               WHERE slate_date = :sd
               ORDER BY card_boost DESC LIMIT 10'''
        ), {'sd': sd}).fetchall()
        for p in pool:
            print(f'  {p.player_name:30s} boost={p.card_boost:.2f} starter={p.is_confirmed_starter}')
"
```

## Step 2: Surface archetype and leverage context

For each player in the frozen lineup, print archetype, streak quality, and
stat leverage. This data is written to `frozen_lineups.payload_json` at
freeze time by job2.

```sh
uv run --frozen --package wnba-oracle python -c "
import json
from wnba_oracle.common.clock import slate_date
from wnba_oracle.db.engine import get_engine
from sqlalchemy import text

sd = slate_date()
engine = get_engine()
SLOT_LABELS = ['2.0x', '1.8x', '1.6x', '1.4x', '1.2x']

with engine.connect() as conn:
    rows = conn.execute(text(
        '''SELECT player_ids, payload_json FROM frozen_lineups
           WHERE slate_date = :sd ORDER BY sequence DESC LIMIT 1'''
    ), {'sd': sd}).fetchall()
    if not rows:
        print('No freeze for', sd)
    else:
        pids = rows[0].player_ids
        payload = rows[0].payload_json or {}
        archetypes = payload.get('archetypes', {})
        for i, pid in enumerate(pids):
            arch = archetypes.get(str(pid), {})
            label = arch.get('primary', 'unknown')
            streak = arch.get('is_streaking', False)
            confidence = arch.get('confidence', 0.0)
            slot = SLOT_LABELS[i] if i < len(SLOT_LABELS) else '?'
            streak_tag = ' STREAKING' if streak else ''
            print(f'  Slot {slot}: pid={pid} archetype={label}{streak_tag} confidence={confidence:.2f}')
"
```

## Step 3: Check for a challenger shadow result

If `WNBA_ORACLE_MODEL_CHALLENGER_SHA` or `PICKER_KNOB_CHALLENGER_JSON` was set
during the last job2 run, a shadow row exists in `model_shadow_runs`. Review it:

```sh
uv run --frozen --package wnba-oracle python -c "
from wnba_oracle.common.clock import slate_date
from wnba_oracle.db.engine import get_engine
from sqlalchemy import text

sd = slate_date()
engine = get_engine()
with engine.connect() as conn:
    rows = conn.execute(text(
        '''SELECT challenger_sha, incumbent_sha, rbo_at_5, ndcg_at_5,
                  realized_value_delta, payload_json
           FROM model_shadow_runs
           WHERE slate_date = :sd'''
    ), {'sd': sd}).fetchall()
    if not rows:
        print('No shadow runs for', sd)
    for r in rows:
        delta = r.realized_value_delta
        delta_str = f'{delta:+.4f}' if delta is not None else 'pending (dayclose backfills)'
        print(f'  challenger={r.challenger_sha[:16]} incumbent={r.incumbent_sha[:16]}')
        print(f'  rbo_at_5={r.rbo_at_5:.3f} ndcg_at_5={r.ndcg_at_5:.3f}')
        print(f'  realized_value_delta={delta_str}')
"
```

## Step 4: Interpret and decide

Read the output from Steps 1-3. Apply these heuristics:

- `recommendation: enter` + EV >= 1.0 + at least 2 Ceiling Anchor or
  Efficient Producer archetypes -> enter with confidence.
- `recommendation: enter_with_caveat` -> review the challenger delta. If
  the challenger significantly outranked the incumbent (rbo < 0.5), consider
  whether the challengers settings should become the new production config.
- `recommendation: skip` -> do not enter. The model sees insufficient edge.
- All Leverage Spike lineup -> high-variance, tournament-only entry; flag
  for operator awareness.

These heuristics do not override the model's recommendation. They add
context for the operator's final check.

## Step 5: Post-game review (after dayclose)

After dayclose completes, `slate_labels.real_score` is populated. The
`realized_value_delta` in `model_shadow_runs` is also backfilled. Run the
post-game script to compare actual vs predicted:

```sh
# From wnba-oracle/ (after dayclose)
uv run --frozen --package wnba-oracle python scripts/replay_slate.py --date <YYYY-MM-DD>
```

Check placement with:

```sh
uv run --frozen --package wnba-oracle python scripts/loss_ledger.py --recent 5
```

## Authoritative data flow reminder

```
job1/job1late -> Postgres (player_pool, player_features, slate_meta)
job2 -> Postgres (frozen_lineups, model_shadow_runs)
dayclose -> Postgres (slate_labels, contest_placements)
API -> reads Postgres only
```

Do not call ESPN or any external data source during a production slate
review. The stored enrichment from job1 is authoritative.
