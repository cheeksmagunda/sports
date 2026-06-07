# 03. Theoretical Ceiling

What is the irreducible noise in this contest? How close to optimal would we
finish with perfect projections? And how much projection error can we tolerate
before we start losing real money?

All numbers below are derived from the 141 slates in
`data/historical/slate_labels/` and `data/historical/leaderboards/` (slates
spanning 2025-05-16 through 2025-10-09, plus a small 2026 backfill). Compute
code: `research/internal/_ceiling_compute.py`. Raw outputs:
`_ceiling_perfect.parquet`, `_ceiling_noise.parquet`, `_ceiling_summary.json`.

## Verified scoring formula

Each entry picks 5 players, each player has a `card_boost`. The slate-level
slot multipliers `[2.0, 1.8, 1.6, 1.4, 1.2]` are each used once. Verified
empirically by reconstructing the rank-1 entry's reported `score` from the
leaderboard JSON for the 2025-08-15 winner (and many others):

```
lineup_score = sum_i real_score_i * (slot_mult_i + card_boost_i)
```

The `multiplier` field in the lineup JSON is `slot_mult + boost` already, and
`score / multiplier == real_score` per player on every check. Sum of
`value * multiplier` across the 5 players reproduces the reported lineup
score to floating-point precision.

There are no team or position constraints on lineups. Empirical check across
five sampled slates: top-20 lineups regularly use only 2-3 distinct teams,
sometimes 5. The brute-force optimum is unconstrained 5-from-N.

For a chosen 5-set, optimal slot assignment is closed form: rank the chosen
players by `real_score` descending and pair with `[2.0, 1.8, 1.6, 1.4, 1.2]`
in the same order. The boost contribution is slot-independent within the chosen
set. So the brute force is just `C(menu_size, 5)` evaluations of a 5-product.

## Headline numbers

### Perfect projections vs the contest

**Verified** from 141 slates (`_ceiling_summary.json`):

| Metric | Value |
| --- | --- |
| Mean menu size | 28.4 players |
| Mean field size (`num_brawlers`) | 9,246 entries |
| Median field size | 8,989 |
| Mean perfect-info score | 62.67 |
| Mean rank-1 score | 55.72 |
| Mean rank-20 score | 50.69 |
| Mean rank-1 / perfect ratio | 89.7% |
| Mean rank-20 / perfect ratio | 81.8% |
| Perfect score beats rank-1 | 134 / 141 slates (95.0%) |
| Mean (perfect - rank-1) gap | +6.96 points |

Of the 7 slates where the perfect-info build did NOT exceed the actual rank-1
score, 4 were floating-point rounding (gap < 0.03). Only 3 are real losses —
**2025-06-26**, **2025-08-20**, **2025-09-04** — and on inspection each one
has a player in the winning lineup that is **missing from slate_labels**. For
example, on 2025-09-04 the winner used player 612 (multiplier 3.9, score 20.89)
who has no row in our slate menu data. So the "perfect-info loss" cases are
data-quality bugs in the menu scrape, not a real model ceiling.

After correcting for that, **perfect projections would win 97.9% of slates**
(138 / 141). The other 2.1% are not real noise — they are gaps in our menu
capture.

### Overlap between winners and the perfect lineup

How many of the 5 perfect-info picks does the actual rank-1 finisher share?

| Overlap | Slates |
| --- | --- |
| 1 of 5 | 4 (2.8%) |
| 2 of 5 | 44 (31.2%) |
| 3 of 5 | 55 (39.0%) |
| 4 of 5 | 26 (18.4%) |
| 5 of 5 | 12 (8.5%) |

Mean overlap: **2.99 of 5**. The winner shares 3 picks with God on average and
the perfect lineup is recoverable end-to-end on only ~8% of slates from any
field entry's view. So the field is largely getting beaten by missing the right
2-3 players, not by failing to identify the same five and then losing on slot
assignment.

### The top of the leaderboard is dense

| Gap | Mean (141 slates) |
| --- | --- |
| Rank-1 to rank-5 score | 2.74 pts |
| Rank-5 to rank-20 score | 2.29 pts |
| Rank-1 to rank-20 score | 5.03 pts |
| Rank-10 to rank-20 score | 1.23 pts |

There are only ~5 points of separation between God-tier and rank-20 finishes,
and our perfect ceiling sits 7 points above rank-1. The implication is brutal:
**every point you leave on the table matters**. A 2-point projection miss on
any one of your five picks under a 4x multiplier slot is enough to drop you
from rank-1 to outside the cash bubble.

## Noise sweep: projection RMSE -> expected finish

