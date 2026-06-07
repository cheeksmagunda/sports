# 00 — Gap Analysis: why we can't win, and what to build

Operator-written synthesis (2026-06-06) over the 15 surviving research reports.
The 47-stream workflow was launched twice; the first run hit a StructuredOutput
schema deadlock and the second silently no-op'd most non-internal phases via
an over-eager skip-if-exists check. The internal forensics (6) and
players + environment (8) phases both completed in full; 1 of 15 external
streams wrote. The data-science, computer-engineering, verify, and fill phases
were not produced. Those are queued to re-run on a tighter prompt
(`scripts/workflow_research_v3.js`) in background; this file is the synthesis
from what is on disk now, plus the operator's prior knowledge of the codebase.

The file is intentionally short. Every claim cites the specific report (path
+ line range) it came from. Every roadmap item names the files to touch, the
metric to move, and the acceptance gate. The build agent works from this list
directly.

## 1. Executive summary

We finish in the 12th percentile of an 8.7k-entry field because our PROJECTIONS
are noise-flooded (~94.8% of the gap to the perfect-hindsight lineup is
projection error, only ~5.2% is construction error — `research/internal/02_loss_decomposition.md`).
Once projections are good enough, the next-largest leaks are over-boosting (we
ship median total boost 12-15; winners run 7.5), inverted slot assignment (we
load boost into slot 0 where it has the lowest leverage; winners do the
opposite), no game-stack logic at all (87% of top-20 lineups stack 2+ from one
game), and a menu-scrape gap that costs roughly 3% of the perfect-win-rate
ceiling.

Headlines:

- **Projections are the lever.** 94.8% of loss is projection error. The D63
  trained heads (offline corr 0.554 vs heuristic 0.246) are the proven fix.
  Wiring them alone lifts the top-500 rate from 33% to 61%
  (`research/internal/03_theoretical_ceiling.md`). **Shipped today as D69
  (commit 174290e, deployed)**.
- **3.0 card_boost is a value trap.** 79% of all 3.0-boost cards miss their
  line; the bucket's mean contribution is 6.11 (Sharpe 1.21) vs 8.86 (Sharpe
  2.01) for the (2.0, 2.5] bucket. Winners run ~0.59 cards at 2.5+; we have
  shipped FIVE 3.0 cards on at least one slate
  (`research/internal/04_boost_economics.md`).
- **Sweet spot is (1.0, 2.5] boost.** Winners over-pick (2.0, 2.5] at 2.6x
  the universe rate. We should build the lineup around this band, allow at
  most ONE 2.5-3.0 lottery, and zero 3.0 punts unless the menu forces it.
- **Winners invert our slot strategy.** Slot 0 (2.0x base) at rank-1 has mean
  card_boost 0.66; slot 4 (1.2x base) has mean 2.19. We do the opposite. Boost
  has the most leverage at the LOW-base slots (`research/internal/01_winners_anatomy.md`
  section 3).
- **Game-stacks are free EV.** 87% of top-20 lineups have 2+ picks from one
  game. Our optimizer has no game-correlation term — every lineup is built as
  if outcomes are independent (`research/internal/01_winners_anatomy.md`).
- **Ownership / contrarian is NOT the lever.** Winners are 60% sub-median
  drafts; we are 90% sub-median. The contrarian dial is already past
  optimal; pulling harder dilutes projection signal we cannot spare
  (`research/internal/02_loss_decomposition.md` open questions).

## 2. The gap, decomposed

Cumulative across 39 slates (9 LIVE frozen + 30 simulated), our lineup leaves
**18.97 mean points per slate vs the perfect-hindsight lineup**. The split:

| Source                        | Share | Mean pts/slate | Fixable? |
|-------------------------------|------:|---------------:|----------|
| Projection error              |  94.8%|         ~18.0  | Yes (D63 heads, components, matchup) |
| Construction error            |   5.2%|          ~1.0  | Mostly: slot assignment is closed-form under known scores |
| Live serving drift            | (LIVE only, ~3 pts; spike 15.2 on the 2026-06-04 bust) | (D69 fixes) |
| Irreducible variance (rank-1 to rank-20) | ~5 pts | floor |

Source: `research/internal/02_loss_decomposition.md` lines 24-46, 95-115.

Theoretical ceiling: even with perfect projections, the picker still finishes
mean rank 1.97 because the field duplicates the optimal lineup. The realistic
target is therefore a top-1% finish (rank ~87 of 8.7k), which translates to
~46-48 points on a typical slate. We average closer to 28-35. The fixable
spread is ~13-18 points (`research/internal/03_theoretical_ceiling.md`).

## 3. What winners actually do

