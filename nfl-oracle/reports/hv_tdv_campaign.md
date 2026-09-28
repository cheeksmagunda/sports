# NFL Highest-value / Total-value campaign (#603)

Generated 2026-09-28. The grid did not execute. Worker volume
`data/raw/corpus_c` listed 0 entries (not truncated) at about 03:15Z, and
this checkout has no local Corpus C or Corpus G payloads. Capture tables
below are the command contract for the next run that has both trees and a
ContextSnapshot. Volume facts and the live-knob recommendation are in
`nfl-oracle/STATUS.md`.

Primary metric is capture ratio: realized total value of the frozen five
divided by the hindsight-best five on the same pool, slots, and boosts.
Win counts are reference only.

## Command

From `nfl-oracle`, after Corpus C and Corpus G are on disk:

```sh
uv run --package nfl-oracle python scripts/hv_tdv_campaign.py \
  --history-root data/raw/corpus_g \
  --contest-root data/raw/corpus_c \
  --context-snapshot /path/to/context.json \
  --out reports/hv_tdv_campaign.json \
  --report reports/hv_tdv_campaign.md
```

Context snapshots seen on the worker (not copied here):

- `/app/nfl-oracle/data/artifacts/context/22d9018b8aea472fc43999172936373058fa6390f13cb927e48fa62f259fa8cd.json`
- `/app/nfl-oracle/data/artifacts/context/d4bfae2cea9397a6c58f851ef1dbefc8b5bc2b8ef0e5afd03eaede7f1ebdf013.json`

Single-arm replay (same inputs):

```sh
uv run --package nfl-oracle nfl-contest-pool-replay \
  --history-root data/raw/corpus_g \
  --contest-root data/raw/corpus_c \
  --context-snapshot /path/to/context.json \
  --optimizer-profile max_value \
  --boost-rank-blend 0.75 \
  --picker-profile boost_0.75 \
  --max-defenders 1 \
  --max-kickers 1 \
  --slot-by-mean \
  --pool-scope visible \
  --out /tmp/contest_pool_replay.json
```

Pass `--max-defenders 0 --max-kickers 0` (CLI defaults) and omit
`--slot-by-mean` for the uncapped joint-slot arm. `--pool-scope contest_games` uses every Corpus G
participant on the contest's games and that roster's own ceiling.

Existing shared-fit blend ladder (no position caps):

```sh
make -C nfl-oracle picker-knob-sweep CONTEXT_SNAPSHOT=/path/to/context.json \
  OUT=/tmp/picker_knob_sweep.json
```

## What the campaign compares

Construction base matches live serve: `max_value` (diversity floor 1/1),
upside weight 0.15, field weight 0.10, simulations 100, weekly retrain,
compact residual samples.

Visible-pool arms:

- blend identity and `boost_0.75`
- defenders uncapped and max 1
- kickers uncapped and max 1
- slots joint and by descending projected mean
- extra ladder: boost 0.25, boost 0.50, position calibration 1.0,
  boost 0.35 with position 0.5, caps off, joint slots

Contest-game arms (separate ceiling): identity and `boost_0.75`, caps off,
joint slots. Columns include mean prior games and cold-start pick counts
(zero Corpus G rows before the slate cutoff).

## Cold-start chalk

Visible pool: contest `draft_stats` players joined to Corpus G. Contest-game
roster: every Corpus G row on a game that visible pool matched. Live collect
rates the search-matched pre-kickoff roster; a started game is not in that
pool. `predict` zeros `prior_log_count` and widens uncertainty when prior
games are low, so a cold player is not given a chalk mean. Contest-game
rows are postgame participants, which is generous on availability versus a
true pregame roster. Do not rank a contest-game capture ratio against a
visible-pool capture ratio.

## Slot-by-mean

`score = value * (slot + boost)`. The boost term does not depend on which
slot the player takes, so the optimal order of a fixed five is by descending
projected value. `slot_by_mean` changes the frozen order only when
`Projection.mean` and the sample mean inside the slot score disagree, or
when a beam proposal was not already in that order.

## Checks this session

`make write-path-check` failed: `gh codespace list` returned HTTP 403 for
this cloud token, so the Codespace route was not proven and the Codespace
was not woken. A direct `git push --dry-run` to `origin` succeeded.

Focused tests: `test_optimizer_position_caps.py` and
`test_replay_contest_pool.py` passed. The historical 91-contest sweep was
not re-run.