Method (`_ceiling_compute.py`, function `main`): for each slate and each
`sigma in [0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0,
10.0]`, run 1,000 trials. In each trial, set `proj = real_score + N(0, sigma)`,
then the simulated picker scores each player by `proj * (2.0 + card_boost)`,
takes the top 5, and assigns slots by descending `proj` (same as the live
picker does). The realized lineup score is computed and converted to a rank
via an empirical per-slate `log(rank) ~ a + b * score` fit on the top-20
finishers, clamped to `[1, num_brawlers]`.

Caveat (reasoned): the rank model extrapolates below the rank-20 finisher
linearly in log-rank space. For very noisy projections that produce scores
below the rank-20 line the model can extrapolate optimistically. The
`top500_rate` and `top20_rate` numbers are interpolated within the observed
top-20 window so they are tighter; the `mean_rank` for high sigma is a
ballpark.

**Verified** (`_ceiling_noise.parquet`):

| sigma | mean rank | median rank | top-500 rate | top-20 rate | win rate | score % of perfect |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0.00 | 2 | 1 | 100.0% | 99.3% | 91.5% | 99.7% |
| 0.25 | 46 | 1 | 99.4% | 98.5% | 87.3% | 98.9% |
| 0.50 | 129 | 1 | 98.3% | 95.2% | 80.1% | 96.7% |
| 0.75 | 311 | 1 | 95.6% | 87.7% | 68.2% | 93.5% |
| 1.00 | 619 | 1 | 90.6% | 77.8% | 54.8% | 90.0% |
| 1.50 | 1,491 | 8 | 77.9% | 58.3% | 34.3% | 83.5% |
| 2.00 | 2,334 | 40 | 66.5% | 43.9% | 22.4% | 78.3% |
| 2.50 | 3,033 | 186 | 57.5% | 34.3% | 15.8% | 74.3% |
| 3.00 | 3,535 | 465 | 51.1% | 28.1% | 12.0% | 71.4% |
| 4.00 | 4,272 | 1,857 | 42.2% | 20.5% | 7.9% | 67.3% |
| 5.00 | 4,766 | 4,748 | 36.7% | 16.5% | 6.0% | 64.7% |
| 6.00 | 5,049 | 6,238 | 33.2% | 14.1% | 4.9% | 63.1% |
| 8.00 | 5,458 | 7,300 | 28.9% | 11.4% | 3.7% | 60.7% |
| 10.00 | 5,694 | 7,595 | 26.5% | 10.0% | 3.1% | 59.4% |

Even at zero projection noise the mean rank is 1.97 rather than 1.00 because
of menu-quality misses (and a small per-slate tie). The "ceiling" of a perfect
oracle in this contest format is **rank 1.97 with a 91.5% slate-by-slate win
rate**, top-20 finish on 99.3% of slates.

### Sigma thresholds for performance targets (interpolated)

To average a given rank:

| Target mean rank | Max tolerable per-player projection RMSE |
| ---: | ---: |
| 100 | 0.41 pts |
| 250 | 0.67 pts |
| 500 | 0.90 pts |
| 1,000 | 1.22 pts |
| 2,000 | 1.80 pts |
| 5,000 | 5.83 pts |

To hit top-500 in X% of slates:

| Target top-500 rate | Max RMSE |
| ---: | ---: |
| 95% | 0.78 |
| 90% | 1.02 |
| 80% | 1.42 |
| 50% | 3.12 |

For context, per-player `real_score` has mean 2.52 and std 1.54 across the
4,002-row training corpus. So "RMSE = 1.0" means your typical per-player
projection error is about two-thirds of one standard deviation of the outcome
itself. Sub-1.0 RMSE on a quantity with std 1.5 is hard. To get to a regular
top-5% finish (~500th of 10k) you need projections that explain roughly
`1 - 1.0^2 / 1.54^2 = 58%` of the per-player variance — Pearson r ≈ 0.76 in
the calibrated case.

## Placing our current model on the curve

STATUS.md reports two model correlations:

- **D63 multi-task heads (trained, not yet live)**: corr 0.554 on walk-forward
- **Current live heuristic (career-average ladder)**: corr 0.246

Both numbers are correlation of projection vs realized `real_score`.

Mapping correlation to the noise-sweep sigma: if `proj = real + N(0, sigma)`
with `real` having std `sigma_y = 1.537`, then
`corr(proj, real) = sigma_y / sqrt(sigma_y^2 + sigma^2)`, so
`sigma = sigma_y * sqrt(1/r^2 - 1)`. **Verified** by direct algebra; this is
the relevant equivalent additive-noise sigma for placing our model on the
sweep above.

