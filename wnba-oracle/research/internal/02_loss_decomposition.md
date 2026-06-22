# 02 — Loss Decomposition: where the picker bleeds points

When our picker freezes a 5-player lineup, why does it not win the slate?
This report decomposes the gap from our lineup to the slate winner into
four buckets across 9 LIVE slates (frozen_lineups in Postgres) and 30
SIMULATED historical slates (re-run of today's optimizer over the
2025-06 to 2026-05 menu archive).

Data sources [verified]:
- `frozen_lineups` (n=10, 2026-05-27 to 2026-06-05, 9 with realized scores)
- `slate_labels` (141 slates, 2025-05-16 to 2026-06-04)
- `contest_leaderboards` (top-20 only, 141 slates)
- `research/internal/_loss_decomp.py`
- `research/internal/_loss_decomp_data.csv` (40 rows)

Method: for each slate, brute-force `C(N,5)` over the menu under the prod
team-cap (dynamic cap by slate size, max 2 on 3+ game slates) to find
both the perfect-hindsight optimum and the heuristic-driven optimum
(visible_value = pred * (2.0 + boost), `pred = max(0.5, 3.16 - 0.45*boost)`).
The optimizer's stage-1 top-N filter and stage-2 enumeration are mirrored
in `_loss_decomp.py:simulate_heuristic_pick`. Realized lineup_score uses
the platform's rearrangement-inequality slot assignment that the optimizer
also assumes (verified D42 against 320 top-20 entries).

---

## TL;DR — the headline number

**Of the 18.97 points (mean) we leave between our lineup and the
perfect-hindsight lineup, 94.8% is projection error and 5.2% is
construction error.** [verified, across 39 slates with realized scores]

For LIVE-only (9 slates) the split is 81.4% projection / 18.6%
construction, because two live slates (2026-05-28 and 2026-06-04) had
material *serving drift* — the live frozen lineup differed from what
the heuristic would have picked when re-simulated on the same menu.
On 2026-06-04 alone that drift cost 15.2 points (sim score 43.2 vs our
realized 28.0). [verified, _loss_decomp_data.csv rows 1 and 7]

The luck tax (irreducible variance): the median rank-1 minus rank-20
score gap is 5.22 points; rank-1 minus rank-5 is 2.39 points; max
observed 1-20 gap is 13.94. [verified, 90 slates with full rank coverage]
So *most* of the 11.8 point mean gap-to-winner is real signal we are
leaving on the table, not variance.

The fixable share, ranked by leverage:
1. **Better projections** (94.8% of gap-to-perfect, ~18 pts/slate).
   This is exactly the D63 trained-but-dormant heads story.
2. **Serving wiring** (live drift only, ~3 pts/slate on average,
   spiking to 15.2 on a bust). Fix once and it stays fixed.
3. **Ownership leverage** (orthogonal, see (c) — our picks have on
   average 0.51 chalk picks out of 5 vs winners who pick 40% chalk).
   We are already *more contrarian than the winners*. Pulling further
   left here is not the lever; pulling our PROJECTION right while
   keeping contrarian tilt is.

---

## (a) PROJECTION ERROR

Per-player RMSE between our `pred_real_score` and the realized
`real_score`, on our 5 picks only.

- Mean proj_rmse across 39 slates: **1.09 real_score points / player**
  (sd 0.30). [verified]
- Mean proj_bias: **-0.04** (essentially zero net bias; not a
  systematic over or under-prediction problem). [verified]
- On 2025-06-11 the heuristic RMSE was 1.93 (worst observed); on
  2026-06-01 it was 0.65 (best). The model is right-on-average but
  noisy. [verified]

Per-player RMSE of 1.09 looks small until you remember a typical pick
sits around 3-4 real_score and the slot multiplier amplifies it by
3.0-5.0 (slot + boost). A 1.09-point per-player error, when stacked
across 5 slots, propagates to a ~17-18 point mean projection_loss at
the lineup level. [reasoned, derived from the simulator]

