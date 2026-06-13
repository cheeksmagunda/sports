# 07 — Placement overhaul: why we finish mid-pack and how to fix it

Date: 2026-06-13. Author: build automation (D86 session).

Tags: `[verified]` = read from code or the operator's screenshots.
`[reasoned]` = synthesized argument. `[literature]` = external source.

## 0. The complaint, stated precisely

The operator's 2026-06-12 entry finished **4,253rd of 8,300 (51st percentile)**
`[screenshot]`. The ask is to consistently reach the top 10%, ideally top 5%.
The operator is right that this should be achievable: we have two seasons of
game logs and a projection model that walk-forward beats the boost heuristic
2x on rank correlation (0.554 vs 0.246, D63). The problem is **not** projection
accuracy. It is contest construction. This document diagnoses why and lays out a
phased fix. Phase 0 ships in this PR.

## 1. What the screenshots actually say

The 2026-06-12 lineup `[screenshot, IMG_8047/8049]`:

| Player            | Drafts | Field own % | Realized mult | Beat proj |
|-------------------|--------|-------------|---------------|-----------|
| Shakira Austin    | 2,600  | 31%         | 2.5x          | +0.5x     |
| Flau'jae Johnson  | 2,900  | 35%         | 2.9x          | +1.1x     |
| Julie Allemand    | 321    | 4%          | 3.8x          | +2.2x     |
| Awa Fam           | 1,700  | 20%         | 3.1x          | +1.7x     |
| Michaela Onyenwere| 494    | 6%          | 3.5x          | +2.3x     |

Total 30.21, 4,253rd of 8,300.

Two facts jump out `[verified from screenshot]`:

1. **Every single player beat their projection** (all five "+x" deltas are
   green). The model was not wrong about these players. We still finished at the
   median.
2. **The two best cards by a wide margin were the two lowest-owned**
   (Allemand 4% own -> 3.8x; Onyenwere 6% own -> 3.5x). The three chalk cards
   (Austin, Johnson, Fam, all 20-35% owned) returned 2.5-3.1x and dragged the
   entry to the middle.

The conclusion is unambiguous `[reasoned]`. When everyone beats projection, the
slate becomes a coin flip decided by **differentiation**. Three of our five
picks were owned by 20-35% of an 8,300-entry field, so meeting or modestly
beating projection on those cards moves us *with the pack*, not past it. The
contrarian legs were the ones that created separation, and we did not have
enough of them. We shipped a lineup that, by construction, could not finish top
10% even when the players performed.

This is the textbook large-field GPP failure mode: **a chalk-heavy build in a
top-heavy payout.** `[literature]`

## 2. Root cause in the code

The picker *intends* to be contrarian (`picker/popularity.py`, D27/D51) and to
optimize payout-EV against a field (`picker/payout.py`, `picker/optimize.py`).
But the machinery has a load-bearing defect that makes the contrarian intent
cosmetic.

### 2.1 The field model is a strawman built from our own projections `[verified]`

`picker/field.py:project_ownership` derives the simulated opponents' ownership
from a softmax of **our own** `pred_real_score * (1 + card_boost)`. Then
`picker/optimize.py:294-309` scores those opponent lineups with **our own**
copula samples. So the entire EV/rank calculation answers the question:

> "How does my lineup rank against a field that drafts exactly what my value
> model thinks is good, and whose players score exactly what my model predicts?"

That field is a strawman. The real field is **observed**: Real Sports shows
each player's live draft count in-app pre-lock (the 2,600 / 2,900 / 321 / 1,700
/ 494 numbers in the screenshot), and `job1` already captures it into
`slate_labels.drafts`. We were loading it (`job2.py:551`) and spending it on a
small scalar contrarian penalty (`popularity.py`), then **throwing it away
before the field simulation.** `FieldPlayerSpec` did not even have a field for
it `[verified, field.py pre-D86]`.

Consequences `[reasoned]`:

- The simulated field never concentrates the way the real field does (35% of
  entries on one player), so the optimizer cannot *see* duplication risk.