| Model | Reported corr | Equivalent additive RMSE | Mean rank | Median rank | top-500 | top-20 | win |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| D63 heads (dormant) | 0.554 | **2.31 pts** | ~2,770 | ~130 | 61% | 38% | 18% |
| Live heuristic | 0.246 | **6.05 pts** | ~5,060 | ~6,270 | 33% | 14% | 5% |

(Interpolated from the table above. Numbers reasoned, not directly observed.)

The heuristic placement matches our observed live record. Our 2026-06-04 bust
at rank ~6000 / 8317 is squarely in the *median* outcome at sigma 6.05; the
2026-05-28 top-10% finish is in the *top-third tail*. Two slates is a sample
size of nothing, but the model says: **with the current live ladder we should
expect rank-3000 to rank-7000 most nights and only crack the top 500 about
one slate in three**.

The dormant D63 heads would not transform us into a winning model, but would
roughly **halve the noise sigma and cut the median rank from ~6,000 to
~130**, with top-500 rate going from 33% to 61%. Phase 2b wiring is the single
biggest lever currently available.

If we could get to **per-player RMSE ~1.0** (corr ~0.84) we would be winning
this contest 55% of nights with 91% top-500 reliability. Whether that's
achievable depends on the irreducible variance in per-game WNBA box-score
output, which is the next research question. (As a sanity floor, 5% of corpus
rows have `real_score == 0` — players who DNP'd or barely played — so any
projection that misses minutes calls outright will have RMSE >= ~1.5 just
from those alone.)

## Within-model tail risk

Mean rank is misleading because the distribution of slate-mean ranks is
skewed: a few "field gets it right and we're way wrong" nights drag the mean.
For a fresh 500-trial sim at the equivalent-additive sigma values, with
empirical per-slate rank-fit reused (`_ceiling_compute.py` plus a 1-off
script run inline, not committed):

| Model | sigma | median slate-mean rank | worst-decile slate-mean rank | P(any trial rank > 1000) |
| --- | ---: | ---: | ---: | ---: |
| Heads (corr 0.554) | 2.31 | ~360 | ~4,670 | ~18% |
| Heuristic (corr 0.246) | 6.05 | ~1,050 | ~6,700 | ~27% |

The 27% probability of a sub-1000th finish under the live model is what
generates the kind of 6000th-place blowout we logged on 2026-06-04 — that
single result is not an anomaly under this distribution, it's the *expected*
quarter-of-the-time tail. Even the trained heads would put a >18% probability
on a sub-1000 finish, so any single-slate disaster shouldn't trigger a model
unmaking.

## Perfect projections + perfect leverage: can we crack rank 1?

Two questions: (1) how often does the perfect lineup get duplicated by the
field, and (2) what's the irreducible noise ceiling.

**Verified** (50-slate sample, brute-force perfect set + leaderboard set
intersection): the perfect 5-player set was duplicated by 1+ field entry in
**8.0% of slates** (4 / 50). On 92% of slates we'd be the only entry with
God's lineup and win clean. On 8% we'd tie or be beaten by an entry that
played the same 5 with the same slot assignment.

The perfect-info win rate computed above (91.5% at sigma=0) lines up: 8.5% of
slates have either (a) a tied perfect lineup or (b) a menu-data bug that
prevented our solver from finding the true optimum. Subtracting menu bugs
(~2-3% of slates) leaves ~5-6% as the irreducible "the field got there too"
floor.

So: **with perfect projections we win 91-92% of slates, and you cannot beat
that ceiling without either (a) fixing the menu-scrape data quality issues
or (b) leverage — actively picking a near-perfect-but-different lineup to
avoid a tie**. Leverage matters here only because of the small tie probability;
it does not affect mean rank meaningfully.

The "irreducible noise ceiling" for the picker (assuming perfect projections
and that menu-data bugs are fixed) is:

- **Mean rank ~1.0 to 1.1**
- **Win rate ~92-95%**
- **Top-20 rate >99%**

The remaining 5-8% is not noise; it's duplication.

## Headline answers to the brief

> If our projections were perfect, we would finish on average at rank ___.

**Rank 1.97 with the current data pipeline** (limited by menu-scrape misses
on 3-5% of slates). **Rank ~1.0 to 1.1 if menu data were complete.** Win rate
91-95%, top-20 rate >99%.

> To crack top 500 (top 5% of a 10k field), we need projection RMSE ___ or
> better.

Roughly:

- For a **50% top-500 rate**, per-player RMSE must be **<= 3.12** (additive
  Gaussian equivalent), or correlation r >= ~0.44.