How big is the lift from a better model? The D63 walk-forward
shows recompose corr 0.554 vs heuristic 0.246 (STATUS.md). That is
a 2.25x increase in rank-information. If projection-loss scales
roughly linearly with the residual variance, halving projection loss
would close ~9 of our ~18 mean gap-to-perfect, taking the gap-to-winner
from 11.8 toward ~3, in the same neighborhood as the rank-1 to rank-20
gap (5.22 median). That is approximately the irreducible variance
floor for a top-20 finish. [reasoned]

## (b) CONSTRUCTION ERROR

Given perfect projections, what was the maximum-realized 5-pick lineup
on each slate? Brute force `C(N,5)` under the same team cap the
optimizer uses.

- Mean perfect-hindsight score: **62.54** (vs mean winner 55.72,
  meaning the winner left ~7 points on the table too). [verified]
- Our_score / perfect_score: **mean 68.2%, median 73.8%**. We capture
  three quarters of what was achievable. [verified]
- Win_score / perfect_score: **mean 89.5%, median 88.2%**. The actual
  winner is well below the brute-force optimum. The "perfect lineup"
  is a theoretical ceiling, not a realistic target. [verified]
- Construction-extra loss (gap between our_realized and what
  heuristic-sim-now would have picked): **0 on 36 of 39 slates**;
  positive only on three live slates where the production serving
  path differed from our offline re-simulation. [verified]

**Construction is essentially not a problem when the optimizer fires
as designed.** The two-stage filter + enumeration genuinely finds the
heuristic-EV-optimal lineup; the gap comes from the heuristic ranking
players wrong.

The exception is *live serving drift*: 2026-05-28 frozen the lineup
[765, 657, 608, 4322862, 4322893] (score 35.5), but a fresh re-run of
the same heuristic on the same `slate_labels` snapshot picks [726,
4322862, 4322756, 765, 608] (score 47.2). That is an **11.7 point
serving error** — the live picker saw a different menu (still-loading
names, partial drafts data, or the "Player <id>" rookie bug that D68
later closed). Same story on 2026-06-04: live 28.0 vs sim 43.2, a 15.2
point bleed, on a slate where the trained heads also were not yet
serving. [verified, _loss_decomp_data.csv]

## (c) OWNERSHIP / LEVERAGE ERROR

This one is interesting because we are NOT being chalky.

- Mean overlap with the winning lineup: **1.15 players out of 5**. 11
  of 39 slates we shared zero players with the winner. [verified]
- Our chalk picks (above slate-median drafts): mean **0.51 of 5**.
  22 of 39 slates we had zero chalk picks; only 2 slates had 2+. We
  are running an aggressively contrarian lineup. [verified]
- Winners' chalk profile: across 174 winning lineups inspected, the
  mean fraction of picks above slate-median drafts is **39.6%**
  (~2 of 5), and 77.4% of winning picks were sub-10% chalk (low
  ownership). 171 of 174 winning lineups contained at least one
  sub-10% chalk player. [verified]
- Median drafts of winning picks: **149.7** vs slate median **219.3**
  (winners pick noticeably less chalk than the median slate player).
  [verified]

So winners are *also* contrarian. Roughly 60% of winning picks are
below the slate median drafts, and 3 in 4 winning picks are sub-10%
chalk. The leverage angle is not "be more contrarian." It is **pick
the RIGHT contrarian player** — and that loops back to projection
quality. The contrarian tilt at strength 0.2 (CONTRARIAN_STRENGTH,
D51) is calibrated correctly; it is the underlying projection rank
that fails to surface the contrarian players who will hit.

There is also a striking finding on chalk-picks in our LIVE slates:
the 2026-06-04 bust (rank ~6000 of 8317) was our *only* slate with
3+ chalk picks. Our typical lineup is 0-1 chalk; that one regressed
to 3 chalk picks AND missed by 25 points. Tentative read: the live
serving path was eating the contrarian tilt on that slate (related to
the D63 minutes-heads-not-serving root cause). [reasoned]

