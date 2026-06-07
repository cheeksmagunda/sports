# Boost Economics — A WNBA Oracle Playbook

Author: research subagent (D63 build), 2026-06-05
Scope: 141 slates of `data/historical/slate_labels` (4,002 player-rows) and
`data/historical/leaderboards` top-20 finishers (2,820 entries, 14,100 picks),
plus 10 of our own frozen lineups from Postgres `frozen_lineups`.
Verified directly from the parquet/Postgres rows except where marked
[reasoning].

## TL;DR — what to load up on, what to avoid

| Bucket               | Mean contrib | Hit rate | Sharpe (mean/std) | Verdict |
|----------------------|--------------|----------|-------------------|---------|
| 0.0                  | 5.51         | 99.0%    | 1.83              | safe filler, low ceiling |
| (0, 0.5]             | 6.36         | 97.2%    | 2.19              | best baseline; load up |
| (0.5, 1.0]           | 6.59         | 93.1%    | 2.04              | filler with upside |
| **(1.0, 1.5]**       | **7.23**     | 82.7%    | **2.03**          | **sweet spot for floor + ceiling** |
| (1.5, 2.0]           | 7.36         | 59.4%    | 1.73              | inflection — variance ramps |
| **(2.0, 2.5]**       | **8.86**     | 50.4%    | **2.01**          | **highest EV per Sharpe; winners over-pick 2.6x** |
| (2.5, 3.0)           | 8.97         | 27.1%    | 2.04              | lottery; OK in moderation |
| **3.0 (max)**        | 6.11         | **8.2%** | **1.21**          | **trap unless ultra-low ownership** |

Numbers above are verified from `slate_labels` (n=4002).
Contrib = `real_score x (1.6 + card_boost)` (1.6 = mean of slot multipliers
[2.0, 1.8, 1.6, 1.4, 1.2]).

Bottom line:

- Build the lineup around (1.0, 2.5] cards. They have the best
  contribution-per-unit-risk and they make winning lineups (winners over-pick
  the (2.0, 2.5] bucket at 2.60x the universe rate).
- One 2.5-3.0 lottery is fine. The data supports it; winners run 0.59 such
  picks per lineup on average.
- The default fielding of FIVE 3.0-boost cards (which our optimizer has done
  on multiple skipped slates) is fighting the data. 79% of all 3.0 boosts
  scored below the line and 69% of top-20 lineups had ZERO 3.0 boosts.

## Section 1 — Distribution of `card_boost` in the menu

The card_boost field is the additive bonus on top of the slot multiplier:
`effective_mult = slot_mult + card_boost`, slot in {2.0, 1.8, 1.6, 1.4, 1.2}.
Source: `src/wnba_oracle/picker/optimize.py:18` and the verification note at
line 41. Range observed: 0.0 to 3.0, in 0.1 increments. There is a hard cap
at 3.0; 19.8% of all menu rows are exactly 3.0.

Per-slate menu averages (141 slates):

- Mean menu size: 28.4 players (min 13, max 38)
- Mean # of 3.0-boost players per slate: 5.6
- Mean # of 2.0-2.9 boost players per slate: 3.4
- Mean # of 1.0-1.9 boost players per slate: 6.6
- Mean # of 0.1-0.9 boost players per slate: 10.5
- Mean # of zero-boost players per slate: 2.2

About 20% of every slate's menu is unhittable lottery tickets (3.0 boost),
and about 30% is the workable (1.0-2.9] band where most expected value lives.

## Section 2 — Bucket economics in detail

(Slot=1.6 contribution = `real_score x (1.6 + card_boost)`.)

| boost_bin   | n    | mean_real | std_real | hit_rate | hit@2x | mean_contrib | std_contrib | Sharpe |
|-------------|------|-----------|----------|----------|--------|--------------|-------------|--------|
| 0.0         | 315  | 3.45      | 1.88     | 0.990    | 0.990  | 5.51         | 3.01        | 1.83   |
| (0, 0.5]    | 890  | 3.36      | 1.53     | 0.972    | 0.967  | 6.36         | 2.90        | 2.19   |
| (0.5, 1.0]  | 714  | 2.76      | 1.35     | 0.931    | 0.805  | 6.59         | 3.24        | 2.04   |
| (1.0, 1.5]  | 457  | 2.51      | 1.23     | 0.827    | 0.466  | 7.23         | 3.56        | 2.03   |
| (1.5, 2.0]  | 438  | 2.17      | 1.26     | 0.594    | 0.142  | 7.36         | 4.24        | 1.73   |
| (2.0, 2.5]  | 250  | 2.28      | 1.12     | 0.504    | 0.028  | 8.86         | 4.40        | 2.01   |
| (2.5, 3.0)  | 144  | 2.07      | 1.01     | 0.271    | 0.000  | 8.97         | 4.39        | 2.04   |
| **3.0 (max)** | **794** | **1.33** | **1.10** | **0.082** | **0.001** | **6.11** | **5.04** | **1.21** |