- With no duplication signal, a chalk lineup looks as differentiated as a
  contrarian one, so the convex payout curve has nothing to bite on.
- The contrarian penalty in `popularity.py` is a fixed -0.16 nudge on
  `pred_real_score` (max 0.12-0.16 real-score units at strength 0.2). On a slate
  where projections range 0.7-3.1, that is far too weak to overcome a chalk
  player's projection edge. It is a tie-breaker, not a leverage engine.

### 2.2 The field-selection model has no correlation `[verified, field.py:65]`

`simulate_field_lineups` draws opponent picks **independently** from ownership.
Real entrants stack: the same chalk players co-occur in the same lineups far
more than independence implies. So even with correct marginal ownership, we
understate how *duplicated* a full chalk build is. The independence assumption
is flagged in the docstring as "revisited in Step 8" and never was.

### 2.3 The payout curve is almost certainly the wrong shape `[verified + reasoned]`

`payout.py:default_curve_for_regime("top_20")` caps the cash line at the 20th
percentile and pays a flat step schedule (8x at top 1%, down to 1.4x at top
20%). `load_curve_from_archive` only overrides this if a local
`data/contest_payouts/*.json` exists, which in the live container it does not
`[reasoned, no archive populated]`. So we optimize a **guessed cash-style
curve** while the operator's stated goal is top 5-10% in an 8,300-entry GPP,
which is a steeply top-heavy structure. Optimizing a top-20 cash curve
rationally produces a higher-floor, chalkier build than the goal wants. The
objective is miscalibrated to the target.

### 2.4 We do not measure our own results `[verified, RESULTS.md]`

`RESULTS.md` has exactly one entry, an in-progress screenshot reconstruction
from 2026-05-28. `contest_leaderboards` stores only the top 20 finishers, so we
cannot recover our own rank from the DB. Every "improvement" since D50 has been
validated on *offline projection accuracy*, never on *realized placement*. We
have been flying without the one instrument that matters. You cannot
consistently hit top 10% if you never record where you actually finished.

## 3. What the literature says to do instead

Large-field GPPs are top-heavy: nearly all the prize money sits in the top few
percent. The canonical academic treatment is Hunter, Vielma & Zaman, *Picking
Winners in Daily Fantasy Sports Using Integer Programming* (INFORMS / arXiv
1604.01455) `[literature]`. Two results carry directly:

1. **Optimize the probability of a top finish, not the mean.** The objective
   should be the chance at least one entry lands in the money, which is a
   submodular function rewarding *ceiling and diversity*, not expected points.
   Our `expected_payout` Monte Carlo is the right shape; it is starved by a bad
   field model (Section 2.1).
2. **Model correlation; stack deliberately.** Same-team (and same-game)
   fantasy outputs are positively correlated, and winning lineups exploit it.
   We have the copula (`sample.py`) and a tiny game-stack bonus (D70/R3) but no
   field-side correlation (Section 2.2).

Haugh & Singal, *How to Play Fantasy Sports Strategically (and Win)* (Columbia)
adds the game-theoretic layer `[literature]`: your opponents' lineups are a
strategic variable, so you must **model opponent ownership explicitly** and
maximize *expected payout given the field*, not expected score. This is exactly
the input we were discarding.

Current practitioner consensus for **single-entry** large-field GPPs (Stokastic,
4for4, dfsbuild, 2024-2026) `[literature]`:

- Build a **core of 3 stable plays plus 2 leverage/contrarian plays.** Winning
  single-entry lineups average roughly **20-30% ownership per player** across
  the build, blending safety with uniqueness. Pure chalk and pure punt both
  lose.
- **Leverage = ceiling x (1 - ownership).** Fade chalk that fails and you leap
  a huge block of the field instantly; own the low-owned ceiling that hits and
  you separate.
- **Ceiling beats floor** once the field is large: you need the boom outcome,
  so volatility is an asset, not a risk, in the upper slots.

Our screenshot is a clean confirmation: the 4-6% owned ceiling plays
(Allemand, Onyenwere) are exactly the leverage the literature prescribes, and
the 31-35% chalk is exactly what it warns against.