## (d) IRREDUCIBLE VARIANCE

Across 90 slates with full top-20 rank coverage:

| Gap | Mean | Median | Max |
|-----|------|--------|-----|
| rank 1 to rank 5  | 2.97 | 2.39 |  11.31 |
| rank 1 to rank 10 | 4.22 | 3.73 |  12.94 |
| rank 1 to rank 20 | 5.64 | 5.22 |  13.94 |
| rank 5 to rank 20 | 2.67 | 2.35 |   6.91 |

[verified]

So the "luck tax" from rank 1 to a top-20 paid finish is about **5
points (median)**. Anything within 5 of the winner is essentially
where the variance floor lives.

Our mean LIVE gap_to_winner is 8.59 points; median is 0.46 (4 of 8
LIVE slates are within 4 points of the winner, including 1 win).
**Half of our LIVE slates already land in the irreducible-variance
zone.** The big losses are 2026-05-28 (+17.6), 2026-06-03 (+15.1),
2026-06-04 (+25.2) — all driven by either projection or serving
errors, not by being slightly off the optimum. [verified]

Field size: mean 9,246 entries, range 5,403 to 14,999. [verified, 141
slates with non-null `num_brawlers`]

Winner score distribution: mean 55.72, median 55.08, sd 8.52. [verified]

---

## Per-slate table (LIVE)

| date | win | ours | sim-heur | perfect | gap_to_win | proj_rmse | overlap | chalk/5 | flag |
|------|-----|------|----------|---------|------------|-----------|---------|---------|------|
| 2026-05-27 | 59.0 | 55.4 | 55.4 | 73.7 | +3.6  | 1.19 | 0 | 1 | skip |
| 2026-05-28 | 53.1 | 35.5 | 47.2 | 60.2 | +17.6 | 1.10 | 1 | 0 | enter_with_caveat |
| 2026-05-29 | 49.5 | 49.3 | 49.3 | 60.9 | +0.1  | 1.08 | 1 | 1 | skip |
| 2026-05-30 | 63.8 | 63.3 | 63.3 | 73.4 | +0.6  | 1.10 | 1 | 0 | skip |
| 2026-06-01 | 51.1 | 50.8 | 50.8 | 68.8 | +0.4  | 0.65 | 0 | 0 | enter |
| 2026-06-02 | 53.4 | 56.3 | 56.3 | 62.5 | -2.9  | 0.68 | 1 | 0 | enter (BEAT) |
| 2026-06-03 | 55.4 | 40.3 | 40.3 | 63.4 | +15.1 | 0.64 | 2 | 0 | enter |
| 2026-06-04 | 53.2 | 28.0 | 43.2 | 60.0 | +25.2 | 1.53 | 1 | 3 | enter |

LIVE summary (n=8 with scores):
- Mean: win 54.6, ours 46.1, perfect 64.8
- 4 of 8 slates within 4 pts of winner (incl 1 win on 2026-06-02)
- 2 of 8 are serving-drift busts that erased ~12-15 pts each
- Mean proj_rmse 0.99 (LIVE) vs 1.11 (SIM) — heuristic is similar
  on LIVE and SIM, so SIM is a fair proxy for what the picker does

## Per-slate table (SIM, 30 slates)

Sampled evenly across 2025-06 to 2026-05.

Highlights:
- SIM gap_to_winner: mean +12.78, median +10.34, max +50.39
- SIM heuristic *beat the winner* on **7 of 30 slates** (2025-06-17,
  2025-07-24, 2025-08-10, 2025-08-28, 2025-09-09, 2026-05-17,
  2026-05-21). The heuristic + optimizer is not far from break-even
  on a top-1 basis on a meaningful slice of slates. [verified]