Verified from `slate_labels` (n=4002, 141 slates).

The 3.0 bucket is the standout outlier:

- Mean real_score 1.33 (lowest of any bucket).
- Hit rate 8.2% (one in twelve).
- "Hit by 2x" essentially never (1 out of 794).
- Highest stdev relative to mean: coefficient of variation 0.83 vs ~0.5 for
  all other buckets.
- Sharpe 1.21, lowest by 0.6 standard deviations from the next-worst bucket.

The (1.0, 1.5] bucket is the most under-appreciated band. It carries an 82.7%
hit rate AND a 7.23 mean contribution that ties the (1.5, 2.0] band. It is
the workhorse anchor of every good lineup.

## Section 3 — Sweet spot at 0.1-granularity

Top boosts ranked by Sharpe (mean_contrib / std_contrib), n>=40:

| boost | n   | mean_contrib | std_contrib | hit_rate | Sharpe |
|-------|-----|--------------|-------------|----------|--------|
| 1.3   | 89  | 7.74         | 3.34        | 0.865    | 2.32   |
| 0.5   | 132 | 6.96         | 3.05        | 0.985    | 2.28   |
| 0.2   | 228 | 6.13         | 2.74        | 0.969    | 2.24   |
| 2.1   | 63  | 8.34         | 3.74        | 0.635    | 2.23   |
| 0.3   | 191 | 6.65         | 2.99        | 0.990    | 2.22   |
| 1.1   | 121 | 6.91         | 3.14        | 0.893    | 2.20   |

Top boosts ranked by mean_contrib (n>=40):

| boost | n  | mean_contrib | std_contrib | hit_rate |
|-------|----|--------------|-------------|----------|
| 2.2   | 42 | 9.69         | 4.57        | 0.595    |
| 2.8   | 41 | 9.03         | 4.17        | 0.268    |
| 2.4   | 53 | 8.97         | 4.48        | 0.396    |
| 2.1   | 63 | 8.34         | 3.74        | 0.635    |
| 2.6   | 42 | 7.84         | 4.57        | 0.262    |
| 2.3   | 53 | 7.75         | 4.15        | 0.377    |
| 1.3   | 89 | 7.74         | 3.34        | 0.865    |
| 1.9   | 88 | 7.74         | 3.90        | 0.625    |

Verified from `slate_labels` (n=4002).

There are two distinct sweet spots:

1. Floor sweet spot: boost 0.2-0.5. Hit rate >96%, contribution 6-7.
   Treat these as "1.6 slot anchors" — when the platform under-prices
   a starter at low boost, this is free yards.
2. Ceiling sweet spot: boost 2.1-2.4. Hit rate 40-64%, mean contribution
   8-10. This is where winners over-index by 2.6x.

The 2.8 boost is the most counter-intuitive ceiling pick (mean contribution
9.03, second only to 2.2), and it has only 27% hit rate. The reason it pays
when it hits: real_score must be >=2.8 with effective mult >=4.4, so even one
explosion delivers ~13 lineup points.

## Section 4 — Boost x ownership (drafts)

This is the most decision-relevant cross-tab in the entire dataset.

Hit rate (real_score >= card_boost) by boost bucket and within-slate
draft-count quartile:

| boost_bin   | Q1-low | Q2    | Q3    | Q4-chalk |
|-------------|--------|-------|-------|----------|
| 0.0         | 1.000  | 1.000 | 1.000 | 0.985    |
| (0, 0.5]    | 0.571  | 1.000 | 0.983 | 0.963    |
| (0.5, 1.0]  | 0.913  | 1.000 | 0.948 | 0.853    |
| (1.0, 1.5]  | 0.950  | 0.973 | 0.811 | 0.484    |
| (1.5, 2.0]  | 0.773  | 0.735 | 0.329 | 0.121    |
| (2.0, 2.5]  | 0.595  | 0.610 | 0.250 | 0.000    |
| (2.5, 3.0)  | 0.312  | 0.286 | 0.154 | 0.000    |
| **3.0 (max)** | **0.140** | 0.027 | 0.009 | 0.000  |

Mean contribution (real_score x (1.6 + boost)) by the same cross-tab:

| boost_bin   | Q1-low | Q2    | Q3   | Q4-chalk |
|-------------|--------|-------|------|----------|
| (1.0, 1.5]  | 8.51   | 9.13  | 6.51 | 3.71     |
| (1.5, 2.0]  | 8.82   | 8.51  | 5.44 | 3.16     |
| (2.0, 2.5]  | 10.04  | 9.77  | 6.02 | 3.36     |
| (2.5, 3.0)  | 9.94   | 8.73  | 6.53 | 3.78     |
| **3.0 (max)** | **8.58** | 3.66 | 3.22 | 2.66 |

Verified from `slate_labels` x slate-relative draft rank.

Key reads:

- **Chalky high-boost is poison.** A (1.5, 2.0] card in Q4 ownership hits
  12.1% vs 77.3% in Q1. The platform sets the boost; the field's response
  encodes their information (it's high because the player got hurt /
  benched / matchup-disadvantaged). Trust the crowd at high boosts.
- **Low-owned 3.0 boosts are the only 3.0 boosts worth touching.** Hit
  rate 14% (still bad but >5x better than chalk) with mean contribution
  8.58 (vs 2.66 for chalk 3.0s).
- **Q1 in the (2.0, 2.5] band is the single best cell in the table.**
  10.04 mean contribution at 59.5% hit. Find unloved 2.0-2.5 boosts.

## Section 5 — Boost x position

Position proxy derived from career game-log averages (G if ast_pg>=3 or
ast>reb; C/Big if reb+blk>2*ast and reb>=5; else F). Match rate to the
labels was 98.6% after unicode normalization.

Hit rate:

| boost_bin   | C/Big | F     | G     |
|-------------|-------|-------|-------|
| (0, 0.5]    | 0.967 | 1.000 | 0.970 |
| (0.5, 1.0]  | 0.948 | 0.905 | 0.927 |
| (1.0, 1.5]  | 0.878 | 0.812 | 0.826 |
| (1.5, 2.0]  | 0.593 | 0.561 | **0.711** |
| (2.0, 2.5]  | 0.607 | 0.476 | 0.452 |
| (2.5, 3.0)  | 0.385 | 0.279 | 0.233 |
| 3.0 (max)   | 0.152 | 0.066 | 0.147 |

Mean contribution:

| boost_bin   | C/Big | F    | G     |
|-------------|-------|------|-------|
| (1.0, 1.5]  | 7.85  | 6.84 | 7.59  |
| (1.5, 2.0]  | 7.43  | 6.73 | **9.54** |
| (2.0, 2.5]  | 9.48  | 8.63 | 8.69  |
| (2.5, 3.0)  | 9.94  | 8.94 | 8.77  |
| 3.0 (max)   | 8.40  | 5.80 | 7.40  |

Verified from `slate_labels` joined to career averages from
`wnba_game_logs.parquet`.

Reads:

- **Guards are most reliable in the (1.5, 2.0] danger zone.** 71% hit rate
  vs 56% for forwards. Mean contribution 9.54 (highest in the row).
  Reasoning [reasoning]: guards' fantasy output is more minutes-dominated and
  less rebound-luck-dominated than forwards/bigs, so when a guard gets a
  1.5+ boost, the platform is usually pricing in a smaller injury or matchup
  effect that gets washed out by usage rate.
- **Bigs win the 3.0 lottery more often.** 15.2% C/Big hit rate at 3.0
  vs 6.6% for forwards. n is small (46) but the gap is consistent.
- **Forwards at 3.0 are the worst pocket in the data.** 6.6% hit, 5.80
  mean contribution. 609 of 794 3.0-boost rows are forwards. This is the
  bin our optimizer keeps loading up on.

## Section 6 — Section field is a time-of-injection proxy (and a warning)

We don't have per-card snapshot timestamps in `slate_labels`, so true
time-of-injection cannot be measured. The `section` column is the closest
proxy: it's the Real Sports UI bucket the card was filed under.

Verified comparison of all 3.0-boost cards split by section:

| section                      | n   | hit_rate | mean_real | mean_drafts |
|------------------------------|-----|----------|-----------|-------------|
| highestBoostedValuePlayers   | 470 | 14.0%    | 1.86      | 29          |
| **mostCommon3xPlayers**      | **300** | **0.0%** | **0.56** | **192**   |
| popularPlayers               | 24  | 0.0%     | 0.45      | 848         |