## 4. The fix, phased

### Phase 0 (THIS PR, D86): feed real ownership into the field model

The keystone. Make the EV engine play against the real, observed, concentrated
field instead of a strawman.

- `FieldPlayerSpec.measured_drafts` added `[shipped]`.
- `project_ownership` uses the real draft counts as the ownership marginal when
  present, back-filling unobserved late entrants from the old estimator rescaled
  to the measured median `[shipped]`. Byte-identical to pre-D86 when no counts
  are attached.
- `job2._build_specs` attaches `measured_drafts` (already loaded for the
  contrarian penalty) to each `FieldPlayerSpec` `[shipped]`.
- Gated by `FIELD_MEASURED_OWNERSHIP_ENABLED` (default on); set false to revert
  with no redeploy.
- 4 tests in `tests/unit/test_field_measured_ownership.py` `[shipped]`.

Why this alone moves placement `[reasoned]`: once the field simulation knows
Austin/Johnson are owned by a third of the field and co-occur as chalk, a chalk
own-lineup's score distribution sits inside a dense, duplicated pack where slot
luck breaks ties against us. A differentiated build with comparable projection
gains separation in the right tail, which the convex curve rewards. Leverage
stops being a 0.16 nudge and becomes a property the rank math optimizes for
directly. This is the cheapest, highest-confidence change available and it
requires no model retrain.

### Phase 1: ingest the real payout curve and right-size the objective

- Capture `info.rankDisplayInfos` from the live contest-stats endpoint into
  `data/contest_payouts/` (and/or a `contest_payouts` table) so
  `load_curve_from_archive` fires in production instead of falling back to the
  guessed top_20 curve. `[proposed]`
- If the real curve is steeply top-heavy (expected), the existing `top_1` /
  archive regimes already encode the right convexity; switch `PAYOUT_REGIME`
  once the curve is confirmed. `[proposed]`
- Add an explicit **leverage term** to the optimizer objective:
  `ev += leverage_weight * sum(1 - ownership_i)` over chosen players, tunable
  via env, so leverage is rewarded even on slates where draft counts are thin.
  `[proposed]`

### Phase 2: close the measurement loop (do this in parallel; it gates the rest)

- Extend `oracle-results` / `results_ledger.py` to record realized rank, field
  size, and per-player ownership for every slate, from a screenshot or the
  contest-stats endpoint, into a `placements` table and `RESULTS.md`.
  `[proposed]`
- Backfill the last ~2 weeks from the operator's screenshots.
- This is the instrument. Every Phase 1/3 knob is tuned against realized
  placement, not offline corr. Without it we are guessing.

### Phase 3: field correlation + duplication model

- Replace independent field sampling with a **stack-aware** field: draw a
  game/team anchor per opponent lineup, then fill from conditional ownership, so
  chalk co-occurs the way it really does. `[proposed]`
- Add a **duplication penalty**: estimate how many field entries match our exact
  build and discount EV by expected ties (the operator loses ties on slot
  tiebreak). `[proposed]`

### Phase 4: ceiling-tilted projection for the upper slots

- The minutes x rate head predicts the mean well. For GPP we additionally want a
  calibrated **p85/p90 ceiling** per player (we already emit p90 quantiles,
  D69). Bias slot-1/slot-2 selection toward high ceiling-over-median among
  comparable-EV players, since the top slot multipliers (2.0/1.8) reward the
  boom. `[proposed]`

## 5. Expected impact and how we will know

- Phase 0 should visibly **de-chalk** the frozen lineup: expect 1-2 of the five
  picks to move from >25% to <10% projected ownership on a typical slate, while
  keeping 2-3 high-floor anchors (matching the 20-30% average the literature
  prescribes). Verify by diffing the next few freezes' projected ownership
  against pre-D86. `[reasoned]`
- True validation is Phase 2: a rolling median finish that drifts from ~50th
  percentile toward the 10-20th over a 10-15 slate sample. One slate is noise;
  the instrument exists to tell EV from variance. `[reasoned]`
