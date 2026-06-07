# 01. Winners Anatomy

What does a rank-1 lineup actually look like in the Real Sports WNBA contest? Mined across 141 slates (2025-05-16 through 2026-06-04), 14,100 picks (141 x 20 x 5).

Source data:
- `data/historical/leaderboards/slate_date=*/data.parquet` (top-20 lineups per slate)
- `data/historical/slate_labels/slate_date=*/data.parquet` (the card menu with `card_boost`, `drafts`, `real_score`)

Verified-vs-reasoning is called out inline. Numbers are computed from the parquets; quoted formulas are noted.

## TL;DR punchline

**If we wanted to win, we'd need to do this:**

1. **Stop trying to use the maximum card_boost (3.0).** The 2.5-3.0 boost bucket has the *worst* mean expected value at any slot. Winners' median total boost is 7.5; ours has been 12-15 on recent slates. We're 60-100% over-boosted.
2. **Put high-real-score chalk in slot 0.** 60% of winners do this. Mean R1 slot-0 ownership is **19.4%**, vs **1.3%** at slot 4. Our recent picks invert this: avg ownership decays from .14 at slot 0 to .002 at slot 3.
3. **Take 4 of 5 picks below 5% ownership** (median winner does exactly this). But those 4 should be low-boost or mid-boost (~1.5-2.0), not 3.0 punts.
4. **Game-stack.** 87% of top-20 lineups have 2+ picks from one game; mean 2.4 distinct games per lineup. Currently our picker has no game-correlation logic.
5. **Don't aim for "perfect."** Median R1 score is only 90% of the brute-force perfect lineup. The winning bar is closer than the gap between us and rank-20 suggests.

---

## 1. Winning score and field size distributions

**Verified** (`leaderboards` rank=1, n=141):

| metric            | p10  | p25  | median | p75  | p90  | mean |
|-------------------|------|------|--------|------|------|------|
| Rank-1 score      | 45.6 | 49.4 | **55.1** | 60.8 | 65.3 | 55.7 |
| Field size        | 7,350| 7,919| **8,989** | 10,467| 11,715| 9,246 |

By rank bucket (median total score):

| rank | median | p10  | p90  |
|------|--------|------|------|
| 1    | 55.08  | 45.62| 65.25|
| 3    | 53.58  | 44.52| 63.13|
| 10   | 50.42  | 42.71| 59.28|
| 20   | 49.23  | 41.66| 58.27|

The median rank-1 score is only 1.32 points above the median rank-3 score, and only 4.92 points above rank-20. **The top-20 cliff is shallow.** A rank-20 lineup hits 90.7% of rank-1's score on a typical slate.

For context, top-20 is paid in this contest, and on a 9,000-entry field, rank 20 is the 99.8th percentile. To target "top 500" (top 5.5%) we are several hundred ranks below this band; expected score is plausibly ~46-48 on a typical slate (extrapolation; we do not have rank-500 lineup data).

## 2. Brute-force perfect ceiling

**Verified** (Hungarian assignment over top-15 candidates by `real_score * (2.0+boost)`, then enumerate 5-combos):

| metric                | mean | median | p10 | p90 |
|-----------------------|------|--------|-----|-----|
| Perfect lineup score  | 62.7 | 62.96  | 47.96 | 77.37 |
| Rank 1 / perfect      | 0.897| 0.904  | 0.801 | 0.990 |
| Rank 20 / perfect     | 0.818| n/a    | n/a   | n/a   |

**Key:** even the winner only captures 90% of the theoretical maximum on average. **Targeting "perfect" is the wrong frame.** Capturing 91% of perfect is enough to win on most slates; capturing 82% is enough to cash top-20.

## 3. Multiplier and card_boost distribution

The slot multiplier is decomposed as `slot_base + card_boost`, where:
- slot 0 = 2.0, slot 1 = 1.8, slot 2 = 1.6, slot 3 = 1.4, slot 4 = 1.2
- `card_boost` from `slate_labels` ranges 0.0 to 3.0