From `research/internal/01_winners_anatomy.md` + `research/players_environment/`:

- **Total boost ≈ 7.5 (median across rank-1 lineups).** We ship 12-15. Cap
  the lineup-level sum.
- **Boost loading per slot, rank-1:** slot 0 mean 0.66, slot 1 1.09, slot 2
  1.56, slot 3 1.85, slot 4 2.19. Boost lives in the low-base slots; chalk
  fills the leverage slot.
- **Most picks are sub-median ownership.** Winners pick 4+/5 below the slate
  median draft count. Our picker already does this; the contrarian dial is
  not the problem.
- **2+ picks from one game in 87% of top-20 lineups.** Game-correlation is
  the largest untapped lever beyond projections.
- **Player-environment patterns** (from `players_environment/01-08`):
  teammate-out leverage, exploitable defensive matchups, schedule-spot
  patterns (3+ days rest, first home after road trip), and recent-form
  momentum are all measurable and currently uncaptured at serve time.

## 4. Where we are bleeding EV

Ranked by per-slate EV cost (high to low):

1. **Projection noise.** ~18 pts/slate vs perfect. (D69 closes part of this
   with the trained heads; component heads + matchup features + participation
   prior close the rest. Source: STATUS.md Phase 3-6 roadmap.)
2. **Over-boosting** (max-boost punts). Cost: ~3-5 pts/slate on average;
   spikes to 15 pts on bust slates like 2026-06-04. Fixable today.
3. **Slot inversion.** Cost: ~1-2 pts/slate when the slot assignment puts
   our highest-boost card in slot 0 instead of slot 4. Closed-form fix.
4. **No game-stack term.** Cost: ~2-3 pts/slate (87% of winners do it, we
   do it only by accident via `OPTIMIZER_MAX_PER_TEAM=2`).
5. **Menu-scrape gap.** ~3% of the perfect-win-rate ceiling. Players appear
   in winning lineups but are missing from `slate_labels` — at least 3 of
   141 slates affected (`research/internal/03_theoretical_ceiling.md` point 4).