- Reverse path for Phase 0: `FIELD_MEASURED_OWNERSHIP_ENABLED=false`, no
  redeploy. If a slate has no measured drafts (early pool), the code falls back
  to the prior estimator automatically.

## 6. One-line summary

We were optimizing a real, accurate projection against a fake field and a
guessed payout curve, with no record of where we actually finished. Phase 0
makes the field real. Phases 1-4 make the objective and the feedback loop real.
The projections were never the problem.

---

## Appendix A. Phases 1-4 as shipped (D87-D90)

A 2026-06-13 follow-on session, anchored to a four-agent deep-research synthesis
(Hunter/Vielma/Zaman canonical formulations, Haugh & Singal portfolio
construction, plus current Stokastic / 4for4 / DFS-academy industry consensus),
shipped infrastructure for Phases 1-4 alongside the Phase 0 fix. Every knob is
**default-off / default-byte-identical** so the rollout is reversible via env
var with no redeploy. The synthesis explicitly warned against bolting additive
correctives onto E[payout] without calibration data; the implementation honours
that by leaving the new knobs at 0.0 until the D90 placement feedback loop has
50-200 logged slates to drive parameter selection.

### D87 -- Phase 1, objective shaping (calibration knobs)

`picker/optimize.py` gains three additive terms in the per-combo `_scan` loop,
each gated by a weight defaulting to 0.0:

  - `OPTIMIZER_LEVERAGE_WEIGHT` -- `mean(-log own_i)` over the 5 chosen picks
    (clipped at 1e-4). Log form penalises chalk asymmetrically.
  - `OPTIMIZER_CEILING_WEIGHT` -- `(p90 - p50) / p50` of the candidate's own
    lineup-score samples. Rewards upper-tail upside in top-heavy payouts.
  - `OPTIMIZER_DUPLICATION_WEIGHT` -- penalises `prod(own_i) * field_size`,
    the expected number of mirror entries against our 5-stack.

The synthesis warns these are folk-wisdom knobs unless calibrated against real
results. We expose them as DORMANT calibration levers for the transition window
after placement data exists but before Phases 3+4 are tuned to the live field.
Once the simulator and per-player marginals are recalibrated, the synthesis
says these can stay at 0.0.

### D88 -- Phase 3, stack-aware (correlated) field simulation

`picker/field.py` gains `simulate_field_lineups_correlated`. Sampling algorithm:
sequential weighted draw-without-replacement; after each pick, remaining-pool
weights are multiplied by `same_team_boost` on the pick's teammates and by
`same_game_boost` on the opposing-team players in the same game (boosts
compound across picks). Default boosts of 1.0 cause the function to delegate
back to `simulate_field_lineups` with the same seed -- byte-identical.

Knobs:
  - `FIELD_SAME_GAME_BOOST` (default 1.0; synthesis suggests 1.4 to start).
  - `FIELD_SAME_TEAM_BOOST` (default 1.0; synthesis suggests 1.15 to start).

Plus a duplication-aware payout mode `OPTIMIZER_DUPLICATION_AWARE_PAYOUT`
(default False) that prices duplication directly inside the EV via
`E[payout(rank) / (1 + n_field_clones)]` -- the research-preferred treatment
over the D87 additive `duplication_weight`. The two are alternatives, not
complements; arm one or the other.

### D89 -- Phase 4, per-player ceiling sigma

`picker/sample.py` gains `ceiling_adjusted_sigma_log`, called from `job2._build_specs`.
The 2026 synthesis names sigma -- not mu -- as the operative upper-tail signal
for top-heavy contests. Two additive multiplicative contributions:

  - `OPTIMIZER_CEILING_SIGMA_BLOWOUT_BOOST` -- widens sigma when `blowout_prob`
    is high (role volatility in projected blowouts).
  - `OPTIMIZER_CEILING_SIGMA_LOW_HISTORY_BOOST` -- widens sigma for players with
    limited recent samples (sample-size shrinkage). The 25-game high-history
    target matches the existing minutes-model n_min_games convention.