The `mostCommon3xPlayers` section is essentially a graveyard. 300 cards
across 112 slates, zero hits, mean realized 0.56 fantasy points. Their
mean draft count is 192 (vs 29 for `highestBoostedValuePlayers`), meaning
the field finds them on its own. These are deep-bench players the platform
auto-tags at 3.0 because they almost never play — and the field then
piles in on them as a moonshot. The actual outcome: dead lineup slot.

Reasoning [reasoning]: the `highestBoostedValuePlayers` section appears to be
populated by an algorithm that picks "interesting" high-boost cards
(maybe based on projected minutes or recent form), while
`mostCommon3xPlayers` is a popularity dump that the field is wrong about.
If we never picked a 3.0-boost card from `mostCommon3xPlayers`, we'd
eliminate 300/4002 (7.5%) of the universe with no EV loss.

A separate time-of-injection signal (cards added late in the day, after the
9am freeze of the menu) cannot be measured from current parquets — would
need diff-snapshots from `data/raw/` or a new scraper job. **Open question**:
do "late-add" boost replacements (after injury news) hit at a different
rate? Worth instrumenting.

## Section 7 — How winners actually compose lineups

Top-20 finishers across 141 slates (2,820 entries, 14,100 picks):

| Metric                            | Universe avg | Top-20 picks | Rank-1 picks |
|-----------------------------------|--------------|--------------|--------------|
| Mean per-pick boost               | 1.39         | 1.27         | 1.50         |
| Mean total lineup boost           | n/a          | 6.33         | 7.48         |
| % of lineups with 0 3.0-boosts    | n/a          | 65.1%        | 52.9%        |
| % of lineups with 0 2.0+ boosts   | n/a          | 30.4%        | 16.7%        |
| % of lineups with >=4 2.0+ boosts | n/a          | 6.5%         | 10.9%        |

Verified from `leaderboards` lineup_json (group by entry_id).

The over/under-pick rate by bucket (how often does a bucket appear in
top-20 picks vs how often it appears in the menu):

| boost_bin   | universe share | top-20 lift | rank-1 lift |
|-------------|----------------|-------------|-------------|
| 0.0         | 7.9%           | 1.47x       | 1.00x       |
| (0, 0.5]    | 22.2%          | 0.91x       | 0.60x       |
| (0.5, 1.0]  | 17.8%          | 0.93x       | 0.90x       |
| (1.0, 1.5]  | 11.4%          | 1.18x       | 1.35x       |
| (1.5, 2.0]  | 10.9%          | 1.18x       | 1.20x       |
| **(2.0, 2.5]** | **6.2%**    | **1.61x**   | **2.60x**   |
| (2.5, 3.0)  | 3.6%           | 1.31x       | 1.42x       |
| 3.0 (max)   | 19.8%          | 0.53x       | 0.66x       |

Winners systematically over-fish in the (2.0, 2.5] bucket and avoid the
3.0 bucket relative to universe. They also lean on 0.0 boosts (stars
on no-boost cards = a stable 4-5 point anchor) at 1.47x universe.

When winners DO take a 3.0, they pick well. Conditional hit rates:

| Bucket      | universe hit | top-20 picks hit | rank-1 picks hit |
|-------------|--------------|------------------|------------------|
| (2.0, 2.5]  | 50.4%        | 74.6%            | 72.9%            |
| (2.5, 3.0)  | 27.1%        | 50.8%            | 47.7%            |
| 3.0 (max)   | 8.2%         | 38.6%            | **57.5%**        |

Verified from leaderboards x slate_labels merge.

A 3.0-boost player picked by a winner hits 57.5% of the time vs 8.2%
universe. The skill is in the SELECTION among 3.0s, not in the choice to
play 3.0s. From the ownership cross-tab, that selection is largely about
finding the low-ownership ones.

## Section 8 — How OUR lineups compare (the gap)

10 frozen lineups from Postgres `frozen_lineups`, 2026-05-27 to 2026-06-05:

| slate     | rec       | #3.0 | #>=2.0 | sum_boost | boosts                  |
|-----------|-----------|------|--------|-----------|--------------------------|
| 2026-06-05 | enter    | 0    | 3      | 7.8       | [0.3, 0.9, 2.4, 2.0, 2.2] |
| 2026-06-04 | enter    | 1    | 2      | 8.1       | [0.1, 0.8, 1.7, 2.5, 3.0] |
| 2026-06-03 | enter    | 1    | 3      | 9.0       | [0.6, 0.8, 2.0, 2.6, 3.0] |
| 2026-06-02 | enter    | 0    | 3      | 7.6       | [0.0, 0.5, 2.5, 2.1, 2.5] |
| 2026-06-01 | enter    | 3    | 4      | 12.0      | [0.2, 3.0, 2.8, 3.0, 3.0] |
| 2026-05-30 | skip     | 5    | 5      | 15.0      | [3.0, 3.0, 3.0, 3.0, 3.0] |
| 2026-05-29 | skip     | 3    | 5      | 14.3      | [2.4, 2.9, 3.0, 3.0, 3.0] |
| 2026-05-28 | enter*   | 5    | 5      | 15.0      | [3.0, 3.0, 3.0, 3.0, 3.0] |
| 2026-05-27 | skip     | 5    | 5      | 15.0      | [3.0, 3.0, 3.0, 3.0, 3.0] |