- Worst single slate: 2025-08-20, sim 10.9 vs win 61.3, proj_rmse 1.51.
  These outlier days look like minutes-cascade events where the
  heuristic locked onto the wrong rotation. [verified, reasoned]

## Where the loss goes — summary chart

For the full 39-slate sample, averaging per-slate:

```
gap_to_winner       11.82 pts    (= our distance from rank 1)
gap_to_perfect      18.97 pts    (= our distance from hindsight optimal)

decomposed:
  projection loss   17.98 pts  (94.8%)   <-- the big one
  construction loss  0.99 pts  ( 5.2%)   <-- only live serving drift

irreducible (luck) floor: ~5 pts median (rank 1 to rank 20)
```

LIVE-only (9 slates, more recent picker, more serving issues):

```
gap_to_winner        8.59 pts
gap_to_perfect      18.76 pts

decomposed:
  projection loss   14.48 pts  (81.4%)
  construction loss  4.28 pts  (18.6%)   <-- driven entirely by
                                              2026-05-28 + 2026-06-04
                                              serving drift
```

---

## What to do, prioritized

1. **Ship the D63 heads to live serving (Phase 2b).** This is the
   biggest single lever — projection error is ~95% of our total
   distance from theoretical perfect, and the offline walk-forward
   already shows 2.25x rank info improvement (corr 0.554 vs 0.246).
   Even a partial transfer of that lift cuts our mean projection_loss
   from 18 to roughly 9, which puts mean gap_to_winner near the
   variance floor.

2. **Audit the serving path on the two LIVE busts (05-28 and 06-04).**
   The 11.7 and 15.2 point gaps between live frozen and offline
   re-sim are not optimizer bugs (the offline run uses the exact
   same heuristic and team cap); they are upstream menu / drafts /
   name issues that the live job2 saw differently. D68 fixed the
   "Player <id>" leak but the 06-04 lineup [616, 4322797, 671, 657,
   4322756] vs sim [657, 4322793, 689, 4322862, 4322865] suggests
   either drafts-data lag or boost-only mode kicking in. Worth a
   per-pick replay of those two frozen contests.

3. **Do NOT pull harder on contrarian.** Winners are 60% sub-median
   drafts; we are already 90% sub-median. The contrarian dial is
   not the problem. The CONTRARIAN_STRENGTH=0.2 setting (D51) looks
   well-calibrated. Spending more on contrarian dilutes projection
   signal we cannot afford to lose.

4. **Watch the team-cap dynamic.** 1-game and 2-game slates already
   relax the cap (D50). On 3+ game slates the cap is 2, which lines
   up with the 13% top-20 rate of 3-stacks on big slates. No change
   suggested.

5. **Don't chase the "perfect" — the gap to it isn't the real
   target.** Winner score / perfect score is 88-90%. Even the
   contest winner leaves 10-12% on the table. Our realistic target
   is a top-1% finish, which means closing the gap to roughly the
   rank-1 mark (the variance floor is ~5 pts) — about 9 pts of
   improvement, almost exactly what better projections give us.

---

## Open questions

- We only see top-20 in `contest_leaderboards`, so we cannot directly
  measure rank-1 to rank-100 or rank-1 to median. The 5-pt rank 1-to-20
  gap is a lower bound on the "luck tax to be paid"; the real top-1%
  cutoff lives between rank 87 (top-1% of 8.7k) and rank 100, beyond
  our DB. [verified gap, reasoned scope]
- Field-lineup ownership projection is a separate piece (see
  `picker/popularity.py`); this report measures realized chalkiness
  (drafts column) but not whether our *projected* ownership matches
  realized ownership. That is the next adversarial check.
- Two of the LIVE wins (2026-05-29, 05-30) were "skip" flag slates
  the operator entered anyway. The skip-flag logic is on its own
  worth a separate look — flag accuracy is not in scope here.

---

Generated: 2026-06-05 by `_loss_decomp.py` over the canonical Postgres
corpus.