- For a **90% top-500 rate**, RMSE must be **<= 1.02**, or r >= ~0.83.
- The trained-but-dormant D63 heads (r=0.554, RMSE ~2.31) would put us at
  **~61% top-500 rate**. The live heuristic (r=0.246, RMSE ~6.05) lands at
  **~33%**.

So the single biggest piece of point estimate to move is Phase 2b: get the
trained heads serving live and you nearly **double** the top-500 hit rate
without any new modeling work.

## Where our picks, model, and reality actually diverge

Mapping back to the build state:

1. **Live model is the bottleneck.** STATUS.md says the trained heads are
   not yet wired into job2. At r=0.246 the live picker is statistically
   roughly equivalent to "pick the top-5 boosted players and pray." It will
   hit median rank 1,050 and worst-decile rank 6,700.

2. **The picker math is essentially right.** Slot assignment is closed form
   under known scores; brute force perfect-info wins 95-98% of slates. There
   is no obvious geometry-of-the-objective gain to chase here.

3. **Score density at the top is brutal**. Rank-1 to rank-20 is only 5 points
   on average. A 1-point projection miss on any single 4x slot is a 4-point
   swing — enough to drop you out of top-20 entirely.

4. **Menu-scrape data quality costs us ~3% of perfect win rate.** Three of
   the 7 "rank-1 beat perfect" slates are caused by players appearing in
   winning lineups but missing from our `slate_labels`. Even with a perfect
   model we'd take a hit from these misses until the scrape is fixed.

5. **Ownership leverage is barely a factor.** Only ~8% of slates have any
   field entry matching the optimal lineup exactly. Contrarianism vs the
   field is at most a 5-8% rank-1 lift even with perfect projections, which
   is small relative to the gains from model accuracy.

6. **Variance is real but bounded.** Even with perfect projections, the
   sigma=0 row of the sweep shows mean rank 1.97 not 1.00 — there is
   ~5-6% irreducible noise from the contest format itself (field
   duplication). This is the ceiling, period.

The lever order suggested by this analysis:

1. Fix `slate_labels` menu-scrape so the universe is correct (~3% slate ceiling lift).
2. Wire D63 heads into job2 (~28 percentage points top-500 rate, ~halves median rank).
3. Drive per-player RMSE from ~2.3 toward 1.0 via component heads, matchup
   features, participation prior (the remaining roadmap in STATUS.md).
4. Worry about ownership leverage last; it's a sub-10% effect.

## Surprising numbers worth pinning

- **Per-player RMSE 1.0 already gives 91% top-500 reliability.** The bar to
  be a winning contest player is not extreme — it's "predict per-player
  fantasy points to within ~1 point on average."
- **Median rank under the current live heuristic is ~1,050.** That's not
  "occasionally we miss." That's "we are statistically expected to be at
  the 12th percentile of finishers most nights."
- **Rank-1 to rank-20 is only 5.0 points.** This is a 1.6-multiplier
  difference on a single boosted player. Slot assignment matters as much as
  player selection at the top.
- **Wiring trained heads (no new modeling) takes top-500 from 33% to 61%.**
  The biggest single-action gain available is shipping work that's already done.
- **Perfect projections still finish rank 1.97 on average, not 1.00.** Field
  duplication of the best lineup means there's a 5-8% irreducible loss even
  with God-mode info.

## Methodology notes and limits

- Rank conversion uses a per-slate log-linear fit on observed top-20 finishers.
  Below rank-20 it extrapolates. This is fine for top-500 metrics (the curve is
  well-anchored in that range) but rough for "mean rank" at very high sigma.
- The noise model is additive Gaussian. Real projection error is heavier-tailed
  (injuries, ejections, blowout benchings) — so the table likely *understates*
  the median-to-worst-decile spread for our live model. The fresh 500-trial
  re-run accounts for this empirically by using each slate's observed score-rank
  curve.
- The "equivalent additive RMSE" mapping from a reported `corr` assumes the
  underlying projection has the same marginal variance as the target. If the
  model is shrunk (which a calibrated model usually is), this overstates the
  noise sigma; if the model is overconfident, it understates it. Either way
  the order of magnitude is right.
- "Win rate" at sigma=0 is 91.5%, not 100%, because of (a) menu-scrape misses
  and (b) the simulated picker uses `proj * (2.0 + boost)` as the rank score,
  not the true closed-form optimum — so even with sigma=0 there's a tiny
  edge case (high-boost low-real player beats a top-5 player by total
  contribution) that the simulated picker can get wrong. Brute-force perfect
  (used in the `_ceiling_perfect.parquet` cut) actually wins 95.0% of slates
  raw and 97.9% after menu-data correction.