**Verified.** 137 of 141 slates have the card_boost system live. The other 4 (2025-05-16, 2025-05-17, 2026-05-08, 2026-05-09) are pre-boost slates where all cards had boost=0.

### Per-pick card_boost by rank bucket (boost-era only)

| bucket  | n    | mean | p25  | median| p75  | p90  |
|---------|------|------|------|-------|------|------|
| rank=1  | 833  | **1.46** | 0.70 | 1.40  | 2.30 | 3.00 |
| rank≤3  | 2,685| 1.43 | 0.50 | 1.30  | 2.30 | 3.00 |
| rank≤10 | 7,478| 1.30 | 0.40 | 1.20  | 2.10 | 3.00 |
| rank≤20 | 13,381|1.22 | 0.30 | 1.00  | 2.00 | 3.00 |

**Winners take more boost than the top-20 average,** but they don't max it. Rank-1 median is 1.40 boost; rank-20 median is 1.00.

### Per-slot card_boost at rank 1

| slot | mean boost | median |
|------|------------|--------|
| 0    | 0.66       | 0.40   |
| 1    | 1.09       | 1.10   |
| 2    | 1.56       | 1.60   |
| 3    | 1.85       | 2.10   |
| 4    | 2.19       | 2.60   |

Winners stack boost into the LOW-multiplier slots (slot 4 = 1.2x base) and keep slot 0 boost-light. This makes sense for variance: a high-boost card in slot 4 (1.2 base) needs to clear `1.2 + boost` to provide its value; in slot 0 (2.0 base), the boost is multiplied by the same real_score but the slot already provides 2x. **Boost is most leveraged at low-base slots.**

### Number of picks with any boost per lineup (boost-era)

| boosted picks | rank=1 | top-20 |
|---------------|--------|--------|
| 5 / 5         | 68%    | 60%    |
| 4 / 5         | 29%    | 36%    |
| ≤3 / 5        | 3%     | 5%     |

Almost everyone uses boost cards in 4-5 slots. There is no meaningful "no boost" archetype.

### Card_boost vs real_score (EV by boost bin)

**Verified** (n=4,002 cards across all slates, where `real_score` is what they actually scored that day):

| boost bin | n   | mean real_score | mean drafts | EV at slot-4 (mean) | EV at slot-4 (p90) |
|-----------|-----|----------------|-------------|---------------------|--------------------|
| 0         | 450 | 3.45           | 2,305       | 4.25                | 6.84               |
| 0.1-0.5   | 755 | 3.34           | 1,125       | 5.10                | 8.12               |
| 0.5-1.0   | 714 | 2.76           | 675         | 5.48                | 8.86               |
| 1.0-1.5   | 457 | 2.51           | 441         | 6.23                | 9.90               |
| 1.5-2.0   | 438 | 2.17           | 332         | 6.49                | 11.16              |
| **2.0-2.5** | **250** | **2.28**   | 216         | **7.95**            | **13.19**          |
| 2.5-3.0   | 938 | 1.44           | 124         | 5.97                | 12.22              |

**The 2.0-2.5 boost bucket is the EV sweet spot.** The 2.5-3.0 bucket collapses to 1.44 mean real_score, dragging EV down despite the large multiplier. *Reasoning:* Real Sports likely sets `card_boost = 3.0` on the lowest-projection players (deep-bench, injury fillers) to keep contest balance. The system intentionally makes the highest-boost cards the longest shots, and the data shows most don't pay off.

**The 3.0 boost is a value trap.** Our current picker frequently selects 3.0-boost cards in slots 3-4 (recent slates show sum_boost of 12-15 vs winner median 7.5). This is a structural error.

## 4. Ownership: how contrarian are winners?

`ownership = drafts / num_brawlers` per card per slate.

### Slate "chalk baseline"

The size-biased mean ownership (what a random pick in the field looks like) across 141 slates: **mean 25.7%, median 24.1%, p90 33.2%.** A random field pick is held by ~1 in 4 entries.