Verified from Postgres `frozen_lineups` table.

Our entered (non-skip) lineups average sum_boost 9.42 vs winners' 7.48.
But the 2026-05-28 "enter_with_caveat" was five 3.0 boosts (the live
6000th/8317 bust). The skip recommendations are also five 3.0 boosts —
the optimizer literally cannot find anything else when minutes priors are
flat, which is the underlying issue.

The 2026-06-05, 06-02, and 06-03 lineups are right in the winner pocket
(sum_boost 7.6-9.0, only 0-1 3.0 boosts). Those are the model behaving.
The pre-D67 lineups (skip-stack-of-5-3.0s) are the optimizer in failure
mode and would have been disasters if entered.

## Boost playbook (recommendations)

1. **Default lineup shape**: target sum_boost 7-9 (winners average 7.48).
   - 1-2 anchors at 0.0-0.5 boost (stars priced at floor; 97% hit rate).
   - 1-2 mid cards at 1.0-1.5 boost (workhorse band; 83% hit, sweet spot).
   - 1-2 dart cards at 2.0-2.5 boost (highest Sharpe at the ceiling; winners
     over-index 2.6x here).
   - At most ONE 3.0 boost, and only when low-owned (drafts in Q1 of the
     slate).

2. **Hard avoid**: any 3.0-boost player tagged `mostCommon3xPlayers`.
   300-card sample, 0 hits. Filter them out at the picker stage.

3. **Hard avoid**: any 2.0+ boost player in the slate's top-quartile of
   drafts. Hit rate collapses to 0-12%. The crowd is right.

4. **When forced into 3.0 territory** (early-week slates with few games):
   - Prefer C/Big over F (15% vs 7% hit rate at 3.0).
   - Prefer low-draft over high-draft. The Q1-ownership 3.0 sub-bucket hits
     14% with 8.58 mean contribution; chalk 3.0s hit 0% with 2.66 contribution.
   - This is exactly the regime the NEVER_SKIP policy (D67) enters. The
     ownership-filter rule above is the critical missing safety net.

5. **The (1.5, 2.0] guard exception**: guards in this band hit 71% vs 56%
   for forwards. When choosing between a guard and a forward both at 1.7
   boost with similar projections, prefer the guard.

6. **Two 2.x cards beats one 3.0**: A (2.0, 2.5] + (2.5, 3.0) pair has
   expected combined contribution ~17.8 with combined hit rate ~13.7%
   (P(both hit) = 0.504 x 0.271). A single 3.0 has contribution 6.11 at
   8.2% hit. Even ignoring covariance, two 2.x picks dominate.

## What the model needs to learn next

[reasoning] The picker currently filters by `pred_real_score * (2.0 + boost)`
which correctly weights ceiling, but it has no ownership term and no
section-aware filter. Adding:

- `if section == 'mostCommon3xPlayers' and pred_minutes_p50 < N: drop`
  (where N is calibrated to ~12 min from the game logs of these players)
- `if boost >= 2.0 and draft_rank_in_slate > 0.75: heavy penalty`
- a sum_boost soft cap around 9 in the lineup combo enumeration

would replicate the winner-distribution shape and likely close the bulk of
the gap between our current entries and a top-20 finish on a normal slate.

## Open questions

- **True time-of-injection effect**: cards added late in the day after
  injury news would intuitively hit harder (the boost is rapidly
  re-priced). Cannot be measured without snapshot diff history; would need
  a new scraper or to mine `data/raw/` snapshot timestamps.
- **Multi-game-day boost inflation**: do per-bucket hit rates differ
  between 1-game and 4-game slates? Brief check: not in this report.
  Worth a follow-up.
- **Section curation rules**: the platform's `highestBoostedValuePlayers`
  algorithm picks the "good" 3.0s (14% hit). Reverse-engineering that
  ruleset (likely projected-minutes-based) could let us pre-filter
  3.0-boost universe at ingest time.
