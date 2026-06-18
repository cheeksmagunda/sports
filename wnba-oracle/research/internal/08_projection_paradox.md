# 08 - The projection paradox is mostly a censored-benchmark artifact

Date: 2026-06-14. Author: build automation (deep-dive session).

Tags: `[verified]` = read from code or DB. `[reasoned]` = synthesized argument.
`[literature]` = external source.

## 0. The question

Two facts have sat in tension across the decision log:

1. The trained heads reach **walk-forward rank correlation 0.554** vs the boost
   heuristic's 0.246 (D63), supposedly more than double the signal.
2. The D91 calibration sweep concluded the optimizer's chosen lineup is "below
   the captured top-20 median on 88% of slates," that "all 16 historical entries
   ranked 21/20," and called this "a player-selection quality issue, not a
   formula bug."

If (1) is real, why does (2) look so bad? The pessimistic reading is that our
projections are secretly 6% worse than the field. This note shows that reading
rests on a censored benchmark and overstates the deficit. It does not prove the
projections are good. It proves we have not actually measured placement.

## 1. Cohort routing is NOT the bug (ruled out) `[verified]`

The first suspect was a serving/training mismatch: `predict_real_score`
(`train/pipeline.py:114-121`) routes each player to a G/F/C cohort via
`cohort_for_position`, while the live serving path hardcodes `position: "F"`
for every player (`scheduler/job2.py:460`). That looked like guards and centers
being served by the wrong head.

It is not a bug, because **the model has only an F cohort.** The training corpus
is pooled into a single cohort: `features/corpus.py:82` does
`corpus.with_columns(pl.lit("F").alias("position"))` because game logs carry no
position. Confirmed against the live artifact `picker_e2ced9ec_1780873338.pkl`:

    heads = [('minutes','F'), ('real_score_per_min','F'), ('points_per_min','F'),
             ('reb_per_min','F'), ('ast_per_min','F'), ('stl_blk_per_min','F')]
    cohort_means = {'F': 2.514}

Every head is F. Serving with `position: "F"` routes every player to the only
head that exists. Train and serve agree. There is no positional misrouting.

The real cost here is a missed opportunity, not a defect: there is no positional
specialization at all. Splitting G/F/C needs a position source joined onto the
game logs (the Real Sports pool already carries position; the identity resolver
could attach it). That is a projection-quality lever for a future session, not
an explanation for the 21/20 result.

## 2. The 21/20 benchmark is right-censored at the top 0.24% `[verified]`

`scripts/backfill_placements.py:110-111` computes the headline number:

    n_above = sum(1 for s in lb_scores if s > our_score)
    rank_str = f"rank {n_above + 1}/{len(lb_scores)} in top-20"

`lb_scores` is `contest_leaderboards.score`, and `contest_leaderboards` stores
**only the top 20 finishers** of the contest (`ingest/contest_stats.py:264`,
"The platform truncates to top 20"). A typical slate has ~8,300 entries
(`research/internal/07*.md`). So:

- "rank 21/20" means our realized lineup scored below all 20 of the **best 20
  entries out of ~8,300**. It says we did not crack the **top ~0.24%**. It says
  nothing about whether we finished 30th or 6,000th. Everything from rank 21 to
  rank 8,300 is invisible because the DB never stored it.
- "beat the top-20 median" (`calibrate_knobs.py:165`, `our_score > median`)
  means beating roughly the **10th-best entry out of ~8,300**, i.e. landing in
  the **top ~0.12%**. The winning config does this on 12.1% of slates.

So the D91 statement "below the captured top-20 median on 88% of slates" decodes
to "we are not in the top ~0.12% of the field on 88% of slates." That is
unremarkable and expected. It is emphatically **not** the same claim as
"below-median placement" or "a 6% selection deficit." A lineup sitting at the
75th-90th percentile of an 8,300 field is still "21/20" on this benchmark. The
benchmark cannot distinguish a strong-but-not-elite finish from a terrible one,
because it only retains the extreme right tail of the field. `[reasoned]`

The `gap_vs_1st` column (~13 points) is the gap to the single best hindsight
lineup, which bundles the field's order-statistic maximum with irreducible
slate variance. It is a ceiling-distance, not a deficit-from-median.

## 3. corr 0.554 and the benchmark measure different things `[reasoned]`

The 0.554 is rank correlation between predicted and realized `real_score` on the
game-log corpus: "given a player, does the head rank their own outcome well."
The placement benchmark is "does our 5-card lineup, after boost handicapping and
slot multipliers, out-score the extreme tail of a specific contest's field."
These are different tasks. A model can rank players well in the absolute and
still build lineups that rarely crack the top 0.1%, because (a) the boost is an
explicit handicap that compresses within-slate edges to near zero
(within-slate corr(boost, value) = +0.016, README), and (b) cracking the top 20
of 8,300 requires a near-optimal ceiling outcome that is mostly variance once
projections are merely good. Neither task is the one we actually care about,
which is **placement percentile**, and that one is unmeasured.

## 4. What we genuinely do not know

- Our real finish distribution. We have one screenshot (RESULTS.md, 2026-05-28,
  ~517th of 8,700, in progress) and a censored top-20 comparison. That is not a
  measurement of median placement.
- Whether the projections or the construction is the binding constraint. The
  gap analysis (`research/00_GAP_ANALYSIS.md`) argues 94.8% of the gap to the
  perfect lineup is projection error; the placement-overhaul doc
  (`research/internal/07*.md`) argues construction/field-modeling is the lever.
  Both are reasoned from offline proxies. Neither is validated on realized rank.

## 5. 2026 best-practice context `[literature]`

Current single-entry large-field GPP consensus (Stokastic, 4for4, dfsbuild,
2024-2026) is that winning lineups average 20-30% ownership per player, that
leverage equals (optimal% - ownership%), and that ceiling and differentiation
decide top-heavy payouts. That consensus is built on operators who **measure
where they finish** across hundreds of contests and back out which exposures
paid. We have been tuning against a proxy that is blind to 99.76% of the field.
The single highest-value move is not another projection or field knob. It is to
make placement observable.

## 6. Recommendation (drives this session's B)

1. Stop treating "21/20" as a deficit signal. It is a top-0.24% censoring
   threshold. Relabel the metric in `backfill_placements.py` /
   `calibrate_knobs.py` output as "cracked captured top-20: yes/no" so it is not
   misread again.
2. Make placement observable from data we already hold. `num_brawlers` (the full
   field size) is already parsed (`contest_stats.py:311`) and persisted in
   `contest_leaderboards` (`db/reads.py:66`). When our entry score lands inside
   the captured top-20, `relative_rank` IS our true field rank, so
   `finish_percentile = rank / num_brawlers` is exactly correct and should be
   recorded automatically. That is shipped this session (see B).
3. For the true picture below the top 20, the only complete fix is the
   full-leaderboard scrape flagged in `research/00_GAP_ANALYSIS.md` open
   question 7 (Real Sports paginates the leaderboard via `pagedRank`). Defer
   until it can be tested against the live endpoint; do not ship blind.

## 7. One-line summary

The projections are not proven good, but they are not proven 6% bad either: the
"21/20 on 16/16 slates" result is a right-censored comparison against the top
0.24% of the field, not a placement measurement. Fix the instrument before
tuning the model.