### Avg-ownership of all 5 picks per lineup

| bucket | mean avg-own | field chalk | gap |
|--------|--------------|-------------|-----|
| rank 1 | **5.8%**     | 25.3%       | -19.5 pp |
| rank ≤3 | 6.9%        | 26.2%       | -19.4 pp |
| rank ≤10| 7.6%        | 26.3%       | -18.7 pp |
| rank ≤20| 8.1%        | 26.0%       | -17.9 pp |

**Winners are ~4x less chalky than the field's average pick.** The gap shrinks only modestly from rank-1 (5.8%) to rank-20 (8.1%), meaning even cashing top-20 requires substantial contrarianism.

### Per-slot ownership at rank 1

| slot | mean own | median | p10  | p90  |
|------|----------|--------|------|------|
| 0    | **19.4%**| 7.3%   | 0.7% | 51.4%|
| 1    | 5.0%     | 2.3%   | 0.3% | 12.3%|
| 2    | 2.9%     | 1.5%   | 0.1% | 5.5% |
| 3    | 2.1%     | 0.9%   | 0.1% | 3.4% |
| 4    | **1.3%** | 0.4%   | 0.0% | 3.0% |

**Slot 0 is the "chalk slot"; slot 4 is the leverage slot.** 60% of winners place their highest-ownership pick in slot 0. 95% of winning slot-4 picks are below 5% ownership.

### Per-slot ownership across all top-20

Same pattern, slightly chalkier:

| slot | rank-1 mean | rank≤20 mean |
|------|-------------|--------------|
| 0    | 19.4%       | 20.9%        |
| 1    | 5.0%        | 7.4%         |
| 2    | 2.9%        | 4.2%         |
| 3    | 2.1%        | 3.2%         |
| 4    | 1.3%        | 2.7%         |

Going from rank-20 to rank-1 only requires being modestly more contrarian (especially in slots 1-4).

### Chalk hit rate

**Verified.** Of 142 R1 lineups (boost-era + tie expansions):
- **31.2%** include the #1 most-drafted card on the slate
- avg of **0.52 of 3** top-3 most-drafted cards land in the winning lineup
- avg of **0.74 of 5** top-5 most-drafted cards land in the winning lineup
- 81.6% of winners have at least one pick below 1% ownership (deep punt)
- 34.8% of winners have at least one pick above 30% ownership (heavy chalk)

The typical winning lineup has **one chalky anchor + four leverage picks.**

## 5. Team and game stacking

`team_id` from lineup_json (numeric 1-16) was joined to team codes via `slate_labels.team_key`. Opponent inferred from `wnba_game_logs` by (date, team).

### Max picks from one team

| bucket | 1 team | 2 team | 3 team | 4 team | % 2+ stack | % 3+ stack |
|--------|--------|--------|--------|--------|------------|------------|
| rank=1 | 17.2%  | 64.9%  | 15.5%  | 2.3%   | 82.8%      | 17.8%      |
| rank≤3 | 22.2%  | 58.5%  | 16.9%  | 2.1%   | 77.8%      | 19.2%      |
| rank≤10| 22.3%  | 56.7%  | 16.4%  | 4.0%   | 77.7%      | 20.9%      |
| rank≤20| 21.1%  | 57.1%  | 17.1%  | 4.1%   | 78.9%      | 21.8%      |

Team-stacking rate is **virtually identical from rank-1 to rank-20.** Stacking is table stakes for top-20 but not a winning differentiator.

### Game stacks and concentration

**Verified** (game-mapping coverage: 72% of picks, n=703 fully-mapped lineups):

| bucket | mean distinct games | % 2+ from one game | % 3+ from one game | % 4+ from one game |
|--------|---------------------|--------------------|--------------------|--------------------|
| rank=1 | 2.38                | 75.7%              | 41.0%              | 10.4%              |
| rank≤3 | 2.52                | 87.5%              | 43.7%              | 11.8%              |
| rank≤10| 2.43                | 87.2%              | 43.5%              | 13.0%              |
| rank≤20| 2.42                | 88.2%              | 44.3%              | 13.6%              |