6. **No late-info hook.** RotoWire fetched but not persisted
   (NEEDS_HUMAN #7); confirmed-starter / late-inactive lands AFTER our
   21:00 UTC freeze. Cost hard to quantify without a backtest of the
   late-news leak window.

## 5. Prioritized build roadmap

The top-3 items are scoped to ship-in-a-day each.

### R1. SHIPPED — D69: wire D63 trained heads into job2 (Tier-0)

- **EV:** lift top-500 rate 33% -> 61% per
  `research/internal/03_theoretical_ceiling.md`.
- **Effort:** S, shipped 2026-06-06 (commit 174290e).
- **Files touched:** `src/wnba_oracle/features/serving_features.py` (new),
  `src/wnba_oracle/scheduler/job1.py`, `src/wnba_oracle/scheduler/job2.py`,
  `tests/unit/test_head_tier0.py`.
- **Acceptance test:** `tests/unit/test_head_tier0.py` (4 cases pass).
  Live verification: watch `head_predict n_in=N n_out=N` and
  `predictor_mix n_head_predicted=N` in cron-job2 Railway logs for tomorrow's
  21:00 UTC freeze (today's slate runs ladder because cron-job1 already
  fired with pre-D69 code).

### R2. NEXT — boost-cap the lineup

- **What:** add an optimizer-side cap on sum-of-card-boosts in the picked 5,
  with a tight ceiling on max single-pick boost. Tunable via env:
  `OPTIMIZER_BOOST_SUM_CAP` (target 9.0, median winner 7.5 +1.5 slack) and
  `OPTIMIZER_MAX_SINGLE_BOOST` (target 2.5; pull only when the optimizer
  would otherwise pick a 3.0 trap). Both default OFF so the change is
  reversible via env, identical to D57's pattern.
- **EV:** prevents the recurring bust pattern. The 2026-06-04 ~6000th
  finish was driven by the picker landing 5 high-boost cards with no minutes
  history. Expected ~3-5 pts/slate on average, ~10-15 pts on bust slates.
- **Effort:** S. Single file change (`src/wnba_oracle/picker/optimize.py`) +
  settings field + one unit test pinning the cap behaviour.
- **Files:** `src/wnba_oracle/picker/optimize.py`,
  `src/wnba_oracle/common/settings.py`, `tests/unit/test_boost_cap.py` (new).
- **Acceptance:** unit test pins that with `BOOST_SUM_CAP=9` set, no lineup
  with sum > 9 is recommended; with cap unset, behaviour unchanged from main.
- **Dependencies:** none. Independent of R1.
- **Risk:** on a thin menu (few non-3.0 cards available) the cap could
  starve the optimizer; mitigated by graceful relax-to-feasible (if no
  lineup satisfies the cap, drop the constraint with a warning log).

### R3. NEXT — game-stack bonus in the optimizer objective

- **What:** add a small per-lineup bonus when 2+ picks come from one game
  (same `game_id` derivable from team+opponent). Winners stack 87% of the
  time; the optimizer should mildly prefer stacks at equal projection.
  Env-knob `OPTIMIZER_GAME_STACK_BONUS=0.5` (in real_score units),
  defaulting to 0.0 (off) for the first release.
- **EV:** ~2-3 pts/slate when the stack hits. Free game-script correlation
  in pace-up games.
- **Effort:** S. ~30 LOC in optimizer + game-id resolver from
  team/opponent.
- **Files:** `src/wnba_oracle/picker/optimize.py`,
  `src/wnba_oracle/common/settings.py`, `tests/unit/test_game_stack.py` (new).
- **Acceptance:** unit test pins that with bonus on, when two equal-score
  lineups differ only by stacking, the stacked one wins. With bonus off,
  behaviour unchanged.
- **Dependencies:** R2.
- **Risk:** stacking magnifies correlation downside on blowouts; mitigated
  by interaction with the existing `GameScriptConfig` blowout penalty.

### R4. Slot-assignment audit

- **What:** verify the slot assignment chooses highest expected
  `slot_multiplier * (real_score + offset)` not `boost * real_score`. The
  closed-form should already do this under `2.0, 1.8, 1.6, 1.4, 1.2`
  multipliers (D42). If it does, no change — log it. If not, fix.
- **EV:** ~1-2 pts/slate when the picked 5 contains a high-boost low-mean
  card that's currently being assigned to slot 0.
- **Effort:** S. One read + assertion + maybe one optimizer constant flip.
- **Files:** `src/wnba_oracle/picker/optimize.py`.
- **Acceptance:** unit test with a hand-crafted 5 cards verifies the
  expected slot order matches what closed-form rearrangement inequality
  prescribes (`real_score` descending into slots 0-1-2-3-4).

### R5. Persist RotoWire confirmed-starter into features_json

- **What:** close NEEDS_HUMAN #7 — RotoWire fetched but never written.
  `job1` already pulls lineups; route the result into the per-player
  `features_json["rotowire_confirmed"]`, which job2's existing
  `_starter_multiplier` already reads. Pure addition.
- **EV:** D63 features depend on `is_confirmed_starter`; today this
  defaults to 0 because no path persists it. Hard to quantify but
  removes a silent feature-leak.
- **Effort:** S. ~10 LOC in `src/wnba_oracle/scheduler/job1.py`.
- **Acceptance:** unit test that with a RotoWire entry naming a player
  as starter, the persisted `features_json` has `rotowire_confirmed=1`.

### R6. Investigate the menu-scrape gap

- **What:** identify the 3+ slates where players appear in winning
  lineups but are missing from `slate_labels`. Fix the scrape so the
  optimizer can pick them.
- **EV:** ~3% lift on perfect-win-rate ceiling. Real-money slates only.
- **Effort:** M. Investigation + scraper hardening.
- **Files:** `src/wnba_oracle/ingest/realsports.py`,
  `src/wnba_oracle/scheduler/job_dayclose.py`.
- **Acceptance:** none of the historical missing-player cases recurs in
  a re-run of `oracle-backfill` on the affected slates.

### R7. Component heads gated on CRPS (Phase 3 from D63)

- **What:** Beta-Binomial FG%/TS%, pin 3P%. Replaces the single
  `real_score_per_min` head with per-component heads that the recompose
  combines. Should drop projection noise floor below the current 1.0 RMSE
  target.
- **EV:** ~3-5 pts/slate per `theoretical_ceiling.md` (driving RMSE from
  1.0 toward 0.5).
- **Effort:** M. New head specs + training + recompose + gate via
  `eval/rotation_gate`. STATUS.md Phase 3.
- **Files:** `src/wnba_oracle/train/pipeline.py`,
  `src/wnba_oracle/features/spec.py`, `src/wnba_oracle/predict/scoring.py`,
  `src/wnba_oracle/eval/rotation_gate.py`.
- **Acceptance:** slate-bootstrap CRPS gate beats heuristic + deflated-edge
  guard; ratifies before swap.
- **Dependencies:** R1.

### R8. Matchup / pace / DvP ingest (Phase 4 from D63)

- **What:** hard-shrunk per-position-vs-opponent stats. The trained heads'
  feature spec already names them (`opp_dvp_forward`, `team_pace`,
  `opp_pace`, etc); none are populated today.
- **EV:** ~2-3 pts/slate when matchup is strongly mispriced by boost.
- **Effort:** M. New ingest module + feature wiring.
- **Files:** `src/wnba_oracle/ingest/` (new matchup module),
  `src/wnba_oracle/features/build.py`.
- **Acceptance:** corr lift on the heads' walk-forward against the no-
  matchup baseline; CRPS gate ratifies.
- **Dependencies:** R1.

### R9. Participation prior (Phase 5 from D63)

- **What:** survivorship-fix the rookie / cold-start probability with a
  roster-eligible denominator. Today the heads can over-predict for
  players who are technically on the roster but rarely play.
- **EV:** prevents cold-start dart busts (the 2026-06-01 root cause).
- **Effort:** M. STATUS.md Phase 5; blueprint in mlb-oracle.
- **Files:** new `src/wnba_oracle/predict/participation.py`.
- **Dependencies:** R7 (so the prior multiplies a calibrated head, not
  the heuristic).

### R10. Re-run the failed external/data-science/computer-engineering research

- **What:** the v2 workflow's external/ds/ce phases silently no-op'd via
  the over-eager skip-if-exists check (target files didn't exist; agents
  returned DONE without writing). Rewrite the prompt to require an
  affirmative `wc -l` of the written file before returning DONE.
- **EV:** unlocks the deeper roadmap (modern statistical methods,
  ownership projection theory, event-driven pipelines).
- **Effort:** S to relaunch (`scripts/workflow_research_v3.js`).

## 6. Player + environment playbook (per-slate cheat-sheet)

From `research/players_environment/`:

- **Reliable winners** (high frequency in winning lineups across 141 slates):
  see `01_winner_player_frequency.md` for the top-30. The picker should
  prefer these names on equal-EV ties.
- **Teammate-out leverage** (`02_teammate_out_leverage.md`): when a typical
  starter is out, the next rotation player gets a usage + minutes spike.
  Cross-reference the per-team starter list against the RotoWire OUT list
  every fire.
- **Matchup edge** (`03_matchup_edge.md`): opponents with above-average
  defensive ratings allowed to a given position are exploitable;
  per-opponent "soft" list is in the report.
- **Schedule spots** (`04_schedule_spot_edges.md`): 3+ days rest > 1 day
  > back-to-back. First home after road trip is + EV. Last road game is - EV.
- **Vegas environment** (`05_vegas_environment.md`): high total + close
  spread is the optimal stack environment; blowout spreads drop the
  blowout-side starters' minutes (D57 already models this).
- **News-driven picks** (`06_news_driven_picks.md`): the upper bound of
  what a better news-ingest pipeline could buy is the per-pick "obvious in
  retrospect" share; the report quantifies it.
- **Recent form** (`08_recent_form_momentum.md`): hot streaks have
  measurable persistence; Real Sports lags by ~N games in pricing it.

## 7. Open questions

- **Top-500 vs top-20 gap.** `contest_leaderboards` stores only top-20, so
  the rank-500 score is extrapolated, not measured. A direct measurement
  needs a one-time scrape of the full leaderboard (which Real Sports
  supports).
- **Field draft% latency.** When does `drafts` finalize relative to our
  21:00 UTC freeze? If field drafts spike post-freeze, our contrarian
  adjustment reads stale ownership.
- **Calibration of D63 heads on stars.** Today's smoke (`A. Wilson p50=5.1`)
  reads low for the MVP — either an absolute-calibration miss or a feature
  routing issue (cohort F pool dragging mean down). Worth measuring head
  predictions vs realized real_score on the first 2-3 live slates.

## 8. Weak links

- **No verify phase ran.** Every claim in this synthesis is from the
  internal forensics or players_environment reports as written; no
  adversarial verifier checked them. The numbers most likely to be off
  (because they involve more complex joins or external scrapes) are:
  player-frequency top-30 list, teammate-out per-min rate boost,
  matchup soft-opponent list. Treat these as directionally correct
  pending re-run of the verify phase.
- **External best-practice not on disk.** Section 3 patterns ("87%
  game-stack", "winners chalk slot-0") are from internal forensics over
  our 141-slate corpus; they are NOT cross-validated against the DFS
  best-practice literature. Re-run R10 to get that cross-validation.
- **Theoretical ceiling assumes Gaussian projection noise.** Real noise
  is heavier-tailed (injuries, ejections, blowouts), so the rank-vs-RMSE
  curve likely understates the median-to-worst-decile spread for the
  live heuristic.

---

Generated 2026-06-06 by the operator from the surviving research output. The
build agent should start at R2 immediately (R1 shipped today).