Both default to 0.0 -- byte-identical to D78. Synthesis suggested starting
values: blowout 0.15, low_history 0.20. The result is clamped at sigma_log_cap
0.9 so stacked extremes can't blow up the percentile bias.

The synthesis's full prescription is gamma marginals with method-of-moments
fits + hierarchical archetype shrinkage. The codebase currently samples on
log(real_score + K) (lognormal-shaped, right-skewed), so the operative WIDENING
lever is sigma. The distribution-family swap is left for a future phase; the
sigma scaling captures the dominant upper-tail effect now.

### D90 -- Phase 2, placement feedback loop (the keystone)

`migrations/versions/20260613_0007_contest_placements.py` adds:
  - `contest_placements` -- one row per (slate_date, contest_id, recorded_at).
    Captures realized outcome (rank, count, score, payout, ROI) plus the
    forecast snapshot at freeze (expected_payout, lineup-score percentiles,
    payout curve, serving knobs, projected ownership) plus actual ownership.
    Append-only via the (slate_date, contest_id, recorded_at) PK.
  - `player_slate_ownership` -- per (slate_date, player_id) projected vs actual
    ownership for the calibration loop.

`scheduler/placements.py` exposes:
  - `record_placement` -- writes a placement row, joining the freeze snapshot.
  - `summarize_placements` -- rolling KPIs (median finish percentile, cash /
    top-10 / top-1 rates). ROI hidden until 500 slates per the synthesis
    threshold. Tuning warning emitted below 100 slates.
  - `compute_pit_value` + `pit_histogram` + `chi2_uniformity_pvalue` --
    Probability-Integral-Transform diagnostics on the predicted finish CDF.
    U-shape signals simulator under-dispersion; dome shape over-dispersion.
  - `ownership_log_loss_by_decile` -- per-bucket binary cross-entropy on
    projected vs actual ownership, localizing miscalibration regimes.

CLI:
    oracle-placements record --slate-date 2026-06-12 --contest-id ... \\
        --rank 4253 --count 8300 --score 32.4 --payout-cents 0 --entry-fee-cents 100
    oracle-placements summary --window 50 --format markdown

Synthesis anti-patterns enforced:
  - ROI gated at SHOW_ROI_AFTER_SLATES=500.
  - Tuning warning under TUNE_WEIGHTS_AFTER_SLATES=100.
  - PIT / chi2 underpowered below 30 PIT values -> chi2 returns None.
  - Append-only PK; re-records keep history.

### What we did NOT ship (and why)

  - Gamma per-player marginals + archetype shrinkage (Phase 4 full): big surgery
    on the sampling distribution; the lognormal-on-(real_score+K) path is
    already right-skewed and sigma scaling captures the dominant upper-tail
    effect. Distribution-family swap is left for after Phase 2 produces
    calibration evidence.
  - Automatic placement ingest from job_dayclose: the CLI works standalone now;
    auto-ingest is a small follow-on once we confirm the manual path is enough
    to populate the metrics surface.
  - The 50-slate-shadow-mode promotion gate from the synthesis (60% trailing
    win-rate vs incumbent): there is no incumbent shadow runner; we'll
    layer this on once the placement loop has data.

### Rollout plan

1. Ship D86-D90 schema + code. Defaults are no-ops. Cron-job2 behaviour
   identical to D86.
2. Operator manually records past placements via `oracle-placements record`
   so the analytics surface has seed data.
3. Watch median finish percentile + PIT histogram for 10-15 slates. If the
   simulator is severely under-dispersed (PIT histogram is U-shaped) the
   first knob to arm is `FIELD_SAME_GAME_BOOST=1.4` (more correlated field
   -> wider rank distribution).
4. After 50+ placements with the D86 fix active, calibrate the leverage /
   ceiling / duplication weights one at a time. Each move is reversible via
   env var.
5. After 100+ placements, evaluate whether the gamma distribution-family swap
   is worth the surgery cost. If sigma scaling alone closed the upper-tail
   gap (per PIT calibration), it isn't.