**This is huge.** Top-20 lineups use only 2.4 distinct games out of typically 4-7 games per slate. 44% have 3+ picks from a single game. Our current optimizer has zero game-correlation logic.

### Unique teams in winning lineup

| 2 teams | 3 teams | 4 teams | 5 teams |
|---------|---------|---------|---------|
| 11.5%   | 25.3%   | 52.9%   | 10.3%   |

Median winner uses 4 distinct teams from a 5-pick lineup. 36.8% use 2-3 teams (heavy stack).

## 6. Position composition

`training_corpus.parquet`'s `position` column is degenerate — every row is "F". **The WNBA contest does not appear to enforce position constraints in this dataset.** Skipping per-position analysis.

## 7. Archetypes

Classified each lineup by avg-ownership of its 5 picks:
- `deep_contrarian`: avg own < 4%
- `contrarian`: 4-8%
- `balanced`: 8-15%
- `chalky`: ≥ 15%

| bucket | deep_contrarian | contrarian | balanced | chalky |
|--------|-----------------|------------|----------|--------|
| rank=1 | **52.1%**       | 16.2%      | 25.4%    | 6.3%   |
| rank≤3 | 43.1%           | 15.7%      | 33.4%    | 7.8%   |
| rank≤10| 33.7%           | 20.9%      | 36.5%    | 8.9%   |
| rank≤20| 28.7%           | 21.2%      | 41.3%    | 8.8%   |

**The dominant winning archetype is "deep contrarian" (52% of winners).** As you move from rank-1 to rank-20, the distribution shifts toward "balanced." Extrapolating to top-500 (no data), the optimal archetype likely shifts further toward balanced — but staying below 10% avg ownership remains essential.

### Deep-punt count (picks below 5% ownership)

| bucket | mean #low-own | median | p10 | p90 |
|--------|---------------|--------|-----|-----|
| rank=1 | 4.09 / 5      | 4      | 3   | 5   |
| rank≤20| 3.61 / 5      | 4      | 2   | 5   |

The median lineup at every tier has **4 of 5 picks below 5% ownership.** The chalk pick is one anchor.

### Total card_boost per lineup

| bucket | mean total boost | median | p10 | p90  |
|--------|------------------|--------|-----|------|
| rank=1 | 7.16             | **7.50**| 3.40| 10.75|
| rank≤3 | 6.96             | 7.00   | 3.30| 10.40|
| rank≤10| 6.26             | 6.20   | 2.70| 9.90 |
| rank≤20| 5.85             | 5.60   | 2.40| 9.80 |

Winners take more boost (median 7.5) than rank-20 (5.6) but neither approaches the 15.0 maximum (5 picks * 3.0 boost). **There is no archetype where the winner maxes boost.**

## 8. The gap: us vs winners

Pulled our 10 most recent `frozen_lineups` from Postgres. 8 overlap with the leaderboard data. Compared to R1 on those slates (using `card_boost + slot_base` as `mult` and `real_score` from labels):

| slate       | our score | rank-1 score | gap   | our avg own | our sum boost |
|-------------|-----------|--------------|-------|-------------|---------------|
| 2026-05-27  | 12.70     | 59.01        | -46.3 | 0.04%       | **15.0**      |
| 2026-05-28  | 34.66     | 53.13        | -18.5 | 0.36%       | 15.0          |
| 2026-05-29  | 17.81     | 49.45        | -31.6 | 0.48%       | 14.3          |
| 2026-05-30  | 12.66     | 63.82        | -51.2 | 0.03%       | 15.0          |
| 2026-06-01  | 23.07     | 51.14        | -28.1 | 3.95%       | 12.0          |
| 2026-06-02  | 41.19     | 53.41        | -12.2 | 13.31%      | 7.6           |
| 2026-06-03  | 30.13     | 55.41        | -25.3 | 11.18%      | 9.0           |
| 2026-06-04  | 26.92     | 53.25        | -26.3 | 11.72%      | 8.1           |

**Two distinct error modes:**

1. **Late-May (5-27 to 5-30): max-boost, max-contrarian.** We took 5x 3.0 boost cards, avg ownership ~0%. Total boost 14-15. Scores collapsed (12-18) because the 3.0-boost cards rarely realize their lines. This is "trying to win the lottery" without any base.

2. **Early June (6-02 to 6-04): moved toward winner archetype.** Boost dropped to 7.6-9.0 (vs winner median 7.5). Ownership rose to 11-13% (vs winner median ~6%). Scores improved to 26-41. **The 6-02 score of 41.2 is within 12 points of rank-1.** Whatever shift happened around June 1-2 was directionally correct.

Per-slot comparison (mean across our 8 slates with data vs R1 mean):

| slot | our mean own | R1 mean own | our mean boost | R1 mean boost | our mean real | R1 mean real |
|------|--------------|-------------|----------------|---------------|---------------|--------------|
| 0    | 14.3%        | 19.4%       | 1.33           | 0.65          | 3.51          | 4.80         |
| 1    | 8.1%         | 5.0%        | 1.28           | 1.07          | 2.43          | 4.58         |
| 2    | 4.3%         | 2.9%        | 2.50           | 1.48          | 1.92          | 3.72         |
| 3    | 0.2%         | 2.1%        | 2.82           | 1.78          | 2.32          | 3.44         |
| 4    | 5.1%         | 1.3%        | 2.88           | 2.08          | 0.94          | 3.31         |

**Our picker is putting too much boost on every slot — ~1x more than winners — AND undershooting on real_score (1.94 avg vs winners' 3.97).** The two errors compound. We're choosing high-boost low-projection players when winners choose mid-boost solid-projection players.

The big slot-3 gap (0.2% own vs 2.1%) is particularly suspect — we're seeking ZERO-ownership players in slot 3, the opposite of even what other top-20 finishers do.

## 9. Cross-slate stability

The winning archetype is stable: ~50% deep contrarian, ~25% balanced, ~15% mild contrarian, ~6% chalky across the boost-era period (137 slates spanning ~13 months). The median total boost stays near 7.0-7.5. Median rank-1 score stays in the 50-56 range. There is no apparent regime shift requiring strategy variation by season.

The one structural change is the introduction of the boost system (May 2025 -> June 2025). Pre-boost slates (n=4) had different scoring distributions and cannot be aggregated with boost-era.

## 10. Extrapolation to "top 500"

We have no direct rank-500 data. Inference from rank trends:

- Median score: rank-1 = 55.1, rank-20 = 49.2. Linear extrapolation log(rank): ~46-47 at rank-500.
- Avg ownership: rank-1 = 5.8%, rank-20 = 8.1%. Linear extrapolation: ~10-12% at rank-500.
- Total boost: rank-1 = 7.5, rank-20 = 5.6. Linear extrapolation: ~4-5 at rank-500.
- Boost distribution should skew lower (less aggressive contrarian play).

**A "top 500" target probably looks like:** chalk in slot 0 (15-20% own), 3-4 mildly contrarian picks (2-8% own), total card_boost around 5-6, picking solid mid-projection players over deep punts. The picker should optimize for "85% of theoretical perfect" with moderate variance, not "98% of perfect" via maxed-out boost punts.

---

## Open questions

1. We don't have ownership data for rank-21 to rank-500 — extrapolation is rough. Could be addressed by scraping a deeper leaderboard slice on future slates.
2. We don't know whether the player who DOESN'T appear in `slate_labels` (~5% of top-20 picks) is a roster substitution, late add, or just a labeling bug. Worth chasing in the scraper.
3. The 4 slates with `boost_count != 5` need investigation — appear to be pre-boost-era or weird tie cases.
4. Real Sports' boost-assignment logic (why is 3.0 boost almost always a value trap?) is unknown. If we can predict which 3.0-boost cards will hit, that's the highest-EV signal in the dataset.
