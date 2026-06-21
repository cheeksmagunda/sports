# WNBA Oracle -- Complete Slate Post-Mortem Analysis
Generated: 2026-06-21
Slates analyzed: 157 (2025-05-16 through 2026-06-20)

This report covers every completed slate in the database, classifying
each player outcome into three categories:

  **(A) Correctly priced** -- the model or field got it right
  **(B) Knowable miss** -- the information was available but under-used
  **(C) Unknowable / winners' edge** -- variance or private information

---

# Aggregate Patterns

**Total slates analyzed**: 157
**Slates with model predictions**: 21
**Slates with enrichment data**: 25

## Classification Distribution

| Category | Count | Pct |
|----------|-------|-----|
| (A) Correctly priced | 2707 | 92.0% |
| (B) Knowable misses | 19 | 0.6% |
| (C) Unknowable / winners' edge | 217 | 7.4% |
| **Total** | **2943** | |

### Sub-category breakdown

| Sub-category | Count |
|-------------|-------|
| chalk_hit | 1044 |
| expected | 932 |
| mid_field | 443 |
| edge_or_luck | 169 |
| chalk_bust | 159 |
| correct_fade | 129 |
| contrarian_dart | 46 |
| knowable_miss | 19 |
| blind_spot | 2 |

## Winning Lineup Patterns

**Game stacks in winning lineups**: 125/157 (80%)

## Most Commonly Owned Players (across all slates)

| Player | Slates in top-20 | Avg ownership | Avg score |
|--------|-----------------|---------------|-----------|
| A. Wilson | 63 | 66% | 10.46 |
| C. Gray | 50 | 31% | 7.80 |
| A. Thomas | 47 | 32% | 7.84 |
| J. Young | 45 | 45% | 9.64 |
| K. Mitchell | 39 | 33% | 8.19 |
| A. Boston | 36 | 36% | 7.93 |
| P. Bueckers | 36 | 37% | 8.58 |
| N. Howard | 36 | 36% | 8.79 |
| N. Collier | 35 | 54% | 9.24 |
| V. Burton | 34 | 38% | 8.67 |
| S. Ionescu | 34 | 36% | 7.78 |
| A. Reese | 34 | 44% | 8.57 |
| C. Williams | 33 | 34% | 8.54 |
| S. Sabally | 33 | 33% | 7.80 |
| R. Howard | 31 | 26% | 8.39 |
| N. Smith | 31 | 30% | 8.04 |
| K. Cardoso | 31 | 26% | 8.82 |
| K. McBride | 31 | 27% | 8.35 |
| D. Hamby | 30 | 30% | 8.82 |
| J. Loyd | 30 | 25% | 7.74 |
| B. Stewart | 29 | 41% | 8.55 |
| N. Ogwumike | 29 | 33% | 9.41 |
| N. Hillmon | 29 | 44% | 9.78 |
| A. Gray | 28 | 29% | 8.17 |
| N. Hiedeman | 28 | 39% | 9.70 |

## Model Accuracy (across model-era slates)

**Overall MAE**: 1.23
**In-band rate**: 51/52 (98%)
**Avg rank correlation (our picks)**: 0.315

### Per-slate model summary

| Date | MAE | In-band | Rank corr | Expected payout |
|------|-----|---------|-----------|-----------------|
| 2026-05-27 | 0.00 | 0/0 | N/A | 0.636 |
| 2026-05-28 | 0.00 | 0/0 | N/A | 1.045 |
| 2026-05-29 | 0.00 | 0/0 | N/A | 0.623 |
| 2026-05-30 | 0.00 | 0/0 | N/A | 0.667 |
| 2026-05-31 | 0.00 | 0/0 | N/A | -inf |
| 2026-06-01 | 0.97 | 3/3 | 0.500 | 1.769 |
| 2026-06-02 | 0.74 | 4/4 | 0.800 | 2.552 |
| 2026-06-03 | 1.96 | 2/2 | N/A | 1.438 |
| 2026-06-04 | 1.08 | 2/2 | N/A | 1.583 |
| 2026-06-05 | 1.01 | 4/4 | 0.800 | 2.251 |
| 2026-06-06 | 0.78 | 2/2 | N/A | 2.745 |
| 2026-06-07 | 0.03 | 2/2 | N/A | 0.821 |
| 2026-06-08 | 1.98 | 3/3 | 1.000 | 0.656 |
| 2026-06-09 | 1.30 | 4/4 | 0.564 | 1.004 |
| 2026-06-10 | 1.49 | 5/5 | -0.200 | 0.796 |
| 2026-06-11 | 2.33 | 2/2 | N/A | 0.844 |
| 2026-06-12 | 0.96 | 3/3 | -0.500 | 0.574 |
| 2026-06-13 | 1.89 | 3/4 | 0.600 | 1.393 |
| 2026-06-18 | 0.70 | 5/5 | 0.300 | 0.651 |
| 2026-06-19 | 1.91 | 3/3 | -1.000 | 1.060 |
| 2026-06-20 | 0.79 | 4/4 | 0.600 | 1.111 |

## Recurring Knowable Misses (Category B)

These players had strong pre-game signals but were under-drafted or under-projected.

### Repeat knowable misses (appeared 2+ times)

| Player | Times missed | Dates | Avg score | Avg drafts |
|--------|-------------|-------|-----------|------------|
| C. Leite | 2 | 2026-06-11, 2026-06-17 | 4.96 | 8 |

### Knowable misses by team

| Team | Count |
|------|-------|
| CHI | 3 |
| POR | 3 |
| DAL | 2 |
| LVA | 2 |
| SEA | 2 |
| ATL | 1 |
| WAS | 1 |
| TOR | 1 |
| PHO | 1 |
| LAS | 1 |
| IND | 1 |
| CON | 1 |

### Knowable misses by boost bucket

| Boost bucket | Count |
|-------------|-------|
| low (0-1.5x) | 11 |
| mid (1.5-2.5x) | 8 |
| high (2.5x+) | 0 |

## Unknowable Outcomes (Category C)

These outcomes were driven by variance or private information. Do not retrain toward them.

| Sub-type | Count |
|----------|-------|
| edge_or_luck | 169 |
| contrarian_dart | 46 |
| blind_spot | 2 |

### Biggest C-category outliers

| Date | Player | Boost | Drafts | Score | Type |
|------|--------|-------|--------|-------|------|
| 2025-07-09 | R. Allen | 3.0x | 23 | 6.95 | edge_or_luck |
| 2026-05-27 | N. Sabally | 0.9x | 16 | 6.79 | edge_or_luck |
| 2025-06-20 | S. Austin | 1.7x | 43 | 6.77 | edge_or_luck |
| 2025-06-01 | O. Sims | 1.6x | 39 | 6.63 | edge_or_luck |
| 2025-07-11 | J. Canada | 0.9x | 43 | 6.56 | edge_or_luck |
| 2025-07-03 | A. James | 2.5x | 47 | 6.48 | edge_or_luck |
| 2025-09-07 | J. Allemand | 1.6x | 31 | 6.28 | edge_or_luck |
| 2025-08-21 | K. Cardoso | 0.8x | 13 | 5.97 | edge_or_luck |
| 2025-06-17 | B. Sykes | 0.5x | 21 | 5.95 | edge_or_luck |
| 2026-05-24 | A. Fudd | 2.3x | 38 | 5.93 | edge_or_luck |
| 2025-06-22 | S. Citron | 1.0x | 10 | 5.82 | edge_or_luck |
| 2025-07-14 | D. Bonner | 2.1x | 35 | 5.77 | edge_or_luck |
| 2025-08-25 | A. Atkins | 0.9x | 27 | 5.74 | edge_or_luck |
| 2025-05-30 | M. Mabrey | 1.3x | 19 | 5.69 | edge_or_luck |
| 2025-08-21 | J. Jones | 0.5x | 24 | 5.67 | edge_or_luck |

## Slate-by-Slate Signal vs Noise Balance

| Date | (A) Priced | (B) Knowable miss | (C) Unknowable | Dominant |
|------|-----------|-------------------|----------------|----------|
| 2025-05-16 | 19 | 0 | 0 | balanced |
| 2025-05-17 | 19 | 0 | 1 | noise |
| 2025-05-18 | 16 | 0 | 1 | noise |
| 2025-05-19 | 19 | 0 | 0 | balanced |
| 2025-05-20 | 15 | 0 | 0 | balanced |
| 2025-05-21 | 19 | 0 | 1 | noise |
| 2025-05-22 | 20 | 0 | 0 | balanced |
| 2025-05-23 | 16 | 0 | 3 | noise |
| 2025-05-24 | 19 | 0 | 0 | balanced |
| 2025-05-25 | 16 | 0 | 3 | noise |
| 2025-05-27 | 15 | 0 | 1 | noise |
| 2025-05-28 | 18 | 0 | 0 | balanced |
| 2025-05-29 | 17 | 0 | 1 | noise |
| 2025-05-30 | 15 | 0 | 3 | noise |
| 2025-05-31 | 19 | 0 | 0 | balanced |
| 2025-06-01 | 17 | 0 | 1 | noise |
| 2025-06-03 | 19 | 0 | 0 | balanced |
| 2025-06-05 | 16 | 0 | 0 | balanced |
| 2025-06-06 | 15 | 0 | 1 | noise |
| 2025-06-07 | 15 | 0 | 2 | noise |
| 2025-06-08 | 18 | 0 | 0 | balanced |
| 2025-06-09 | 18 | 0 | 0 | balanced |
| 2025-06-10 | 20 | 0 | 0 | balanced |
| 2025-06-11 | 17 | 0 | 2 | noise |
| 2025-06-13 | 18 | 0 | 1 | noise |
| 2025-06-14 | 17 | 0 | 2 | noise |
| 2025-06-15 | 14 | 0 | 4 | noise |
| 2025-06-17 | 10 | 0 | 8 | noise |
| 2025-06-18 | 12 | 0 | 0 | balanced |
| 2025-06-19 | 18 | 0 | 0 | balanced |
| 2025-06-20 | 16 | 0 | 3 | noise |
| 2025-06-21 | 15 | 0 | 1 | noise |
| 2025-06-22 | 12 | 0 | 7 | noise |
| 2025-06-24 | 13 | 0 | 5 | noise |
| 2025-06-25 | 17 | 0 | 1 | noise |
| 2025-06-26 | 17 | 0 | 0 | balanced |
| 2025-06-27 | 13 | 0 | 6 | noise |
| 2025-06-28 | 18 | 0 | 0 | balanced |
| 2025-06-29 | 16 | 0 | 4 | noise |
| 2025-07-01 | 17 | 0 | 0 | balanced |
| 2025-07-03 | 16 | 0 | 4 | noise |
| 2025-07-05 | 18 | 0 | 0 | balanced |
| 2025-07-06 | 18 | 0 | 1 | noise |
| 2025-07-07 | 16 | 0 | 2 | noise |
| 2025-07-08 | 19 | 0 | 0 | balanced |
| 2025-07-09 | 16 | 0 | 2 | noise |
| 2025-07-10 | 18 | 0 | 0 | balanced |
| 2025-07-11 | 18 | 0 | 1 | noise |
| 2025-07-12 | 20 | 0 | 0 | balanced |
| 2025-07-13 | 14 | 0 | 3 | noise |
| 2025-07-14 | 19 | 0 | 1 | noise |
| 2025-07-15 | 17 | 0 | 0 | balanced |
| 2025-07-16 | 16 | 0 | 2 | noise |
| 2025-07-22 | 16 | 0 | 3 | noise |
| 2025-07-23 | 17 | 0 | 0 | balanced |
| 2025-07-24 | 16 | 0 | 2 | noise |
| 2025-07-25 | 19 | 0 | 0 | balanced |
| 2025-07-26 | 19 | 0 | 0 | balanced |
| 2025-07-27 | 11 | 0 | 6 | noise |
| 2025-07-28 | 18 | 0 | 1 | noise |
| 2025-07-29 | 16 | 0 | 4 | noise |
| 2025-07-30 | 14 | 0 | 3 | noise |
| 2025-07-31 | 19 | 0 | 0 | balanced |
| 2025-08-01 | 16 | 0 | 4 | noise |
| 2025-08-02 | 19 | 0 | 0 | balanced |
| 2025-08-03 | 19 | 0 | 1 | noise |
| 2025-08-05 | 17 | 0 | 2 | noise |
| 2025-08-06 | 20 | 0 | 0 | balanced |
| 2025-08-07 | 15 | 0 | 3 | noise |
| 2025-08-08 | 18 | 0 | 0 | balanced |
| 2025-08-09 | 19 | 0 | 0 | balanced |
| 2025-08-10 | 16 | 0 | 4 | noise |
| 2025-08-11 | 16 | 0 | 0 | balanced |
| 2025-08-12 | 16 | 0 | 2 | noise |
| 2025-08-13 | 14 | 0 | 4 | noise |
| 2025-08-15 | 14 | 0 | 5 | noise |
| 2025-08-16 | 18 | 0 | 0 | balanced |
| 2025-08-17 | 14 | 0 | 5 | noise |
| 2025-08-19 | 14 | 0 | 6 | noise |
| 2025-08-20 | 17 | 0 | 0 | balanced |
| 2025-08-21 | 16 | 0 | 3 | noise |
| 2025-08-22 | 18 | 0 | 1 | noise |
| 2025-08-23 | 17 | 0 | 1 | noise |
| 2025-08-24 | 15 | 0 | 1 | noise |
| 2025-08-25 | 15 | 0 | 3 | noise |
| 2025-08-26 | 18 | 0 | 1 | noise |
| 2025-08-27 | 15 | 0 | 1 | noise |
| 2025-08-28 | 17 | 0 | 2 | noise |
| 2025-08-29 | 17 | 0 | 1 | noise |
| 2025-08-30 | 14 | 0 | 3 | noise |
| 2025-08-31 | 18 | 0 | 1 | noise |
| 2025-09-01 | 17 | 0 | 1 | noise |
| 2025-09-02 | 19 | 0 | 0 | balanced |
| 2025-09-03 | 17 | 0 | 1 | noise |
| 2025-09-04 | 16 | 0 | 2 | noise |
| 2025-09-05 | 18 | 0 | 1 | noise |
| 2025-09-06 | 18 | 0 | 1 | noise |
| 2025-09-07 | 15 | 0 | 2 | noise |
| 2025-09-08 | 14 | 0 | 0 | balanced |
| 2025-09-09 | 15 | 0 | 4 | noise |
| 2025-09-10 | 14 | 0 | 0 | balanced |
| 2025-09-11 | 15 | 0 | 5 | noise |
| 2025-09-14 | 18 | 0 | 2 | noise |
| 2025-09-16 | 20 | 0 | 0 | balanced |
| 2025-09-17 | 20 | 0 | 0 | balanced |
| 2025-09-18 | 19 | 0 | 1 | noise |
| 2025-09-19 | 18 | 0 | 0 | balanced |
| 2025-09-21 | 19 | 0 | 1 | noise |
| 2025-09-23 | 20 | 0 | 0 | balanced |
| 2025-09-26 | 20 | 0 | 0 | balanced |
| 2025-09-28 | 19 | 0 | 0 | balanced |
| 2025-09-30 | 18 | 0 | 0 | balanced |
| 2025-10-03 | 19 | 0 | 0 | balanced |
| 2025-10-05 | 18 | 0 | 0 | balanced |
| 2025-10-08 | 19 | 0 | 0 | balanced |
| 2025-10-10 | 18 | 0 | 0 | balanced |
| 2026-05-08 | 19 | 0 | 0 | balanced |
| 2026-05-09 | 16 | 0 | 4 | noise |
| 2026-05-10 | 19 | 0 | 1 | noise |
| 2026-05-12 | 20 | 0 | 0 | balanced |
| 2026-05-13 | 18 | 0 | 2 | noise |
| 2026-05-14 | 17 | 0 | 1 | noise |
| 2026-05-15 | 18 | 0 | 2 | noise |
| 2026-05-17 | 19 | 0 | 1 | noise |
| 2026-05-18 | 18 | 0 | 1 | noise |
| 2026-05-19 | 20 | 0 | 0 | balanced |
| 2026-05-20 | 17 | 0 | 3 | noise |
| 2026-05-21 | 18 | 0 | 2 | noise |
| 2026-05-22 | 18 | 0 | 2 | noise |
| 2026-05-23 | 20 | 0 | 0 | balanced |
| 2026-05-24 | 18 | 0 | 2 | noise |
| 2026-05-25 | 20 | 0 | 0 | balanced |
| 2026-05-27 | 15 | 0 | 5 | noise |
| 2026-05-28 | 20 | 0 | 0 | balanced |
| 2026-05-29 | 20 | 0 | 0 | balanced |
| 2026-05-30 | 19 | 0 | 1 | noise |
| 2026-05-31 | 20 | 0 | 0 | balanced |
| 2026-06-01 | 20 | 0 | 0 | balanced |
| 2026-06-02 | 20 | 0 | 0 | balanced |
| 2026-06-03 | 19 | 0 | 1 | noise |
| 2026-06-04 | 20 | 0 | 0 | balanced |
| 2026-06-05 | 18 | 1 | 1 | balanced |
| 2026-06-06 | 19 | 0 | 1 | noise |
| 2026-06-07 | 20 | 0 | 0 | balanced |
| 2026-06-08 | 19 | 0 | 1 | noise |
| 2026-06-09 | 18 | 2 | 0 | signal |
| 2026-06-10 | 20 | 0 | 0 | balanced |
| 2026-06-11 | 17 | 2 | 1 | signal |
| 2026-06-12 | 17 | 2 | 1 | signal |
| 2026-06-13 | 15 | 4 | 1 | signal |
| 2026-06-14 | 20 | 0 | 0 | balanced |
| 2026-06-15 | 18 | 2 | 0 | signal |
| 2026-06-16 | 20 | 0 | 0 | balanced |
| 2026-06-17 | 10 | 6 | 4 | signal |
| 2026-06-18 | 20 | 0 | 0 | balanced |
| 2026-06-19 | 15 | 0 | 5 | noise |
| 2026-06-20 | 18 | 0 | 2 | noise |


---

# Per-Slate Analysis


## 2025-05-16

**Players**: 19 HV
 | **Score range**: 2.26 -- 7.58 (median 3.07)

**Leaderboard**: top score 45.75, floor 43.65, median 44.09

**Winner** (score 45.75):
  - N. Collier (2x) = 10.75
  - K. Plum (1.8x) = 13.65
  - A. Gray (1.6x) = 9.37
  - B. Sykes (1.4x) = 5.71
  - C. Williams (1.2x) = 6.27
  - **Game stack**: team 5: 2 players

**Field ownership** (top-20 entries):
  - N. Collier (1.6x/1.8x/2x/1.4x): 20/20 = 100%, avg 10.43
  - K. Plum (1.6x/1.4x/1.2x/2x/1.8x): 20/20 = 100%, avg 12.97
  - A. Gray (1.6x/1.4x/1.2x/2x/1.8x): 20/20 = 100%, avg 8.85
  - C. Williams (1.6x/1.4x/1.2x/2x/1.8x): 20/20 = 100%, avg 7.62
  - B. Griner (1.6x/1.2x/1.4x): 11/20 = 55%, avg 4.40
  - B. Jones (1.2x/1.4x): 3/20 = 15%, avg 4.67
  - D. Hamby (1.4x): 3/20 = 15%, avg 4.47
  - R. Howard (1.2x): 2/20 = 10%, avg 2.73

### Outcome Classification

**(A) Correctly priced** (19 players):
  - K. Plum (LAS, 0.0x, 1700 drafts) = 7.58 -- High-draft player delivered as expected
  - A. Gray (ATL, 0.0x, 301 drafts) = 5.86 -- High-draft player delivered as expected
  - N. Collier (MIN, 0.0x, 4000 drafts) = 5.38 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.0x, 248 drafts) = 5.22 -- High-draft player delivered as expected
  - T. Fágbénlé (TOR, 0.0x, 72 drafts) = 4.39 -- High-draft player delivered as expected
  - B. Sykes (TOR, 0.0x, 18 drafts) = 4.08 -- Mid-draft player with mid outcome -- no edge either way
  - B. Jones (ATL, 0.0x, 166 drafts) = 3.69 -- High-draft player delivered as expected
  - D. Hamby (LAS, 0.0x, 460 drafts) = 3.19 -- High-draft player delivered as expected
  - A. Stevens (CHI, 0.0x, 92 drafts) = 3.14 -- High-draft player delivered as expected
  - B. Griner (CON, 0.0x, 702 drafts) = 3.07 -- High-draft player delivered as expected
  - S. Citron (WAS, 0.0x, 8 drafts) = 2.99 -- Outcome roughly matched draft position and signals
  - J. Shepard (DAL, 0.0x, 2 drafts) = 2.93 -- Outcome roughly matched draft position and signals
  - O. Sims (DAL, 0.0x, 91 drafts) = 2.9 -- Outcome roughly matched draft position and signals
  - T. Hayes (GSV, 0.0x, 49 drafts) = 2.63 -- Mid-draft player with mid outcome -- no edge either way
  - K. Iriafen (WAS, 0.0x, 1 drafts) = 2.5 -- Outcome roughly matched draft position and signals
  - J. Melbourne (SEA, 0.0x, 1 drafts) = 2.56 -- Outcome roughly matched draft position and signals
  - R. Howard (ATL, 0.0x, 231 drafts) = 2.28 -- Outcome roughly matched draft position and signals
  - T. Paopao (ATL, 0.0x, 4 drafts) = 2.27 -- Outcome roughly matched draft position and signals
  - D. Carrington (CHI, 0.0x, 305 drafts) = 2.26 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-05-17

**Players**: 20 HV
 | **Score range**: 2.02 -- 5.62 (median 2.70)

**Leaderboard**: top score 42.21, floor 40.67, median 41.56

**Winner** (score 42.21):
  - C. Clark (2x) = 11.23
  - A. Wilson (1.8x) = 9.42
  - B. Stewart (1.6x) = 8.12
  - A. Boston (1.4x) = 7.08
  - N. Cloud (1.2x) = 6.36
  - **Game stack**: team 3: 2 players

**Field ownership** (top-20 entries):
  - C. Clark (1.6x/1.8x/2x): 20/20 = 100%, avg 10.39
  - A. Wilson (1.6x/1.8x/2x/1.2x): 20/20 = 100%, avg 9.53
  - B. Stewart (1.6x/1.4x/1.2x/2x/1.8x): 19/20 = 95%, avg 8.49
  - S. Sabally (1.6x/1.2x/1.8x/1.4x): 14/20 = 70%, avg 6.98
  - A. Boston (1.2x/1.4x): 13/20 = 65%, avg 6.61
  - A. Thomas (1.2x/1.4x): 10/20 = 50%, avg 5.40
  - N. Cloud (1.6x/1.2x): 4/20 = 20%, avg 6.89

### Outcome Classification

**(A) Correctly priced** (19 players):
  - C. Clark (IND, 0.0x, 3800 drafts) = 5.62 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 4000 drafts) = 5.24 -- High-draft player delivered as expected
  - B. Stewart (NYL, 0.0x, 330 drafts) = 5.07 -- High-draft player delivered as expected
  - A. Boston (IND, 0.0x, 88 drafts) = 5.05 -- High-draft player delivered as expected
  - S. Sabally (NYL, 0.0x, 49 drafts) = 4.94 -- Mid-draft player with mid outcome -- no edge either way
  - A. Thomas (PHO, 0.0x, 414 drafts) = 4.22 -- High-draft player delivered as expected
  - J. Jones (NYL, 0.0x, 11 drafts) = 4.0 -- Mid-draft player with mid outcome -- no edge either way
  - S. Diggins (CHI, 0.0x, 206 drafts) = 3.25 -- High-draft player delivered as expected
  - K. Mitchell (IND, 0.0x, 65 drafts) = 2.7 -- Outcome roughly matched draft position and signals
  - N. Howard (MIN, 0.0x, 5 drafts) = 2.69 -- Outcome roughly matched draft position and signals
  - J. Young (LVA, 0.0x, 94 drafts) = 2.58 -- Outcome roughly matched draft position and signals
  - K. Burke (CON, 0.0x, 1 drafts) = 2.24 -- Outcome roughly matched draft position and signals
  - S. Ionescu (NYL, 0.0x, 473 drafts) = 2.22 -- Outcome roughly matched draft position and signals
  - A. Atkins (LAS, 0.0x, 9 drafts) = 2.2 -- Outcome roughly matched draft position and signals
  - K. Westbeld (PHO, 0.0x, 175 drafts) = 2.16 -- Outcome roughly matched draft position and signals
  - L. Hull (IND, 0.0x, 59 drafts) = 2.12 -- Outcome roughly matched draft position and signals
  - C. Gray (LVA, 0.0x, 101 drafts) = 2.1 -- Outcome roughly matched draft position and signals
  - N. Ogwumike (LAS, 0.0x, 232 drafts) = 2.06 -- Outcome roughly matched draft position and signals
  - L. Held (TOR, 0.0x, 182 drafts) = 2.02 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - N. Cloud (CHI, 0.0x, 14 drafts) = 5.3 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-05-18

**Players**: 17 HV
 | **Score range**: 0.92 -- 4.78 (median 3.04)

**Leaderboard**: top score 47.05, floor 42.98, median 44.25

**Winner** (score 47.05):
  - A. Stevens (2.5x) = 11.96
  - B. Carleton (4.2x) = 11.74
  - D. Hamby (2.1x) = 8.75
  - K. Iriafen (2.3x) = 6.82
  - N. Hiedeman (4.2x) = 7.78

**Field ownership** (top-20 entries):
  - B. Carleton (4x/4.2x/4.4x/3.8x/3.6x): 20/20 = 100%, avg 10.68
  - A. Stevens (1.9x/2.3x/2.1x/1.7x/2.5x): 13/20 = 65%, avg 10.71
  - D. Hamby (1.9x/2.1x/2.3x/2.5x): 13/20 = 65%, avg 8.87
  - B. Sykes (1.5x/2.1x/1.7x/1.9x): 12/20 = 60%, avg 8.34
  - N. Collier (1.6x/1.8x/2x): 10/20 = 50%, avg 8.83
  - N. Hiedeman (4.4x/4.2x/4.8x): 9/20 = 45%, avg 8.20
  - C. Williams (1.6x/1.4x/1.2x/2x/1.8x): 9/20 = 45%, avg 7.46
  - S. Citron (2x): 4/20 = 20%, avg 5.46

### Outcome Classification

**(A) Correctly priced** (16 players):
  - B. Carleton (POR, 2.4x, 183 drafts) = 2.8 -- Outcome roughly matched draft position and signals
  - A. Stevens (CHI, 0.5x, 248 drafts) = 4.78 -- High-draft player delivered as expected
  - D. Hamby (LAS, 0.5x, 486 drafts) = 4.16 -- High-draft player delivered as expected
  - B. Sykes (TOR, 0.1x, 252 drafts) = 4.72 -- High-draft player delivered as expected
  - N. Hiedeman (SEA, 3.0x, 131 drafts) = 1.85 -- Outcome roughly matched draft position and signals
  - N. Collier (MIN, 0.0x, 4300 drafts) = 4.55 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.0x, 488 drafts) = 4.48 -- High-draft player delivered as expected
  - J. Melbourne (SEA, 0.9x, 81 drafts) = 3.06 -- High-draft player delivered as expected
  - K. Iriafen (WAS, 0.9x, 96 drafts) = 2.96 -- Outcome roughly matched draft position and signals
  - A. Smith (DAL, 0.0x, 137 drafts) = 3.89 -- High-draft player delivered as expected
  - J. Shepard (DAL, 0.6x, 208 drafts) = 2.95 -- Outcome roughly matched draft position and signals
  - S. Citron (WAS, 0.6x, 165 drafts) = 2.73 -- Outcome roughly matched draft position and signals
  - K. Plum (LAS, 0.0x, 3200 drafts) = 3.04 -- High-draft player delivered as expected
  - S. Barker (POR, 3.0x, 58 drafts) = 1.16 -- High-draft player underperformed -- field took the loss equally
  - K. Samuelson (POR, 2.6x, 176 drafts) = 1.16 -- High-draft player underperformed -- field took the loss equally
  - E. Engstler (POR, 2.6x, 71 drafts) = 0.92 -- High-draft player underperformed -- field took the loss equally

**(C) Unknowable / winners' edge** (1 players):
  - O. Nelson-Ododa (CON, 0.0x, 2 drafts) = 3.13 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-05-19

**Players**: 19 HV
 | **Score range**: 0.00 -- 4.64 (median 1.09)

**Leaderboard**: top score 65.32, floor 65.16, median 65.16

**Winner** (score 65.32):
  - P. Bueckers (3.6x) = 14.21
  - G. Williams (3.7x) = 17.04
  - N. Ogwumike (3x) = 13.92
  - M. Hines-Allen (3.8x) = 9.53
  - E. Magbegor (3.8x) = 10.62

**Field ownership** (top-20 entries):
  - P. Bueckers (3.4x/3.6x): 20/20 = 100%, avg 13.46
  - G. Williams (3.7x/3.3x): 20/20 = 100%, avg 15.29
  - N. Ogwumike (3.4x/3x): 20/20 = 100%, avg 15.68
  - M. Hines-Allen (3.8x/3.6x): 20/20 = 100%, avg 9.05
  - E. Magbegor (3.8x/4.2x): 20/20 = 100%, avg 11.69

### Outcome Classification

**(A) Correctly priced** (19 players):
  - G. Williams (GSV, 1.9x, 181 drafts) = 4.6 -- High-draft player delivered as expected
  - N. Ogwumike (LAS, 1.4x, 573 drafts) = 4.64 -- High-draft player delivered as expected
  - P. Bueckers (DAL, 1.6x, 1800 drafts) = 3.95 -- High-draft player delivered as expected
  - E. Magbegor (SEA, 2.6x, 158 drafts) = 2.8 -- Outcome roughly matched draft position and signals
  - M. Hines-Allen (IND, 2.4x, 123 drafts) = 2.51 -- Outcome roughly matched draft position and signals
  - S. Diggins (CHI, 0.4x, 3100 drafts) = 4.52 -- High-draft player delivered as expected
  - N. Smith (LVA, 3.0x, 117 drafts) = 1.55 -- Outcome roughly matched draft position and signals
  - M. Siegrist (DAL, 1.8x, 152 drafts) = 1.79 -- Outcome roughly matched draft position and signals
  - A. Ogunbowale (DAL, 1.3x, 2400 drafts) = 1.09 -- High-draft player underperformed -- field took the loss equally
  - E. Wheeler (LAS, 3.0x, 109 drafts) = 0.64 -- High-draft player underperformed -- field took the loss equally
  - A. Clark (DAL, 0.0x, 113 drafts) = 1.29 -- High-draft player underperformed -- field took the loss equally
  - T. Harris (IND, 2.6x, 111 drafts) = 0.5 -- High-draft player underperformed -- field took the loss equally
  - L. Yueru (DAL, 1.8x, 183 drafts) = 0.59 -- High-draft player underperformed -- field took the loss equally
  - D. Carrington (CHI, 1.1x, 738 drafts) = 0.63 -- High-draft player underperformed -- field took the loss equally
  - K. Charles (GSV, 1.8x, 169 drafts) = 0.46 -- High-draft player underperformed -- field took the loss equally
  - J. Quinerly (DAL, 3.0x, 119 drafts) = 0.22 -- High-draft player underperformed -- field took the loss equally
  - D. Malonga (SEA, 3.0x, 90 drafts) = 0.12 -- High-draft player underperformed -- field took the loss equally
  - L. Geiselsöder (POR, 0.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - L. Brown (SEA, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-05-20

**Players**: 15 HV
 | **Score range**: 0.81 -- 5.32 (median 3.35)

**Leaderboard**: top score 53.93, floor 53.56, median 53.62

**Winner** (score 53.93):
  - C. Clark (2x) = 10.63
  - A. Wilson (1.8x) = 9.09
  - R. Howard (2.7x) = 12.90
  - K. Mitchell (2.2x) = 7.36
  - J. Loyd (4.2x) = 13.94
  - **Game stack**: team 3: 2 players, team 1: 2 players

**Field ownership** (top-20 entries):
  - C. Clark (1.8x/2x): 20/20 = 100%, avg 9.99
  - A. Wilson (1.8x/2x): 20/20 = 100%, avg 9.69
  - R. Howard (2.5x/2.7x): 20/20 = 100%, avg 12.23
  - J. Loyd (4.4x/4.6x/4.2x): 20/20 = 100%, avg 14.04
  - B. Griner (1.9x/2.1x): 11/20 = 55%, avg 7.94
  - K. Mitchell (2.4x/2x/2.2x): 9/20 = 45%, avg 7.44

### Outcome Classification

**(A) Correctly priced** (15 players):
  - J. Loyd (LVA, 3.0x, 118 drafts) = 3.32 -- High-draft player delivered as expected
  - R. Howard (ATL, 1.1x, 111 drafts) = 4.78 -- High-draft player delivered as expected
  - C. Clark (IND, 0.0x, 4100 drafts) = 5.32 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 4800 drafts) = 5.05 -- High-draft player delivered as expected
  - B. Griner (CON, 0.5x, 186 drafts) = 3.81 -- High-draft player delivered as expected
  - K. Mitchell (IND, 0.8x, 138 drafts) = 3.35 -- High-draft player delivered as expected
  - A. Boston (IND, 0.0x, 240 drafts) = 4.67 -- High-draft player delivered as expected
  - B. Jones (ATL, 0.2x, 130 drafts) = 4.09 -- High-draft player delivered as expected
  - C. Gray (LVA, 1.3x, 142 drafts) = 2.5 -- Outcome roughly matched draft position and signals
  - A. Gray (ATL, 0.0x, 244 drafts) = 3.46 -- High-draft player delivered as expected
  - N. Coffey (MIN, 2.9x, 2 drafts) = 1.3 -- Low-draft player correctly faded by the field
  - K. Bell (LVA, 3.0x, 3 drafts) = 1.2 -- Low-draft player correctly faded by the field
  - K. Stokes (GSV, 3.0x, 2 drafts) = 1.17 -- Low-draft player correctly faded by the field
  - J. Young (LVA, 0.9x, 149 drafts) = 1.89 -- Outcome roughly matched draft position and signals
  - M. Caldwell (MIN, 3.0x, 2 drafts) = 0.81 -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-05-21

**Players**: 20 HV
 | **Score range**: 1.33 -- 5.12 (median 3.18)

**Leaderboard**: top score 52.49, floor 50.71, median 50.71

**Winner** (score 52.49):
  - P. Bueckers (2.6x) = 9.34
  - N. Collier (1.8x) = 8.72
  - A. Ogunbowale (3.7x) = 12.63
  - D. Carrington (3.9x) = 6.24
  - V. Burton (3.5999999999999996x) = 15.56
  - **Game stack**: team 12: 2 players

**Field ownership** (top-20 entries):
  - N. Collier (1.8x/2x): 20/20 = 100%, avg 9.65
  - A. Ogunbowale (3.7x/3.9x): 20/20 = 100%, avg 13.21
  - K. Thornton (4.3x/4.1x/3.9x): 19/20 = 95%, avg 13.45
  - S. Dolson (4.2x): 13/20 = 65%, avg 6.60
  - S. Whitcomb (4.2x): 13/20 = 65%, avg 7.43
  - D. Carrington (4.1x/3.9x): 4/20 = 20%, avg 6.48
  - N. Smith (4.1x/3.9x): 4/20 = 20%, avg 8.23
  - P. Bueckers (2.4x/2.6x): 2/20 = 10%, avg 8.98

### Outcome Classification

**(A) Correctly priced** (19 players):
  - K. Thornton (GSV, 2.7x, 16 drafts) = 3.18 -- Mid-draft player with mid outcome -- no edge either way
  - A. Ogunbowale (DAL, 2.1x, 205 drafts) = 3.41 -- High-draft player delivered as expected
  - N. Hiedeman (SEA, 2.7x, 2 drafts) = 2.49 -- Outcome roughly matched draft position and signals
  - A. Stevens (CHI, 0.1x, 275 drafts) = 5.12 -- High-draft player delivered as expected
  - M. Akoa Makani (PHO, 3.0x, 2 drafts) = 2.03 -- Outcome roughly matched draft position and signals
  - B. Sykes (TOR, 0.0x, 671 drafts) = 4.91 -- High-draft player delivered as expected
  - N. Smith (LVA, 2.7x, 3 drafts) = 2.08 -- Outcome roughly matched draft position and signals
  - N. Collier (MIN, 0.0x, 4500 drafts) = 4.85 -- High-draft player delivered as expected
  - P. Bueckers (DAL, 0.6x, 1000 drafts) = 3.59 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.1x, 520 drafts) = 4.22 -- High-draft player delivered as expected
  - S. Sabally (NYL, 0.0x, 477 drafts) = 4.42 -- High-draft player delivered as expected
  - S. Whitcomb (PHO, 3.0x, 3 drafts) = 1.77 -- Outcome roughly matched draft position and signals
  - B. Carleton (POR, 1.3x, 145 drafts) = 2.47 -- Outcome roughly matched draft position and signals
  - K. Plum (LAS, 0.0x, 2500 drafts) = 3.97 -- High-draft player delivered as expected
  - M. Billings (IND, 3.0x, 8 drafts) = 1.58 -- Outcome roughly matched draft position and signals
  - S. Dolson (SEA, 2.8x, 51 drafts) = 1.57 -- Outcome roughly matched draft position and signals
  - M. Hines-Allen (IND, 1.5x, 117 drafts) = 2.08 -- Outcome roughly matched draft position and signals
  - D. Carrington (CHI, 2.5x, 15 drafts) = 1.6 -- Mid-draft player with mid outcome -- no edge either way
  - K. Samuelson (POR, 3.0x, 6 drafts) = 1.33 -- Low-draft player correctly faded by the field

**(C) Unknowable / winners' edge** (1 players):
  - V. Burton (GSV, 2.4x, 1 drafts) = 4.32 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-05-22

**Players**: 20 HV
 | **Score range**: 1.12 -- 4.70 (median 2.12)

**Leaderboard**: top score 52.14, floor 47.43, median 49.34

**Winner** (score 52.14):
  - N. Sabally (4x) = 6.07
  - N. Howard (4x) = 18.79
  - S. Ionescu (2.8x) = 8.76
  - L. Hull (3.5x) = 9.07
  - K. Burke (2.4x) = 9.45

**Field ownership** (top-20 entries):
  - N. Howard (4x/4.2x/3.4x/3.8x/3.6x): 20/20 = 100%, avg 18.09
  - S. Ionescu (3x/2.8x/2.6x/2.4x/3.2x): 14/20 = 70%, avg 9.03
  - L. Hull (3.5x/4.1x/3.7x/3.9x/3.3x): 12/20 = 60%, avg 9.89
  - K. Burke (2.4x/3.2x/2.6x/2.8x): 10/20 = 50%, avg 10.79
  - T. Paopao (4.8x/4.6x/4.2x/4.4x/5x): 8/20 = 40%, avg 7.85
  - C. Vandersloot (4.1x/3.7x/3.9x): 5/20 = 25%, avg 9.16
  - A. Reese (3.2x/3x/3.6x): 5/20 = 25%, avg 3.34
  - R. Howard (2.1x/1.5x/2.3x): 4/20 = 20%, avg 7.91

### Outcome Classification

**(A) Correctly priced** (20 players):
  - N. Howard (MIN, 2.2x, 126 drafts) = 4.7 -- High-draft player delivered as expected
  - K. Burke (CON, 1.2x, 99 drafts) = 3.94 -- High-draft player delivered as expected
  - L. Hull (IND, 2.1x, 91 drafts) = 2.59 -- Outcome roughly matched draft position and signals
  - E. Williams (CHI, 3.0x, 10 drafts) = 2.12 -- Mid-draft player with mid outcome -- no edge either way
  - C. Vandersloot (CHI, 2.5x, 13 drafts) = 2.35 -- Mid-draft player with mid outcome -- no edge either way
  - R. Banham (CHI, 3.0x, 10 drafts) = 2.08 -- Mid-draft player with mid outcome -- no edge either way
  - S. Ionescu (NYL, 1.2x, 690 drafts) = 3.13 -- High-draft player delivered as expected
  - R. Howard (ATL, 0.3x, 152 drafts) = 3.95 -- High-draft player delivered as expected
  - N. Cloud (CHI, 0.0x, 302 drafts) = 4.44 -- High-draft player delivered as expected
  - T. Paopao (ATL, 3.0x, 85 drafts) = 1.76 -- Outcome roughly matched draft position and signals
  - B. Jones (ATL, 0.2x, 127 drafts) = 3.75 -- High-draft player delivered as expected
  - R. Gardner (NYL, 3.0x, 7 drafts) = 1.59 -- Outcome roughly matched draft position and signals
  - N. Coffey (MIN, 2.9x, 72 drafts) = 1.47 -- High-draft player underperformed -- field took the loss equally
  - H. Van Lith (CON, 3.0x, 54 drafts) = 1.36 -- High-draft player underperformed -- field took the loss equally
  - D. Dantas (IND, 3.0x, 1 drafts) = 1.26 -- Low-draft player correctly faded by the field
  - N. Sabally (TOR, 2.0x, 14 drafts) = 1.52 -- Mid-draft player with mid outcome -- no edge either way
  - R. Allen (NYL, 3.0x, 10 drafts) = 1.12 -- Mid-draft player with mid outcome -- no edge either way
  - L. Fiebich (NYL, 2.8x, 14 drafts) = 1.16 -- Mid-draft player with mid outcome -- no edge either way
  - J. Jones (NYL, 0.1x, 177 drafts) = 2.41 -- Outcome roughly matched draft position and signals
  - K. Mitchell (IND, 0.6x, 109 drafts) = 1.93 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-05-23

**Players**: 19 HV
 | **Score range**: 2.01 -- 5.96 (median 3.49)

**Leaderboard**: top score 65.25, floor 61.85, median 61.85

**Winner** (score 65.25):
  - S. Dolson (4.6x) = 12.94
  - S. Sutton (4.8x) = 7.62
  - M. Akoa Makani (4.4x) = 12.17
  - M. Mabrey (4.4x) = 17.86
  - J. Salaün (4.2x) = 14.66

**Field ownership** (top-20 entries):
  - M. Mabrey (4.4x/4.6x/4.2x): 20/20 = 100%, avg 17.90
  - J. Salaün (4.4x/4.6x/4.2x): 20/20 = 100%, avg 15.63
  - N. Collier (1.8x/2x): 19/20 = 95%, avg 11.73
  - S. Barker (4.2x): 13/20 = 65%, avg 8.60
  - N. Hiedeman (3.7x): 12/20 = 60%, avg 7.43
  - A. Wilson (1.8x/2x): 6/20 = 30%, avg 8.66
  - J. Young (2.4x/2.8x): 4/20 = 20%, avg 11.60
  - S. Dolson (4x/4.6x): 2/20 = 10%, avg 12.10

### Outcome Classification

**(A) Correctly priced** (16 players):
  - M. Mabrey (TOR, 3.0x, 76 drafts) = 4.06 -- High-draft player delivered as expected
  - J. Young (LVA, 1.2x, 279 drafts) = 4.3 -- High-draft player delivered as expected
  - S. Dolson (SEA, 2.6x, 9 drafts) = 2.81 -- Outcome roughly matched draft position and signals
  - S. Diggins (CHI, 0.2x, 251 drafts) = 5.87 -- High-draft player delivered as expected
  - M. Akoa Makani (PHO, 2.8x, 1 drafts) = 2.77 -- Outcome roughly matched draft position and signals
  - N. Ogwumike (LAS, 0.4x, 255 drafts) = 4.98 -- High-draft player delivered as expected
  - N. Collier (MIN, 0.0x, 1800 drafts) = 5.96 -- High-draft player delivered as expected
  - K. Iriafen (WAS, 0.8x, 195 drafts) = 3.77 -- High-draft player delivered as expected
  - D. Hamby (LAS, 0.4x, 224 drafts) = 4.39 -- High-draft player delivered as expected
  - S. Barker (POR, 3.0x, 8 drafts) = 2.05 -- Outcome roughly matched draft position and signals
  - S. Citron (WAS, 0.8x, 198 drafts) = 3.37 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 5700 drafts) = 4.56 -- High-draft player delivered as expected
  - K. Thornton (GSV, 1.1x, 3 drafts) = 2.82 -- Outcome roughly matched draft position and signals
  - J. Loyd (LVA, 1.1x, 69 drafts) = 2.8 -- Outcome roughly matched draft position and signals
  - O. Nelson-Ododa (CON, 1.2x, 7 drafts) = 2.49 -- Outcome roughly matched draft position and signals
  - N. Hiedeman (SEA, 1.9x, 5 drafts) = 2.01 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (3 players):
  - J. Salaün (GSV, 3.0x, 4 drafts) = 3.49 -- Above-expectation outcome, ambiguous whether knowable
  - S. Rivers (CON, 1.9x, 1 drafts) = 3.74 -- Above-expectation outcome, ambiguous whether knowable
  - C. Leite (POR, 1.3x, 1 drafts) = 3.4 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 3 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-05-24

**Players**: 19 HV
 | **Score range**: 1.48 -- 6.36 (median 2.66)

**Leaderboard**: top score 55.50, floor 49.26, median 50.15

**Winner** (score 55.50):
  - A. Boston (2.2x) = 13.99
  - S. Ionescu (2.6x) = 13.38
  - J. Jones (2.1x) = 11.71
  - A. Gray (1.5999999999999999x) = 9.77
  - L. Hull (2.7x) = 6.64
  - **Game stack**: team 3: 2 players, team 4: 2 players

**Field ownership** (top-20 entries):
  - S. Ionescu (2.8x/2.6x/2.4x/2x/2.2x): 18/20 = 90%, avg 12.64
  - A. Gray (1.6x/1.4x/2x/1.8x/2.2x): 18/20 = 90%, avg 10.66
  - A. Boston (1.6x/1.8x/2x/2.2x): 17/20 = 85%, avg 12.27
  - J. Jones (1.9x/2.3x/2.1x/1.7x/2.5x): 13/20 = 65%, avg 12.23
  - K. Mitchell (2.4x/2x/2.8x): 8/20 = 40%, avg 7.29
  - L. Hull (3.1x/2.9x/2.7x/3.5x): 5/20 = 25%, avg 7.33
  - N. Cloud (1.2x/2x/1.8x): 5/20 = 25%, avg 8.78
  - N. Smith (3.5x/3.7x/3.3x): 4/20 = 20%, avg 7.23

### Outcome Classification

**(A) Correctly priced** (19 players):
  - S. Ionescu (NYL, 0.8x, 348 drafts) = 5.15 -- High-draft player delivered as expected
  - A. Boston (IND, 0.2x, 167 drafts) = 6.36 -- High-draft player delivered as expected
  - J. Jones (NYL, 0.5x, 92 drafts) = 5.58 -- High-draft player delivered as expected
  - A. Gray (ATL, 0.2x, 497 drafts) = 6.11 -- High-draft player delivered as expected
  - T. Harris (IND, 3.0x, 33 drafts) = 1.98 -- Mid-draft player with mid outcome -- no edge either way
  - N. Cloud (CHI, 0.0x, 359 drafts) = 4.88 -- High-draft player delivered as expected
  - M. Siegrist (DAL, 2.2x, 100 drafts) = 2.24 -- Outcome roughly matched draft position and signals
  - D. Bonner (PHO, 3.0x, 6 drafts) = 1.82 -- Outcome roughly matched draft position and signals
  - K. Mitchell (IND, 0.8x, 79 drafts) = 3.17 -- High-draft player delivered as expected
  - N. Coffey (MIN, 2.7x, 49 drafts) = 1.88 -- Mid-draft player with mid outcome -- no edge either way
  - L. Hull (IND, 1.5x, 92 drafts) = 2.46 -- Outcome roughly matched draft position and signals
  - N. Smith (LVA, 2.1x, 139 drafts) = 2.06 -- Outcome roughly matched draft position and signals
  - B. Stewart (NYL, 0.3x, 541 drafts) = 3.54 -- High-draft player delivered as expected
  - K. Charles (GSV, 3.0x, 29 drafts) = 1.6 -- Mid-draft player with mid outcome -- no edge either way
  - B. Jones (ATL, 0.2x, 450 drafts) = 3.58 -- High-draft player delivered as expected
  - M. Caldwell (MIN, 3.0x, 40 drafts) = 1.48 -- Mid-draft player with mid outcome -- no edge either way
  - R. Howard (ATL, 0.2x, 440 drafts) = 3.32 -- High-draft player delivered as expected
  - P. Bueckers (DAL, 0.5x, 986 drafts) = 2.66 -- Outcome roughly matched draft position and signals
  - B. Griner (CON, 0.9x, 290 drafts) = 2.19 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-05-25

**Players**: 19 HV
 | **Score range**: 1.83 -- 5.99 (median 3.15)

**Leaderboard**: top score 63.21, floor 59.13, median 59.58

**Winner** (score 63.21):
  - A. Reese (4.4x) = 12.69
  - N. Ogwumike (2x) = 11.49
  - E. Williams (4x) = 7.90
  - A. Clark (4.4x) = 8.48
  - E. Wheeler (4.2x) = 22.65
  - **Game stack**: team 9: 2 players

**Field ownership** (top-20 entries):
  - A. Reese (4.4x/4x/3.8x/3.6x): 20/20 = 100%, avg 11.51
  - E. Wheeler (4.4x/4.2x): 20/20 = 100%, avg 23.62
  - N. Ogwumike (2x/2.2x): 19/20 = 95%, avg 11.55
  - A. Gray (2x): 17/20 = 85%, avg 8.02
  - S. Barker (4.2x): 17/20 = 85%, avg 4.81
  - A. Wilson (1.8x/2x): 2/20 = 10%, avg 5.68
  - E. Williams (4x): 1/20 = 5%, avg 7.90
  - A. Clark (4.4x): 1/20 = 5%, avg 8.48

### Outcome Classification

**(A) Correctly priced** (16 players):
  - A. Reese (ATL, 2.4x, 625 drafts) = 2.88 -- Outcome roughly matched draft position and signals
  - N. Ogwumike (LAS, 0.2x, 238 drafts) = 5.75 -- High-draft player delivered as expected
  - O. Sims (DAL, 1.7x, 26 drafts) = 3.35 -- Mid-draft player with mid outcome -- no edge either way
  - A. Stevens (CHI, 0.2x, 176 drafts) = 5.58 -- High-draft player delivered as expected
  - K. Plum (LAS, 0.0x, 1000 drafts) = 5.99 -- High-draft player delivered as expected
  - K. Cardoso (CHI, 2.9x, 7 drafts) = 2.35 -- Outcome roughly matched draft position and signals
  - N. Hillmon (ATL, 3.0x, 1 drafts) = 2.59 -- Outcome roughly matched draft position and signals
  - M. Akoa Makani (PHO, 1.7x, 2 drafts) = 2.76 -- Outcome roughly matched draft position and signals
  - D. Hamby (LAS, 0.2x, 205 drafts) = 4.6 -- High-draft player delivered as expected
  - A. Clark (DAL, 3.0x, 2 drafts) = 1.93 -- Outcome roughly matched draft position and signals
  - J. Loyd (LVA, 1.0x, 62 drafts) = 3.15 -- High-draft player delivered as expected
  - K. Westbeld (PHO, 1.9x, 7 drafts) = 2.4 -- Outcome roughly matched draft position and signals
  - A. Gray (ATL, 0.0x, 448 drafts) = 4.01 -- High-draft player delivered as expected
  - M. Mabrey (TOR, 1.3x, 35 drafts) = 2.61 -- Mid-draft player with mid outcome -- no edge either way
  - E. Williams (CHI, 2.4x, 3 drafts) = 1.98 -- Outcome roughly matched draft position and signals
  - S. Whitcomb (PHO, 2.4x, 1 drafts) = 1.83 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (3 players):
  - E. Wheeler (LAS, 3.0x, 5 drafts) = 5.39 -- Above-expectation outcome, ambiguous whether knowable
  - N. Coffey (MIN, 2.4x, 8 drafts) = 3.71 -- Above-expectation outcome, ambiguous whether knowable
  - M. Caldwell (MIN, 3.0x, 2 drafts) = 3.16 -- High-boost low-draft player who overperformed

**Takeaway**: 3 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-05-27

**Players**: 16 HV
 | **Score range**: 2.53 -- 6.11 (median 4.13)

**Leaderboard**: top score 60.84, floor 55.17, median 56.06

**Winner** (score 60.84):
  - P. Bueckers (2.5x) = 12.67
  - T. Charles (2.8x) = 11.26
  - A. Ogunbowale (3.1x) = 13.33
  - A. Reese (2.9x) = 12.13
  - K. Cardoso (3.2x) = 11.45
  - **Game stack**: team 12: 2 players

**Field ownership** (top-20 entries):
  - A. Reese (3.5x/3.1x/2.7x/2.9x/3.3x): 19/20 = 95%, avg 12.70
  - A. Ogunbowale (3.5x/2.7x/3.1x/2.9x/3.3x): 14/20 = 70%, avg 13.08
  - P. Bueckers (1.9x/2.3x/2.1x/1.7x/2.5x): 9/20 = 45%, avg 11.21
  - N. Collier (2x): 8/20 = 40%, avg 9.33
  - K. Cardoso (3.2x/4x/3.8x/3.4x): 5/20 = 25%, avg 12.59
  - D. Carrington (4.5x/3.7x/3.9x): 5/20 = 25%, avg 10.65
  - C. Vandersloot (2.9x/2.7x/3.3x): 5/20 = 25%, avg 11.66
  - D. Hamby (1.6x/1.8x/2x/2.2x): 5/20 = 25%, avg 11.15

### Outcome Classification

**(A) Correctly priced** (15 players):
  - A. Ogunbowale (DAL, 1.5x, 75 drafts) = 4.3 -- High-draft player delivered as expected
  - A. Reese (ATL, 1.5x, 684 drafts) = 4.18 -- High-draft player delivered as expected
  - K. Cardoso (CHI, 2.0x, 10 drafts) = 3.58 -- Mid-draft player with mid outcome -- no edge either way
  - J. Sheldon (CHI, 3.0x, 1 drafts) = 2.86 -- Outcome roughly matched draft position and signals
  - A. Thomas (PHO, 0.3x, 372 drafts) = 6.11 -- High-draft player delivered as expected
  - C. Vandersloot (CHI, 1.5x, 35 drafts) = 3.96 -- Mid-draft player with mid outcome -- no edge either way
  - N. Hillmon (ATL, 3.0x, 6 drafts) = 2.72 -- Outcome roughly matched draft position and signals
  - D. Hamby (LAS, 0.2x, 272 drafts) = 5.81 -- High-draft player delivered as expected
  - P. Bueckers (DAL, 0.5x, 774 drafts) = 5.07 -- High-draft player delivered as expected
  - R. Howard (ATL, 0.4x, 280 drafts) = 5.03 -- High-draft player delivered as expected
  - D. Carrington (CHI, 2.5x, 17 drafts) = 2.68 -- Mid-draft player with mid outcome -- no edge either way
  - G. Williams (GSV, 0.7x, 185 drafts) = 4.13 -- High-draft player delivered as expected
  - K. Nurse (TOR, 3.0x, 1 drafts) = 2.53 -- Outcome roughly matched draft position and signals
  - B. Stewart (NYL, 0.3x, 639 drafts) = 4.69 -- High-draft player delivered as expected
  - K. Westbeld (PHO, 1.6x, 20 drafts) = 2.95 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (1 players):
  - A. Atkins (LAS, 1.9x, 3 drafts) = 3.51 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-05-28

**Players**: 18 HV
 | **Score range**: 0.00 -- 3.66 (median 1.58)

**Leaderboard**: top score 45.59, floor 41.81, median 42.55

**Winner** (score 45.59):
  - S. Citron (2.8x) = 6.48
  - S. Colson (4.8x) = 5.04
  - E. Engstler (4.6x) = 7.41
  - D. Bonner (4.4x) = 16.09
  - S. Austin (4.2x) = 10.57
  - **Game stack**: team 7: 2 players

**Field ownership** (top-20 entries):
  - D. Bonner (4.8x/4.6x/4.2x/4.4x/5x): 20/20 = 100%, avg 16.93
  - K. Iriafen (2.3x/2.7x/2.9x/2.1x/2.5x): 13/20 = 65%, avg 8.01
  - E. Engstler (4.8x/4.6x/4.2x/4.4x/5x): 11/20 = 55%, avg 7.32
  - S. Austin (4.4x/4.2x): 8/20 = 40%, avg 10.70
  - K. Mitchell (1.9x/2.3x/2.7x/2.1x/2.5x): 8/20 = 40%, avg 6.09
  - S. Citron (2.8x/2.6x/2.4x/2x/2.2x): 6/20 = 30%, avg 5.63
  - S. Colson (4.4x/4.6x/4.2x/4.8x): 6/20 = 30%, avg 4.73
  - B. Sykes (1.9x/1.5x): 5/20 = 25%, avg 5.42

### Outcome Classification

**(A) Correctly priced** (18 players):
  - D. Bonner (PHO, 3.0x, 207 drafts) = 3.66 -- High-draft player delivered as expected
  - S. Austin (WAS, 3.0x, 9 drafts) = 2.52 -- Outcome roughly matched draft position and signals
  - K. Iriafen (WAS, 0.9x, 481 drafts) = 3.07 -- High-draft player delivered as expected
  - E. Engstler (POR, 3.0x, 86 drafts) = 1.61 -- Outcome roughly matched draft position and signals
  - K. Mitchell (IND, 0.7x, 935 drafts) = 2.62 -- Outcome roughly matched draft position and signals
  - D. Dantas (IND, 3.0x, 108 drafts) = 1.32 -- High-draft player underperformed -- field took the loss equally
  - S. Citron (WAS, 0.8x, 412 drafts) = 2.31 -- Outcome roughly matched draft position and signals
  - A. Boston (IND, 0.0x, 5300 drafts) = 3.23 -- High-draft player delivered as expected
  - B. Sykes (TOR, 0.1x, 1600 drafts) = 2.98 -- Outcome roughly matched draft position and signals
  - L. Hull (IND, 1.4x, 391 drafts) = 1.58 -- Outcome roughly matched draft position and signals
  - L. Olsen (WAS, 3.0x, 107 drafts) = 1.07 -- High-draft player underperformed -- field took the loss equally
  - J. Melbourne (SEA, 1.5x, 160 drafts) = 1.44 -- High-draft player underperformed -- field took the loss equally
  - N. Howard (MIN, 1.0x, 342 drafts) = 0.64 -- High-draft player underperformed -- field took the loss equally
  - A. Edwards (CON, 2.8x, 13 drafts) = 0.4 -- Mid-draft player with mid outcome -- no edge either way
  - S. Cunningham (IND, 3.0x, 418 drafts) = 0.37 -- High-draft player underperformed -- field took the loss equally
  - S. Dolson (SEA, 2.3x, 157 drafts) = 0.35 -- High-draft player underperformed -- field took the loss equally
  - B. Turner (LVA, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - S. Koné (ATL, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-05-29

**Players**: 18 HV
 | **Score range**: 1.20 -- 6.80 (median 2.66)

**Leaderboard**: top score 62.26, floor 59.87, median 60.18

**Winner** (score 62.26):
  - B. Stewart (2.2x) = 11.99
  - A. Ogunbowale (2.8x) = 19.03
  - M. Hines-Allen (3.4000000000000004x) = 8.53
  - J. Salaün (3.0999999999999996x) = 10.77
  - K. Cardoso (2.5x) = 11.94

**Field ownership** (top-20 entries):
  - A. Ogunbowale (2.4x/2.8x/3x/2.6x): 20/20 = 100%, avg 18.96
  - K. Cardoso (3.1x/2.7x/2.9x/2.5x/3.3x): 20/20 = 100%, avg 13.47
  - B. Stewart (1.6x/1.4x/2x/1.8x/2.2x): 16/20 = 80%, avg 10.70
  - P. Bueckers (1.9x/2.3x/1.5x/2.1x/1.7x): 14/20 = 70%, avg 8.60
  - A. Atkins (2.9x/3.1x/2.5x/2.7x): 9/20 = 45%, avg 8.95
  - S. Ionescu (1.9x/2.3x/2.1x/1.7x/2.5x): 9/20 = 45%, avg 9.78
  - M. Hines-Allen (3.2x/3.4x/3x): 5/20 = 25%, avg 7.83
  - C. Vandersloot (2.4x/2.8x/2.2x): 5/20 = 25%, avg 8.31

### Outcome Classification

**(A) Correctly priced** (17 players):
  - A. Ogunbowale (DAL, 1.0x, 482 drafts) = 6.8 -- High-draft player delivered as expected
  - K. Cardoso (CHI, 1.3x, 182 drafts) = 4.78 -- High-draft player delivered as expected
  - R. Allen (NYL, 3.0x, 18 drafts) = 2.44 -- Mid-draft player with mid outcome -- no edge either way
  - B. Stewart (NYL, 0.2x, 2800 drafts) = 5.45 -- High-draft player delivered as expected
  - M. Billings (IND, 2.5x, 2 drafts) = 2.66 -- Outcome roughly matched draft position and signals
  - S. Ionescu (NYL, 0.5x, 870 drafts) = 4.51 -- High-draft player delivered as expected
  - A. Atkins (LAS, 1.3x, 131 drafts) = 3.34 -- High-draft player delivered as expected
  - P. Bueckers (DAL, 0.3x, 3100 drafts) = 4.59 -- High-draft player delivered as expected
  - C. Vandersloot (CHI, 1.0x, 139 drafts) = 3.46 -- High-draft player delivered as expected
  - M. Onyenwere (WAS, 3.0x, 1 drafts) = 2.03 -- Outcome roughly matched draft position and signals
  - M. Hines-Allen (IND, 1.8x, 129 drafts) = 2.51 -- Outcome roughly matched draft position and signals
  - D. Carrington (CHI, 1.9x, 189 drafts) = 2.23 -- Outcome roughly matched draft position and signals
  - K. Burke (CON, 1.3x, 81 drafts) = 2.51 -- Outcome roughly matched draft position and signals
  - A. Reese (ATL, 0.9x, 630 drafts) = 2.27 -- Outcome roughly matched draft position and signals
  - S. Talbot (LVA, 3.0x, 1 drafts) = 1.27 -- Low-draft player correctly faded by the field
  - V. Burton (GSV, 0.7x, 159 drafts) = 2.31 -- Outcome roughly matched draft position and signals
  - K. Nurse (TOR, 3.0x, 23 drafts) = 1.2 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (1 players):
  - J. Salaün (GSV, 1.7x, 4 drafts) = 3.47 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-05-30

**Players**: 18 HV
 | **Score range**: 2.06 -- 8.77 (median 4.13)

**Leaderboard**: top score 61.51, floor 55.47, median 57.21

**Winner** (score 61.51):
  - A. Wilson (2x) = 17.54
  - S. Ionescu (2.2x) = 11.54
  - C. Gray (2.9000000000000004x) = 11.04
  - M. Mabrey (2.7x) = 15.36
  - D. Bonner (3.0999999999999996x) = 6.03
  - **Game stack**: team 1: 2 players

**Field ownership** (top-20 entries):
  - A. Wilson (1.2x/2x): 19/20 = 95%, avg 17.17
  - M. Mabrey (2.9x/3.1x/2.5x/2.7x): 14/20 = 70%, avg 16.01
  - S. Ionescu (1.6x/2x/2.2x): 10/20 = 50%, avg 10.80
  - J. Young (2.4x/2x/2.2x/2.6x): 9/20 = 45%, avg 10.48
  - C. Gray (3.1x/2.7x/2.9x/2.5x/3.3x): 6/20 = 30%, avg 11.04
  - D. Bonner (3.3x/3.7x/3.5x/3.1x): 6/20 = 30%, avg 6.48
  - R. Howard (2.1x/1.5x/1.7x): 5/20 = 25%, avg 10.49
  - S. Sabally (1.5x/2.1x/1.7x/2.3x): 5/20 = 25%, avg 9.62

### Outcome Classification

**(A) Correctly priced** (15 players):
  - A. Wilson (LVA, 0.0x, 3700 drafts) = 8.77 -- High-draft player delivered as expected
  - N. Hillmon (ATL, 2.8x, 4 drafts) = 2.92 -- Outcome roughly matched draft position and signals
  - S. Ionescu (NYL, 0.4x, 538 drafts) = 5.24 -- High-draft player delivered as expected
  - R. Howard (ATL, 0.3x, 208 drafts) = 5.9 -- High-draft player delivered as expected
  - J. Young (LVA, 0.8x, 201 drafts) = 4.58 -- High-draft player delivered as expected
  - C. Gray (LVA, 1.3x, 205 drafts) = 3.81 -- High-draft player delivered as expected
  - N. Hiedeman (SEA, 2.3x, 2 drafts) = 2.83 -- Outcome roughly matched draft position and signals
  - S. Sabally (NYL, 0.3x, 206 drafts) = 5.17 -- High-draft player delivered as expected
  - S. Rivers (CON, 1.9x, 1 drafts) = 2.97 -- Outcome roughly matched draft position and signals
  - J. Jones (NYL, 0.2x, 11 drafts) = 4.9 -- Mid-draft player with mid outcome -- no edge either way
  - A. Boston (IND, 0.1x, 326 drafts) = 5.12 -- High-draft player delivered as expected
  - A. Smith (DAL, 0.6x, 42 drafts) = 4.13 -- Mid-draft player with mid outcome -- no edge either way
  - E. Wheeler (LAS, 1.4x, 2 drafts) = 2.92 -- Outcome roughly matched draft position and signals
  - K. Stokes (GSV, 3.0x, 4 drafts) = 2.06 -- Outcome roughly matched draft position and signals
  - K. McBride (MIN, 1.1x, 9 drafts) = 2.8 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (3 players):
  - M. Mabrey (TOR, 1.3x, 19 drafts) = 5.69 -- Above-expectation outcome, ambiguous whether knowable
  - S. Whitcomb (PHO, 2.8x, 5 drafts) = 3.57 -- Above-expectation outcome, ambiguous whether knowable
  - L. Fiebich (NYL, 2.7x, 7 drafts) = 3.0 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 3 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-05-31

**Players**: 19 HV
 | **Score range**: 0.18 -- 5.06 (median 1.51)

**Leaderboard**: top score 59.17, floor 53.31, median 54.71

**Winner** (score 59.17):
  - C. Vandersloot (2.8x) = 9.17
  - A. Atkins (2.8x) = 14.16
  - D. Carrington (3.4000000000000004x) = 12.57
  - M. Siegrist (3.4x) = 9.72
  - N. Smith (3.5999999999999996x) = 13.54
  - **Game stack**: team 8: 2 players

**Field ownership** (top-20 entries):
  - N. Smith (4x/4.2x/4.4x/3.8x/3.6x): 20/20 = 100%, avg 14.97
  - D. Carrington (3x/3.6x/3.2x/3.8x/3.4x): 19/20 = 95%, avg 12.42
  - A. Atkins (3x/2.8x/2.6x/2.4x/2.2x): 17/20 = 85%, avg 13.62
  - M. Siegrist (3.6x/4x/3.2x/3.8x/3.4x): 11/20 = 55%, avg 10.19
  - C. Vandersloot (2.4x/2.8x/2.6x/2x): 10/20 = 50%, avg 7.73
  - A. Reese (2.8x/3x): 7/20 = 35%, avg 7.94
  - A. Ogunbowale (2.3x/2.5x): 4/20 = 20%, avg 4.37
  - K. Nurse (4.6x/4.2x): 4/20 = 20%, avg 8.01

### Outcome Classification

**(A) Correctly priced** (19 players):
  - N. Smith (LVA, 2.4x, 128 drafts) = 3.76 -- High-draft player delivered as expected
  - A. Atkins (LAS, 1.0x, 301 drafts) = 5.06 -- High-draft player delivered as expected
  - D. Carrington (CHI, 1.8x, 373 drafts) = 3.7 -- High-draft player delivered as expected
  - M. Siegrist (DAL, 2.0x, 138 drafts) = 2.86 -- Outcome roughly matched draft position and signals
  - K. Nurse (TOR, 3.0x, 110 drafts) = 1.86 -- Outcome roughly matched draft position and signals
  - C. Vandersloot (CHI, 0.8x, 576 drafts) = 3.28 -- High-draft player delivered as expected
  - A. Reese (ATL, 1.0x, 1000 drafts) = 2.7 -- Outcome roughly matched draft position and signals
  - K. Charles (GSV, 3.0x, 75 drafts) = 1.51 -- Outcome roughly matched draft position and signals
  - E. Williams (CHI, 2.3x, 91 drafts) = 1.52 -- Outcome roughly matched draft position and signals
  - R. Allen (NYL, 2.9x, 92 drafts) = 1.18 -- High-draft player underperformed -- field took the loss equally
  - A. James (DAL, 3.0x, 75 drafts) = 1.09 -- High-draft player underperformed -- field took the loss equally
  - A. Ogunbowale (DAL, 0.5x, 5500 drafts) = 1.78 -- Outcome roughly matched draft position and signals
  - M. Onyenwere (WAS, 3.0x, 97 drafts) = 0.8 -- High-draft player underperformed -- field took the loss equally
  - H. Van Lith (CON, 3.0x, 370 drafts) = 0.69 -- High-draft player underperformed -- field took the loss equally
  - K. Cardoso (CHI, 0.8x, 650 drafts) = 1.2 -- High-draft player underperformed -- field took the loss equally
  - J. Quinerly (DAL, 3.0x, 4 drafts) = 0.64 -- Low-draft player correctly faded by the field
  - R. Banham (CHI, 3.0x, 76 drafts) = 0.51 -- High-draft player underperformed -- field took the loss equally
  - M. Hines-Allen (IND, 1.6x, 146 drafts) = 0.47 -- High-draft player underperformed -- field took the loss equally
  - L. Geiselsöder (POR, 3.0x, 2 drafts) = 0.18 -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-06-01

**Players**: 18 HV
 | **Score range**: 1.85 -- 6.63 (median 2.76)

**Leaderboard**: top score 58.96, floor 51.97, median 53.06

**Winner** (score 58.96):
  - N. Collier (2x) = 9.62
  - A. Wilson (1.8x) = 8.89
  - O. Sims (3.2x) = 21.23
  - B. Carleton (3.2x) = 8.18
  - D. Evans (4.2x) = 11.04
  - **Game stack**: team 1: 2 players

**Field ownership** (top-20 entries):
  - O. Sims (3x/2.8x/3.2x/3.6x/3.4x): 20/20 = 100%, avg 20.43
  - A. Wilson (1.6x/1.8x/2x/1.2x): 16/20 = 80%, avg 9.20
  - N. Collier (1.6x/1.8x/2x/1.4x): 11/20 = 55%, avg 9.10
  - S. Sabally (1.6x/2x/1.4x): 7/20 = 35%, avg 7.12
  - J. Loyd (2.4x/3x/2.2x/2.6x): 6/20 = 30%, avg 8.65
  - G. Williams (2.1x/2.3x/2.5x): 5/20 = 25%, avg 8.29
  - B. Carleton (3.2x/3x): 4/20 = 20%, avg 7.93
  - C. Williams (2x/2.2x): 4/20 = 20%, avg 8.41

### Outcome Classification

**(A) Correctly priced** (17 players):
  - M. Johannes (NYL, 2.7x, 4 drafts) = 2.8 -- Outcome roughly matched draft position and signals
  - D. Evans (LVA, 3.0x, 3 drafts) = 2.63 -- Outcome roughly matched draft position and signals
  - K. Martin (LAS, 3.0x, 19 drafts) = 2.35 -- Mid-draft player with mid outcome -- no edge either way
  - S. Barker (POR, 3.0x, 1 drafts) = 2.17 -- Outcome roughly matched draft position and signals
  - J. Loyd (LVA, 1.0x, 20 drafts) = 3.41 -- Mid-draft player with mid outcome -- no edge either way
  - K. Westbeld (PHO, 1.6x, 1 drafts) = 2.76 -- Outcome roughly matched draft position and signals
  - K. McBride (MIN, 0.9x, 58 drafts) = 3.42 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 4800 drafts) = 4.94 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.4x, 281 drafts) = 4.1 -- High-draft player delivered as expected
  - B. Carleton (POR, 1.8x, 27 drafts) = 2.56 -- Mid-draft player with mid outcome -- no edge either way
  - N. Collier (MIN, 0.0x, 2000 drafts) = 4.81 -- High-draft player delivered as expected
  - G. Williams (GSV, 0.7x, 178 drafts) = 3.54 -- High-draft player delivered as expected
  - M. Akoa Makani (PHO, 1.6x, 4 drafts) = 2.57 -- Outcome roughly matched draft position and signals
  - S. Whitcomb (PHO, 1.9x, 5 drafts) = 2.26 -- Outcome roughly matched draft position and signals
  - K. Thornton (GSV, 1.2x, 35 drafts) = 2.75 -- Mid-draft player with mid outcome -- no edge either way
  - J. Sheldon (CHI, 2.7x, 4 drafts) = 1.85 -- Outcome roughly matched draft position and signals
  - T. Hayes (GSV, 2.2x, 23 drafts) = 2.07 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (1 players):
  - O. Sims (DAL, 1.6x, 39 drafts) = 6.63 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-06-03

**Players**: 19 HV
 | **Score range**: 1.41 -- 4.38 (median 3.29)

**Leaderboard**: top score 53.83, floor 46.79, median 47.77

**Winner** (score 53.83):
  - K. Iriafen (2.8x) = 8.59
  - D. Carrington (3.2x) = 11.44
  - L. Hull (3x) = 9.86
  - M. Hines-Allen (3.3x) = 12.91
  - L. Held (3.8x) = 11.03
  - **Game stack**: team 3: 2 players

**Field ownership** (top-20 entries):
  - D. Carrington (3.2x/3x/3.4x/2.8x): 19/20 = 95%, avg 10.99
  - M. Hines-Allen (3.5x/3.1x/3.7x/3.9x/3.3x): 12/20 = 60%, avg 13.62
  - E. Magbegor (2.7x/3.1x/2.9x/2.5x/3.3x): 11/20 = 55%, avg 9.57
  - K. Mitchell (2.8x/2.6x/2.4x/2x/2.2x): 9/20 = 45%, avg 11.01
  - L. Hull (2.8x/3x/2.6x): 8/20 = 40%, avg 9.20
  - M. Siegrist (3.5x/3.1x/2.9x/3.7x/3.3x): 8/20 = 40%, avg 8.47
  - G. Williams (2.4x/2x/2.6x): 6/20 = 30%, avg 8.68
  - E. Wheeler (3x/2.8x/2.6x/3.2x/3.4x): 6/20 = 30%, avg 10.05

### Outcome Classification

**(A) Correctly priced** (19 players):
  - M. Hines-Allen (IND, 1.9x, 33 drafts) = 3.91 -- Mid-draft player with mid outcome -- no edge either way
  - L. Held (TOR, 2.6x, 7 drafts) = 2.9 -- Outcome roughly matched draft position and signals
  - K. Mitchell (IND, 0.8x, 263 drafts) = 4.38 -- High-draft player delivered as expected
  - D. Carrington (CHI, 1.4x, 354 drafts) = 3.57 -- High-draft player delivered as expected
  - E. Wheeler (LAS, 1.4x, 180 drafts) = 3.43 -- High-draft player delivered as expected
  - L. Hull (IND, 1.4x, 34 drafts) = 3.29 -- Mid-draft player with mid outcome -- no edge either way
  - E. Magbegor (SEA, 1.3x, 204 drafts) = 3.36 -- High-draft player delivered as expected
  - K. McBride (MIN, 0.7x, 20 drafts) = 3.67 -- Mid-draft player with mid outcome -- no edge either way
  - A. Smith (DAL, 0.6x, 243 drafts) = 3.73 -- High-draft player delivered as expected
  - S. Austin (WAS, 3.0x, 6 drafts) = 1.93 -- Outcome roughly matched draft position and signals
  - M. Siegrist (DAL, 1.7x, 38 drafts) = 2.61 -- Mid-draft player with mid outcome -- no edge either way
  - G. Williams (GSV, 0.6x, 343 drafts) = 3.57 -- High-draft player delivered as expected
  - K. Iriafen (WAS, 0.8x, 218 drafts) = 3.07 -- High-draft player delivered as expected
  - N. Hiedeman (SEA, 1.8x, 5 drafts) = 2.23 -- Outcome roughly matched draft position and signals
  - E. Engstler (POR, 3.0x, 1 drafts) = 1.66 -- Outcome roughly matched draft position and signals
  - L. Geiselsöder (POR, 3.0x, 1 drafts) = 1.59 -- Outcome roughly matched draft position and signals
  - N. Collier (MIN, 0.0x, 5800 drafts) = 3.65 -- High-draft player delivered as expected
  - D. Dantas (IND, 3.0x, 1 drafts) = 1.41 -- Low-draft player correctly faded by the field
  - B. Sykes (TOR, 0.3x, 362 drafts) = 3.04 -- High-draft player delivered as expected

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-06-05

**Players**: 16 HV
 | **Score range**: 1.32 -- 4.34 (median 2.73)

**Leaderboard**: top score 48.41, floor 43.84, median 45.77

**Winner** (score 48.41):
  - K. Iriafen (2.8x) = 8.77
  - K. Burke (3.6x) = 9.18
  - T. Fágbénlé (2.7x) = 9.63
  - L. Held (3.5x) = 11.28
  - J. Melbourne (3.5x) = 9.55
  - **Game stack**: team 16: 2 players

**Field ownership** (top-20 entries):
  - L. Held (3.5x/4.1x/3.7x/3.9x/3.3x): 20/20 = 100%, avg 11.70
  - T. Fágbénlé (2.3x/3.1x/2.7x/2.9x/2.5x): 17/20 = 85%, avg 9.34
  - K. Iriafen (2.4x/2.8x): 10/20 = 50%, avg 8.64
  - J. Melbourne (3.5x/3.7x/3.9x): 10/20 = 50%, avg 9.71
  - B. Stewart (1.8x/2x/2.2x): 9/20 = 45%, avg 8.59
  - K. Burke (3.2x/3.6x): 7/20 = 35%, avg 8.89
  - S. Sabally (1.9x/2.1x/2.3x): 7/20 = 35%, avg 7.67
  - S. Ionescu (1.6x/2x/1.4x/2.2x): 5/20 = 25%, avg 6.21

### Outcome Classification

**(A) Correctly priced** (16 players):
  - C. Zandalasini (GSV, 3.0x, 30 drafts) = 2.81 -- Mid-draft player with mid outcome -- no edge either way
  - L. Held (TOR, 2.1x, 177 drafts) = 3.22 -- High-draft player delivered as expected
  - S. Austin (WAS, 2.6x, 5 drafts) = 2.62 -- Outcome roughly matched draft position and signals
  - J. Melbourne (SEA, 2.3x, 132 drafts) = 2.73 -- Outcome roughly matched draft position and signals
  - T. Fágbénlé (TOR, 1.1x, 186 drafts) = 3.57 -- High-draft player delivered as expected
  - K. Burke (CON, 1.8x, 107 drafts) = 2.55 -- Outcome roughly matched draft position and signals
  - B. Stewart (NYL, 0.2x, 3100 drafts) = 4.34 -- High-draft player delivered as expected
  - K. Iriafen (WAS, 0.8x, 349 drafts) = 3.13 -- High-draft player delivered as expected
  - S. Sabally (NYL, 0.3x, 1400 drafts) = 3.7 -- High-draft player delivered as expected
  - I. Harrison (TOR, 2.3x, 1 drafts) = 1.86 -- Outcome roughly matched draft position and signals
  - K. Westbeld (PHO, 1.6x, 189 drafts) = 2.13 -- Outcome roughly matched draft position and signals
  - S. Ionescu (NYL, 0.2x, 2800 drafts) = 3.38 -- High-draft player delivered as expected
  - K. Martin (LAS, 3.0x, 66 drafts) = 1.41 -- High-draft player underperformed -- field took the loss equally
  - S. Citron (WAS, 1.1x, 222 drafts) = 2.15 -- Outcome roughly matched draft position and signals
  - R. Gardner (NYL, 3.0x, 4 drafts) = 1.32 -- Low-draft player correctly faded by the field
  - V. Burton (GSV, 0.7x, 293 drafts) = 2.26 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-06-06

**Players**: 16 HV
 | **Score range**: 1.24 -- 5.78 (median 3.21)

**Leaderboard**: top score 52.07, floor 52.07, median 52.07

**Winner** (score 52.07):
  - M. Mabrey (2.9x) = 16.77
  - D. Carrington (3x) = 4.78
  - R. Jackson (3.9x) = 6.01
  - N. Hillmon (3.6x) = 7.95
  - L. Geiselsöder (4.2x) = 16.57
  - **Game stack**: team 8: 2 players

**Field ownership** (top-20 entries):
  - M. Mabrey (2.9x): 20/20 = 100%, avg 16.77
  - D. Carrington (3x): 20/20 = 100%, avg 4.78
  - R. Jackson (3.9x): 20/20 = 100%, avg 6.01
  - N. Hillmon (3.6x): 20/20 = 100%, avg 7.95
  - L. Geiselsöder (4.2x): 20/20 = 100%, avg 16.57

### Outcome Classification

**(A) Correctly priced** (15 players):
  - M. Mabrey (TOR, 0.9x, 248 drafts) = 5.78 -- High-draft player delivered as expected
  - A. Stevens (CHI, 0.3x, 305 drafts) = 5.69 -- High-draft player delivered as expected
  - J. Quinerly (DAL, 3.0x, 2 drafts) = 2.55 -- Outcome roughly matched draft position and signals
  - S. Rivers (CON, 1.9x, 5 drafts) = 2.94 -- Outcome roughly matched draft position and signals
  - B. Griner (CON, 1.3x, 210 drafts) = 3.24 -- High-draft player delivered as expected
  - K. Charles (GSV, 3.0x, 41 drafts) = 1.95 -- Mid-draft player with mid outcome -- no edge either way
  - O. Sims (DAL, 0.9x, 251 drafts) = 3.21 -- High-draft player delivered as expected
  - N. Hillmon (ATL, 2.2x, 40 drafts) = 2.21 -- Mid-draft player with mid outcome -- no edge either way
  - K. Plum (LAS, 0.1x, 2700 drafts) = 4.11 -- High-draft player delivered as expected
  - D. Hamby (LAS, 0.2x, 614 drafts) = 3.86 -- High-draft player delivered as expected
  - R. Howard (ATL, 0.1x, 686 drafts) = 3.46 -- High-draft player delivered as expected
  - R. Jackson (CHI, 2.3x, 12 drafts) = 1.54 -- Mid-draft player with mid outcome -- no edge either way
  - S. Barker (POR, 3.0x, 48 drafts) = 1.24 -- Mid-draft player with mid outcome -- no edge either way
  - A. Gray (ATL, 0.0x, 3400 drafts) = 2.79 -- Outcome roughly matched draft position and signals
  - D. Carrington (CHI, 1.2x, 542 drafts) = 1.59 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - L. Geiselsöder (POR, 3.0x, 3 drafts) = 3.95 -- High-boost low-draft player who overperformed

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-06-07

**Players**: 17 HV
 | **Score range**: 1.61 -- 5.50 (median 2.71)

**Leaderboard**: top score 58.63, floor 44.69, median 45.69

**Winner** (score 58.63):
  - K. Thornton (3.3x) = 16.09
  - G. Williams (2.4x) = 13.19
  - M. Billings (4.1x) = 15.59
  - L. Held (3.2x) = 7.89
  - L. Hull (2.4x) = 5.86
  - **Game stack**: team 14: 2 players, team 3: 2 players

**Field ownership** (top-20 entries):
  - G. Williams (2.4x/2x/2.2x/2.6x): 19/20 = 95%, avg 12.67
  - L. Held (3x/3.2x/3.8x/3.6x/3.4x): 17/20 = 85%, avg 7.83
  - S. Diggins (1.9x/2.3x/2.1x/1.7x/2.5x): 16/20 = 80%, avg 9.98
  - N. Ogwumike (1.6x/2.4x/2x/1.8x/2.2x): 11/20 = 55%, avg 7.21
  - V. Burton (1.9x/2.3x/2.7x/2.1x/2.5x): 9/20 = 45%, avg 11.48
  - S. Sabally (1.9x/2.1x/1.7x/2.3x): 9/20 = 45%, avg 7.84
  - K. Thornton (3.1x/2.7x/3.3x): 3/20 = 15%, avg 14.79
  - M. Billings (4.1x/3.9x): 2/20 = 10%, avg 15.21

### Outcome Classification

**(A) Correctly priced** (15 players):
  - G. Williams (GSV, 0.6x, 311 drafts) = 5.5 -- High-draft player delivered as expected
  - V. Burton (GSV, 0.7x, 109 drafts) = 4.99 -- High-draft player delivered as expected
  - S. Diggins (CHI, 0.5x, 337 drafts) = 4.49 -- High-draft player delivered as expected
  - C. Zandalasini (GSV, 2.1x, 9 drafts) = 2.71 -- Outcome roughly matched draft position and signals
  - N. Howard (MIN, 1.6x, 51 drafts) = 2.83 -- Outcome roughly matched draft position and signals
  - K. Martin (LAS, 3.0x, 5 drafts) = 1.95 -- Outcome roughly matched draft position and signals
  - L. Held (TOR, 1.8x, 227 drafts) = 2.47 -- Outcome roughly matched draft position and signals
  - A. Nye (ATL, 3.0x, 1 drafts) = 1.91 -- Outcome roughly matched draft position and signals
  - S. Sabally (NYL, 0.3x, 846 drafts) = 3.82 -- High-draft player delivered as expected
  - N. Ogwumike (LAS, 0.4x, 449 drafts) = 3.6 -- High-draft player delivered as expected
  - L. Hull (IND, 1.2x, 152 drafts) = 2.44 -- Outcome roughly matched draft position and signals
  - D. Bonner (PHO, 2.1x, 11 drafts) = 1.77 -- Mid-draft player with mid outcome -- no edge either way
  - K. Mitchell (IND, 0.6x, 361 drafts) = 2.68 -- Outcome roughly matched draft position and signals
  - E. Williams (CHI, 2.3x, 1 drafts) = 1.61 -- Outcome roughly matched draft position and signals
  - E. Magbegor (SEA, 1.1x, 153 drafts) = 2.12 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (2 players):
  - M. Billings (IND, 2.5x, 1 drafts) = 3.8 -- High-boost low-draft player who overperformed
  - K. Thornton (GSV, 1.3x, 5 drafts) = 4.88 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-06-08

**Players**: 18 HV
 | **Score range**: 1.37 -- 6.76 (median 2.91)

**Leaderboard**: top score 53.55, floor 48.42, median 49.42

**Winner** (score 53.55):
  - N. Collier (2x) = 13.53
  - A. Ogunbowale (2.6x) = 10.48
  - M. Mabrey (2.2x) = 7.88
  - M. Siegrist (3.0999999999999996x) = 10.50
  - J. Sheldon (4x) = 11.16
  - **Game stack**: team 12: 2 players

**Field ownership** (top-20 entries):
  - N. Collier (1.8x/2x): 19/20 = 95%, avg 13.31
  - A. Ogunbowale (2.8x/2.6x/2.4x/2x/2.2x): 16/20 = 80%, avg 9.12
  - M. Siegrist (3.5x/3.1x/2.9x/3.7x/3.3x): 15/20 = 75%, avg 10.55
  - B. Sykes (1.9x/2.1x/2.3x): 14/20 = 70%, avg 9.94
  - M. Mabrey (2.4x/1.8x/2.2x/2x): 8/20 = 40%, avg 7.70
  - K. McBride (1.9x/2.1x/2.3x/2.5x): 8/20 = 40%, avg 9.75
  - A. Smith (1.8x/2x/2.2x): 7/20 = 35%, avg 6.50
  - T. Charles (2.4x/2.6x): 3/20 = 15%, avg 6.66

### Outcome Classification

**(A) Correctly priced** (18 players):
  - A. Edwards (CON, 3.0x, 3 drafts) = 2.91 -- Outcome roughly matched draft position and signals
  - N. Collier (MIN, 0.0x, 5000 drafts) = 6.76 -- High-draft player delivered as expected
  - J. Sheldon (CHI, 2.8x, 2 drafts) = 2.79 -- Outcome roughly matched draft position and signals
  - M. Siegrist (DAL, 1.7x, 84 drafts) = 3.39 -- High-draft player delivered as expected
  - A. Ogunbowale (DAL, 0.8x, 284 drafts) = 4.03 -- High-draft player delivered as expected
  - K. McBride (MIN, 0.5x, 112 drafts) = 4.48 -- High-draft player delivered as expected
  - B. Sykes (TOR, 0.5x, 277 drafts) = 4.46 -- High-draft player delivered as expected
  - M. Mabrey (TOR, 0.6x, 342 drafts) = 3.58 -- High-draft player delivered as expected
  - A. Smith (DAL, 0.6x, 202 drafts) = 3.25 -- High-draft player delivered as expected
  - S. Citron (WAS, 1.1x, 126 drafts) = 2.49 -- Outcome roughly matched draft position and signals
  - C. Williams (MIN, 0.5x, 293 drafts) = 3.01 -- High-draft player delivered as expected
  - L. Geiselsöder (POR, 2.3x, 25 drafts) = 1.71 -- Mid-draft player with mid outcome -- no edge either way
  - E. Engstler (POR, 3.0x, 1 drafts) = 1.47 -- Low-draft player correctly faded by the field
  - B. Carleton (POR, 1.8x, 108 drafts) = 1.85 -- Outcome roughly matched draft position and signals
  - S. Austin (WAS, 2.0x, 9 drafts) = 1.71 -- Outcome roughly matched draft position and signals
  - L. Olsen (WAS, 3.0x, 1 drafts) = 1.37 -- Low-draft player correctly faded by the field
  - N. Hiedeman (SEA, 1.7x, 105 drafts) = 1.84 -- Outcome roughly matched draft position and signals
  - K. Iriafen (WAS, 0.7x, 257 drafts) = 2.51 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-06-09

**Players**: 18 HV
 | **Score range**: 0.00 -- 4.08 (median 1.90)

**Leaderboard**: top score 53.11, floor 47.18, median 49.06

**Winner** (score 53.11):
  - D. Hamby (2.2x) = 8.65
  - T. Fágbénlé (2.9000000000000004x) = 11.85
  - J. Salaün (3.4000000000000004x) = 12.19
  - J. Vanloo (4.4x) = 9.56
  - C. Leite (3.9000000000000004x) = 10.87

**Field ownership** (top-20 entries):
  - J. Salaün (3x/3.6x/3.2x/3.8x/3.4x): 18/20 = 90%, avg 11.99
  - C. Leite (4.1x/4.7x/4.3x/4.5x/3.9x): 18/20 = 90%, avg 11.36
  - T. Fágbénlé (2.3x/3.1x/2.7x/2.9x/2.5x): 15/20 = 75%, avg 11.46
  - K. Plum (1.9x/2.1x): 10/20 = 50%, avg 8.00
  - D. Hamby (1.6x/1.8x/2x/2.2x): 9/20 = 45%, avg 7.77
  - K. Thornton (2.3x/2.7x/2.9x/2.1x/2.5x): 8/20 = 40%, avg 9.13
  - J. Allemand (4.4x/4.6x/4.2x/4.8x): 7/20 = 35%, avg 8.63
  - M. Billings (3.1x/3.7x/3.3x): 6/20 = 30%, avg 6.60

### Outcome Classification

**(A) Correctly priced** (18 players):
  - J. Salaün (GSV, 1.8x, 122 drafts) = 3.59 -- High-draft player delivered as expected
  - C. Leite (POR, 2.7x, 105 drafts) = 2.79 -- Outcome roughly matched draft position and signals
  - T. Fágbénlé (TOR, 1.1x, 194 drafts) = 4.08 -- High-draft player delivered as expected
  - K. Thornton (GSV, 0.9x, 371 drafts) = 3.58 -- High-draft player delivered as expected
  - J. Allemand (TOR, 3.0x, 107 drafts) = 1.9 -- Outcome roughly matched draft position and signals
  - D. Hamby (LAS, 0.2x, 1000 drafts) = 3.93 -- High-draft player delivered as expected
  - K. Plum (LAS, 0.1x, 5400 drafts) = 3.96 -- High-draft player delivered as expected
  - A. Stevens (CHI, 0.2x, 584 drafts) = 3.34 -- High-draft player delivered as expected
  - M. Billings (IND, 1.7x, 142 drafts) = 1.94 -- Outcome roughly matched draft position and signals
  - S. Barker (POR, 3.0x, 106 drafts) = 1.25 -- High-draft player underperformed -- field took the loss equally
  - V. Burton (GSV, 0.6x, 818 drafts) = 1.83 -- Outcome roughly matched draft position and signals
  - E. Cannon (LAS, 3.0x, 85 drafts) = 0.76 -- High-draft player underperformed -- field took the loss equally
  - O. Sims (DAL, 0.9x, 321 drafts) = 1.17 -- High-draft player underperformed -- field took the loss equally
  - R. Jackson (CHI, 2.3x, 213 drafts) = 0.47 -- High-draft player underperformed -- field took the loss equally
  - K. Martin (LAS, 3.0x, 283 drafts) = 0.09 -- High-draft player underperformed -- field took the loss equally
  - C. Zandalasini (GSV, 1.6x, None drafts) = None -- Low-draft player correctly faded by the field
  - T. Hayes (GSV, 1.9x, None drafts) = None -- Low-draft player correctly faded by the field
  - L. Amihere (GSV, 0.0x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-06-10

**Players**: 20 HV
 | **Score range**: 0.96 -- 5.90 (median 1.77)

**Leaderboard**: top score 46.15, floor 43.43, median 44.96

**Winner** (score 46.15):
  - B. Stewart (2.1x) = 8.58
  - S. Ionescu (2x) = 11.79
  - A. Reese (2.7x) = 9.49
  - N. Howard (2.9x) = 9.10
  - K. Burke (2.8x) = 7.19
  - **Game stack**: team 4: 2 players

**Field ownership** (top-20 entries):
  - S. Ionescu (1.8x/2x/2.2x): 20/20 = 100%, avg 12.15
  - A. Reese (2.9x/2.3x/2.5x/2.7x): 19/20 = 95%, avg 9.08
  - B. Stewart (1.9x/2.1x/1.7x/1.5x): 16/20 = 80%, avg 7.71
  - N. Howard (3.5x/3.1x/2.7x/2.9x/3.3x): 16/20 = 80%, avg 9.26
  - A. Gray (1.9x/1.5x/1.3x/2.1x/1.7x): 11/20 = 55%, avg 7.85
  - K. Burke (3.2x/2.8x/3x): 8/20 = 40%, avg 7.70
  - D. Bonner (3.9x/3.3x): 4/20 = 20%, avg 5.31
  - B. Jones (2.1x/2.3x): 3/20 = 15%, avg 7.17

### Outcome Classification

**(A) Correctly priced** (20 players):
  - S. Ionescu (NYL, 0.2x, 1800 drafts) = 5.9 -- High-draft player delivered as expected
  - N. Howard (MIN, 1.5x, 151 drafts) = 3.14 -- High-draft player delivered as expected
  - A. Reese (ATL, 1.1x, 331 drafts) = 3.51 -- High-draft player delivered as expected
  - A. Gray (ATL, 0.1x, 1100 drafts) = 4.67 -- High-draft player delivered as expected
  - K. Burke (CON, 1.6x, 112 drafts) = 2.57 -- Outcome roughly matched draft position and signals
  - J. Canada (ATL, 3.0x, 13 drafts) = 1.77 -- Mid-draft player with mid outcome -- no edge either way
  - B. Jones (ATL, 0.7x, 178 drafts) = 3.21 -- High-draft player delivered as expected
  - B. Stewart (NYL, 0.1x, 3900 drafts) = 4.09 -- High-draft player delivered as expected
  - N. Sabally (TOR, 2.1x, 14 drafts) = 2.04 -- Mid-draft player with mid outcome -- no edge either way
  - N. Coffey (MIN, 2.4x, 4 drafts) = 1.56 -- Outcome roughly matched draft position and signals
  - R. Banham (CHI, 3.0x, 7 drafts) = 1.3 -- Low-draft player correctly faded by the field
  - D. Bonner (PHO, 2.1x, 140 drafts) = 1.54 -- Outcome roughly matched draft position and signals
  - K. Nurse (TOR, 3.0x, 7 drafts) = 1.18 -- Low-draft player correctly faded by the field
  - N. Hillmon (ATL, 2.0x, 8 drafts) = 1.42 -- Low-draft player correctly faded by the field
  - B. Griner (CON, 1.1x, 205 drafts) = 1.69 -- Outcome roughly matched draft position and signals
  - K. Cardoso (CHI, 1.2x, 164 drafts) = 1.61 -- Outcome roughly matched draft position and signals
  - E. Williams (CHI, 2.3x, 20 drafts) = 1.17 -- Mid-draft player with mid outcome -- no edge either way
  - R. Gardner (NYL, 3.0x, 14 drafts) = 1.01 -- Mid-draft player with mid outcome -- no edge either way
  - M. Onyenwere (WAS, 3.0x, 8 drafts) = 0.96 -- Low-draft player correctly faded by the field
  - A. Boston (IND, 0.2x, 564 drafts) = 2.05 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-06-11

**Players**: 19 HV
 | **Score range**: 2.12 -- 8.00 (median 3.91)

**Leaderboard**: top score 72.69, floor 62.72, median 65.46

**Winner** (score 72.69):
  - D. Carrington (3.4x) = 10.49
  - R. Jackson (4.8x) = 25.93
  - N. Ogwumike (2x) = 9.71
  - J. Young (2.2x) = 14.57
  - P. Bueckers (1.5x) = 12.00
  - **Game stack**: team 8: 2 players

**Field ownership** (top-20 entries):
  - R. Jackson (4.4x/4.6x/4.2x/4.8x): 20/20 = 100%, avg 23.12
  - P. Bueckers (1.9x/2.1x/1.5x/1.7x): 15/20 = 75%, avg 14.88
  - N. Collier (1.8x/2x): 15/20 = 75%, avg 10.56
  - A. Wilson (1.8x/2x): 12/20 = 60%, avg 8.66
  - D. Carrington (3.4x/3x/2.6x/2.8x): 11/20 = 55%, avg 8.75
  - J. Young (2.4x/2.2x/2.6x): 7/20 = 35%, avg 15.70
  - S. Sabally (1.9x/2.1x/2.3x): 5/20 = 25%, avg 7.23
  - N. Ogwumike (2x): 2/20 = 10%, avg 9.71

### Outcome Classification

**(A) Correctly priced** (17 players):
  - J. Young (LVA, 0.8x, 171 drafts) = 6.62 -- High-draft player delivered as expected
  - P. Bueckers (DAL, 0.3x, 527 drafts) = 8.0 -- High-draft player delivered as expected
  - D. Hamby (LAS, 0.2x, 212 drafts) = 5.34 -- High-draft player delivered as expected
  - N. Ogwumike (LAS, 0.4x, 173 drafts) = 4.86 -- High-draft player delivered as expected
  - N. Collier (MIN, 0.0x, 3100 drafts) = 5.5 -- High-draft player delivered as expected
  - E. Magbegor (SEA, 1.1x, 94 drafts) = 3.53 -- High-draft player delivered as expected
  - D. Carrington (CHI, 1.4x, 158 drafts) = 3.08 -- High-draft player delivered as expected
  - K. Westbeld (PHO, 1.7x, 22 drafts) = 2.83 -- Mid-draft player with mid outcome -- no edge either way
  - C. Gray (LVA, 1.2x, 174 drafts) = 3.18 -- High-draft player delivered as expected
  - S. Whitcomb (PHO, 2.1x, 2 drafts) = 2.29 -- Outcome roughly matched draft position and signals
  - G. Williams (GSV, 0.4x, 211 drafts) = 3.91 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 3300 drafts) = 4.52 -- High-draft player delivered as expected
  - M. Akoa Makani (PHO, 2.0x, 3 drafts) = 2.12 -- Outcome roughly matched draft position and signals
  - A. Stevens (CHI, 0.2x, 162 drafts) = 3.82 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.1x, 238 drafts) = 3.98 -- High-draft player delivered as expected
  - S. Diggins (CHI, 0.4x, 179 drafts) = 3.4 -- High-draft player delivered as expected
  - K. McBride (MIN, 0.4x, 24 drafts) = 3.35 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (2 players):
  - R. Jackson (CHI, 3.0x, 2 drafts) = 5.4 -- No enrichment data available -- cannot assess if knowable
  - E. Wheeler (LAS, 1.3x, 2 drafts) = 4.33 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-06-13

**Players**: 19 HV
 | **Score range**: 1.51 -- 6.35 (median 2.91)

**Leaderboard**: top score 57.88, floor 56.73, median 56.73

**Winner** (score 57.88):
  - J. Young (2.5x) = 10.91
  - J. Loyd (2.9000000000000004x) = 10.91
  - J. Canada (4.6x) = 15.17
  - L. Geiselsöder (3.6x) = 10.88
  - K. Stokes (4.2x) = 10.01
  - **Game stack**: team 1: 2 players

**Field ownership** (top-20 entries):
  - J. Young (2.5x): 20/20 = 100%, avg 10.91
  - J. Canada (4.6x): 20/20 = 100%, avg 15.17
  - L. Geiselsöder (3.6x): 20/20 = 100%, avg 10.88
  - K. Stokes (4.2x): 20/20 = 100%, avg 10.01
  - C. Gray (2.9x): 19/20 = 95%, avg 9.76
  - J. Loyd (2.9x): 1/20 = 5%, avg 10.91

### Outcome Classification

**(A) Correctly priced** (18 players):
  - R. Howard (ATL, 0.3x, 284 drafts) = 6.35 -- High-draft player delivered as expected
  - A. Ogunbowale (DAL, 0.8x, 275 drafts) = 4.87 -- High-draft player delivered as expected
  - L. Geiselsöder (POR, 2.2x, 26 drafts) = 3.02 -- Mid-draft player with mid outcome -- no edge either way
  - K. Stokes (GSV, 3.0x, 25 drafts) = 2.38 -- Mid-draft player with mid outcome -- no edge either way
  - K. Cardoso (CHI, 1.3x, 142 drafts) = 3.6 -- High-draft player delivered as expected
  - J. Loyd (LVA, 1.1x, 181 drafts) = 3.76 -- High-draft player delivered as expected
  - J. Young (LVA, 0.5x, 846 drafts) = 4.36 -- High-draft player delivered as expected
  - C. Gray (LVA, 1.1x, 295 drafts) = 3.36 -- High-draft player delivered as expected
  - R. Banham (CHI, 3.0x, 3 drafts) = 2.03 -- Outcome roughly matched draft position and signals
  - R. Allen (NYL, 3.0x, 5 drafts) = 1.93 -- Outcome roughly matched draft position and signals
  - A. Atkins (LAS, 1.0x, 140 drafts) = 2.91 -- Outcome roughly matched draft position and signals
  - D. Carrington (CHI, 1.3x, 228 drafts) = 2.58 -- Outcome roughly matched draft position and signals
  - M. Hines-Allen (IND, 2.1x, 120 drafts) = 1.93 -- Outcome roughly matched draft position and signals
  - B. Jones (ATL, 0.7x, 175 drafts) = 2.87 -- Outcome roughly matched draft position and signals
  - M. Caldwell (MIN, 3.0x, 2 drafts) = 1.51 -- Outcome roughly matched draft position and signals
  - E. Williams (CHI, 2.4x, 1 drafts) = 1.75 -- Outcome roughly matched draft position and signals
  - A. Reese (ATL, 0.9x, 394 drafts) = 2.36 -- Outcome roughly matched draft position and signals
  - A. Gray (ATL, 0.1x, 820 drafts) = 2.96 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - J. Canada (ATL, 3.0x, 6 drafts) = 3.3 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-06-14

**Players**: 19 HV
 | **Score range**: 1.59 -- 9.64 (median 2.97)

**Leaderboard**: top score 60.11, floor 57.83, median 58.72

**Winner** (score 60.11):
  - C. Clark (2.2x) = 17.10
  - N. Collier (1.8x) = 17.35
  - S. Ionescu (1.8x) = 9.60
  - K. Thornton (2.2x) = 8.35
  - L. Hull (2.5999999999999996x) = 7.71
  - **Game stack**: team 3: 2 players

**Field ownership** (top-20 entries):
  - C. Clark (1.8x/2x/2.2x): 20/20 = 100%, avg 15.70
  - N. Collier (1.6x/1.8x/2x): 20/20 = 100%, avg 18.70
  - S. Ionescu (1.6x/1.8x/2x/1.4x): 20/20 = 100%, avg 9.49
  - K. Thornton (2.4x/2x/2.2x): 13/20 = 65%, avg 8.35
  - R. Jackson (2.5x/2.7x): 9/20 = 45%, avg 6.43
  - N. Hiedeman (2.9x): 4/20 = 20%, avg 9.93
  - L. Hull (2.8x/2.6x): 3/20 = 15%, avg 7.91
  - B. Stewart (1.7x): 3/20 = 15%, avg 6.02

### Outcome Classification

**(A) Correctly priced** (17 players):
  - N. Collier (MIN, 0.0x, 2700 drafts) = 9.64 -- High-draft player delivered as expected
  - C. Clark (IND, 0.2x, 2200 drafts) = 7.77 -- High-draft player delivered as expected
  - S. Ionescu (NYL, 0.2x, 863 drafts) = 5.33 -- High-draft player delivered as expected
  - K. Thornton (GSV, 0.8x, 173 drafts) = 3.79 -- High-draft player delivered as expected
  - A. Clark (DAL, 3.0x, 48 drafts) = 2.09 -- Mid-draft player with mid outcome -- no edge either way
  - L. Hull (IND, 1.4x, 63 drafts) = 2.97 -- Outcome roughly matched draft position and signals
  - E. Magbegor (SEA, 1.0x, 184 drafts) = 3.02 -- High-draft player delivered as expected
  - A. Boston (IND, 0.2x, 234 drafts) = 4.11 -- High-draft player delivered as expected
  - B. Carleton (POR, 1.8x, 2 drafts) = 2.37 -- Outcome roughly matched draft position and signals
  - D. Dantas (IND, 3.0x, 2 drafts) = 1.72 -- Outcome roughly matched draft position and signals
  - T. Fágbénlé (TOR, 0.9x, 129 drafts) = 2.92 -- Outcome roughly matched draft position and signals
  - R. Jackson (CHI, 1.3x, 9 drafts) = 2.55 -- Outcome roughly matched draft position and signals
  - E. Cannon (LAS, 3.0x, 1 drafts) = 1.59 -- Outcome roughly matched draft position and signals
  - K. Mitchell (IND, 0.7x, 129 drafts) = 2.9 -- Outcome roughly matched draft position and signals
  - V. Burton (GSV, 0.6x, 263 drafts) = 2.89 -- Outcome roughly matched draft position and signals
  - C. Williams (MIN, 0.6x, 70 drafts) = 2.88 -- Outcome roughly matched draft position and signals
  - S. Diggins (CHI, 0.4x, 444 drafts) = 3.11 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (2 players):
  - N. Sabally (TOR, 1.9x, 2 drafts) = 3.29 -- Above-expectation outcome, ambiguous whether knowable
  - N. Hiedeman (SEA, 1.7x, 3 drafts) = 3.42 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-06-15

**Players**: 18 HV
 | **Score range**: 1.42 -- 7.69 (median 3.29)

**Leaderboard**: top score 53.67, floor 51.11, median 52.21

**Winner** (score 53.67):
  - A. Reese (2.9x) = 15.17
  - S. Sabally (2.1x) = 9.46
  - K. Cardoso (2.7x) = 3.92
  - J. Sheldon (3.6999999999999997x) = 12.19
  - H. Van Lith (4.2x) = 12.93
  - **Game stack**: team 8: 2 players

**Field ownership** (top-20 entries):
  - A. Gray (1.9x/2.1x/1.3x): 19/20 = 95%, avg 15.27
  - A. Reese (2.3x/2.7x/2.9x/2.1x/2.5x): 17/20 = 85%, avg 12.59
  - S. Sabally (1.9x/2.1x/1.7x/2.3x): 14/20 = 70%, avg 9.33
  - C. Gray (2.4x/2.8x/2.2x/2.6x): 11/20 = 55%, avg 9.82
  - J. Young (1.6x/1.8x/2x/2.4x): 7/20 = 35%, avg 6.26
  - A. Thomas (1.9x/2.1x/1.7x): 5/20 = 25%, avg 7.71
  - J. Loyd (2.2x/2.6x): 4/20 = 20%, avg 8.01
  - J. Sheldon (3.5x/3.7x): 3/20 = 15%, avg 11.97

### Outcome Classification

**(A) Correctly priced** (14 players):
  - A. Gray (ATL, 0.1x, 1100 drafts) = 7.69 -- High-draft player delivered as expected
  - A. Reese (ATL, 0.9x, 216 drafts) = 5.23 -- High-draft player delivered as expected
  - C. Gray (LVA, 1.0x, 298 drafts) = 3.91 -- High-draft player delivered as expected
  - S. Whitcomb (PHO, 2.0x, 62 drafts) = 2.85 -- Outcome roughly matched draft position and signals
  - J. Loyd (LVA, 1.0x, 233 drafts) = 3.48 -- High-draft player delivered as expected
  - S. Sabally (NYL, 0.3x, 765 drafts) = 4.51 -- High-draft player delivered as expected
  - J. Canada (ATL, 1.6x, 15 drafts) = 2.57 -- Mid-draft player with mid outcome -- no edge either way
  - K. Nurse (TOR, 3.0x, 1 drafts) = 1.82 -- Outcome roughly matched draft position and signals
  - K. Stokes (GSV, 3.0x, 47 drafts) = 1.71 -- Mid-draft player with mid outcome -- no edge either way
  - A. Thomas (PHO, 0.1x, 926 drafts) = 4.06 -- High-draft player delivered as expected
  - J. Young (LVA, 0.4x, 779 drafts) = 3.22 -- High-draft player delivered as expected
  - S. Austin (WAS, 2.0x, 1 drafts) = 1.91 -- Outcome roughly matched draft position and signals
  - M. Mabrey (TOR, 0.6x, 382 drafts) = 2.85 -- Outcome roughly matched draft position and signals
  - N. Mack (PHO, 3.0x, 15 drafts) = 1.42 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (4 players):
  - T. Paopao (ATL, 3.0x, 2 drafts) = 4.08 -- High-boost low-draft player who overperformed
  - N. Hillmon (ATL, 2.4x, 1 drafts) = 3.78 -- Above-expectation outcome, ambiguous whether knowable
  - H. Van Lith (CON, 3.0x, 9 drafts) = 3.08 -- Above-expectation outcome, ambiguous whether knowable
  - J. Sheldon (CHI, 2.3x, 1 drafts) = 3.29 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 4 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-06-17

**Players**: 18 HV
 | **Score range**: 1.91 -- 7.74 (median 3.62)

**Leaderboard**: top score 53.31, floor 48.95, median 49.72

**Winner** (score 53.31):
  - S. Ionescu (2.1x) = 16.25
  - A. Stevens (2.2x) = 6.86
  - M. Billings (3.3x) = 11.34
  - R. Jackson (2.5999999999999996x) = 5.09
  - T. Paopao (4.1x) = 13.78
  - **Game stack**: team 8: 2 players

**Field ownership** (top-20 entries):
  - S. Ionescu (1.9x/1.5x/1.3x/2.1x/1.7x): 17/20 = 85%, avg 14.79
  - N. Ogwumike (1.6x/2.4x/2x/1.8x/2.2x): 15/20 = 75%, avg 11.90
  - A. Ogunbowale (1.9x/2.3x/2.7x/2.1x/2.5x): 12/20 = 60%, avg 9.77
  - P. Bueckers (2.1x/1.5x/1.7x/1.3x): 7/20 = 35%, avg 6.57
  - G. Williams (2x/2.2x): 5/20 = 25%, avg 10.66
  - S. Diggins (1.6x/2.4x/2x): 4/20 = 20%, avg 8.03
  - A. Reese (2.1x/2.3x): 4/20 = 20%, avg 7.26
  - B. Sykes (1.9x/2.1x/2.3x): 4/20 = 20%, avg 12.19

### Outcome Classification

**(A) Correctly priced** (10 players):
  - S. Ionescu (NYL, 0.1x, 407 drafts) = 7.74 -- High-draft player delivered as expected
  - A. Clark (DAL, 3.0x, 16 drafts) = 2.92 -- Mid-draft player with mid outcome -- no edge either way
  - N. Ogwumike (LAS, 0.4x, 193 drafts) = 5.79 -- High-draft player delivered as expected
  - G. Williams (GSV, 0.4x, 197 drafts) = 4.93 -- High-draft player delivered as expected
  - A. Ogunbowale (DAL, 0.7x, 146 drafts) = 4.25 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.6x, 24 drafts) = 4.34 -- Mid-draft player with mid outcome -- no edge either way
  - S. Austin (WAS, 1.9x, 1 drafts) = 2.74 -- Outcome roughly matched draft position and signals
  - M. Hines-Allen (IND, 2.1x, 9 drafts) = 2.34 -- Outcome roughly matched draft position and signals
  - K. Stokes (GSV, 3.0x, 4 drafts) = 1.91 -- Outcome roughly matched draft position and signals
  - R. Howard (ATL, 0.2x, 120 drafts) = 4.25 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (8 players):
  - T. Paopao (ATL, 2.9x, 3 drafts) = 3.36 -- High-boost low-draft player who overperformed
  - B. Sykes (TOR, 0.5x, 21 drafts) = 5.95 -- Above-expectation outcome, ambiguous whether knowable
  - L. Amihere (GSV, 3.0x, 1 drafts) = 3.33 -- High-boost low-draft player who overperformed
  - K. Cardoso (CHI, 1.2x, 6 drafts) = 4.02 -- Above-expectation outcome, ambiguous whether knowable
  - M. Billings (IND, 1.7x, 1 drafts) = 3.44 -- Above-expectation outcome, ambiguous whether knowable
  - N. Howard (MIN, 1.5x, 3 drafts) = 3.43 -- Above-expectation outcome, ambiguous whether knowable
  - A. Atkins (LAS, 1.0x, 4 drafts) = 3.62 -- Above-expectation outcome, ambiguous whether knowable
  - S. Citron (WAS, 1.2x, 7 drafts) = 3.17 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 8 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-06-18

**Players**: 12 HV
 | **Score range**: 0.96 -- 3.80 (median 2.21)

**Leaderboard**: top score 45.61, floor 41.73, median 43.68

**Winner** (score 45.61):
  - A. Morrow (5x) = 15.67
  - O. Nelson-Ododa (3.4000000000000004x) = 10.73
  - N. Mack (4.4x) = 6.29
  - L. Held (3.3x) = 8.04
  - K. Laksa (3.4000000000000004x) = 4.88
  - **Game stack**: team 11: 2 players

**Field ownership** (top-20 entries):
  - A. Morrow (4.8x/4.6x/4.2x/4.4x/5x): 20/20 = 100%, avg 14.54
  - O. Nelson-Ododa (3x/2.8x/3.2x/3.4x/3.3x): 20/20 = 100%, avg 9.83
  - L. Held (3.5x/3.1x/3.7x/3.9x/3.3x): 18/20 = 90%, avg 8.50
  - M. Mabrey (1.9x/2.1x/2.5x): 8/20 = 40%, avg 4.53
  - A. Thomas (2.1x/1.7x/1.3x): 7/20 = 35%, avg 7.10
  - S. Rivers (3.4x/3.8x/3.1x): 5/20 = 25%, avg 4.91
  - J. Sheldon (3.5x/3.7x/3.9x): 5/20 = 25%, avg 4.85
  - S. Sabally (1.8x/1.4x/2.2x): 4/20 = 20%, avg 5.11

### Outcome Classification

**(A) Correctly priced** (12 players):
  - A. Morrow (CON, 3.0x, 88 drafts) = 3.13 -- High-draft player delivered as expected
  - O. Nelson-Ododa (CON, 1.6x, 149 drafts) = 3.16 -- High-draft player delivered as expected
  - L. Held (TOR, 1.9x, 211 drafts) = 2.44 -- Outcome roughly matched draft position and signals
  - K. Copper (PHO, 2.1x, 124 drafts) = 2.21 -- Outcome roughly matched draft position and signals
  - A. Thomas (PHO, 0.1x, 3400 drafts) = 3.8 -- High-draft player delivered as expected
  - N. Mack (PHO, 2.8x, 65 drafts) = 1.43 -- High-draft player underperformed -- field took the loss equally
  - S. Sabally (NYL, 0.2x, 3400 drafts) = 3.0 -- High-draft player delivered as expected
  - S. Rivers (CON, 1.8x, 95 drafts) = 1.43 -- High-draft player underperformed -- field took the loss equally
  - K. Westbeld (PHO, 1.7x, 152 drafts) = 1.61 -- Outcome roughly matched draft position and signals
  - M. Mabrey (TOR, 0.7x, 588 drafts) = 2.13 -- Outcome roughly matched draft position and signals
  - J. Sheldon (CHI, 1.9x, 152 drafts) = 1.28 -- High-draft player underperformed -- field took the loss equally
  - M. Akoa Makani (PHO, 2.0x, 112 drafts) = 0.96 -- High-draft player underperformed -- field took the loss equally

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-06-19

**Players**: 18 HV
 | **Score range**: 1.31 -- 5.72 (median 2.70)

**Leaderboard**: top score 47.99, floor 43.94, median 46.04

**Winner** (score 47.99):
  - B. Stewart (2.1x) = 12.01
  - K. Laksa (4x) = 9.36
  - S. Whitcomb (3.4000000000000004x) = 9.31
  - M. Akoa Makani (3.6x) = 13.97
  - K. Westbeld (3x) = 3.35
  - **Game stack**: team 6: 3 players

**Field ownership** (top-20 entries):
  - M. Akoa Makani (3.2x/4x/4.2x/3.4x/3.8x/3.6x): 18/20 = 90%, avg 14.70
  - B. Stewart (1.9x/1.5x/1.3x/2.1x/1.7x): 16/20 = 80%, avg 10.58
  - A. Thomas (1.9x/1.5x/1.3x/2.1x/1.7x): 14/20 = 70%, avg 9.24
  - S. Whitcomb (3x/3.6x/3.2x/3.8x/3.4x): 8/20 = 40%, avg 9.03
  - N. Cloud (2.1x/2.3x): 8/20 = 40%, avg 8.48
  - K. Laksa (3.4x/4x/3.8x/3.6x): 7/20 = 35%, avg 8.89
  - N. Howard (3.3x/2.5x/3.1x): 5/20 = 25%, avg 6.64
  - C. Clark (1.2x/2x/1.4x): 5/20 = 25%, avg 3.99

### Outcome Classification

**(A) Correctly priced** (18 players):
  - M. Akoa Makani (PHO, 2.2x, 63 drafts) = 3.88 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.1x, 185 drafts) = 5.39 -- High-draft player delivered as expected
  - B. Stewart (NYL, 0.1x, 417 drafts) = 5.72 -- High-draft player delivered as expected
  - T. Hayes (GSV, 2.0x, 22 drafts) = 2.7 -- Mid-draft player with mid outcome -- no edge either way
  - N. Cloud (CHI, 0.7x, 108 drafts) = 3.86 -- High-draft player delivered as expected
  - S. Whitcomb (PHO, 1.8x, 52 drafts) = 2.74 -- Outcome roughly matched draft position and signals
  - S. Cunningham (IND, 3.0x, 57 drafts) = 1.99 -- Outcome roughly matched draft position and signals
  - A. Boston (IND, 0.2x, 304 drafts) = 3.84 -- High-draft player delivered as expected
  - N. Mack (PHO, 2.7x, 1 drafts) = 1.73 -- Outcome roughly matched draft position and signals
  - K. Martin (LAS, 3.0x, 42 drafts) = 1.58 -- Mid-draft player with mid outcome -- no edge either way
  - K. Thornton (GSV, 0.8x, 203 drafts) = 2.61 -- Outcome roughly matched draft position and signals
  - N. Howard (MIN, 1.3x, 115 drafts) = 2.17 -- Outcome roughly matched draft position and signals
  - S. Ionescu (NYL, 0.0x, 2200 drafts) = 3.51 -- High-draft player delivered as expected
  - V. Burton (GSV, 0.7x, 170 drafts) = 2.54 -- Outcome roughly matched draft position and signals
  - L. Amihere (GSV, 0.4x, 16 drafts) = 3.04 -- Mid-draft player with mid outcome -- no edge either way
  - C. Leite (POR, 2.2x, 34 drafts) = 1.51 -- Mid-draft player with mid outcome -- no edge either way
  - M. Johannes (NYL, 2.8x, 2 drafts) = 1.31 -- Low-draft player correctly faded by the field
  - M. Billings (IND, 1.5x, 45 drafts) = 1.6 -- Mid-draft player with mid outcome -- no edge either way

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-06-20

**Players**: 19 HV
 | **Score range**: 1.70 -- 6.77 (median 3.09)

**Leaderboard**: top score 57.95, floor 53.90, median 54.85

**Winner** (score 57.95):
  - P. Bueckers (2.1x) = 8.46
  - S. Austin (3.5x) = 23.71
  - T. Charles (2.6x) = 10.14
  - J. Young (1.9x) = 8.89
  - G. Williams (1.6x) = 6.76

**Field ownership** (top-20 entries):
  - S. Austin (3.5x/3.1x/2.9x/3.7x/3.3x): 20/20 = 100%, avg 22.01
  - P. Bueckers (1.9x/2.1x): 7/20 = 35%, avg 8.34
  - J. Young (1.9x/2.3x/2.1x/1.7x/2.5x): 7/20 = 35%, avg 9.70
  - N. Ogwumike (2.1x/1.5x/2.3x): 6/20 = 30%, avg 12.38
  - G. Williams (1.6x/2x/2.2x): 5/20 = 25%, avg 8.28
  - R. Howard (1.8x/2x): 5/20 = 25%, avg 6.12
  - O. Nelson-Ododa (2.9x/3.1x/2.7x/3.3x): 5/20 = 25%, avg 5.73
  - J. Canada (3x): 5/20 = 25%, avg 7.49

### Outcome Classification

**(A) Correctly priced** (16 players):
  - N. Ogwumike (LAS, 0.3x, 367 drafts) = 6.41 -- High-draft player delivered as expected
  - A. Morrow (CON, 3.0x, 2 drafts) = 2.47 -- Outcome roughly matched draft position and signals
  - J. Young (LVA, 0.5x, 297 drafts) = 4.68 -- High-draft player delivered as expected
  - S. Diggins (CHI, 0.4x, 274 drafts) = 4.73 -- High-draft player delivered as expected
  - N. Smith (LVA, 2.5x, 2 drafts) = 2.31 -- Outcome roughly matched draft position and signals
  - E. Wheeler (LAS, 1.1x, 111 drafts) = 3.3 -- High-draft player delivered as expected
  - G. Williams (GSV, 0.4x, 305 drafts) = 4.23 -- High-draft player delivered as expected
  - B. Jones (ATL, 0.8x, 119 drafts) = 3.54 -- High-draft player delivered as expected
  - A. Nye (ATL, 3.0x, 31 drafts) = 1.96 -- Mid-draft player with mid outcome -- no edge either way
  - B. Sykes (TOR, 0.4x, 215 drafts) = 4.03 -- High-draft player delivered as expected
  - S. Citron (WAS, 1.1x, 99 drafts) = 2.99 -- Outcome roughly matched draft position and signals
  - J. Loyd (LVA, 0.9x, 159 drafts) = 3.09 -- High-draft player delivered as expected
  - N. Coffey (MIN, 2.8x, 1 drafts) = 1.8 -- Outcome roughly matched draft position and signals
  - S. Rivers (CON, 1.8x, 7 drafts) = 2.4 -- Outcome roughly matched draft position and signals
  - A. Clark (DAL, 3.0x, 34 drafts) = 1.7 -- Mid-draft player with mid outcome -- no edge either way
  - J. Canada (ATL, 1.4x, 3 drafts) = 2.5 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (3 players):
  - S. Austin (WAS, 1.7x, 43 drafts) = 6.77 -- Above-expectation outcome, ambiguous whether knowable
  - A. James (DAL, 3.0x, 5 drafts) = 3.32 -- Above-expectation outcome, ambiguous whether knowable
  - L. Yueru (DAL, 3.0x, 1 drafts) = 3.01 -- High-boost low-draft player who overperformed

**Takeaway**: 3 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-06-21

**Players**: 16 HV
 | **Score range**: 1.16 -- 4.37 (median 2.74)

**Leaderboard**: top score 47.56, floor 44.88, median 44.88

**Winner** (score 47.56):
  - K. Copper (3.6x) = 11.96
  - M. Kliundikova (4.3x) = 15.37
  - S. Whitcomb (3.3x) = 9.03
  - K. Nurse (4.4x) = 6.35
  - R. Allen (4.2x) = 4.86
  - **Game stack**: team 6: 2 players, team 16: 2 players

**Field ownership** (top-20 entries):
  - M. Kliundikova (4.3x/4.1x/3.9x): 20/20 = 100%, avg 14.69
  - K. Copper (3.6x): 19/20 = 95%, avg 11.96
  - S. Whitcomb (3.1x/3.3x): 19/20 = 95%, avg 8.51
  - M. Akoa Makani (3x): 19/20 = 95%, avg 5.75
  - R. Jackson (2.9x/3.1x): 18/20 = 90%, avg 4.03
  - K. Nurse (4.4x): 1/20 = 5%, avg 6.35
  - R. Allen (4.2x): 1/20 = 5%, avg 4.86
  - C. Williams (2.5x): 1/20 = 5%, avg 10.94

### Outcome Classification

**(A) Correctly priced** (15 players):
  - K. Copper (PHO, 1.6x, 166 drafts) = 3.32 -- High-draft player delivered as expected
  - M. Onyenwere (WAS, 3.0x, 1 drafts) = 2.42 -- Outcome roughly matched draft position and signals
  - C. Williams (MIN, 0.5x, 373 drafts) = 4.37 -- High-draft player delivered as expected
  - K. McBride (MIN, 0.6x, 231 drafts) = 4.14 -- High-draft player delivered as expected
  - S. Whitcomb (PHO, 1.7x, 50 drafts) = 2.74 -- Outcome roughly matched draft position and signals
  - A. Thomas (PHO, 0.1x, 598 drafts) = 3.71 -- High-draft player delivered as expected
  - A. Stevens (CHI, 0.4x, 201 drafts) = 3.07 -- High-draft player delivered as expected
  - M. Akoa Makani (PHO, 1.8x, 65 drafts) = 1.92 -- Outcome roughly matched draft position and signals
  - K. Cardoso (CHI, 1.0x, 111 drafts) = 2.34 -- Outcome roughly matched draft position and signals
  - R. Banham (CHI, 3.0x, 2 drafts) = 1.51 -- Outcome roughly matched draft position and signals
  - K. Nurse (TOR, 3.0x, 2 drafts) = 1.44 -- Low-draft player correctly faded by the field
  - S. Sabally (NYL, 0.3x, 322 drafts) = 2.85 -- Outcome roughly matched draft position and signals
  - K. Westbeld (PHO, 1.8x, 56 drafts) = 1.64 -- Outcome roughly matched draft position and signals
  - R. Allen (NYL, 3.0x, 6 drafts) = 1.16 -- Low-draft player correctly faded by the field
  - A. Atkins (LAS, 0.9x, 81 drafts) = 1.92 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - M. Kliundikova (TOR, 2.5x, 8 drafts) = 3.57 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-06-22

**Players**: 19 HV
 | **Score range**: 2.41 -- 5.87 (median 4.29)

**Leaderboard**: top score 56.15, floor 50.90, median 52.80

**Winner** (score 56.15):
  - B. Stewart (2.1x) = 8.51
  - N. Ogwumike (2x) = 10.60
  - A. Reese (2.3x) = 8.22
  - S. Citron (2.4x) = 13.97
  - T. Paopao (3.7x) = 14.85
  - **Game stack**: team 2: 2 players

**Field ownership** (top-20 entries):
  - T. Paopao (4.3x/3.7x/3.9x/4.5x): 12/20 = 60%, avg 15.65
  - S. Citron (3x/2.8x/2.6x/2.4x/2.2x): 10/20 = 50%, avg 15.49
  - S. Austin (2.8x/2.2x/2.6x): 8/20 = 40%, avg 10.83
  - K. Thornton (2.4x/2.8x/2.2x/2.6x): 7/20 = 35%, avg 10.61
  - B. Stewart (1.9x/2.1x): 6/20 = 30%, avg 8.37
  - K. Iriafen (2.4x/2.8x/3x/2.6x): 6/20 = 30%, avg 13.42
  - P. Bueckers (1.9x/2.1x): 6/20 = 30%, avg 9.22
  - G. Williams (1.9x/2.1x/1.7x/2.3x): 4/20 = 20%, avg 8.01

### Outcome Classification

**(A) Correctly priced** (12 players):
  - S. Talbot (LVA, 3.0x, 18 drafts) = 2.97 -- Mid-draft player with mid outcome -- no edge either way
  - A. Boston (IND, 0.2x, 106 drafts) = 5.87 -- High-draft player delivered as expected
  - S. Austin (WAS, 1.0x, 72 drafts) = 4.29 -- High-draft player delivered as expected
  - K. Thornton (GSV, 0.8x, 309 drafts) = 4.32 -- High-draft player delivered as expected
  - A. Ogunbowale (DAL, 0.7x, 91 drafts) = 4.33 -- High-draft player delivered as expected
  - N. Ogwumike (LAS, 0.2x, 266 drafts) = 5.3 -- High-draft player delivered as expected
  - N. Hillmon (ATL, 2.0x, 1 drafts) = 2.82 -- Outcome roughly matched draft position and signals
  - J. Young (LVA, 0.4x, 80 drafts) = 4.33 -- High-draft player delivered as expected
  - N. Smith (LVA, 2.3x, 4 drafts) = 2.41 -- Outcome roughly matched draft position and signals
  - S. Diggins (CHI, 0.4x, 210 drafts) = 4.18 -- High-draft player delivered as expected
  - A. Reese (ATL, 0.7x, 162 drafts) = 3.57 -- High-draft player delivered as expected
  - A. Gray (ATL, 0.1x, 209 drafts) = 4.74 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (7 players):
  - E. Williams (CHI, 2.5x, 2 drafts) = 4.07 -- High-boost low-draft player who overperformed
  - T. Paopao (ATL, 2.5x, 1 drafts) = 4.01 -- High-boost low-draft player who overperformed
  - S. Citron (WAS, 1.0x, 10 drafts) = 5.82 -- Above-expectation outcome, ambiguous whether knowable
  - M. Johannes (NYL, 2.8x, 1 drafts) = 3.33 -- High-boost low-draft player who overperformed
  - K. Iriafen (WAS, 1.0x, 23 drafts) = 5.16 -- Above-expectation outcome, ambiguous whether knowable
  - A. Atkins (LAS, 1.0x, 4 drafts) = 4.69 -- Above-expectation outcome, ambiguous whether knowable
  - K. Mitchell (IND, 0.8x, 4 drafts) = 3.66 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 7 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-06-24

**Players**: 18 HV
 | **Score range**: 1.82 -- 7.25 (median 3.87)

**Leaderboard**: top score 59.84, floor 49.95, median 51.70

**Winner** (score 59.84):
  - N. Ogwumike (2.2x) = 7.35
  - A. Boston (2x) = 14.51
  - A. Reese (2.3x) = 11.93
  - K. Cardoso (2.4x) = 12.56
  - L. Yueru (4.2x) = 13.50

**Field ownership** (top-20 entries):
  - A. Boston (1.6x/1.4x/2x/1.8x/2.2x): 16/20 = 80%, avg 14.33
  - A. Reese (2.1x/2.3x/2.5x/2.7x): 11/20 = 55%, avg 12.31
  - A. Stevens (1.8x/2x/2.2x/2.4x): 9/20 = 45%, avg 11.12
  - S. Diggins (1.9x/2.1x/1.5x/2.3x): 6/20 = 30%, avg 8.71
  - R. Howard (1.6x/1.8x/2x/2.2x): 6/20 = 30%, avg 7.61
  - N. Ogwumike (1.6x/1.8x/2x/2.2x): 5/20 = 25%, avg 6.41
  - L. Yueru (4.4x/4.2x): 5/20 = 25%, avg 13.63
  - A. Smith (1.9x/2.3x/2.7x): 5/20 = 25%, avg 12.93

### Outcome Classification

**(A) Correctly priced** (13 players):
  - A. Boston (IND, 0.2x, 499 drafts) = 7.25 -- High-draft player delivered as expected
  - A. Reese (ATL, 0.7x, 373 drafts) = 5.19 -- High-draft player delivered as expected
  - A. Stevens (CHI, 0.4x, 101 drafts) = 5.21 -- High-draft player delivered as expected
  - L. Hull (IND, 1.3x, 21 drafts) = 3.61 -- Mid-draft player with mid outcome -- no edge either way
  - S. Diggins (CHI, 0.3x, 223 drafts) = 4.66 -- High-draft player delivered as expected
  - S. Austin (WAS, 0.9x, 74 drafts) = 3.27 -- High-draft player delivered as expected
  - A. Ogunbowale (DAL, 0.6x, 176 drafts) = 3.59 -- High-draft player delivered as expected
  - A. James (DAL, 3.0x, 21 drafts) = 1.86 -- Mid-draft player with mid outcome -- no edge either way
  - D. Dantas (IND, 3.0x, 11 drafts) = 1.82 -- Mid-draft player with mid outcome -- no edge either way
  - D. Hamby (LAS, 0.3x, 140 drafts) = 3.83 -- High-draft player delivered as expected
  - R. Howard (ATL, 0.2x, 220 drafts) = 3.87 -- High-draft player delivered as expected
  - R. Jackson (CHI, 1.4x, 406 drafts) = 2.4 -- Outcome roughly matched draft position and signals
  - B. Jones (ATL, 0.8x, 144 drafts) = 2.76 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (5 players):
  - L. Yueru (DAL, 3.0x, 2 drafts) = 3.21 -- High-boost low-draft player who overperformed
  - K. Cardoso (CHI, 1.0x, 17 drafts) = 5.23 -- Above-expectation outcome, ambiguous whether knowable
  - J. Shepard (DAL, 1.7x, 4 drafts) = 4.11 -- Above-expectation outcome, ambiguous whether knowable
  - A. Smith (DAL, 0.7x, 9 drafts) = 5.62 -- Above-expectation outcome, ambiguous whether knowable
  - K. Mitchell (IND, 0.7x, 26 drafts) = 5.21 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 5 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-06-25

**Players**: 18 HV
 | **Score range**: 1.36 -- 5.80 (median 2.83)

**Leaderboard**: top score 51.76, floor 47.86, median 48.65

**Winner** (score 51.76):
  - A. Wilson (2x) = 11.59
  - K. Burke (3.6x) = 15.22
  - V. Burton (2.4000000000000004x) = 9.80
  - S. Rivers (3.2x) = 6.41
  - M. Johannes (3.5999999999999996x) = 8.74
  - **Game stack**: team 11: 2 players

**Field ownership** (top-20 entries):
  - A. Wilson (1.6x/1.8x/2x): 18/20 = 90%, avg 11.27
  - B. Stewart (1.9x/1.5x/1.7x/2.1x): 17/20 = 85%, avg 9.26
  - K. Burke (3x/3.2x/3.8x/3.6x/3.4x): 16/20 = 80%, avg 13.74
  - V. Burton (2.4x/2x/2.2x/2.6x): 9/20 = 45%, avg 9.35
  - M. Johannes (3.8x/3.6x): 8/20 = 40%, avg 8.98
  - J. Young (1.8x/2x/2.2x): 8/20 = 40%, avg 7.41
  - C. Gray (2.3x/2.7x): 6/20 = 30%, avg 7.29
  - S. Rivers (3.2x/3x): 4/20 = 20%, avg 6.21

### Outcome Classification

**(A) Correctly priced** (17 players):
  - K. Burke (CON, 1.8x, 111 drafts) = 4.23 -- High-draft player delivered as expected
  - S. Talbot (LVA, 3.0x, 4 drafts) = 2.65 -- Outcome roughly matched draft position and signals
  - A. Wilson (LVA, 0.0x, 4000 drafts) = 5.8 -- High-draft player delivered as expected
  - V. Burton (GSV, 0.8x, 180 drafts) = 4.08 -- High-draft player delivered as expected
  - M. Johannes (NYL, 2.4x, 110 drafts) = 2.43 -- Outcome roughly matched draft position and signals
  - B. Stewart (NYL, 0.1x, 1400 drafts) = 4.91 -- High-draft player delivered as expected
  - T. Hayes (GSV, 1.5x, 16 drafts) = 2.7 -- Mid-draft player with mid outcome -- no edge either way
  - K. Bell (LVA, 3.0x, 2 drafts) = 2.05 -- Outcome roughly matched draft position and signals
  - R. Gardner (NYL, 3.0x, 3 drafts) = 1.88 -- Outcome roughly matched draft position and signals
  - C. Gray (LVA, 0.9x, 261 drafts) = 3.08 -- High-draft player delivered as expected
  - J. Young (LVA, 0.4x, 310 drafts) = 3.71 -- High-draft player delivered as expected
  - J. Loyd (LVA, 0.9x, 302 drafts) = 2.83 -- Outcome roughly matched draft position and signals
  - S. Rivers (CON, 1.8x, 108 drafts) = 2.0 -- Outcome roughly matched draft position and signals
  - K. Thornton (GSV, 0.7x, 793 drafts) = 2.51 -- Outcome roughly matched draft position and signals
  - J. Sheldon (CHI, 1.9x, 156 drafts) = 1.7 -- Outcome roughly matched draft position and signals
  - S. Ionescu (NYL, 0.0x, 2000 drafts) = 3.09 -- High-draft player delivered as expected
  - N. Sabally (TOR, 1.8x, 22 drafts) = 1.36 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (1 players):
  - K. Martin (LAS, 3.0x, 8 drafts) = 3.03 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-06-26

**Players**: 17 HV
 | **Score range**: 1.19 -- 4.15 (median 2.86)

**Leaderboard**: top score 53.20, floor 45.49, median 47.19

**Winner** (score 53.20):
  - D. Evans (5x) = 12.87
  - S. Citron (2.7x) = 9.48
  - L. Olsen (4.6x) = 13.13
  - S. Sutton (4.1x) = 12.72
  - S. Dolson (4.2x) = 4.99
  - **Game stack**: team 7: 2 players

**Field ownership** (top-20 entries):
  - S. Sutton (4.1x/4.7x/4.3x/4.5x/3.9x): 18/20 = 90%, avg 13.34
  - D. Evans (4.4x/4.6x/5x/4.2x): 12/20 = 60%, avg 11.89
  - S. Citron (2.3x/2.7x/2.9x/2.1x/2.5x): 11/20 = 55%, avg 8.85
  - L. Olsen (4.4x/4.6x/4.2x/5x): 11/20 = 55%, avg 12.66
  - A. Wilson (1.6x/1.2x/2x/1.8x): 10/20 = 50%, avg 7.22
  - C. Gray (2.8x/2.6x/2.4x/2x/2.2x): 8/20 = 40%, avg 7.53
  - S. Austin (2.4x/2.8x/2.2x/2x): 7/20 = 35%, avg 8.06
  - J. Young (1.6x/2.4x/1.8x/2.2x): 5/20 = 25%, avg 7.31

### Outcome Classification

**(A) Correctly priced** (17 players):
  - L. Olsen (WAS, 3.0x, 24 drafts) = 2.85 -- Mid-draft player with mid outcome -- no edge either way
  - D. Evans (LVA, 3.0x, 22 drafts) = 2.57 -- Mid-draft player with mid outcome -- no edge either way
  - S. Citron (WAS, 0.9x, 275 drafts) = 3.51 -- High-draft player delivered as expected
  - S. Cunningham (IND, 3.0x, 16 drafts) = 1.97 -- Mid-draft player with mid outcome -- no edge either way
  - S. Austin (WAS, 0.8x, 310 drafts) = 3.44 -- High-draft player delivered as expected
  - C. Gray (LVA, 0.8x, 276 drafts) = 3.11 -- High-draft player delivered as expected
  - K. Plum (LAS, 0.3x, 405 drafts) = 4.03 -- High-draft player delivered as expected
  - A. Stevens (CHI, 0.3x, 164 drafts) = 3.91 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 4600 drafts) = 4.15 -- High-draft player delivered as expected
  - J. Young (LVA, 0.4x, 364 drafts) = 3.51 -- High-draft player delivered as expected
  - K. Mitchell (IND, 0.6x, 303 drafts) = 2.86 -- Outcome roughly matched draft position and signals
  - A. Edwards (CON, 3.0x, 31 drafts) = 1.44 -- Mid-draft player with mid outcome -- no edge either way
  - A. Boston (IND, 0.1x, 1100 drafts) = 3.16 -- High-draft player delivered as expected
  - R. Jackson (CHI, 1.4x, 308 drafts) = 1.9 -- Outcome roughly matched draft position and signals
  - K. Stokes (GSV, 3.0x, 25 drafts) = 1.29 -- Mid-draft player with mid outcome -- no edge either way
  - K. Iriafen (WAS, 0.8x, 248 drafts) = 2.15 -- Outcome roughly matched draft position and signals
  - S. Dolson (SEA, 3.0x, 21 drafts) = 1.19 -- Mid-draft player with mid outcome -- no edge either way

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-06-27

**Players**: 19 HV
 | **Score range**: 2.22 -- 6.64 (median 3.95)

**Leaderboard**: top score 57.84, floor 51.46, median 52.67

**Winner** (score 57.84):
  - S. Whitcomb (3.6x) = 12.09
  - K. Laksa (3.9000000000000004x) = 7.24
  - K. Nurse (4.6x) = 14.74
  - T. Hayes (2.7x) = 7.16
  - A. Morrow (4.2x) = 16.61

**Field ownership** (top-20 entries):
  - K. Mitchell (2.6x/2.4x/2x/1.8x/2.2x): 18/20 = 90%, avg 14.90
  - P. Bueckers (1.9x/2.1x): 14/20 = 70%, avg 10.82
  - A. Thomas (1.9x/2.1x/1.7x/1.3x): 8/20 = 40%, avg 11.79
  - A. Reese (2.4x/1.8x/2.2x/2x): 6/20 = 30%, avg 8.34
  - S. Whitcomb (2.8x/3x/3.6x): 5/20 = 25%, avg 10.08
  - N. Howard (3.2x/3.4x/2.8x): 5/20 = 25%, avg 14.15
  - B. Jones (2.4x/2x/2.2x): 5/20 = 25%, avg 8.20
  - A. Boston (1.9x/2.1x/1.5x): 4/20 = 20%, avg 8.73

### Outcome Classification

**(A) Correctly priced** (13 players):
  - K. Mitchell (IND, 0.6x, 178 drafts) = 6.64 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.1x, 494 drafts) = 6.29 -- High-draft player delivered as expected
  - O. Nelson-Ododa (CON, 1.5x, 16 drafts) = 3.37 -- Mid-draft player with mid outcome -- no edge either way
  - B. Carleton (POR, 1.9x, 2 drafts) = 2.94 -- Outcome roughly matched draft position and signals
  - C. Williams (MIN, 0.6x, 142 drafts) = 4.36 -- High-draft player delivered as expected
  - P. Bueckers (DAL, 0.1x, 1600 drafts) = 5.3 -- High-draft player delivered as expected
  - D. Malonga (SEA, 3.0x, 2 drafts) = 2.22 -- Outcome roughly matched draft position and signals
  - B. Jones (ATL, 0.8x, 126 drafts) = 3.87 -- High-draft player delivered as expected
  - N. Collier (MIN, 0.0x, 1000 drafts) = 5.34 -- High-draft player delivered as expected
  - S. Diggins (CHI, 0.3x, 297 drafts) = 4.64 -- High-draft player delivered as expected
  - K. Thornton (GSV, 0.7x, 61 drafts) = 3.95 -- High-draft player delivered as expected
  - A. Atkins (LAS, 0.8x, 47 drafts) = 3.78 -- Mid-draft player with mid outcome -- no edge either way
  - S. Sabally (NYL, 0.3x, 312 drafts) = 4.53 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (6 players):
  - A. Morrow (CON, 3.0x, 1 drafts) = 3.95 -- High-boost low-draft player who overperformed
  - N. Howard (MIN, 1.6x, 4 drafts) = 4.48 -- Above-expectation outcome, ambiguous whether knowable
  - J. Canada (ATL, 1.8x, 1 drafts) = 4.17 -- Above-expectation outcome, ambiguous whether knowable
  - K. Nurse (TOR, 3.0x, 1 drafts) = 3.2 -- High-boost low-draft player who overperformed
  - S. Whitcomb (PHO, 1.6x, 5 drafts) = 3.36 -- Above-expectation outcome, ambiguous whether knowable
  - N. Sabally (TOR, 1.9x, 1 drafts) = 3.03 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 6 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-06-28

**Players**: 18 HV
 | **Score range**: -0.00 -- 3.95 (median 1.33)

**Leaderboard**: top score 50.10, floor 45.49, median 47.33

**Winner** (score 50.10):
  - S. Citron (2.8x) = 11.07
  - A. James (4.6x) = 12.97
  - M. Hines-Allen (3.8000000000000003x) = 14.07
  - N. Smith (3.6x) = 4.78
  - S. Sutton (3.5999999999999996x) = 7.22

**Field ownership** (top-20 entries):
  - S. Citron (2.8x/2.6x/2.4x/2x/2.2x): 20/20 = 100%, avg 10.08
  - A. James (4.8x/4x/4.6x/4.2x/4.4x): 20/20 = 100%, avg 12.15
  - M. Hines-Allen (4x/4.2x/3.4x/3.8x/3.6x): 20/20 = 100%, avg 13.96
  - S. Sutton (4x/4.2x/4.4x/3.8x/3.6x): 10/20 = 50%, avg 7.90
  - A. Ogunbowale (2.6x/2.4x/2x/1.8x/2.2x): 9/20 = 45%, avg 5.00
  - L. Yueru (4.4x/5x/4.2x): 8/20 = 40%, avg 5.05
  - N. Smith (4x/3.8x/3.6x): 4/20 = 20%, avg 4.98
  - S. Austin (2.4x/2.8x/2.6x): 4/20 = 20%, avg 4.19

### Outcome Classification

**(A) Correctly priced** (18 players):
  - M. Hines-Allen (IND, 2.2x, 165 drafts) = 3.7 -- High-draft player delivered as expected
  - A. James (DAL, 2.8x, 183 drafts) = 2.82 -- Outcome roughly matched draft position and signals
  - S. Citron (WAS, 0.8x, 915 drafts) = 3.95 -- High-draft player delivered as expected
  - J. Quinerly (DAL, 3.0x, 8 drafts) = 1.98 -- Outcome roughly matched draft position and signals
  - A. Ogunbowale (DAL, 0.6x, 2300 drafts) = 2.21 -- Outcome roughly matched draft position and signals
  - N. Smith (LVA, 2.2x, 169 drafts) = 1.33 -- High-draft player underperformed -- field took the loss equally
  - L. Yueru (DAL, 3.0x, 202 drafts) = 1.13 -- High-draft player underperformed -- field took the loss equally
  - A. Edwards (CON, 3.0x, 157 drafts) = 0.94 -- High-draft player underperformed -- field took the loss equally
  - K. Iriafen (WAS, 0.8x, 728 drafts) = 1.6 -- Outcome roughly matched draft position and signals
  - S. Austin (WAS, 0.8x, 744 drafts) = 1.58 -- Outcome roughly matched draft position and signals
  - B. Sykes (TOR, 0.4x, 286 drafts) = 1.52 -- Outcome roughly matched draft position and signals
  - L. Olsen (WAS, 3.0x, 16 drafts) = 0.42 -- Mid-draft player with mid outcome -- no edge either way
  - K. Charles (GSV, 3.0x, 147 drafts) = 0.3 -- High-draft player underperformed -- field took the loss equally
  - S. Koné (ATL, 3.0x, 4 drafts) = 0.2 -- Low-draft player correctly faded by the field
  - P. Bueckers (DAL, 0.1x, None drafts) = None -- Low-draft player correctly faded by the field
  - S. Dolson (SEA, 3.0x, None drafts) = -0.0 -- Low-draft player correctly faded by the field
  - D. Carrington (CHI, 1.2x, None drafts) = None -- Low-draft player correctly faded by the field
  - M. Siegrist (DAL, 1.7x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-06-29

**Players**: 20 HV
 | **Score range**: 1.99 -- 5.76 (median 3.60)

**Leaderboard**: top score 57.19, floor 53.60, median 54.44

**Winner** (score 57.19):
  - N. Collier (2x) = 9.14
  - A. Atkins (2.6x) = 8.40
  - A. Morrow (4.2x) = 15.93
  - A. Reese (2x) = 11.51
  - R. Banham (4.2x) = 12.21

**Field ownership** (top-20 entries):
  - A. Morrow (3.8x/4x/4.2x): 20/20 = 100%, avg 15.10
  - A. Reese (2.4x/2x/2.2x/2.6x): 16/20 = 80%, avg 13.60
  - A. Wilson (1.8x/2x): 10/20 = 50%, avg 10.92
  - N. Collier (1.8x/2x): 9/20 = 45%, avg 9.03
  - A. Atkins (2.4x/2.6x): 7/20 = 35%, avg 8.03
  - R. Banham (4.4x/4.2x/4.8x): 6/20 = 30%, avg 12.59
  - K. Martin (4.4x/5x/4.2x): 6/20 = 30%, avg 8.70
  - T. Hayes (2.8x/2.6x): 3/20 = 15%, avg 9.84

### Outcome Classification

**(A) Correctly priced** (16 players):
  - A. Reese (ATL, 0.6x, 385 drafts) = 5.76 -- High-draft player delivered as expected
  - R. Banham (CHI, 3.0x, 4 drafts) = 2.91 -- Outcome roughly matched draft position and signals
  - A. Nye (ATL, 3.0x, 1 drafts) = 2.92 -- Outcome roughly matched draft position and signals
  - N. Hiedeman (SEA, 1.8x, 14 drafts) = 3.07 -- Mid-draft player with mid outcome -- no edge either way
  - T. Hayes (GSV, 1.2x, 341 drafts) = 3.6 -- High-draft player delivered as expected
  - D. Hamby (LAS, 0.3x, 108 drafts) = 4.94 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 2100 drafts) = 5.63 -- High-draft player delivered as expected
  - B. Jones (ATL, 0.7x, 86 drafts) = 4.03 -- High-draft player delivered as expected
  - K. Martin (LAS, 3.0x, 32 drafts) = 1.99 -- Mid-draft player with mid outcome -- no edge either way
  - K. McBride (MIN, 0.6x, 33 drafts) = 3.76 -- Mid-draft player with mid outcome -- no edge either way
  - C. Williams (MIN, 0.6x, 171 drafts) = 3.75 -- High-draft player delivered as expected
  - V. Burton (GSV, 0.8x, 58 drafts) = 3.39 -- High-draft player delivered as expected
  - K. Plum (LAS, 0.2x, 371 drafts) = 4.25 -- High-draft player delivered as expected
  - N. Collier (MIN, 0.0x, 3000 drafts) = 4.57 -- High-draft player delivered as expected
  - K. Copper (PHO, 1.3x, 8 drafts) = 2.75 -- Outcome roughly matched draft position and signals
  - A. Atkins (LAS, 0.8x, 24 drafts) = 3.23 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (4 players):
  - A. Morrow (CON, 2.6x, 7 drafts) = 3.79 -- Above-expectation outcome, ambiguous whether knowable
  - E. Williams (CHI, 2.3x, 1 drafts) = 3.28 -- Above-expectation outcome, ambiguous whether knowable
  - J. Canada (ATL, 1.4x, 3 drafts) = 3.42 -- Above-expectation outcome, ambiguous whether knowable
  - N. Cloud (CHI, 0.8x, 4 drafts) = 3.56 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 4 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-07-01

**Players**: 17 HV
 | **Score range**: -0.13 -- 4.24 (median 1.31)

**Leaderboard**: top score 40.77, floor 37.92, median 39.13

**Winner** (score 40.77):
  - A. Smith (2.6x) = 8.08
  - A. Boston (1.9000000000000001x) = 8.06
  - S. Cunningham (4.6x) = 12.09
  - J. Shepard (3x) = 5.22
  - N. Howard (2.5x) = 7.31
  - **Game stack**: team 12: 2 players, team 3: 2 players

**Field ownership** (top-20 entries):
  - S. Cunningham (4.4x/4.6x/4.2x): 20/20 = 100%, avg 11.38
  - N. Howard (3.1x/2.7x/2.9x/2.5x/3.3x): 20/20 = 100%, avg 7.93
  - A. Boston (1.9x/2.1x/1.5x): 19/20 = 95%, avg 8.11
  - N. Collier (1.8x/2x): 16/20 = 80%, avg 5.31
  - A. Smith (2.4x/2x/2.2x/2.6x): 15/20 = 75%, avg 6.92
  - J. Shepard (3.2x/2.8x/3x): 6/20 = 30%, avg 5.16
  - A. McDonald (2.2x/2.6x): 2/20 = 10%, avg 5.30
  - L. Hull (2.8x): 1/20 = 5%, avg 3.68

### Outcome Classification

**(A) Correctly priced** (17 players):
  - S. Cunningham (IND, 3.0x, 347 drafts) = 2.63 -- Outcome roughly matched draft position and signals
  - N. Howard (MIN, 1.3x, 224 drafts) = 2.93 -- Outcome roughly matched draft position and signals
  - A. Boston (IND, 0.1x, 1000 drafts) = 4.24 -- High-draft player delivered as expected
  - A. Smith (DAL, 0.6x, 329 drafts) = 3.11 -- High-draft player delivered as expected
  - J. Shepard (DAL, 1.6x, 128 drafts) = 1.74 -- Outcome roughly matched draft position and signals
  - N. Collier (MIN, 0.0x, 7100 drafts) = 2.67 -- Outcome roughly matched draft position and signals
  - L. Hull (IND, 1.4x, 248 drafts) = 1.31 -- High-draft player underperformed -- field took the loss equally
  - K. McBride (MIN, 0.6x, 304 drafts) = 1.7 -- Outcome roughly matched draft position and signals
  - K. Mitchell (IND, 0.5x, 517 drafts) = 1.49 -- High-draft player underperformed -- field took the loss equally
  - M. Timpson (IND, 3.0x, 7 drafts) = 0.63 -- Low-draft player correctly faded by the field
  - C. Williams (MIN, 0.5x, 412 drafts) = 1.05 -- High-draft player underperformed -- field took the loss equally
  - D. Miller (CON, 3.0x, 106 drafts) = 0.39 -- High-draft player underperformed -- field took the loss equally
  - B. Carleton (POR, 1.8x, 159 drafts) = 0.51 -- High-draft player underperformed -- field took the loss equally
  - M. Kliundikova (TOR, 2.1x, 141 drafts) = 0.34 -- High-draft player underperformed -- field took the loss equally
  - B. Turner (LVA, 3.0x, 5 drafts) = 0.09 -- Low-draft player correctly faded by the field
  - N. Hiedeman (SEA, 1.7x, None drafts) = -0.13 -- Low-draft player correctly faded by the field
  - C. Clark (IND, 0.2x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-07-03

**Players**: 20 HV
 | **Score range**: 2.06 -- 6.48 (median 4.26)

**Leaderboard**: top score 83.30, floor 79.79, median 80.13

**Winner** (score 83.30):
  - K. Copper (3.2x) = 13.41
  - E. Wheeler (2.9000000000000004x) = 12.14
  - A. James (4.1x) = 26.58
  - J. Quinerly (4.4x) = 21.03
  - L. Yueru (4.2x) = 10.14
  - **Game stack**: team 12: 3 players

**Field ownership** (top-20 entries):
  - K. Copper (3.2x/3x/2.8x): 20/20 = 100%, avg 12.57
  - A. James (4.3x/4.1x/3.9x): 20/20 = 100%, avg 25.93
  - J. Quinerly (4.4x/4.6x/4.2x): 20/20 = 100%, avg 21.37
  - L. Yueru (4.6x/4.2x): 18/20 = 90%, avg 10.19
  - N. Collier (2x): 17/20 = 85%, avg 9.82
  - J. Canada (3x): 2/20 = 10%, avg 13.24
  - E. Wheeler (2.9x): 1/20 = 5%, avg 12.14
  - J. Allemand (4.2x): 1/20 = 5%, avg 7.76

### Outcome Classification

**(A) Correctly priced** (16 players):
  - K. Copper (PHO, 1.2x, 343 drafts) = 4.19 -- High-draft player delivered as expected
  - N. Cloud (CHI, 0.8x, 13 drafts) = 4.73 -- Mid-draft player with mid outcome -- no edge either way
  - E. Wheeler (LAS, 1.1x, 20 drafts) = 4.19 -- Mid-draft player with mid outcome -- no edge either way
  - D. Hamby (LAS, 0.3x, 179 drafts) = 5.4 -- High-draft player delivered as expected
  - I. Harrison (TOR, 3.0x, 1 drafts) = 2.48 -- Outcome roughly matched draft position and signals
  - L. Yueru (DAL, 3.0x, 10 drafts) = 2.41 -- Mid-draft player with mid outcome -- no edge either way
  - C. Williams (MIN, 0.6x, 31 drafts) = 4.26 -- Mid-draft player with mid outcome -- no edge either way
  - N. Howard (MIN, 1.3x, 12 drafts) = 3.18 -- Mid-draft player with mid outcome -- no edge either way
  - B. Jones (ATL, 0.7x, 17 drafts) = 3.87 -- Mid-draft player with mid outcome -- no edge either way
  - B. Stewart (NYL, 0.1x, 544 drafts) = 4.87 -- High-draft player delivered as expected
  - K. Mitchell (IND, 0.5x, 41 drafts) = 4.01 -- Mid-draft player with mid outcome -- no edge either way
  - M. Akoa Makani (PHO, 1.9x, 9 drafts) = 2.56 -- Outcome roughly matched draft position and signals
  - N. Ogwumike (LAS, 0.3x, 178 drafts) = 4.34 -- High-draft player delivered as expected
  - A. Edwards (CON, 3.0x, 1 drafts) = 2.06 -- Outcome roughly matched draft position and signals
  - N. Collier (MIN, 0.0x, 2600 drafts) = 4.91 -- High-draft player delivered as expected
  - P. Bueckers (DAL, 0.1x, 809 drafts) = 4.43 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (4 players):
  - A. James (DAL, 2.5x, 47 drafts) = 6.48 -- Above-expectation outcome, ambiguous whether knowable
  - J. Quinerly (DAL, 3.0x, 9 drafts) = 4.78 -- Above-expectation outcome, ambiguous whether knowable
  - L. Olsen (WAS, 3.0x, 1 drafts) = 3.37 -- High-boost low-draft player who overperformed
  - J. Canada (ATL, 1.2x, 6 drafts) = 4.41 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 4 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-07-05

**Players**: 18 HV
 | **Score range**: 1.07 -- 4.90 (median 2.88)

**Leaderboard**: top score 51.94, floor 50.08, median 50.08

**Winner** (score 51.94):
  - K. Thornton (2.8x) = 9.97
  - N. Howard (3x) = 11.76
  - T. Hayes (2.7x) = 12.11
  - J. Shepard (3x) = 11.09
  - J. Allemand (4.2x) = 7.01
  - **Game stack**: team 14: 2 players

**Field ownership** (top-20 entries):
  - N. Howard (3x/2.6x): 20/20 = 100%, avg 10.27
  - T. Hayes (2.7x): 20/20 = 100%, avg 12.11
  - N. Collier (2x): 19/20 = 95%, avg 7.26
  - A. Boston (1.9x): 19/20 = 95%, avg 9.32
  - S. Talbot (4.2x): 19/20 = 95%, avg 11.21
  - K. Thornton (2.8x): 1/20 = 5%, avg 9.97
  - J. Shepard (3x): 1/20 = 5%, avg 11.09
  - J. Allemand (4.2x): 1/20 = 5%, avg 7.01

### Outcome Classification

**(A) Correctly priced** (18 players):
  - T. Hayes (GSV, 1.1x, 97 drafts) = 4.48 -- High-draft player delivered as expected
  - S. Talbot (LVA, 3.0x, 12 drafts) = 2.67 -- Mid-draft player with mid outcome -- no edge either way
  - J. Shepard (DAL, 1.6x, 106 drafts) = 3.7 -- High-draft player delivered as expected
  - N. Howard (MIN, 1.2x, 200 drafts) = 3.92 -- High-draft player delivered as expected
  - A. Boston (IND, 0.1x, 893 drafts) = 4.9 -- High-draft player delivered as expected
  - R. Jackson (CHI, 1.5x, 17 drafts) = 2.88 -- Mid-draft player with mid outcome -- no edge either way
  - K. Thornton (GSV, 0.8x, 445 drafts) = 3.56 -- High-draft player delivered as expected
  - A. Stevens (CHI, 0.3x, 237 drafts) = 4.02 -- High-draft player delivered as expected
  - B. Carleton (POR, 1.9x, 144 drafts) = 2.24 -- Outcome roughly matched draft position and signals
  - J. Allemand (TOR, 3.0x, 6 drafts) = 1.67 -- Outcome roughly matched draft position and signals
  - K. Plum (LAS, 0.3x, 679 drafts) = 3.21 -- High-draft player delivered as expected
  - N. Collier (MIN, 0.0x, 4800 drafts) = 3.63 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.6x, 227 drafts) = 2.77 -- Outcome roughly matched draft position and signals
  - D. Hamby (LAS, 0.2x, 462 drafts) = 2.87 -- Outcome roughly matched draft position and signals
  - A. Smith (DAL, 0.6x, 230 drafts) = 2.35 -- Outcome roughly matched draft position and signals
  - K. Mitchell (IND, 0.5x, 356 drafts) = 2.27 -- Outcome roughly matched draft position and signals
  - K. McBride (MIN, 0.7x, 220 drafts) = 2.02 -- Outcome roughly matched draft position and signals
  - S. Cunningham (IND, 3.0x, 59 drafts) = 1.07 -- High-draft player underperformed -- field took the loss equally

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-07-06

**Players**: 19 HV
 | **Score range**: 1.57 -- 5.34 (median 3.04)

**Leaderboard**: top score 58.03, floor 49.53, median 50.84

**Winner** (score 58.03):
  - A. Wilson (2x) = 8.55
  - C. Williams (2.4x) = 11.16
  - A. Atkins (2.3x) = 7.00
  - R. Banham (4.4x) = 16.51
  - D. Evans (4.2x) = 14.81
  - **Game stack**: team 1: 2 players

**Field ownership** (top-20 entries):
  - R. Banham (4.4x/4.6x/5x/4.2x): 20/20 = 100%, avg 16.62
  - C. Williams (2.4x/2x/2.2x/2.6x): 14/20 = 70%, avg 10.76
  - A. Reese (1.9x/2.1x/2.3x/2.5x): 12/20 = 60%, avg 8.97
  - M. Kliundikova (4.1x/4.7x/4.9x/4.3x/4.5x): 8/20 = 40%, avg 9.77
  - D. Miller (4.4x/4.2x): 7/20 = 35%, avg 11.20
  - A. Wilson (1.8x/2x): 6/20 = 30%, avg 8.41
  - M. Onyenwere (4.4x/5x/4.2x): 5/20 = 25%, avg 9.88
  - E. Williams (4.1x/3.7x/3.9x): 5/20 = 25%, avg 8.76

### Outcome Classification

**(A) Correctly priced** (18 players):
  - R. Banham (CHI, 3.0x, 29 drafts) = 3.75 -- Mid-draft player with mid outcome -- no edge either way
  - D. Miller (CON, 3.0x, 8 drafts) = 2.65 -- Outcome roughly matched draft position and signals
  - D. Malonga (SEA, 3.0x, 1 drafts) = 2.58 -- Outcome roughly matched draft position and signals
  - N. Smith (LVA, 2.3x, 47 drafts) = 2.92 -- Mid-draft player with mid outcome -- no edge either way
  - C. Williams (MIN, 0.6x, 221 drafts) = 4.65 -- High-draft player delivered as expected
  - S. Ionescu (NYL, 0.2x, 309 drafts) = 5.34 -- High-draft player delivered as expected
  - M. Onyenwere (WAS, 3.0x, 17 drafts) = 2.24 -- Mid-draft player with mid outcome -- no edge either way
  - M. Kliundikova (TOR, 2.9x, 17 drafts) = 2.15 -- Mid-draft player with mid outcome -- no edge either way
  - E. Magbegor (SEA, 1.0x, 65 drafts) = 3.49 -- High-draft player delivered as expected
  - A. Reese (ATL, 0.5x, 752 drafts) = 4.02 -- High-draft player delivered as expected
  - G. Williams (GSV, 0.4x, 110 drafts) = 4.04 -- High-draft player delivered as expected
  - A. Clark (DAL, 3.0x, 3 drafts) = 1.88 -- Outcome roughly matched draft position and signals
  - E. Williams (CHI, 2.1x, 40 drafts) = 2.2 -- Mid-draft player with mid outcome -- no edge either way
  - A. Wilson (LVA, 0.0x, 2800 drafts) = 4.28 -- High-draft player delivered as expected
  - A. Atkins (LAS, 0.7x, 188 drafts) = 3.04 -- High-draft player delivered as expected
  - J. Young (LVA, 0.5x, 183 drafts) = 3.03 -- High-draft player delivered as expected
  - K. Bell (LVA, 3.0x, 1 drafts) = 1.57 -- Outcome roughly matched draft position and signals
  - N. Ogwumike (LAS, 0.3x, 155 drafts) = 3.25 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (1 players):
  - D. Evans (LVA, 3.0x, 1 drafts) = 3.53 -- High-boost low-draft player who overperformed

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-07-07

**Players**: 18 HV
 | **Score range**: 1.60 -- 7.44 (median 3.20)

**Leaderboard**: top score 69.45, floor 62.68, median 65.43

**Winner** (score 69.45):
  - P. Bueckers (2.1x) = 3.03
  - A. Thomas (1.9000000000000001x) = 11.68
  - K. Williams (4.6x) = 19.29
  - N. Mack (4.4x) = 15.36
  - S. Whitcomb (2.7x) = 20.10
  - **Game stack**: team 6: 4 players

**Field ownership** (top-20 entries):
  - S. Whitcomb (3.5x/3.1x/2.7x/2.9x/3.3x): 20/20 = 100%, avg 23.97
  - A. Thomas (1.9x/1.5x/1.3x/2.1x/1.7x): 13/20 = 65%, avg 11.68
  - N. Hillmon (3x/3.6x/3.2x/3.8x/3.4x): 9/20 = 45%, avg 11.53
  - J. Quinerly (4.4x/4.6x/4.2x/4.8x): 7/20 = 35%, avg 11.18
  - M. Billings (3.2x/3x/3.8x): 7/20 = 35%, avg 10.33
  - M. Hines-Allen (4.1x/3.9x/3.5x/3.3x): 6/20 = 30%, avg 8.52
  - K. Brown (4.6x/4.8x/5x): 6/20 = 30%, avg 13.22
  - K. Westbeld (3.1x/3.9x/3.3x): 5/20 = 25%, avg 6.56

### Outcome Classification

**(A) Correctly priced** (16 players):
  - S. Whitcomb (PHO, 1.5x, 216 drafts) = 7.44 -- High-draft player delivered as expected
  - N. Hillmon (ATL, 1.8x, 99 drafts) = 3.51 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.1x, 1200 drafts) = 6.15 -- High-draft player delivered as expected
  - J. Quinerly (DAL, 3.0x, 96 drafts) = 2.51 -- Outcome roughly matched draft position and signals
  - M. Billings (IND, 1.8x, 108 drafts) = 3.2 -- High-draft player delivered as expected
  - B. Jones (ATL, 0.6x, 276 drafts) = 4.03 -- High-draft player delivered as expected
  - J. Canada (ATL, 1.0x, 337 drafts) = 3.48 -- High-draft player delivered as expected
  - M. Hines-Allen (IND, 2.1x, 144 drafts) = 2.37 -- Outcome roughly matched draft position and signals
  - A. Gray (ATL, 0.2x, 657 drafts) = 4.17 -- High-draft player delivered as expected
  - K. Thornton (GSV, 0.7x, 269 drafts) = 3.06 -- High-draft player delivered as expected
  - K. Martin (LAS, 3.0x, 15 drafts) = 1.6 -- Mid-draft player with mid outcome -- no edge either way
  - M. Akoa Makani (PHO, 1.8x, 182 drafts) = 2.03 -- Outcome roughly matched draft position and signals
  - K. Westbeld (PHO, 1.9x, 152 drafts) = 1.94 -- Outcome roughly matched draft position and signals
  - R. Howard (ATL, 0.3x, 34 drafts) = 3.18 -- Mid-draft player with mid outcome -- no edge either way
  - V. Burton (GSV, 0.8x, 148 drafts) = 2.46 -- Outcome roughly matched draft position and signals
  - A. James (DAL, 1.7x, 981 drafts) = 1.77 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (2 players):
  - K. Williams (PHO, 3.0x, 4 drafts) = 4.19 -- Above-expectation outcome, ambiguous whether knowable
  - N. Mack (PHO, 3.0x, 1 drafts) = 3.49 -- High-boost low-draft player who overperformed

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-07-08

**Players**: 19 HV
 | **Score range**: 1.09 -- 5.75 (median 2.39)

**Leaderboard**: top score 52.39, floor 47.57, median 50.51

**Winner** (score 52.39):
  - A. Reese (2.4x) = 9.30
  - S. Austin (2.7x) = 11.95
  - E. Williams (3.6x) = 9.48
  - L. Fiebich (3.8x) = 12.92
  - R. Banham (3.9000000000000004x) = 8.73
  - **Game stack**: team 8: 2 players

**Field ownership** (top-20 entries):
  - L. Fiebich (4.4x/3.8x/3.6x): 15/20 = 75%, avg 12.83
  - A. Reese (2.4x/2x/2.2x): 14/20 = 70%, avg 8.97
  - R. Banham (4.3x/4.1x/3.9x): 13/20 = 65%, avg 9.18
  - S. Ionescu (1.9x/2.1x/1.7x): 13/20 = 65%, avg 11.54
  - E. Williams (3.2x/3.4x/3.8x/3.6x): 12/20 = 60%, avg 9.35
  - S. Austin (2.5x/2.7x): 9/20 = 45%, avg 11.75
  - D. Evans (4.4x/4.6x/4.2x): 9/20 = 45%, avg 10.48
  - N. Smith (3.5x/3.7x/3.9x): 6/20 = 30%, avg 8.16

### Outcome Classification

**(A) Correctly priced** (19 players):
  - L. Fiebich (NYL, 2.4x, 64 drafts) = 3.4 -- High-draft player delivered as expected
  - S. Austin (WAS, 0.9x, 90 drafts) = 4.43 -- High-draft player delivered as expected
  - D. Evans (LVA, 3.0x, 53 drafts) = 2.46 -- Outcome roughly matched draft position and signals
  - S. Ionescu (NYL, 0.1x, 1100 drafts) = 5.75 -- High-draft player delivered as expected
  - E. Williams (CHI, 2.0x, 63 drafts) = 2.63 -- Outcome roughly matched draft position and signals
  - R. Banham (CHI, 2.7x, 17 drafts) = 2.24 -- Mid-draft player with mid outcome -- no edge either way
  - A. Edwards (CON, 3.0x, 2 drafts) = 2.04 -- Outcome roughly matched draft position and signals
  - A. Reese (ATL, 0.4x, 920 drafts) = 3.88 -- High-draft player delivered as expected
  - N. Smith (LVA, 2.1x, 194 drafts) = 2.25 -- Outcome roughly matched draft position and signals
  - K. Burke (CON, 1.6x, 148 drafts) = 2.38 -- Outcome roughly matched draft position and signals
  - B. Stewart (NYL, 0.1x, 958 drafts) = 4.0 -- High-draft player delivered as expected
  - K. Bell (LVA, 3.0x, 50 drafts) = 1.6 -- Outcome roughly matched draft position and signals
  - S. Citron (WAS, 0.8x, 151 drafts) = 2.82 -- Outcome roughly matched draft position and signals
  - K. Nurse (TOR, 3.0x, 3 drafts) = 1.45 -- Low-draft player correctly faded by the field
  - K. Iriafen (WAS, 1.0x, 87 drafts) = 2.39 -- Outcome roughly matched draft position and signals
  - J. Young (LVA, 0.5x, 262 drafts) = 2.85 -- Outcome roughly matched draft position and signals
  - M. Johannes (NYL, 2.4x, 106 drafts) = 1.5 -- High-draft player underperformed -- field took the loss equally
  - B. Sykes (TOR, 0.6x, 130 drafts) = 2.1 -- Outcome roughly matched draft position and signals
  - R. Allen (NYL, 3.0x, 1 drafts) = 1.09 -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-07-09

**Players**: 18 HV
 | **Score range**: 2.29 -- 6.95 (median 3.62)

**Leaderboard**: top score 81.62, floor 71.04, median 74.60

**Winner** (score 81.62):
  - A. James (3.7x) = 10.61
  - R. Banham (4.3x) = 9.83
  - J. Quinerly (4.6x) = 15.19
  - R. Allen (4.4x) = 30.56
  - L. Yueru (4.2x) = 15.43
  - **Game stack**: team 12: 3 players

**Field ownership** (top-20 entries):
  - R. Allen (4.8x/4.6x/4.2x/4.4x/5x): 20/20 = 100%, avg 31.60
  - L. Yueru (4.8x/4.6x/4.2x/4.4x/5x): 16/20 = 80%, avg 16.58
  - J. Quinerly (4.8x/4.6x/4.2x/4.4x/5x): 15/20 = 75%, avg 15.23
  - R. Banham (4.1x/4.3x/4.5x/3.7x/3.9x): 11/20 = 55%, avg 9.41
  - A. James (3.5x/3.7x/3.3x): 7/20 = 35%, avg 10.20
  - E. Williams (3.5x/3.7x/3.9x): 6/20 = 30%, avg 10.33
  - M. Onyenwere (4.6x/4.2x/4.8x/5x): 5/20 = 25%, avg 5.02
  - K. Cardoso (2.1x/2.3x/2.9x/2.7x): 5/20 = 25%, avg 6.78

### Outcome Classification

**(A) Correctly priced** (16 players):
  - L. Yueru (DAL, 3.0x, 37 drafts) = 3.67 -- Mid-draft player with mid outcome -- no edge either way
  - J. Quinerly (DAL, 3.0x, 56 drafts) = 3.3 -- High-draft player delivered as expected
  - V. Burton (GSV, 0.8x, 74 drafts) = 4.51 -- High-draft player delivered as expected
  - E. Williams (CHI, 1.9x, 75 drafts) = 2.87 -- Outcome roughly matched draft position and signals
  - R. Banham (CHI, 2.5x, 44 drafts) = 2.29 -- Mid-draft player with mid outcome -- no edge either way
  - A. James (DAL, 1.7x, 389 drafts) = 2.87 -- Outcome roughly matched draft position and signals
  - E. Magbegor (SEA, 1.0x, 45 drafts) = 3.45 -- Mid-draft player with mid outcome -- no edge either way
  - K. Thornton (GSV, 0.7x, 90 drafts) = 3.79 -- High-draft player delivered as expected
  - S. Diggins (CHI, 0.3x, 115 drafts) = 4.32 -- High-draft player delivered as expected
  - J. Sheldon (CHI, 2.0x, 2 drafts) = 2.45 -- Outcome roughly matched draft position and signals
  - B. Carleton (POR, 1.9x, 52 drafts) = 2.49 -- Outcome roughly matched draft position and signals
  - A. Thomas (PHO, 0.0x, 648 drafts) = 4.73 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.5x, 191 drafts) = 3.74 -- High-draft player delivered as expected
  - G. Williams (GSV, 0.4x, 97 drafts) = 3.56 -- High-draft player delivered as expected
  - E. Wheeler (LAS, 1.1x, 57 drafts) = 2.65 -- Outcome roughly matched draft position and signals
  - P. Bueckers (DAL, 0.2x, 1200 drafts) = 3.62 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (2 players):
  - R. Allen (NYL, 3.0x, 23 drafts) = 6.95 -- Above-expectation outcome, ambiguous whether knowable
  - S. Rivers (CON, 1.8x, 1 drafts) = 4.45 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-07-10

**Players**: 18 HV
 | **Score range**: 1.01 -- 4.42 (median 2.39)

**Leaderboard**: top score 42.88, floor 41.09, median 41.81

**Winner** (score 42.88):
  - N. Collier (2x) = 8.83
  - A. Smith (2.5x) = 9.14
  - S. Sutton (3.9x) = 5.98
  - N. Hiedeman (3.4x) = 10.83
  - D. Evans (4.2x) = 8.10

**Field ownership** (top-20 entries):
  - N. Hiedeman (3.6x/4x/3.2x/3.8x/3.4x): 16/20 = 80%, avg 11.15
  - C. Williams (1.9x/2.3x/2.6x/2.1x/1.7x/2.5x): 13/20 = 65%, avg 9.05
  - N. Collier (1.6x/1.8x/2x/1.4x): 11/20 = 55%, avg 8.35
  - K. Plum (1.9x/2.1x/1.7x/2.3x): 11/20 = 55%, avg 8.64
  - A. Smith (1.9x/2.3x/2.7x/2.1x/2.5x): 9/20 = 45%, avg 8.49
  - J. Loyd (3x/2.8x/2.6x/2.4x/3.2x): 9/20 = 45%, avg 8.50
  - C. Gray (3x/2.8x/2.6x/2.4x/2.2x): 8/20 = 40%, avg 7.46
  - S. Austin (2.4x/2.8x): 8/20 = 40%, avg 7.03

### Outcome Classification

**(A) Correctly priced** (18 players):
  - N. Hiedeman (SEA, 2.0x, 77 drafts) = 3.19 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.5x, 232 drafts) = 4.2 -- High-draft player delivered as expected
  - J. Loyd (LVA, 1.2x, 185 drafts) = 3.16 -- High-draft player delivered as expected
  - A. Smith (DAL, 0.7x, 125 drafts) = 3.65 -- High-draft player delivered as expected
  - D. Evans (LVA, 3.0x, 59 drafts) = 1.93 -- Outcome roughly matched draft position and signals
  - K. Plum (LAS, 0.3x, 449 drafts) = 4.19 -- High-draft player delivered as expected
  - N. Collier (MIN, 0.0x, 3400 drafts) = 4.42 -- High-draft player delivered as expected
  - C. Gray (LVA, 1.0x, 287 drafts) = 2.9 -- Outcome roughly matched draft position and signals
  - J. Allemand (TOR, 3.0x, 6 drafts) = 1.69 -- Outcome roughly matched draft position and signals
  - M. Kliundikova (TOR, 3.0x, 4 drafts) = 1.71 -- Outcome roughly matched draft position and signals
  - S. Austin (WAS, 0.8x, 322 drafts) = 2.81 -- Outcome roughly matched draft position and signals
  - A. Edwards (CON, 3.0x, 48 drafts) = 1.39 -- Mid-draft player with mid outcome -- no edge either way
  - B. Carleton (POR, 1.8x, 102 drafts) = 1.61 -- Outcome roughly matched draft position and signals
  - J. Young (LVA, 0.5x, 833 drafts) = 2.39 -- Outcome roughly matched draft position and signals
  - D. Miller (CON, 3.0x, 2 drafts) = 1.16 -- Low-draft player correctly faded by the field
  - K. Iriafen (WAS, 1.0x, 220 drafts) = 1.85 -- Outcome roughly matched draft position and signals
  - R. Jackson (CHI, 1.4x, 26 drafts) = 1.57 -- Mid-draft player with mid outcome -- no edge either way
  - E. Cannon (LAS, 3.0x, 2 drafts) = 1.01 -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-07-11

**Players**: 19 HV
 | **Score range**: 1.23 -- 6.56 (median 3.01)

**Leaderboard**: top score 52.66, floor 45.35, median 48.72

**Winner** (score 52.66):
  - A. Boston (2.1x) = 8.41
  - S. Diggins (2.1x) = 6.52
  - R. Howard (1.9000000000000001x) = 7.09
  - J. Canada (2.3x) = 15.09
  - S. Cunningham (4.2x) = 15.56
  - **Game stack**: team 3: 2 players, team 2: 2 players

**Field ownership** (top-20 entries):
  - J. Canada (2.3x/2.7x/2.9x/2.1x/2.5x): 19/20 = 95%, avg 16.40
  - S. Cunningham (4.4x/4.6x/5x/4.2x): 12/20 = 60%, avg 15.99
  - G. Williams (2.4x/2.2x): 10/20 = 50%, avg 7.85
  - A. Boston (1.9x/2.1x): 7/20 = 35%, avg 8.30
  - S. Diggins (1.9x/2.1x/2.3x): 7/20 = 35%, avg 6.78
  - E. Magbegor (2.9x/2.3x/2.5x/2.7x): 6/20 = 30%, avg 7.83
  - N. Hillmon (3.3x/3.1x): 6/20 = 30%, avg 5.11
  - O. Nelson-Ododa (2.9x/3.1x/2.7x): 6/20 = 30%, avg 8.52

### Outcome Classification

**(A) Correctly priced** (18 players):
  - S. Cunningham (IND, 3.0x, 15 drafts) = 3.71 -- Mid-draft player with mid outcome -- no edge either way
  - K. Mitchell (IND, 0.6x, 185 drafts) = 4.08 -- High-draft player delivered as expected
  - O. Nelson-Ododa (CON, 1.5x, 100 drafts) = 3.01 -- High-draft player delivered as expected
  - E. Magbegor (SEA, 0.9x, 187 drafts) = 3.01 -- High-draft player delivered as expected
  - R. Howard (ATL, 0.3x, 224 drafts) = 3.73 -- High-draft player delivered as expected
  - A. Boston (IND, 0.1x, 1200 drafts) = 4.0 -- High-draft player delivered as expected
  - G. Williams (GSV, 0.4x, 514 drafts) = 3.47 -- High-draft player delivered as expected
  - B. Griner (CON, 1.7x, 122 drafts) = 2.17 -- Outcome roughly matched draft position and signals
  - N. Ogwumike (LAS, 0.3x, 488 drafts) = 3.4 -- High-draft player delivered as expected
  - S. Rivers (CON, 1.6x, 143 drafts) = 2.13 -- Outcome roughly matched draft position and signals
  - S. Diggins (CHI, 0.3x, 1300 drafts) = 3.1 -- High-draft player delivered as expected
  - E. Wheeler (LAS, 1.0x, 153 drafts) = 2.35 -- Outcome roughly matched draft position and signals
  - N. Howard (MIN, 1.2x, 122 drafts) = 2.19 -- Outcome roughly matched draft position and signals
  - L. Lacan (CON, 3.0x, 4 drafts) = 1.39 -- Low-draft player correctly faded by the field
  - M. Caldwell (MIN, 3.0x, 1 drafts) = 1.38 -- Low-draft player correctly faded by the field
  - C. Clark (IND, 0.3x, 2200 drafts) = 2.82 -- Outcome roughly matched draft position and signals
  - D. Malonga (SEA, 3.0x, 24 drafts) = 1.23 -- Mid-draft player with mid outcome -- no edge either way
  - N. Hillmon (ATL, 1.7x, 94 drafts) = 1.63 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - J. Canada (ATL, 0.9x, 43 drafts) = 6.56 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-07-12

**Players**: 20 HV
 | **Score range**: 1.13 -- 8.81 (median 3.05)

**Leaderboard**: top score 57.20, floor 50.59, median 52.12

**Winner** (score 57.20):
  - N. Collier (2x) = 10.42
  - A. Wilson (1.8x) = 15.85
  - K. Cardoso (2.5x) = 10.89
  - T. Hayes (2.5999999999999996x) = 9.52
  - R. Banham (3.5999999999999996x) = 10.52
  - **Game stack**: team 8: 2 players

**Field ownership** (top-20 entries):
  - A. Wilson (1.6x/1.8x/2x/1.4x): 19/20 = 95%, avg 16.31
  - N. Collier (1.8x/2x): 16/20 = 80%, avg 10.03
  - K. Cardoso (2.1x/2.3x/2.5x): 10/20 = 50%, avg 10.11
  - J. Young (1.9x/2.1x/1.7x/2.3x): 10/20 = 50%, avg 9.87
  - A. Atkins (2.4x/2x/2.2x/2.6x): 10/20 = 50%, avg 10.02
  - A. Reese (1.9x/2.1x/2.3x/2.5x): 10/20 = 50%, avg 6.77
  - T. Hayes (2.4x/2.8x/3x/2.6x): 6/20 = 30%, avg 9.76
  - R. Banham (3.8x/3.6x): 4/20 = 20%, avg 10.67

### Outcome Classification

**(A) Correctly priced** (20 players):
  - A. Wilson (LVA, 0.0x, 313 drafts) = 8.81 -- High-draft player delivered as expected
  - A. Atkins (LAS, 0.8x, 75 drafts) = 4.68 -- High-draft player delivered as expected
  - R. Banham (CHI, 2.4x, 22 drafts) = 2.92 -- Mid-draft player with mid outcome -- no edge either way
  - K. Cardoso (CHI, 0.9x, 89 drafts) = 4.36 -- High-draft player delivered as expected
  - J. Young (LVA, 0.5x, 505 drafts) = 4.99 -- High-draft player delivered as expected
  - T. Hayes (GSV, 1.2x, 73 drafts) = 3.66 -- High-draft player delivered as expected
  - J. Salaün (GSV, 1.6x, 38 drafts) = 3.05 -- Mid-draft player with mid outcome -- no edge either way
  - N. Collier (MIN, 0.0x, 2700 drafts) = 5.21 -- High-draft player delivered as expected
  - V. Burton (GSV, 0.7x, 305 drafts) = 3.54 -- High-draft player delivered as expected
  - A. Smith (DAL, 0.6x, 117 drafts) = 3.57 -- High-draft player delivered as expected
  - K. McBride (MIN, 0.9x, 89 drafts) = 2.84 -- Outcome roughly matched draft position and signals
  - A. Reese (ATL, 0.5x, 789 drafts) = 3.16 -- High-draft player delivered as expected
  - T. Fágbénlé (TOR, 1.2x, 100 drafts) = 2.44 -- Outcome roughly matched draft position and signals
  - C. Williams (MIN, 0.5x, 523 drafts) = 3.02 -- High-draft player delivered as expected
  - J. Loyd (LVA, 1.1x, 209 drafts) = 2.37 -- Outcome roughly matched draft position and signals
  - D. Evans (LVA, 3.0x, 58 drafts) = 1.41 -- High-draft player underperformed -- field took the loss equally
  - C. Zandalasini (GSV, 2.3x, 36 drafts) = 1.42 -- Mid-draft player with mid outcome -- no edge either way
  - K. Thornton (GSV, 0.7x, 583 drafts) = 2.25 -- Outcome roughly matched draft position and signals
  - K. Martin (LAS, 3.0x, 65 drafts) = 1.13 -- High-draft player underperformed -- field took the loss equally
  - R. Allen (NYL, 2.3x, 10 drafts) = 1.18 -- Mid-draft player with mid outcome -- no edge either way

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-07-13

**Players**: 17 HV
 | **Score range**: 2.28 -- 5.26 (median 3.87)

**Leaderboard**: top score 69.60, floor 67.28, median 67.28

**Winner** (score 69.60):
  - S. Rivers (3.6x) = 16.82
  - L. Fiebich (3.8x) = 18.77
  - L. Yueru (4.5x) = 16.45
  - J. Quinerly (4.3x) = 7.50
  - L. Lacan (4.2x) = 10.06
  - **Game stack**: team 11: 2 players, team 12: 2 players

**Field ownership** (top-20 entries):
  - S. Rivers (3.4x/3.6x): 19/20 = 95%, avg 16.77
  - B. Hartley (4.1x/3.9x): 19/20 = 95%, avg 17.00
  - L. Yueru (4.3x/4.1x/4.5x): 18/20 = 90%, avg 15.20
  - J. Quinerly (4.3x/4.5x): 17/20 = 85%, avg 7.80
  - L. Lacan (4.4x/4.6x/4.2x): 16/20 = 80%, avg 10.48
  - J. Allemand (4.4x/4.2x): 4/20 = 20%, avg 10.44
  - R. Jackson (2.9x/3.5x/3.3x): 3/20 = 15%, avg 14.13
  - L. Fiebich (4x/3.8x): 2/20 = 10%, avg 19.27

### Outcome Classification

**(A) Correctly priced** (14 players):
  - S. Rivers (CON, 1.6x, 145 drafts) = 4.67 -- High-draft player delivered as expected
  - R. Jackson (CHI, 1.5x, 19 drafts) = 4.37 -- Mid-draft player with mid outcome -- no edge either way
  - M. Caldwell (MIN, 3.0x, 1 drafts) = 2.8 -- Outcome roughly matched draft position and signals
  - S. Cunningham (IND, 2.8x, 17 drafts) = 2.8 -- Mid-draft player with mid outcome -- no edge either way
  - E. Magbegor (SEA, 0.9x, 136 drafts) = 4.29 -- High-draft player delivered as expected
  - J. Allemand (TOR, 3.0x, 1 drafts) = 2.46 -- Outcome roughly matched draft position and signals
  - C. Clark (IND, 0.3x, 904 drafts) = 5.26 -- High-draft player delivered as expected
  - L. Lacan (CON, 3.0x, 2 drafts) = 2.39 -- Outcome roughly matched draft position and signals
  - B. Stewart (NYL, 0.1x, 1200 drafts) = 4.93 -- High-draft player delivered as expected
  - K. Mitchell (IND, 0.6x, 128 drafts) = 3.87 -- High-draft player delivered as expected
  - K. Plum (LAS, 0.3x, 581 drafts) = 4.27 -- High-draft player delivered as expected
  - A. Stevens (CHI, 0.3x, 195 drafts) = 4.17 -- High-draft player delivered as expected
  - N. Sabally (TOR, 2.1x, 1 drafts) = 2.28 -- Outcome roughly matched draft position and signals
  - N. Hillmon (ATL, 1.7x, 6 drafts) = 2.44 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (3 players):
  - L. Fiebich (NYL, 2.0x, 4 drafts) = 4.94 -- Above-expectation outcome, ambiguous whether knowable
  - L. Yueru (DAL, 2.9x, 9 drafts) = 3.66 -- Above-expectation outcome, ambiguous whether knowable
  - N. Howard (MIN, 1.2x, 9 drafts) = 3.17 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 3 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-07-14

**Players**: 20 HV
 | **Score range**: 1.48 -- 5.77 (median 2.50)

**Leaderboard**: top score 58.66, floor 55.69, median 57.02

**Winner** (score 58.66):
  - C. Williams (2.5x) = 13.90
  - N. Collier (1.8x) = 9.92
  - V. Burton (2.3x) = 9.07
  - A. Reese (1.9x) = 6.72
  - D. Bonner (3.3x) = 19.05
  - **Game stack**: team 5: 2 players

**Field ownership** (top-20 entries):
  - D. Bonner (3.5x/3.9x/3.3x): 20/20 = 100%, avg 19.57
  - C. Williams (1.9x/2.3x/2.1x/1.7x/2.5x): 17/20 = 85%, avg 11.68
  - A. Reese (1.9x/2.1x/2.3x): 16/20 = 80%, avg 7.78
  - N. Collier (1.6x/1.8x/2x/1.4x): 15/20 = 75%, avg 10.28
  - A. Thomas (1.6x/1.4x/1.2x/2x/1.8x): 15/20 = 75%, avg 9.01
  - V. Burton (2.1x/2.3x/2.7x): 9/20 = 45%, avg 8.81
  - B. Carleton (3.5x/3.3x): 2/20 = 10%, avg 11.16
  - T. Hayes (2.3x): 1/20 = 5%, avg 6.34

### Outcome Classification

**(A) Correctly priced** (19 players):
  - C. Williams (MIN, 0.5x, 266 drafts) = 5.56 -- High-draft player delivered as expected
  - B. Carleton (POR, 1.9x, 67 drafts) = 3.28 -- High-draft player delivered as expected
  - N. Collier (MIN, 0.0x, 3900 drafts) = 5.51 -- High-draft player delivered as expected
  - N. Mack (PHO, 2.3x, 18 drafts) = 2.5 -- Mid-draft player with mid outcome -- no edge either way
  - V. Burton (GSV, 0.7x, 241 drafts) = 3.95 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.0x, 1500 drafts) = 4.93 -- High-draft player delivered as expected
  - M. Onyenwere (WAS, 3.0x, 1 drafts) = 1.91 -- Outcome roughly matched draft position and signals
  - R. Allen (NYL, 2.4x, 8 drafts) = 2.16 -- Outcome roughly matched draft position and signals
  - M. Billings (IND, 1.8x, 114 drafts) = 2.42 -- Outcome roughly matched draft position and signals
  - K. Westbeld (PHO, 1.9x, 99 drafts) = 2.32 -- Outcome roughly matched draft position and signals
  - K. McBride (MIN, 0.9x, 139 drafts) = 3.08 -- High-draft player delivered as expected
  - A. Reese (ATL, 0.5x, 1000 drafts) = 3.54 -- High-draft player delivered as expected
  - T. Hayes (GSV, 1.1x, 62 drafts) = 2.76 -- Outcome roughly matched draft position and signals
  - C. Zandalasini (GSV, 2.4x, 1 drafts) = 1.84 -- Outcome roughly matched draft position and signals
  - J. Salaün (GSV, 1.4x, 27 drafts) = 2.23 -- Mid-draft player with mid outcome -- no edge either way
  - M. Akoa Makani (PHO, 1.8x, 109 drafts) = 1.67 -- Outcome roughly matched draft position and signals
  - N. Hiedeman (SEA, 1.9x, 91 drafts) = 1.61 -- Outcome roughly matched draft position and signals
  - R. Banham (CHI, 2.2x, 36 drafts) = 1.48 -- Mid-draft player with mid outcome -- no edge either way
  - A. Smith (DAL, 0.6x, 143 drafts) = 2.17 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - D. Bonner (PHO, 2.1x, 35 drafts) = 5.77 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-07-15

**Players**: 17 HV
 | **Score range**: 1.50 -- 5.01 (median 2.70)

**Leaderboard**: top score 56.96, floor 52.19, median 52.83

**Winner** (score 56.96):
  - S. Austin (2.9x) = 9.27
  - T. Charles (2.9000000000000004x) = 12.55
  - N. Howard (2.8x) = 13.27
  - L. Lacan (3.9x) = 10.52
  - J. Allemand (4.2x) = 11.35

**Field ownership** (top-20 entries):
  - J. Allemand (4.4x/4.6x/4.2x): 17/20 = 85%, avg 11.61
  - N. Howard (3x/2.8x/2.6x/2.4x/3.2x): 16/20 = 80%, avg 13.56
  - S. Austin (2.9x/2.3x/2.7x): 11/20 = 55%, avg 8.68
  - L. Lacan (4.1x/3.7x/3.9x): 11/20 = 55%, avg 10.33
  - S. Cunningham (4x/3.8x/4.2x): 11/20 = 55%, avg 9.44
  - T. Charles (2.9x/3.1x/2.5x/2.7x): 10/20 = 50%, avg 12.55
  - K. Mitchell (2.1x/2.3x/2.5x): 8/20 = 40%, avg 9.81
  - R. Jackson (3.3x/2.9x/3.1x): 5/20 = 25%, avg 9.77

### Outcome Classification

**(A) Correctly priced** (17 players):
  - N. Howard (MIN, 1.2x, 133 drafts) = 4.74 -- High-draft player delivered as expected
  - J. Allemand (TOR, 3.0x, 29 drafts) = 2.7 -- Mid-draft player with mid outcome -- no edge either way
  - L. Lacan (CON, 2.5x, 12 drafts) = 2.7 -- Mid-draft player with mid outcome -- no edge either way
  - D. Hamby (LAS, 0.3x, 336 drafts) = 5.01 -- High-draft player delivered as expected
  - S. Cunningham (IND, 2.6x, 68 drafts) = 2.36 -- Outcome roughly matched draft position and signals
  - R. Jackson (CHI, 1.3x, 401 drafts) = 3.15 -- High-draft player delivered as expected
  - K. Mitchell (IND, 0.5x, 330 drafts) = 4.04 -- High-draft player delivered as expected
  - K. Plum (LAS, 0.2x, 1100 drafts) = 4.45 -- High-draft player delivered as expected
  - S. Austin (WAS, 0.9x, 355 drafts) = 3.2 -- High-draft player delivered as expected
  - A. Edwards (CON, 3.0x, 30 drafts) = 1.64 -- Mid-draft player with mid outcome -- no edge either way
  - S. Rivers (CON, 1.4x, 199 drafts) = 2.4 -- Outcome roughly matched draft position and signals
  - A. Stevens (CHI, 0.3x, 322 drafts) = 3.38 -- High-draft player delivered as expected
  - A. Morrow (CON, 2.3x, 5 drafts) = 1.8 -- Outcome roughly matched draft position and signals
  - R. Burrell (LAS, 3.0x, 2 drafts) = 1.5 -- Outcome roughly matched draft position and signals
  - C. Clark (IND, 0.3x, 2500 drafts) = 2.91 -- Outcome roughly matched draft position and signals
  - A. Boston (IND, 0.1x, 1800 drafts) = 2.64 -- Outcome roughly matched draft position and signals
  - S. Citron (WAS, 0.9x, 273 drafts) = 1.91 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-07-16

**Players**: 18 HV
 | **Score range**: 1.90 -- 6.24 (median 2.90)

**Leaderboard**: top score 63.70, floor 50.04, median 52.22

**Winner** (score 63.70):
  - A. Wilson (2x) = 12.48
  - L. Geiselsöder (4x) = 13.94
  - L. Yueru (4.1x) = 11.10
  - M. Johannes (3.9x) = 10.38
  - J. Quinerly (4x) = 15.80
  - **Game stack**: team 12: 2 players

**Field ownership** (top-20 entries):
  - J. Quinerly (4.4x/4x/4.2x/4.8x): 20/20 = 100%, avg 16.48
  - A. Wilson (2x): 12/20 = 60%, avg 12.48
  - L. Yueru (4.1x/4.3x/4.5x/3.7x/3.9x): 12/20 = 60%, avg 11.24
  - B. Stewart (1.9x/1.5x/1.7x/2.1x): 10/20 = 50%, avg 11.20
  - S. Cunningham (4x/3.8x/3.6x): 5/20 = 25%, avg 5.02
  - D. Evans (4.3x/4.1x/4.7x): 4/20 = 20%, avg 8.18
  - N. Smith (4x/3.8x/3.6x/4.2x): 4/20 = 20%, avg 7.73
  - A. Nye (4.4x/5x/4.2x): 4/20 = 20%, avg 10.77

### Outcome Classification

**(A) Correctly priced** (16 players):
  - J. Quinerly (DAL, 2.8x, 13 drafts) = 3.95 -- Mid-draft player with mid outcome -- no edge either way
  - T. Paopao (ATL, 3.0x, 1 drafts) = 2.9 -- Outcome roughly matched draft position and signals
  - B. Stewart (NYL, 0.1x, 424 drafts) = 6.22 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 2100 drafts) = 6.24 -- High-draft player delivered as expected
  - L. Yueru (DAL, 2.5x, 40 drafts) = 2.71 -- Mid-draft player with mid outcome -- no edge either way
  - M. Johannes (NYL, 2.5x, 16 drafts) = 2.66 -- Mid-draft player with mid outcome -- no edge either way
  - A. Nye (ATL, 3.0x, 4 drafts) = 2.32 -- Outcome roughly matched draft position and signals
  - B. Griner (CON, 1.7x, 12 drafts) = 2.97 -- Mid-draft player with mid outcome -- no edge either way
  - N. Mack (PHO, 2.1x, 8 drafts) = 2.77 -- Outcome roughly matched draft position and signals
  - D. Dantas (IND, 3.0x, 1 drafts) = 2.19 -- Outcome roughly matched draft position and signals
  - I. Harrison (TOR, 3.0x, 6 drafts) = 2.15 -- Outcome roughly matched draft position and signals
  - D. Evans (LVA, 2.9x, 5 drafts) = 1.9 -- Outcome roughly matched draft position and signals
  - N. Ogwumike (LAS, 0.3x, 130 drafts) = 3.85 -- High-draft player delivered as expected
  - E. Wheeler (LAS, 1.1x, 26 drafts) = 2.81 -- Mid-draft player with mid outcome -- no edge either way
  - B. Carleton (POR, 1.8x, 4 drafts) = 2.27 -- Outcome roughly matched draft position and signals
  - S. Ionescu (NYL, 0.1x, 497 drafts) = 3.98 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (2 players):
  - L. Geiselsöder (POR, 2.2x, 3 drafts) = 3.48 -- Above-expectation outcome, ambiguous whether knowable
  - K. McBride (MIN, 0.9x, 3 drafts) = 3.71 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-07-22

**Players**: 19 HV
 | **Score range**: 1.75 -- 5.31 (median 3.22)

**Leaderboard**: top score 51.99, floor 44.99, median 45.40

**Winner** (score 51.99):
  - L. Yueru (4.3x) = 8.30
  - J. Quinerly (4.2x) = 8.86
  - S. Cunningham (4.1x) = 9.47
  - D. Evans (4.199999999999999x) = 13.43
  - I. Harrison (4.2x) = 11.93
  - **Game stack**: team 12: 2 players

**Field ownership** (top-20 entries):
  - J. Quinerly (3.8x/4x/4.2x/3.6x): 12/20 = 60%, avg 8.33
  - S. Cunningham (4.3x/4.1x/3.9x): 12/20 = 60%, avg 9.32
  - A. Wilson (1.6x/1.8x/2x): 12/20 = 60%, avg 10.26
  - L. Yueru (4.1x/3.5x/4.3x/3.7x/3.9x): 11/20 = 55%, avg 7.42
  - N. Collier (1.8x/2x): 9/20 = 45%, avg 9.55
  - J. Allemand (4.1x/4.5x/3.9x): 8/20 = 40%, avg 8.77
  - L. Fiebich (3.2x/3.4x/2.8x): 7/20 = 35%, avg 9.92
  - D. Evans (4.4x/4x/4.2x): 6/20 = 30%, avg 13.11

### Outcome Classification

**(A) Correctly priced** (16 players):
  - I. Harrison (TOR, 3.0x, 4 drafts) = 2.84 -- Outcome roughly matched draft position and signals
  - D. Hamby (LAS, 0.3x, 149 drafts) = 4.85 -- High-draft player delivered as expected
  - B. Carleton (POR, 1.7x, 3 drafts) = 2.98 -- Outcome roughly matched draft position and signals
  - K. Nurse (TOR, 3.0x, 2 drafts) = 2.55 -- Outcome roughly matched draft position and signals
  - R. Jackson (CHI, 1.2x, 29 drafts) = 3.33 -- Mid-draft player with mid outcome -- no edge either way
  - A. Wilson (LVA, 0.0x, 1800 drafts) = 5.31 -- High-draft player delivered as expected
  - S. Cunningham (IND, 2.5x, 28 drafts) = 2.31 -- Mid-draft player with mid outcome -- no edge either way
  - S. Austin (WAS, 0.8x, 267 drafts) = 3.64 -- High-draft player delivered as expected
  - J. Allemand (TOR, 2.7x, 9 drafts) = 2.13 -- Outcome roughly matched draft position and signals
  - N. Collier (MIN, 0.0x, 2600 drafts) = 4.88 -- High-draft player delivered as expected
  - K. Mitchell (IND, 0.5x, 156 drafts) = 3.84 -- High-draft player delivered as expected
  - S. Citron (WAS, 0.9x, 27 drafts) = 3.22 -- Mid-draft player with mid outcome -- no edge either way
  - J. Quinerly (DAL, 2.4x, 47 drafts) = 2.11 -- Mid-draft player with mid outcome -- no edge either way
  - G. Williams (GSV, 0.5x, 176 drafts) = 3.62 -- High-draft player delivered as expected
  - A. Ogunbowale (DAL, 0.7x, 26 drafts) = 3.34 -- Mid-draft player with mid outcome -- no edge either way
  - H. Van Lith (CON, 3.0x, 2 drafts) = 1.75 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (3 players):
  - D. Evans (LVA, 2.8x, 1 drafts) = 3.2 -- High-boost low-draft player who overperformed
  - L. Fiebich (NYL, 1.6x, 4 drafts) = 3.1 -- Above-expectation outcome, ambiguous whether knowable
  - K. McBride (MIN, 0.8x, 7 drafts) = 3.58 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 3 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-07-23

**Players**: 17 HV
 | **Score range**: 0.00 -- 5.85 (median 2.04)

**Leaderboard**: top score 47.84, floor 43.21, median 44.20

**Winner** (score 47.84):
  - A. Gray (2.2x) = 12.86
  - D. Bonner (3.3x) = 8.18
  - B. Griner (3.3x) = 8.79
  - N. Mack (3.3x) = 9.12
  - M. Caldwell (4.2x) = 8.89
  - **Game stack**: team 6: 2 players

**Field ownership** (top-20 entries):
  - A. Gray (1.8x/2x/2.2x): 18/20 = 90%, avg 12.41
  - M. Caldwell (4.4x/5x/4.2x/4.8x): 16/20 = 80%, avg 9.34
  - B. Griner (3.1x/2.9x/3.3x): 15/20 = 75%, avg 8.22
  - N. Mack (3.5x/3.1x/3.7x/3.9x/3.3x): 15/20 = 75%, avg 9.57
  - D. Bonner (3.5x/3.1x/2.9x/3.3x): 13/20 = 65%, avg 7.99
  - B. Jones (2.3x/2.5x): 6/20 = 30%, avg 6.88
  - N. Hillmon (2.9x/3.5x/3.1x/3.3x): 6/20 = 30%, avg 6.17
  - J. Canada (2.1x/2.3x/2.5x): 4/20 = 20%, avg 5.93

### Outcome Classification

**(A) Correctly priced** (17 players):
  - A. Gray (ATL, 0.2x, 1200 drafts) = 5.85 -- High-draft player delivered as expected
  - N. Mack (PHO, 1.9x, 110 drafts) = 2.76 -- Outcome roughly matched draft position and signals
  - M. Caldwell (MIN, 3.0x, 105 drafts) = 2.12 -- Outcome roughly matched draft position and signals
  - B. Griner (CON, 1.7x, 207 drafts) = 2.66 -- Outcome roughly matched draft position and signals
  - D. Bonner (PHO, 1.5x, 204 drafts) = 2.48 -- Outcome roughly matched draft position and signals
  - B. Jones (ATL, 0.7x, 280 drafts) = 2.91 -- Outcome roughly matched draft position and signals
  - J. Canada (ATL, 0.7x, 262 drafts) = 2.58 -- Outcome roughly matched draft position and signals
  - N. Hillmon (ATL, 1.7x, 137 drafts) = 1.91 -- Outcome roughly matched draft position and signals
  - S. Whitcomb (PHO, 1.2x, 171 drafts) = 2.04 -- Outcome roughly matched draft position and signals
  - A. Thomas (PHO, 0.0x, 3800 drafts) = 2.36 -- Outcome roughly matched draft position and signals
  - S. Sabally (NYL, 0.3x, 600 drafts) = 1.56 -- Outcome roughly matched draft position and signals
  - K. Westbeld (PHO, 2.0x, 117 drafts) = 0.84 -- High-draft player underperformed -- field took the loss equally
  - K. Copper (PHO, 0.9x, 217 drafts) = 0.96 -- High-draft player underperformed -- field took the loss equally
  - L. Held (TOR, 2.0x, 109 drafts) = 0.52 -- High-draft player underperformed -- field took the loss equally
  - N. Coffey (MIN, 3.0x, 100 drafts) = 0.36 -- High-draft player underperformed -- field took the loss equally
  - T. Paopao (ATL, 3.0x, 111 drafts) = 0.09 -- High-draft player underperformed -- field took the loss equally
  - M. Akoa Makani (PHO, 1.8x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-07-24

**Players**: 18 HV
 | **Score range**: 1.77 -- 5.85 (median 3.20)

**Leaderboard**: top score 55.07, floor 49.23, median 50.61

**Winner** (score 55.07):
  - T. Charles (3x) = 14.06
  - N. Howard (2.9000000000000004x) = 14.36
  - C. Gray (2.7x) = 5.62
  - S. Cunningham (3.8x) = 9.18
  - J. Allemand (3.7x) = 11.85

**Field ownership** (top-20 entries):
  - T. Charles (2.4x/3x/2.6x/2.2x): 20/20 = 100%, avg 12.19
  - N. Howard (2.3x/3.1x/2.7x/2.9x/2.5x): 19/20 = 95%, avg 13.89
  - K. Plum (1.8x/2x/2.2x/1.4x): 12/20 = 60%, avg 11.61
  - E. Wheeler (3.1x/2.3x/2.5x/2.7x): 6/20 = 30%, avg 7.27
  - D. Hamby (1.6x/2x/2.2x/1.4x): 5/20 = 25%, avg 7.72
  - A. Boston (1.6x/1.8x): 5/20 = 25%, avg 5.06
  - S. Cunningham (4x/3.8x/3.6x): 4/20 = 20%, avg 9.18
  - J. Allemand (3.7x/3.9x): 4/20 = 20%, avg 12.17

### Outcome Classification

**(A) Correctly priced** (16 players):
  - D. Malonga (SEA, 3.0x, 21 drafts) = 3.88 -- Mid-draft player with mid outcome -- no edge either way
  - N. Howard (MIN, 1.1x, 137 drafts) = 4.95 -- High-draft player delivered as expected
  - K. Plum (LAS, 0.2x, 360 drafts) = 5.85 -- High-draft player delivered as expected
  - L. Brown (SEA, 3.0x, 1 drafts) = 2.47 -- Outcome roughly matched draft position and signals
  - S. Cunningham (IND, 2.4x, 43 drafts) = 2.42 -- Mid-draft player with mid outcome -- no edge either way
  - A. Stevens (CHI, 0.3x, 155 drafts) = 4.54 -- High-draft player delivered as expected
  - D. Hamby (LAS, 0.2x, 289 drafts) = 4.39 -- High-draft player delivered as expected
  - N. Smith (LVA, 2.2x, 9 drafts) = 2.25 -- Outcome roughly matched draft position and signals
  - S. Diggins (CHI, 0.4x, 203 drafts) = 3.53 -- High-draft player delivered as expected
  - E. Wheeler (LAS, 1.1x, 131 drafts) = 2.73 -- Outcome roughly matched draft position and signals
  - G. Williams (GSV, 0.4x, 276 drafts) = 3.47 -- High-draft player delivered as expected
  - J. Young (LVA, 0.5x, 172 drafts) = 3.28 -- High-draft player delivered as expected
  - R. Burrell (LAS, 3.0x, 1 drafts) = 1.77 -- Outcome roughly matched draft position and signals
  - E. Magbegor (SEA, 0.9x, 148 drafts) = 2.69 -- Outcome roughly matched draft position and signals
  - E. Williams (CHI, 2.0x, 23 drafts) = 1.93 -- Mid-draft player with mid outcome -- no edge either way
  - K. Mitchell (IND, 0.5x, 244 drafts) = 3.04 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (2 players):
  - J. Allemand (TOR, 2.5x, 5 drafts) = 3.2 -- Above-expectation outcome, ambiguous whether knowable
  - O. Nelson-Ododa (CON, 1.5x, 2 drafts) = 3.19 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-07-25

**Players**: 19 HV
 | **Score range**: 1.57 -- 5.35 (median 2.73)

**Leaderboard**: top score 46.16, floor 42.63, median 43.74

**Winner** (score 46.16):
  - T. Hayes (3.2x) = 10.34
  - H. Jones (4.7x) = 9.96
  - A. James (3.4000000000000004x) = 7.99
  - C. Leite (4.199999999999999x) = 10.18
  - J. Salaün (2.5999999999999996x) = 7.68
  - **Game stack**: team 14: 2 players

**Field ownership** (top-20 entries):
  - C. Williams (1.9x/2.1x/2.3x/2.5x): 15/20 = 75%, avg 11.74
  - P. Bueckers (1.6x/1.4x/2x/1.8x/2.2x): 14/20 = 70%, avg 7.02
  - A. Thomas (1.9x/2.1x/1.7x/1.3x): 11/20 = 55%, avg 9.46
  - S. Ionescu (1.6x/1.4x/2x/1.8x/2.2x): 11/20 = 55%, avg 9.17
  - H. Jones (4.3x/4.1x/4.5x/4.7x): 8/20 = 40%, avg 9.16
  - T. Hayes (2.4x/3.2x/3x/2.8x): 6/20 = 30%, avg 9.27
  - J. Salaün (3.4x/3x/2.6x): 6/20 = 30%, avg 8.67
  - N. Collier (1.2x/2x/1.8x): 5/20 = 25%, avg 7.60

### Outcome Classification

**(A) Correctly priced** (19 players):
  - C. Williams (MIN, 0.5x, 146 drafts) = 5.35 -- High-draft player delivered as expected
  - C. Leite (POR, 2.8x, 21 drafts) = 2.42 -- Mid-draft player with mid outcome -- no edge either way
  - S. Ionescu (NYL, 0.2x, 308 drafts) = 5.15 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.1x, 258 drafts) = 5.18 -- High-draft player delivered as expected
  - T. Hayes (GSV, 1.2x, 71 drafts) = 3.23 -- High-draft player delivered as expected
  - J. Jones (NYL, 0.6x, 34 drafts) = 3.88 -- Mid-draft player with mid outcome -- no edge either way
  - J. Salaün (GSV, 1.4x, 34 drafts) = 2.95 -- Mid-draft player with mid outcome -- no edge either way
  - L. Geiselsöder (POR, 1.9x, 32 drafts) = 2.52 -- Mid-draft player with mid outcome -- no edge either way
  - J. Shepard (DAL, 1.9x, 2 drafts) = 2.47 -- Outcome roughly matched draft position and signals
  - A. James (DAL, 1.8x, 29 drafts) = 2.35 -- Mid-draft player with mid outcome -- no edge either way
  - M. Akoa Makani (PHO, 1.8x, 4 drafts) = 2.3 -- Outcome roughly matched draft position and signals
  - B. Carleton (POR, 1.7x, 90 drafts) = 2.28 -- Outcome roughly matched draft position and signals
  - N. Collier (MIN, 0.0x, 2500 drafts) = 4.22 -- High-draft player delivered as expected
  - T. Fágbénlé (TOR, 1.3x, 42 drafts) = 2.56 -- Mid-draft player with mid outcome -- no edge either way
  - P. Bueckers (DAL, 0.2x, 831 drafts) = 3.78 -- High-draft player delivered as expected
  - N. Mack (PHO, 1.8x, 12 drafts) = 2.13 -- Mid-draft player with mid outcome -- no edge either way
  - J. Young (LVA, 0.5x, 114 drafts) = 3.02 -- High-draft player delivered as expected
  - D. Evans (LVA, 2.7x, 2 drafts) = 1.57 -- Outcome roughly matched draft position and signals
  - A. Smith (DAL, 0.7x, 99 drafts) = 2.73 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-07-26

**Players**: 19 HV
 | **Score range**: 1.41 -- 5.86 (median 2.48)

**Leaderboard**: top score 54.75, floor 51.26, median 52.96

**Winner** (score 54.75):
  - S. Ionescu (2.1x) = 11.95
  - R. Jackson (3x) = 17.59
  - L. Fiebich (3.1x) = 7.61
  - J. Allemand (3.6x) = 8.27
  - D. Malonga (4.2x) = 9.34
  - **Game stack**: team 4: 2 players

**Field ownership** (top-20 entries):
  - R. Jackson (3x/2.8x/2.6x/2.4x/3.2x): 20/20 = 100%, avg 16.65
  - S. Ionescu (1.9x/2.1x/1.5x/2x): 18/20 = 90%, avg 11.48
  - J. Allemand (3.4x/4x/3.6x): 11/20 = 55%, avg 8.18
  - K. Plum (1.6x/1.8x/2x/2.2x): 9/20 = 45%, avg 8.17
  - L. Fiebich (2.9x/2.7x/3.1x): 8/20 = 40%, avg 7.24
  - N. Cloud (2.8x/2.6x/2.4x/2x/2.5x): 8/20 = 40%, avg 10.89
  - D. Malonga (4.4x/4.6x/4.2x): 7/20 = 35%, avg 9.53
  - S. Citron (2.3x/2.7x/2.9x/2.1x/2.5x): 6/20 = 30%, avg 8.05

### Outcome Classification

**(A) Correctly priced** (19 players):
  - R. Jackson (CHI, 1.2x, 135 drafts) = 5.86 -- High-draft player delivered as expected
  - N. Cloud (CHI, 0.8x, 134 drafts) = 4.76 -- High-draft player delivered as expected
  - S. Ionescu (NYL, 0.1x, 1700 drafts) = 5.69 -- High-draft player delivered as expected
  - D. Malonga (SEA, 3.0x, 23 drafts) = 2.22 -- Mid-draft player with mid outcome -- no edge either way
  - R. Burrell (LAS, 3.0x, 5 drafts) = 2.08 -- Outcome roughly matched draft position and signals
  - J. Allemand (TOR, 2.2x, 33 drafts) = 2.3 -- Mid-draft player with mid outcome -- no edge either way
  - K. Plum (LAS, 0.2x, 635 drafts) = 4.23 -- High-draft player delivered as expected
  - S. Citron (WAS, 0.9x, 175 drafts) = 3.18 -- High-draft player delivered as expected
  - D. Hamby (LAS, 0.2x, 429 drafts) = 4.15 -- High-draft player delivered as expected
  - L. Fiebich (NYL, 1.5x, 32 drafts) = 2.45 -- Mid-draft player with mid outcome -- no edge either way
  - J. Jones (NYL, 0.5x, 286 drafts) = 2.84 -- Outcome roughly matched draft position and signals
  - S. Dolson (SEA, 3.0x, 6 drafts) = 1.41 -- Low-draft player correctly faded by the field
  - S. Austin (WAS, 0.8x, 142 drafts) = 2.48 -- Outcome roughly matched draft position and signals
  - N. Ogwumike (LAS, 0.4x, 263 drafts) = 2.81 -- Outcome roughly matched draft position and signals
  - E. Magbegor (SEA, 0.9x, 97 drafts) = 2.28 -- Outcome roughly matched draft position and signals
  - A. Stevens (CHI, 0.3x, 173 drafts) = 2.83 -- Outcome roughly matched draft position and signals
  - B. Sykes (TOR, 0.7x, 210 drafts) = 2.27 -- Outcome roughly matched draft position and signals
  - E. Wheeler (LAS, 1.1x, 86 drafts) = 1.9 -- Outcome roughly matched draft position and signals
  - S. Diggins (CHI, 0.4x, 269 drafts) = 2.31 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-07-27

**Players**: 17 HV
 | **Score range**: 2.24 -- 8.21 (median 3.45)

**Leaderboard**: top score 69.42, floor 60.83, median 62.20

**Winner** (score 69.42):
  - N. Collier (2x) = 16.42
  - K. Mitchell (2.3x) = 18.72
  - J. Young (2.1x) = 12.54
  - C. Gray (2.5x) = 10.13
  - B. Griner (2.8x) = 11.60
  - **Game stack**: team 1: 2 players

**Field ownership** (top-20 entries):
  - N. Collier (1.6x/1.8x/2x/1.4x): 20/20 = 100%, avg 15.43
  - K. Mitchell (1.9x/2.1x/1.7x/2.3x): 20/20 = 100%, avg 16.77
  - A. Thomas (1.9x/1.5x/1.3x/2.1x/1.7x): 15/20 = 75%, avg 10.56
  - J. Young (1.9x/2.3x/2.1x/1.7x/2.5x): 14/20 = 70%, avg 12.12
  - A. Wilson (1.6x/1.8x/2x/1.2x): 14/20 = 70%, avg 9.38
  - C. Gray (2.3x/2.5x/2.7x): 6/20 = 30%, avg 10.00
  - T. Charles (2.1x/2.3x): 4/20 = 20%, avg 9.38
  - A. Boston (1.8x/1.4x): 4/20 = 20%, avg 5.74

### Outcome Classification

**(A) Correctly priced** (11 players):
  - K. Mitchell (IND, 0.5x, 482 drafts) = 8.14 -- High-draft player delivered as expected
  - N. Collier (MIN, 0.0x, 2400 drafts) = 8.21 -- High-draft player delivered as expected
  - J. Young (LVA, 0.5x, 152 drafts) = 5.97 -- High-draft player delivered as expected
  - B. Griner (CON, 1.6x, 36 drafts) = 4.14 -- Mid-draft player with mid outcome -- no edge either way
  - R. Banham (CHI, 2.4x, 31 drafts) = 3.14 -- Mid-draft player with mid outcome -- no edge either way
  - A. Thomas (PHO, 0.1x, 395 drafts) = 6.42 -- High-draft player delivered as expected
  - C. Gray (LVA, 1.1x, 148 drafts) = 4.05 -- High-draft player delivered as expected
  - M. Caldwell (MIN, 3.0x, 7 drafts) = 2.27 -- Outcome roughly matched draft position and signals
  - K. Nurse (TOR, 3.0x, 4 drafts) = 2.24 -- Outcome roughly matched draft position and signals
  - R. Allen (NYL, 2.6x, 2 drafts) = 2.37 -- Outcome roughly matched draft position and signals
  - A. Wilson (LVA, 0.0x, 1900 drafts) = 5.38 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (6 players):
  - M. Timpson (IND, 3.0x, 1 drafts) = 3.77 -- High-boost low-draft player who overperformed
  - J. Melbourne (SEA, 3.0x, 1 drafts) = 3.21 -- High-boost low-draft player who overperformed
  - K. Bell (LVA, 3.0x, 1 drafts) = 3.35 -- High-boost low-draft player who overperformed
  - J. Sheldon (CHI, 2.1x, 1 drafts) = 3.31 -- Above-expectation outcome, ambiguous whether knowable
  - L. Lacan (CON, 1.9x, 2 drafts) = 3.29 -- Above-expectation outcome, ambiguous whether knowable
  - J. Loyd (LVA, 1.3x, 8 drafts) = 3.45 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 6 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-07-28

**Players**: 19 HV
 | **Score range**: 1.29 -- 6.31 (median 2.67)

**Leaderboard**: top score 54.31, floor 49.23, median 50.34

**Winner** (score 54.31):
  - P. Bueckers (2.2x) = 10.58
  - N. Ogwumike (2.2x) = 13.87
  - A. Ogunbowale (2.3x) = 12.64
  - L. Geiselsöder (3.3x) = 9.52
  - D. Malonga (4.2x) = 7.70
  - **Game stack**: team 12: 2 players

**Field ownership** (top-20 entries):
  - N. Ogwumike (1.6x/2.4x/2x/1.8x/2.2x): 19/20 = 95%, avg 13.47
  - A. Ogunbowale (1.9x/2.3x/2.7x/2.4x/2.1x/2.5x): 19/20 = 95%, avg 13.36
  - S. Diggins (1.6x/2.4x/2x/1.8x/2.2x): 13/20 = 65%, avg 11.28
  - G. Williams (1.9x/2.1x/2.3x/2.5x): 7/20 = 35%, avg 7.82
  - P. Bueckers (1.8x/2x/2.2x/1.4x): 6/20 = 30%, avg 9.46
  - O. Nelson-Ododa (2.8x/3x/2.6x): 6/20 = 30%, avg 8.14
  - J. Jones (1.9x/2.1x/1.7x/2.3x): 6/20 = 30%, avg 5.07
  - E. Magbegor (2.1x/2.9x/2.3x/2.5x): 5/20 = 25%, avg 7.98

### Outcome Classification

**(A) Correctly priced** (18 players):
  - A. Ogunbowale (DAL, 0.7x, 280 drafts) = 5.5 -- High-draft player delivered as expected
  - N. Ogwumike (LAS, 0.4x, 312 drafts) = 6.31 -- High-draft player delivered as expected
  - S. Diggins (CHI, 0.4x, 325 drafts) = 5.43 -- High-draft player delivered as expected
  - L. Geiselsöder (POR, 1.9x, 11 drafts) = 2.88 -- Mid-draft player with mid outcome -- no edge either way
  - P. Bueckers (DAL, 0.2x, 535 drafts) = 4.81 -- High-draft player delivered as expected
  - O. Nelson-Ododa (CON, 1.4x, 84 drafts) = 2.94 -- Outcome roughly matched draft position and signals
  - E. Magbegor (SEA, 0.9x, 114 drafts) = 3.3 -- High-draft player delivered as expected
  - D. Malonga (SEA, 3.0x, 13 drafts) = 1.83 -- Mid-draft player with mid outcome -- no edge either way
  - G. Williams (GSV, 0.5x, 258 drafts) = 3.58 -- High-draft player delivered as expected
  - L. Yueru (DAL, 2.4x, 41 drafts) = 1.87 -- Mid-draft player with mid outcome -- no edge either way
  - A. Morrow (CON, 2.2x, 6 drafts) = 1.94 -- Outcome roughly matched draft position and signals
  - M. Johannes (NYL, 2.5x, 22 drafts) = 1.77 -- Mid-draft player with mid outcome -- no edge either way
  - A. Clark (DAL, 3.0x, 3 drafts) = 1.45 -- Low-draft player correctly faded by the field
  - D. Carrington (CHI, 1.4x, 36 drafts) = 2.12 -- Mid-draft player with mid outcome -- no edge either way
  - J. Sheldon (CHI, 2.0x, 88 drafts) = 1.68 -- Outcome roughly matched draft position and signals
  - J. Jones (NYL, 0.5x, 461 drafts) = 2.67 -- Outcome roughly matched draft position and signals
  - L. Lacan (CON, 1.5x, 9 drafts) = 1.7 -- Outcome roughly matched draft position and signals
  - I. Harrison (TOR, 2.8x, 17 drafts) = 1.29 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (1 players):
  - S. Talbot (LVA, 3.0x, 3 drafts) = 3.1 -- High-boost low-draft player who overperformed

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-07-29

**Players**: 20 HV
 | **Score range**: 1.49 -- 9.21 (median 3.79)

**Leaderboard**: top score 73.25, floor 66.31, median 66.34

**Winner** (score 73.25):
  - A. Wilson (2x) = 18.41
  - K. Iriafen (3x) = 16.12
  - J. Young (2x) = 12.54
  - R. Banham (3.6x) = 14.20
  - S. Citron (2.1x) = 11.96
  - **Game stack**: team 1: 2 players, team 7: 2 players

**Field ownership** (top-20 entries):
  - A. Wilson (2x): 20/20 = 100%, avg 18.41
  - R. Banham (3.4x/3.6x): 17/20 = 85%, avg 13.55
  - J. Young (2x/2.2x): 15/20 = 75%, avg 13.72
  - J. Canada (2.4x/2x/2.6x): 15/20 = 75%, avg 10.78
  - T. Hayes (2.4x/3x/2.6x): 13/20 = 65%, avg 9.90
  - K. Iriafen (2.4x/2.8x/3x/2.6x): 5/20 = 25%, avg 14.83
  - S. Citron (2.1x/2.3x/2.5x): 5/20 = 25%, avg 13.33
  - M. Caldwell (4.4x/4.2x): 4/20 = 20%, avg 13.34

### Outcome Classification

**(A) Correctly priced** (16 players):
  - A. Wilson (LVA, 0.0x, 4000 drafts) = 9.21 -- High-draft player delivered as expected
  - K. Iriafen (WAS, 1.2x, 131 drafts) = 5.37 -- High-draft player delivered as expected
  - R. Banham (CHI, 2.2x, 16 drafts) = 3.95 -- Mid-draft player with mid outcome -- no edge either way
  - S. Citron (WAS, 0.9x, 153 drafts) = 5.7 -- High-draft player delivered as expected
  - J. Young (LVA, 0.4x, 380 drafts) = 6.27 -- High-draft player delivered as expected
  - E. Engstler (POR, 3.0x, 1 drafts) = 2.8 -- Outcome roughly matched draft position and signals
  - R. Burrell (LAS, 3.0x, 19 drafts) = 2.57 -- Mid-draft player with mid outcome -- no edge either way
  - J. Canada (ATL, 0.8x, 45 drafts) = 4.52 -- Mid-draft player with mid outcome -- no edge either way
  - A. Reese (ATL, 0.5x, 271 drafts) = 4.44 -- High-draft player delivered as expected
  - B. Sykes (TOR, 0.8x, 139 drafts) = 3.94 -- High-draft player delivered as expected
  - N. Smith (LVA, 2.1x, 31 drafts) = 2.28 -- Mid-draft player with mid outcome -- no edge either way
  - K. Cardoso (CHI, 1.0x, 147 drafts) = 3.11 -- High-draft player delivered as expected
  - R. Allen (NYL, 2.5x, 1 drafts) = 1.88 -- Outcome roughly matched draft position and signals
  - D. Evans (LVA, 2.7x, 16 drafts) = 1.69 -- Mid-draft player with mid outcome -- no edge either way
  - C. Leite (POR, 2.7x, 2 drafts) = 1.73 -- Outcome roughly matched draft position and signals
  - K. Nurse (TOR, 3.0x, 2 drafts) = 1.49 -- Low-draft player correctly faded by the field

**(C) Unknowable / winners' edge** (4 players):
  - C. Zandalasini (GSV, 2.2x, 2 drafts) = 4.92 -- Above-expectation outcome, ambiguous whether knowable
  - M. Caldwell (MIN, 3.0x, 3 drafts) = 3.1 -- High-boost low-draft player who overperformed
  - N. Hillmon (ATL, 1.7x, 2 drafts) = 3.58 -- Above-expectation outcome, ambiguous whether knowable
  - T. Hayes (GSV, 1.2x, 7 drafts) = 3.79 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 4 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-07-30

**Players**: 17 HV
 | **Score range**: 2.04 -- 6.57 (median 3.78)

**Leaderboard**: top score 63.91, floor 54.19, median 55.49

**Winner** (score 63.91):
  - N. Collier (2x) = 13.15
  - N. Hillmon (3.4000000000000004x) = 18.66
  - M. Johannes (4.1x) = 8.03
  - M. Caldwell (4.1x) = 8.37
  - T. Paopao (4.2x) = 15.70
  - **Game stack**: team 5: 2 players, team 2: 2 players

**Field ownership** (top-20 entries):
  - N. Collier (1.2x/2x): 16/20 = 80%, avg 12.82
  - N. Hillmon (3.2x/3.4x/3x/2.8x): 15/20 = 75%, avg 16.83
  - T. Paopao (4.4x/5x/4.2x/4.8x): 10/20 = 50%, avg 16.30
  - H. Jones (4.1x/3.7x/3.9x): 10/20 = 50%, avg 10.19
  - M. Caldwell (4.3x/4.1x/3.9x): 9/20 = 45%, avg 8.37
  - S. Ionescu (1.9x/1.7x): 5/20 = 25%, avg 8.75
  - S. Cunningham (4.1x/3.7x): 5/20 = 25%, avg 6.45
  - P. Bueckers (1.6x/2x): 4/20 = 20%, avg 8.55

### Outcome Classification

**(A) Correctly priced** (14 players):
  - N. Collier (MIN, 0.0x, 3600 drafts) = 6.57 -- High-draft player delivered as expected
  - I. Harrison (TOR, 2.8x, 3 drafts) = 2.48 -- Outcome roughly matched draft position and signals
  - C. Williams (MIN, 0.4x, 190 drafts) = 4.84 -- High-draft player delivered as expected
  - K. McBride (MIN, 0.9x, 143 drafts) = 3.78 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.0x, 508 drafts) = 5.2 -- High-draft player delivered as expected
  - S. Ionescu (NYL, 0.1x, 581 drafts) = 4.81 -- High-draft player delivered as expected
  - A. Smith (DAL, 0.7x, 105 drafts) = 3.7 -- High-draft player delivered as expected
  - N. Cloud (CHI, 0.7x, 95 drafts) = 3.67 -- High-draft player delivered as expected
  - P. Bueckers (DAL, 0.2x, 592 drafts) = 4.5 -- High-draft player delivered as expected
  - A. Gray (ATL, 0.3x, 208 drafts) = 4.26 -- High-draft player delivered as expected
  - M. Caldwell (MIN, 2.7x, 9 drafts) = 2.04 -- Outcome roughly matched draft position and signals
  - L. Geiselsöder (POR, 1.8x, 5 drafts) = 2.56 -- Outcome roughly matched draft position and signals
  - A. Boston (IND, 0.2x, 290 drafts) = 4.29 -- High-draft player delivered as expected
  - B. Jones (ATL, 0.7x, 127 drafts) = 3.32 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (3 players):
  - N. Hillmon (ATL, 1.6x, 15 drafts) = 5.49 -- Above-expectation outcome, ambiguous whether knowable
  - T. Paopao (ATL, 3.0x, 4 drafts) = 3.74 -- Above-expectation outcome, ambiguous whether knowable
  - K. Copper (PHO, 1.3x, 1 drafts) = 3.12 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 3 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-07-31

**Players**: 19 HV
 | **Score range**: 0.00 -- 3.47 (median 1.69)

**Leaderboard**: top score 46.97, floor 43.01, median 43.78

**Winner** (score 46.97):
  - T. Fágbénlé (3.4x) = 10.11
  - E. Engstler (4.8x) = 9.01
  - V. Burton (2.4000000000000004x) = 8.33
  - K. Martin (4.4x) = 12.41
  - S. Sutton (3.5999999999999996x) = 7.11

**Field ownership** (top-20 entries):
  - K. Martin (4.8x/4.6x/4.2x/4.4x/5x): 20/20 = 100%, avg 12.58
  - V. Burton (2.4x/2.8x/2.6x/2x): 16/20 = 80%, avg 8.76
  - S. Sutton (4x/4.2x/4.4x/3.8x/3.6x): 15/20 = 75%, avg 7.69
  - T. Fágbénlé (3x/2.8x/2.6x/3.2x/3.4x): 13/20 = 65%, avg 8.87
  - S. Austin (2.3x/2.7x/2.9x/2.1x/2.5x): 12/20 = 60%, avg 7.29
  - S. Citron (2.4x/2.8x/2.6x): 11/20 = 55%, avg 7.67
  - L. Amihere (3.5x/3.7x): 5/20 = 25%, avg 5.66
  - E. Engstler (4.6x/4.8x): 3/20 = 15%, avg 8.88

### Outcome Classification

**(A) Correctly priced** (19 players):
  - K. Martin (LAS, 3.0x, 141 drafts) = 2.82 -- Outcome roughly matched draft position and signals
  - T. Fágbénlé (TOR, 1.4x, 175 drafts) = 2.97 -- Outcome roughly matched draft position and signals
  - V. Burton (GSV, 0.8x, 768 drafts) = 3.47 -- High-draft player delivered as expected
  - E. Engstler (POR, 3.0x, 114 drafts) = 1.88 -- Outcome roughly matched draft position and signals
  - S. Austin (WAS, 0.9x, 658 drafts) = 2.92 -- Outcome roughly matched draft position and signals
  - S. Citron (WAS, 0.8x, 2000 drafts) = 2.93 -- Outcome roughly matched draft position and signals
  - I. Rupert (GSV, 1.9x, 5 drafts) = 2.08 -- Outcome roughly matched draft position and signals
  - L. Amihere (GSV, 2.1x, 89 drafts) = 1.55 -- Outcome roughly matched draft position and signals
  - B. Sykes (TOR, 0.7x, 1600 drafts) = 2.32 -- Outcome roughly matched draft position and signals
  - J. Salaün (GSV, 1.5x, 159 drafts) = 1.77 -- Outcome roughly matched draft position and signals
  - J. Melbourne (SEA, 3.0x, 99 drafts) = 1.13 -- High-draft player underperformed -- field took the loss equally
  - K. Iriafen (WAS, 1.0x, 626 drafts) = 1.69 -- Outcome roughly matched draft position and signals
  - L. Olsen (WAS, 3.0x, 97 drafts) = 0.99 -- High-draft player underperformed -- field took the loss equally
  - T. Hayes (GSV, 1.1x, 399 drafts) = 0.68 -- High-draft player underperformed -- field took the loss equally
  - C. Leite (POR, 2.6x, 126 drafts) = 0.31 -- High-draft player underperformed -- field took the loss equally
  - K. Chen (GSV, 3.0x, 6 drafts) = 0.26 -- Low-draft player correctly faded by the field
  - S. Dolson (SEA, 3.0x, 103 drafts) = 0.05 -- High-draft player underperformed -- field took the loss equally
  - C. Zandalasini (GSV, 1.6x, None drafts) = None -- Low-draft player correctly faded by the field
  - K. Thornton (GSV, 0.8x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-08-01

**Players**: 20 HV
 | **Score range**: 2.12 -- 6.76 (median 3.74)

**Leaderboard**: top score 60.67, floor 52.78, median 55.72

**Winner** (score 60.67):
  - R. Banham (4.1x) = 10.58
  - N. Hillmon (3.2x) = 12.05
  - C. Brink (4.6x) = 9.73
  - M. Caldwell (4x) = 18.13
  - K. Nurse (4.2x) = 10.17

**Field ownership** (top-20 entries):
  - M. Caldwell (4.6x/4x/4.2x/4.4x/3.8x): 20/20 = 100%, avg 18.40
  - R. Banham (4.1x/3.7x/3.9x/3.3x): 14/20 = 70%, avg 9.84
  - N. Hillmon (3.2x/3x/3.4x/2.8x): 13/20 = 65%, avg 11.88
  - C. Brink (4.4x/4.6x/4.2x/5x): 12/20 = 60%, avg 9.28
  - S. Cunningham (3.5x/3.7x/3.9x): 5/20 = 25%, avg 7.35
  - K. Nurse (4.4x/4.2x): 3/20 = 15%, avg 10.34
  - S. Ionescu (2.1x): 3/20 = 15%, avg 9.59
  - K. Cardoso (2.9x/2.7x): 3/20 = 15%, avg 7.95

### Outcome Classification

**(A) Correctly priced** (16 players):
  - N. Ogwumike (LAS, 0.3x, 271 drafts) = 6.76 -- High-draft player delivered as expected
  - V. Burton (GSV, 0.8x, 19 drafts) = 4.68 -- Mid-draft player with mid outcome -- no edge either way
  - N. Hillmon (ATL, 1.4x, 84 drafts) = 3.77 -- High-draft player delivered as expected
  - N. Howard (MIN, 1.0x, 14 drafts) = 4.23 -- Mid-draft player with mid outcome -- no edge either way
  - R. Jackson (CHI, 1.1x, 53 drafts) = 3.84 -- High-draft player delivered as expected
  - J. Allemand (TOR, 2.3x, 31 drafts) = 2.72 -- Mid-draft player with mid outcome -- no edge either way
  - K. Nurse (TOR, 3.0x, 2 drafts) = 2.42 -- Outcome roughly matched draft position and signals
  - A. Gray (ATL, 0.2x, 227 drafts) = 5.18 -- High-draft player delivered as expected
  - E. Magbegor (SEA, 0.9x, 112 drafts) = 3.74 -- High-draft player delivered as expected
  - M. Mabrey (TOR, 1.0x, 10 drafts) = 3.58 -- Mid-draft player with mid outcome -- no edge either way
  - A. Stevens (CHI, 0.4x, 153 drafts) = 4.45 -- High-draft player delivered as expected
  - C. Brink (LAS, 3.0x, 466 drafts) = 2.12 -- Outcome roughly matched draft position and signals
  - R. Banham (CHI, 2.1x, 199 drafts) = 2.58 -- Outcome roughly matched draft position and signals
  - G. Williams (GSV, 0.5x, 209 drafts) = 4.1 -- High-draft player delivered as expected
  - J. Salaün (GSV, 1.5x, 59 drafts) = 2.79 -- Outcome roughly matched draft position and signals
  - B. Jones (ATL, 0.7x, 108 drafts) = 3.61 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (4 players):
  - M. Caldwell (MIN, 2.6x, 5 drafts) = 4.53 -- Above-expectation outcome, ambiguous whether knowable
  - E. Williams (CHI, 1.9x, 2 drafts) = 3.38 -- Above-expectation outcome, ambiguous whether knowable
  - O. Nelson-Ododa (CON, 1.3x, 3 drafts) = 3.57 -- Above-expectation outcome, ambiguous whether knowable
  - L. Lacan (CON, 1.6x, 1 drafts) = 3.16 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 4 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-02

**Players**: 19 HV
 | **Score range**: 0.45 -- 6.61 (median 1.24)

**Leaderboard**: top score 61.67, floor 54.03, median 56.00

**Winner** (score 61.67):
  - K. McBride (2.8x) = 18.52
  - A. Smith (2.5x) = 7.47
  - J. Shepard (3.4000000000000004x) = 15.83
  - N. Hiedeman (3.5x) = 12.52
  - C. Williams (1.6x) = 7.33
  - **Game stack**: team 5: 2 players, team 12: 2 players

**Field ownership** (top-20 entries):
  - K. McBride (2.8x/2.6x/2.4x/2x/2.2x): 20/20 = 100%, avg 16.33
  - J. Shepard (3x/3.6x/3.2x/3.8x/3.4x): 20/20 = 100%, avg 15.27
  - N. Hiedeman (3.5x/4.1x/3.7x/3.9x/3.3x): 17/20 = 85%, avg 12.64
  - C. Williams (1.6x/2.4x/2x/2.2x): 10/20 = 50%, avg 9.90
  - A. Smith (1.9x/2.3x/2.5x/2.7x): 8/20 = 40%, avg 7.10
  - B. Carleton (3.5x/3.1x/2.9x/3.7x/3.3x): 7/20 = 35%, avg 5.25
  - N. Collier (2x/1.4x): 6/20 = 30%, avg 7.30
  - M. Kliundikova (5x/4.2x): 3/20 = 15%, avg 6.30

### Outcome Classification

**(A) Correctly priced** (19 players):
  - K. McBride (MIN, 0.8x, 139 drafts) = 6.61 -- High-draft player delivered as expected
  - J. Shepard (DAL, 1.8x, 68 drafts) = 4.66 -- High-draft player delivered as expected
  - N. Hiedeman (SEA, 2.1x, 57 drafts) = 3.58 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.4x, 214 drafts) = 4.58 -- High-draft player delivered as expected
  - A. Smith (DAL, 0.7x, 128 drafts) = 2.99 -- Outcome roughly matched draft position and signals
  - N. Collier (MIN, 0.0x, 2900 drafts) = 3.84 -- High-draft player delivered as expected
  - M. Kliundikova (TOR, 3.0x, 57 drafts) = 1.41 -- High-draft player underperformed -- field took the loss equally
  - K. Stokes (GSV, 3.0x, 44 drafts) = 1.24 -- Mid-draft player with mid outcome -- no edge either way
  - B. Carleton (POR, 1.7x, 77 drafts) = 1.59 -- Outcome roughly matched draft position and signals
  - A. Nye (ATL, 3.0x, 58 drafts) = 1.08 -- High-draft player underperformed -- field took the loss equally
  - J. Loyd (LVA, 1.3x, 98 drafts) = 1.58 -- Outcome roughly matched draft position and signals
  - K. Bell (LVA, 3.0x, 57 drafts) = 0.86 -- High-draft player underperformed -- field took the loss equally
  - M. Gustafson (POR, 3.0x, 48 drafts) = 0.82 -- Mid-draft player with mid outcome -- no edge either way
  - N. Smith (LVA, 2.0x, 74 drafts) = 0.93 -- High-draft player underperformed -- field took the loss equally
  - C. Gray (LVA, 1.1x, 138 drafts) = 0.91 -- High-draft player underperformed -- field took the loss equally
  - D. Evans (LVA, 2.7x, 50 drafts) = 0.5 -- High-draft player underperformed -- field took the loss equally
  - A. Wilson (LVA, 0.0x, 1800 drafts) = 1.15 -- High-draft player underperformed -- field took the loss equally
  - J. Young (LVA, 0.4x, 201 drafts) = 0.95 -- High-draft player underperformed -- field took the loss equally
  - A. Kosu (MIN, 3.0x, 2 drafts) = 0.45 -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-08-03

**Players**: 20 HV
 | **Score range**: 1.98 -- 5.38 (median 3.79)

**Leaderboard**: top score 63.02, floor 51.95, median 54.56

**Winner** (score 63.02):
  - N. Howard (3x) = 14.91
  - J. Young (2.2x) = 11.83
  - J. Loyd (2.9000000000000004x) = 15.29
  - J. Canada (2.0999999999999996x) = 7.96
  - E. Williams (3x) = 13.04
  - **Game stack**: team 1: 2 players

**Field ownership** (top-20 entries):
  - J. Loyd (2.9x/2.5x/2.7x): 15/20 = 75%, avg 14.31
  - N. Howard (2.4x/2.8x/3x/2.6x): 13/20 = 65%, avg 13.15
  - A. Wilson (1.8x/2x): 10/20 = 50%, avg 9.03
  - J. Young (2.4x/2.2x): 8/20 = 40%, avg 12.23
  - N. Hillmon (2.5x/2.7x): 8/20 = 40%, avg 8.84
  - K. Iriafen (3.1x/2.3x/2.5x/2.7x): 7/20 = 35%, avg 11.46
  - S. Ionescu (1.9x/2.1x): 7/20 = 35%, avg 10.63
  - E. Williams (3.2x/3.4x/3x/3.6x): 5/20 = 25%, avg 14.08

### Outcome Classification

**(A) Correctly priced** (19 players):
  - E. Williams (CHI, 1.8x, 21 drafts) = 4.35 -- Mid-draft player with mid outcome -- no edge either way
  - N. Howard (MIN, 1.0x, 59 drafts) = 4.97 -- High-draft player delivered as expected
  - K. Iriafen (WAS, 1.1x, 20 drafts) = 4.38 -- Mid-draft player with mid outcome -- no edge either way
  - K. Charles (GSV, 3.0x, 1 drafts) = 2.79 -- Outcome roughly matched draft position and signals
  - J. Young (LVA, 0.4x, 191 drafts) = 5.38 -- High-draft player delivered as expected
  - D. Malonga (SEA, 3.0x, 2 drafts) = 2.53 -- Outcome roughly matched draft position and signals
  - S. Cunningham (IND, 2.3x, 22 drafts) = 2.91 -- Mid-draft player with mid outcome -- no edge either way
  - A. Morrow (CON, 2.2x, 4 drafts) = 2.94 -- Outcome roughly matched draft position and signals
  - K. Copper (PHO, 1.1x, 188 drafts) = 3.91 -- High-draft player delivered as expected
  - B. Jones (ATL, 0.7x, 114 drafts) = 4.31 -- High-draft player delivered as expected
  - N. Hillmon (ATL, 1.3x, 32 drafts) = 3.43 -- Mid-draft player with mid outcome -- no edge either way
  - L. Amihere (GSV, 2.1x, 1 drafts) = 2.76 -- Outcome roughly matched draft position and signals
  - S. Ionescu (NYL, 0.1x, 813 drafts) = 5.35 -- High-draft player delivered as expected
  - M. Akoa Makani (PHO, 1.9x, 18 drafts) = 2.73 -- Mid-draft player with mid outcome -- no edge either way
  - D. Evans (LVA, 2.8x, 1 drafts) = 2.17 -- Outcome roughly matched draft position and signals
  - T. Paopao (ATL, 2.9x, 7 drafts) = 2.2 -- Outcome roughly matched draft position and signals
  - J. Canada (ATL, 0.7x, 114 drafts) = 3.79 -- High-draft player delivered as expected
  - A. Nye (ATL, 3.0x, 1 drafts) = 1.98 -- Outcome roughly matched draft position and signals
  - A. Boston (IND, 0.2x, 391 drafts) = 4.39 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (1 players):
  - J. Loyd (LVA, 1.3x, 26 drafts) = 5.27 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-05

**Players**: 19 HV
 | **Score range**: 2.25 -- 6.07 (median 3.58)

**Leaderboard**: top score 52.97, floor 47.69, median 49.25

**Winner** (score 52.97):
  - N. Howard (2.9x) = 9.08
  - R. Jackson (2.9000000000000004x) = 12.81
  - E. Williams (3.3x) = 11.81
  - J. Allemand (3.5x) = 10.02
  - D. Malonga (4.1x) = 9.24
  - **Game stack**: team 8: 2 players

**Field ownership** (top-20 entries):
  - K. Mitchell (1.9x/2.3x/2.5x): 12/20 = 60%, avg 14.25
  - R. Jackson (2.3x/3.1x/2.7x/2.9x/2.5x): 9/20 = 45%, avg 12.03
  - K. Plum (1.8x/1.4x/2.2x): 8/20 = 40%, avg 9.64
  - N. Howard (2.1x/2.9x/2.5x/2.7x): 6/20 = 30%, avg 8.14
  - D. Malonga (4.1x): 6/20 = 30%, avg 9.24
  - E. Williams (2.9x/3.1x/3.5x/3.3x): 5/20 = 25%, avg 11.52
  - J. Allemand (3.5x/3.3x): 5/20 = 25%, avg 9.79
  - J. Shepard (3.2x/3.4x/3.6x): 5/20 = 25%, avg 11.57

### Outcome Classification

**(A) Correctly priced** (17 players):
  - K. Mitchell (IND, 0.5x, 277 drafts) = 6.07 -- High-draft player delivered as expected
  - R. Jackson (CHI, 1.1x, 33 drafts) = 4.42 -- Mid-draft player with mid outcome -- no edge either way
  - S. Talbot (LVA, 3.0x, 1 drafts) = 2.8 -- Outcome roughly matched draft position and signals
  - E. Williams (CHI, 1.7x, 39 drafts) = 3.58 -- Mid-draft player with mid outcome -- no edge either way
  - J. Shepard (DAL, 1.6x, 24 drafts) = 3.4 -- Mid-draft player with mid outcome -- no edge either way
  - J. Allemand (TOR, 2.1x, 3 drafts) = 2.86 -- Outcome roughly matched draft position and signals
  - K. Cardoso (CHI, 0.9x, 30 drafts) = 4.04 -- Mid-draft player with mid outcome -- no edge either way
  - K. Plum (LAS, 0.2x, 492 drafts) = 5.08 -- High-draft player delivered as expected
  - S. Sabally (NYL, 0.5x, 42 drafts) = 4.45 -- Mid-draft player with mid outcome -- no edge either way
  - D. Malonga (SEA, 2.9x, 1 drafts) = 2.25 -- Outcome roughly matched draft position and signals
  - D. Carrington (CHI, 1.5x, 5 drafts) = 2.95 -- Outcome roughly matched draft position and signals
  - A. Stevens (CHI, 0.3x, 171 drafts) = 4.41 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.0x, 1800 drafts) = 5.06 -- High-draft player delivered as expected
  - E. Wheeler (LAS, 1.1x, 18 drafts) = 3.14 -- Mid-draft player with mid outcome -- no edge either way
  - K. McBride (MIN, 0.7x, 90 drafts) = 3.58 -- High-draft player delivered as expected
  - L. Lacan (CON, 1.5x, 1 drafts) = 2.73 -- Outcome roughly matched draft position and signals
  - N. Ogwumike (LAS, 0.3x, 285 drafts) = 3.99 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (2 players):
  - D. Bonner (PHO, 1.8x, 2 drafts) = 3.33 -- Above-expectation outcome, ambiguous whether knowable
  - L. Fiebich (NYL, 1.6x, 3 drafts) = 3.2 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-06

**Players**: 20 HV
 | **Score range**: -0.00 -- 5.26 (median 1.38)

**Leaderboard**: top score 43.89, floor 41.55, median 42.40

**Winner** (score 43.89):
  - A. Wilson (2x) = 10.53
  - K. Charles (4.6x) = 12.16
  - N. Smith (3.7x) = 9.42
  - J. Loyd (2.5999999999999996x) = 6.56
  - C. Leite (3.8x) = 5.23
  - **Game stack**: team 1: 3 players

**Field ownership** (top-20 entries):
  - A. Wilson (1.6x/1.8x/2x): 20/20 = 100%, avg 10.16
  - K. Charles (4.8x/4x/4.6x/4.2x/4.4x): 20/20 = 100%, avg 10.97
  - N. Smith (3.5x/4.1x/3.7x/3.9x/3.3x): 20/20 = 100%, avg 9.12
  - J. Young (1.6x/2.4x/2x/2.2x): 11/20 = 55%, avg 6.23
  - J. Loyd (3x/2.6x): 8/20 = 40%, avg 6.81
  - C. Gray (2.9x/2.7x): 8/20 = 40%, avg 5.66
  - C. Leite (4x/3.8x/4.2x): 5/20 = 25%, avg 5.61
  - T. Fágbénlé (3.2x/2.8x/3x): 5/20 = 25%, avg 5.67

### Outcome Classification

**(A) Correctly priced** (20 players):
  - K. Charles (GSV, 2.8x, 107 drafts) = 2.64 -- Outcome roughly matched draft position and signals
  - A. Wilson (LVA, 0.0x, 5300 drafts) = 5.26 -- High-draft player delivered as expected
  - N. Smith (LVA, 2.1x, 127 drafts) = 2.55 -- Outcome roughly matched draft position and signals
  - J. Salaün (GSV, 1.5x, 139 drafts) = 2.32 -- Outcome roughly matched draft position and signals
  - J. Loyd (LVA, 1.2x, 240 drafts) = 2.52 -- Outcome roughly matched draft position and signals
  - T. Hayes (GSV, 1.2x, 21 drafts) = 2.36 -- Mid-draft player with mid outcome -- no edge either way
  - J. Young (LVA, 0.4x, 580 drafts) = 2.88 -- Outcome roughly matched draft position and signals
  - T. Fágbénlé (TOR, 1.4x, 147 drafts) = 1.89 -- Outcome roughly matched draft position and signals
  - C. Leite (POR, 2.6x, 95 drafts) = 1.38 -- High-draft player underperformed -- field took the loss equally
  - C. Gray (LVA, 1.1x, 261 drafts) = 2.02 -- Outcome roughly matched draft position and signals
  - K. Bell (LVA, 3.0x, 103 drafts) = 0.9 -- High-draft player underperformed -- field took the loss equally
  - C. Zandalasini (GSV, 1.6x, 11 drafts) = 0.95 -- Mid-draft player with mid outcome -- no edge either way
  - V. Burton (GSV, 0.8x, 369 drafts) = 0.39 -- High-draft player underperformed -- field took the loss equally
  - D. Evans (LVA, 2.7x, 80 drafts) = 0.16 -- High-draft player underperformed -- field took the loss equally
  - K. Martin (LAS, 3.0x, 157 drafts) = 0.15 -- High-draft player underperformed -- field took the loss equally
  - I. Rupert (GSV, 1.4x, 22 drafts) = 0.08 -- Mid-draft player with mid outcome -- no edge either way
  - L. Amihere (GSV, 2.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - A. Nye (ATL, 3.0x, None drafts) = -0.0 -- Low-draft player correctly faded by the field
  - K. Stokes (GSV, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - K. Chen (GSV, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-08-07

**Players**: 18 HV
 | **Score range**: 1.60 -- 5.28 (median 3.22)

**Leaderboard**: top score 58.87, floor 51.68, median 53.33

**Winner** (score 58.87):
  - L. Lacan (3.4x) = 10.94
  - S. Cunningham (3.9000000000000004x) = 10.15
  - J. Allemand (3.6x) = 16.74
  - R. Banham (3.5x) = 11.12
  - C. Brink (3.9000000000000004x) = 9.91

**Field ownership** (top-20 entries):
  - J. Allemand (3.2x/3.4x/3.8x/3.6x): 19/20 = 95%, avg 16.93
  - C. Brink (4.3x/4.1x/3.9x/4.7x): 14/20 = 70%, avg 10.39
  - S. Cunningham (3.5x/3.7x/3.9x/3.3x): 10/20 = 50%, avg 9.22
  - R. Jackson (2.8x/3x): 10/20 = 50%, avg 8.09
  - B. Hartley (3.5x): 8/20 = 40%, avg 9.96
  - R. Burrell (4.4x/4.2x): 7/20 = 35%, avg 6.83
  - A. Thomas (1.8x/2x): 6/20 = 30%, avg 10.21
  - T. Paopao (4x/4.2x): 5/20 = 25%, avg 6.77

### Outcome Classification

**(A) Correctly priced** (15 players):
  - J. Allemand (TOR, 2.0x, 10 drafts) = 4.65 -- Mid-draft player with mid outcome -- no edge either way
  - C. Brink (LAS, 2.7x, 299 drafts) = 2.54 -- Outcome roughly matched draft position and signals
  - N. Coffey (MIN, 3.0x, 3 drafts) = 2.37 -- Outcome roughly matched draft position and signals
  - S. Cunningham (IND, 2.1x, 44 drafts) = 2.6 -- Mid-draft player with mid outcome -- no edge either way
  - A. Thomas (PHO, 0.0x, 2300 drafts) = 5.28 -- High-draft player delivered as expected
  - K. Cardoso (CHI, 0.8x, 231 drafts) = 3.53 -- High-draft player delivered as expected
  - J. Canada (ATL, 0.6x, 119 drafts) = 3.68 -- High-draft player delivered as expected
  - A. Gray (ATL, 0.2x, 495 drafts) = 3.88 -- High-draft player delivered as expected
  - S. Sabally (NYL, 0.5x, 222 drafts) = 3.35 -- High-draft player delivered as expected
  - M. Mabrey (TOR, 1.0x, 22 drafts) = 2.77 -- Mid-draft player with mid outcome -- no edge either way
  - R. Jackson (CHI, 1.0x, 335 drafts) = 2.73 -- Outcome roughly matched draft position and signals
  - T. Paopao (ATL, 2.8x, 13 drafts) = 1.68 -- Mid-draft player with mid outcome -- no edge either way
  - R. Burrell (LAS, 3.0x, 1 drafts) = 1.6 -- Outcome roughly matched draft position and signals
  - D. Hamby (LAS, 0.2x, 354 drafts) = 3.56 -- High-draft player delivered as expected
  - A. Morrow (CON, 2.2x, 3 drafts) = 1.74 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (3 players):
  - D. Bonner (PHO, 1.7x, 5 drafts) = 3.58 -- Above-expectation outcome, ambiguous whether knowable
  - R. Banham (CHI, 2.1x, 6 drafts) = 3.18 -- Above-expectation outcome, ambiguous whether knowable
  - L. Lacan (CON, 1.4x, 6 drafts) = 3.22 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 3 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-08

**Players**: 18 HV
 | **Score range**: 1.57 -- 5.39 (median 2.87)

**Leaderboard**: top score 56.55, floor 51.18, median 52.55

**Winner** (score 56.55):
  - S. Citron (2.8x) = 15.10
  - K. McBride (2.5x) = 6.93
  - E. Meesseman (2.8x) = 13.44
  - D. Carrington (2.9x) = 4.91
  - D. Malonga (3.9000000000000004x) = 16.17

**Field ownership** (top-20 entries):
  - D. Malonga (4.3x/4.1x/3.9x): 20/20 = 100%, avg 16.38
  - A. Wilson (1.8x/2x): 14/20 = 70%, avg 9.05
  - E. Meesseman (3.2x/2.8x/3x/2.6x): 11/20 = 55%, avg 13.53
  - S. Ionescu (1.9x/2.1x/1.5x): 9/20 = 45%, avg 7.66
  - S. Citron (2.4x/2.8x/2.2x): 8/20 = 40%, avg 13.08
  - K. McBride (2.1x/2.3x/2.5x/2.7x): 8/20 = 40%, avg 6.58
  - N. Smith (3.5x/3.7x): 5/20 = 25%, avg 8.41
  - J. Young (1.8x/2x/2.2x/2.4x): 5/20 = 25%, avg 9.84

### Outcome Classification

**(A) Correctly priced** (18 players):
  - D. Malonga (SEA, 2.7x, 32 drafts) = 4.15 -- Mid-draft player with mid outcome -- no edge either way
  - S. Citron (WAS, 0.8x, 160 drafts) = 5.39 -- High-draft player delivered as expected
  - A. Smith (DAL, 0.7x, 125 drafts) = 4.79 -- High-draft player delivered as expected
  - J. Young (LVA, 0.4x, 188 drafts) = 4.64 -- High-draft player delivered as expected
  - M. Johannes (NYL, 2.6x, 4 drafts) = 2.31 -- Outcome roughly matched draft position and signals
  - N. Smith (LVA, 2.1x, 42 drafts) = 2.37 -- Mid-draft player with mid outcome -- no edge either way
  - A. Wilson (LVA, 0.0x, 3800 drafts) = 4.56 -- High-draft player delivered as expected
  - K. Iriafen (WAS, 1.0x, 116 drafts) = 3.03 -- High-draft player delivered as expected
  - C. Gray (LVA, 1.1x, 147 drafts) = 2.93 -- Outcome roughly matched draft position and signals
  - L. Olsen (WAS, 3.0x, 2 drafts) = 1.81 -- Outcome roughly matched draft position and signals
  - S. Ionescu (NYL, 0.1x, 1100 drafts) = 4.03 -- High-draft player delivered as expected
  - E. Wheeler (LAS, 1.1x, 131 drafts) = 2.7 -- Outcome roughly matched draft position and signals
  - S. Dolson (SEA, 3.0x, 1 drafts) = 1.57 -- Outcome roughly matched draft position and signals
  - J. Loyd (LVA, 1.1x, 144 drafts) = 2.44 -- Outcome roughly matched draft position and signals
  - K. McBride (MIN, 0.7x, 183 drafts) = 2.77 -- Outcome roughly matched draft position and signals
  - J. Jones (NYL, 0.6x, 60 drafts) = 2.87 -- Outcome roughly matched draft position and signals
  - B. Sykes (TOR, 0.8x, 6 drafts) = 2.55 -- Outcome roughly matched draft position and signals
  - N. Cloud (CHI, 0.8x, 130 drafts) = 2.5 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-08-09

**Players**: 19 HV
 | **Score range**: 1.23 -- 4.98 (median 2.10)

**Leaderboard**: top score 50.49, floor 45.43, median 46.06

**Winner** (score 50.49):
  - K. Mitchell (2.4x) = 11.94
  - S. Cunningham (3.8x) = 10.25
  - C. Brink (3.6x) = 2.92
  - C. Zandalasini (3.0999999999999996x) = 13.11
  - L. Hull (3.3x) = 12.26
  - **Game stack**: team 3: 3 players

**Field ownership** (top-20 entries):
  - L. Hull (3.5x/4.1x/3.7x/3.9x/3.3x): 20/20 = 100%, avg 13.27
  - S. Cunningham (3.6x/4x/3.2x/3.8x/3.4x): 16/20 = 80%, avg 9.38
  - K. Mitchell (2.4x/2x/2.2x): 14/20 = 70%, avg 11.45
  - R. Banham (3.2x/3.4x/3.6x): 9/20 = 45%, avg 5.36
  - A. Boston (1.6x/2x/2.2x): 9/20 = 45%, avg 7.70
  - K. Cardoso (2.4x/2.8x/2.6x): 5/20 = 25%, avg 6.45
  - C. Zandalasini (3.5x/2.9x/3.1x): 4/20 = 20%, avg 13.74
  - J. Allemand (2.9x/3.5x/3.1x): 4/20 = 20%, avg 6.08

### Outcome Classification

**(A) Correctly priced** (19 players):
  - C. Zandalasini (GSV, 1.7x, 11 drafts) = 4.23 -- Mid-draft player with mid outcome -- no edge either way
  - L. Hull (IND, 2.1x, 138 drafts) = 3.72 -- High-draft player delivered as expected
  - K. Mitchell (IND, 0.4x, 902 drafts) = 4.98 -- High-draft player delivered as expected
  - S. Cunningham (IND, 2.0x, 92 drafts) = 2.7 -- Outcome roughly matched draft position and signals
  - M. Timpson (IND, 3.0x, 4 drafts) = 2.1 -- Outcome roughly matched draft position and signals
  - V. Burton (GSV, 0.8x, 176 drafts) = 3.55 -- High-draft player delivered as expected
  - M. Westbeld (CHI, 3.0x, 2 drafts) = 1.9 -- Outcome roughly matched draft position and signals
  - J. Salaün (GSV, 1.5x, 31 drafts) = 2.52 -- Mid-draft player with mid outcome -- no edge either way
  - T. Hayes (GSV, 1.2x, 118 drafts) = 2.58 -- Outcome roughly matched draft position and signals
  - A. Boston (IND, 0.2x, 981 drafts) = 3.65 -- High-draft player delivered as expected
  - R. Allen (NYL, 2.5x, 3 drafts) = 1.6 -- Outcome roughly matched draft position and signals
  - K. Cardoso (CHI, 0.8x, 372 drafts) = 2.48 -- Outcome roughly matched draft position and signals
  - J. Allemand (TOR, 1.7x, 76 drafts) = 1.87 -- Outcome roughly matched draft position and signals
  - E. Williams (CHI, 1.6x, 121 drafts) = 1.9 -- Outcome roughly matched draft position and signals
  - B. Turner (LVA, 3.0x, 1 drafts) = 1.32 -- Low-draft player correctly faded by the field
  - C. Leite (POR, 2.6x, 19 drafts) = 1.36 -- Mid-draft player with mid outcome -- no edge either way
  - D. Dantas (IND, 3.0x, 2 drafts) = 1.23 -- Low-draft player correctly faded by the field
  - R. Banham (CHI, 2.0x, 126 drafts) = 1.53 -- Outcome roughly matched draft position and signals
  - R. Jackson (CHI, 1.0x, 526 drafts) = 2.01 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-08-10

**Players**: 20 HV
 | **Score range**: 2.24 -- 6.34 (median 3.83)

**Leaderboard**: top score 64.18, floor 58.61, median 60.25

**Winner** (score 64.18):
  - A. Wilson (2x) = 12.68
  - J. Allemand (3.5x) = 12.06
  - N. Hillmon (2.9000000000000004x) = 10.13
  - D. Malonga (3.9x) = 14.93
  - C. Brink (3.5999999999999996x) = 14.37

**Field ownership** (top-20 entries):
  - D. Malonga (4.3x/3.7x/3.9x): 20/20 = 100%, avg 14.44
  - A. Wilson (1.6x/1.8x/2x): 16/20 = 80%, avg 12.44
  - C. Brink (4x/4.2x/4.4x/3.8x/3.6x): 16/20 = 80%, avg 15.57
  - N. Hillmon (2.9x/2.7x): 11/20 = 55%, avg 10.07
  - J. Allemand (3.5x/3.7x/3.3x/3.1x): 10/20 = 50%, avg 11.30
  - A. Smith (2.4x): 6/20 = 30%, avg 10.95
  - S. Citron (2.1x/2.5x): 5/20 = 25%, avg 7.87
  - D. Carrington (3.1x/2.7x): 4/20 = 20%, avg 10.71

### Outcome Classification

**(A) Correctly priced** (16 players):
  - C. Brink (LAS, 2.4x, 207 drafts) = 3.99 -- High-draft player delivered as expected
  - D. Malonga (SEA, 2.5x, 27 drafts) = 3.83 -- Mid-draft player with mid outcome -- no edge either way
  - S. Dolson (SEA, 3.0x, 1 drafts) = 2.94 -- Outcome roughly matched draft position and signals
  - B. Jones (ATL, 0.7x, 117 drafts) = 4.95 -- High-draft player delivered as expected
  - J. Allemand (TOR, 1.7x, 11 drafts) = 3.44 -- Mid-draft player with mid outcome -- no edge either way
  - A. Wilson (LVA, 0.0x, 3000 drafts) = 6.34 -- High-draft player delivered as expected
  - J. Young (LVA, 0.4x, 198 drafts) = 5.0 -- High-draft player delivered as expected
  - A. Smith (DAL, 0.6x, 106 drafts) = 4.56 -- High-draft player delivered as expected
  - N. Hillmon (ATL, 1.3x, 16 drafts) = 3.49 -- Mid-draft player with mid outcome -- no edge either way
  - D. Evans (LVA, 2.9x, 3 drafts) = 2.24 -- Outcome roughly matched draft position and signals
  - B. Sykes (TOR, 0.8x, 32 drafts) = 3.93 -- Mid-draft player with mid outcome -- no edge either way
  - K. Plum (LAS, 0.2x, 329 drafts) = 4.77 -- High-draft player delivered as expected
  - E. Engstler (POR, 3.0x, 1 drafts) = 2.4 -- Outcome roughly matched draft position and signals
  - D. Hamby (LAS, 0.3x, 205 drafts) = 4.43 -- High-draft player delivered as expected
  - K. Iriafen (WAS, 1.0x, 65 drafts) = 3.18 -- High-draft player delivered as expected
  - D. Bonner (PHO, 1.6x, 8 drafts) = 2.54 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (4 players):
  - S. Rivers (CON, 1.6x, 6 drafts) = 4.11 -- Above-expectation outcome, ambiguous whether knowable
  - D. Carrington (CHI, 1.5x, 9 drafts) = 3.57 -- Above-expectation outcome, ambiguous whether knowable
  - L. Lacan (CON, 1.3x, 3 drafts) = 3.02 -- Above-expectation outcome, ambiguous whether knowable
  - M. Mabrey (TOR, 1.0x, 8 drafts) = 3.14 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 4 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-11

**Players**: 16 HV
 | **Score range**: 0.18 -- 3.09 (median 1.98)

**Leaderboard**: top score 44.16, floor 41.69, median 42.60

**Winner** (score 44.16):
  - V. Burton (2.8x) = 8.61
  - T. Hayes (3x) = 8.43
  - O. Nelson-Ododa (3x) = 9.26
  - A. Morrow (3.6999999999999997x) = 10.49
  - J. Salaün (2.7x) = 7.37
  - **Game stack**: team 14: 3 players, team 11: 2 players

**Field ownership** (top-20 entries):
  - A. Morrow (4.1x/3.5x/4.3x/3.7x/3.9x/3.8x): 20/20 = 100%, avg 10.73
  - O. Nelson-Ododa (3x/2.8x/2.6x/3.2x/3.4x): 18/20 = 90%, avg 9.30
  - T. Hayes (3x/2.8x/2.6x/2.4x/3.2x): 17/20 = 85%, avg 7.57
  - V. Burton (2.4x/2.8x/2.6x): 16/20 = 80%, avg 8.27
  - J. Salaün (3.5x/3.1x/2.7x/2.9x/3.3x): 10/20 = 50%, avg 8.19
  - C. Zandalasini (3.4x/2.6x/2.8x): 8/20 = 40%, avg 6.60
  - T. Fágbénlé (3.1x/2.9x/3.3x/3.5x): 8/20 = 40%, avg 7.14
  - S. Rivers (2.9x/3.1x/3.3x): 3/20 = 15%, avg 6.13

### Outcome Classification

**(A) Correctly priced** (16 players):
  - A. Morrow (CON, 2.3x, 155 drafts) = 2.83 -- Outcome roughly matched draft position and signals
  - O. Nelson-Ododa (CON, 1.4x, 193 drafts) = 3.09 -- High-draft player delivered as expected
  - J. Salaün (GSV, 1.5x, 244 drafts) = 2.73 -- Outcome roughly matched draft position and signals
  - T. Hayes (GSV, 1.2x, 357 drafts) = 2.81 -- Outcome roughly matched draft position and signals
  - V. Burton (GSV, 0.8x, 2500 drafts) = 3.08 -- High-draft player delivered as expected
  - T. Fágbénlé (TOR, 1.5x, 245 drafts) = 2.23 -- Outcome roughly matched draft position and signals
  - C. Zandalasini (GSV, 1.4x, 210 drafts) = 2.26 -- Outcome roughly matched draft position and signals
  - S. Rivers (CON, 1.5x, 210 drafts) = 1.98 -- Outcome roughly matched draft position and signals
  - I. Rupert (GSV, 2.1x, 7 drafts) = 1.67 -- Outcome roughly matched draft position and signals
  - K. Martin (LAS, 3.0x, 198 drafts) = 1.21 -- High-draft player underperformed -- field took the loss equally
  - A. Edwards (CON, 3.0x, 180 drafts) = 1.19 -- High-draft player underperformed -- field took the loss equally
  - L. Lacan (CON, 1.2x, 237 drafts) = 0.97 -- High-draft player underperformed -- field took the loss equally
  - M. Mabrey (TOR, 1.0x, 1300 drafts) = 0.85 -- High-draft player underperformed -- field took the loss equally
  - C. Leite (POR, 2.6x, 150 drafts) = 0.46 -- High-draft player underperformed -- field took the loss equally
  - K. Charles (GSV, 2.8x, 141 drafts) = 0.24 -- High-draft player underperformed -- field took the loss equally
  - L. Amihere (GSV, 2.0x, 108 drafts) = 0.18 -- High-draft player underperformed -- field took the loss equally

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-08-12

**Players**: 18 HV
 | **Score range**: 1.71 -- 5.47 (median 3.40)

**Leaderboard**: top score 54.17, floor 50.96, median 52.29

**Winner** (score 54.17):
  - M. Hines-Allen (4.1x) = 13.40
  - S. Cunningham (3.8x) = 8.87
  - L. Fiebich (3.2x) = 13.99
  - J. Jones (2x) = 10.94
  - K. Plum (1.4x) = 6.97
  - **Game stack**: team 3: 2 players, team 4: 2 players

**Field ownership** (top-20 entries):
  - J. Jones (2.6x/2.4x/2x/1.8x/2.2x): 18/20 = 90%, avg 13.01
  - L. Fiebich (3x/2.8x/3.2x/3.6x/3.4x): 17/20 = 85%, avg 14.25
  - S. Cunningham (3.2x/3.4x/3.8x/3.6x): 11/20 = 55%, avg 8.27
  - M. Hines-Allen (4.1x/3.5x/3.3x): 9/20 = 45%, avg 11.73
  - M. Johannes (4.3x/3.7x): 7/20 = 35%, avg 9.21
  - K. Plum (1.6x/1.8x/1.4x/2.2x): 5/20 = 25%, avg 9.16
  - A. Stevens (2.4x/2x/2.2x/1.8x): 5/20 = 25%, avg 8.58
  - J. Allemand (3.4x/3x): 5/20 = 25%, avg 4.12

### Outcome Classification

**(A) Correctly priced** (16 players):
  - L. Fiebich (NYL, 1.6x, 135 drafts) = 4.37 -- High-draft player delivered as expected
  - J. Jones (NYL, 0.6x, 284 drafts) = 5.47 -- High-draft player delivered as expected
  - M. Hines-Allen (IND, 2.1x, 62 drafts) = 3.27 -- High-draft player delivered as expected
  - K. Plum (LAS, 0.2x, 718 drafts) = 4.98 -- High-draft player delivered as expected
  - M. Johannes (NYL, 2.5x, 35 drafts) = 2.38 -- Mid-draft player with mid outcome -- no edge either way
  - D. Hamby (LAS, 0.2x, 820 drafts) = 4.48 -- High-draft player delivered as expected
  - N. Howard (MIN, 0.9x, 177 drafts) = 3.4 -- High-draft player delivered as expected
  - A. Stevens (CHI, 0.4x, 178 drafts) = 4.05 -- High-draft player delivered as expected
  - S. Cunningham (IND, 2.0x, 266 drafts) = 2.33 -- Outcome roughly matched draft position and signals
  - S. Talbot (LVA, 3.0x, 36 drafts) = 1.73 -- Mid-draft player with mid outcome -- no edge either way
  - R. Burrell (LAS, 2.9x, 32 drafts) = 1.71 -- Mid-draft player with mid outcome -- no edge either way
  - R. Jackson (CHI, 1.0x, 247 drafts) = 2.76 -- Outcome roughly matched draft position and signals
  - K. Mitchell (IND, 0.4x, 669 drafts) = 3.38 -- High-draft player delivered as expected
  - P. Bueckers (DAL, 0.2x, 649 drafts) = 3.47 -- High-draft player delivered as expected
  - N. Cloud (CHI, 0.8x, 215 drafts) = 2.29 -- Outcome roughly matched draft position and signals
  - S. Ionescu (NYL, 0.1x, 2400 drafts) = 2.88 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (2 players):
  - L. Yueru (DAL, 2.6x, 3 drafts) = 3.44 -- High-boost low-draft player who overperformed
  - M. Siegrist (DAL, 1.7x, 7 drafts) = 3.88 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-13

**Players**: 18 HV
 | **Score range**: 1.95 -- 8.58 (median 3.57)

**Leaderboard**: top score 59.07, floor 55.94, median 57.01

**Winner** (score 59.07):
  - A. Wilson (2x) = 11.33
  - V. Burton (2.6x) = 22.31
  - N. Hillmon (2.8x) = 6.94
  - C. Gray (2.5x) = 9.27
  - E. Williams (2.8x) = 9.23
  - **Game stack**: team 1: 2 players

**Field ownership** (top-20 entries):
  - V. Burton (2.8x/2.6x/2.4x/2x/2.2x): 20/20 = 100%, avg 21.71
  - A. Wilson (1.2x/2x/1.4x/1.8x): 18/20 = 90%, avg 9.75
  - N. Ogwumike (1.9x/2.3x/1.5x/2.1x/1.7x): 11/20 = 55%, avg 10.50
  - C. Gray (2.3x/3.1x/2.7x/2.9x/2.5x): 10/20 = 50%, avg 9.86
  - J. Loyd (2.9x/2.3x/2.5x/2.7x): 8/20 = 40%, avg 9.29
  - K. Iriafen (2.4x/3x/2.2x/2.6x): 7/20 = 35%, avg 7.88
  - K. Cardoso (2.4x/2x/2.2x): 5/20 = 25%, avg 8.63
  - N. Hillmon (2.8x/3x/2.6x): 3/20 = 15%, avg 6.94

### Outcome Classification

**(A) Correctly priced** (14 players):
  - V. Burton (GSV, 0.8x, 144 drafts) = 8.58 -- High-draft player delivered as expected
  - N. Ogwumike (LAS, 0.3x, 258 drafts) = 5.32 -- High-draft player delivered as expected
  - E. Williams (CHI, 1.6x, 15 drafts) = 3.3 -- Mid-draft player with mid outcome -- no edge either way
  - A. Morrow (CON, 2.1x, 15 drafts) = 2.82 -- Mid-draft player with mid outcome -- no edge either way
  - C. Gray (LVA, 1.1x, 146 drafts) = 3.71 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 4000 drafts) = 5.66 -- High-draft player delivered as expected
  - J. Loyd (LVA, 1.1x, 120 drafts) = 3.57 -- High-draft player delivered as expected
  - K. Cardoso (CHI, 0.8x, 54 drafts) = 3.92 -- High-draft player delivered as expected
  - R. Howard (ATL, 0.3x, 46 drafts) = 4.61 -- Mid-draft player with mid outcome -- no edge either way
  - E. Engstler (POR, 3.0x, 4 drafts) = 2.4 -- Outcome roughly matched draft position and signals
  - O. Nelson-Ododa (CON, 1.4x, 5 drafts) = 2.86 -- Outcome roughly matched draft position and signals
  - K. Iriafen (WAS, 1.0x, 142 drafts) = 3.06 -- High-draft player delivered as expected
  - B. Griner (CON, 1.6x, 11 drafts) = 2.35 -- Mid-draft player with mid outcome -- no edge either way
  - M. Caldwell (MIN, 2.3x, 8 drafts) = 1.95 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (4 players):
  - C. Zandalasini (GSV, 1.4x, 4 drafts) = 4.6 -- Above-expectation outcome, ambiguous whether knowable
  - L. Lacan (CON, 1.3x, 9 drafts) = 3.92 -- Above-expectation outcome, ambiguous whether knowable
  - S. Rivers (CON, 1.5x, 9 drafts) = 3.37 -- Above-expectation outcome, ambiguous whether knowable
  - T. Hayes (GSV, 1.1x, 3 drafts) = 3.03 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 4 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-15

**Players**: 19 HV
 | **Score range**: 2.43 -- 5.40 (median 3.60)

**Leaderboard**: top score 61.97, floor 55.38, median 57.78

**Winner** (score 61.97):
  - A. Wilson (2x) = 10.79
  - C. Zandalasini (3x) = 12.17
  - S. Cunningham (3.5x) = 10.22
  - J. Allemand (3x) = 15.13
  - E. Engstler (4.2x) = 13.67

**Field ownership** (top-20 entries):
  - E. Engstler (4.2x): 19/20 = 95%, avg 13.67
  - C. Zandalasini (3.2x/3x/2.8x): 16/20 = 80%, avg 12.42
  - J. Allemand (3.2x/3x/3.4x): 16/20 = 80%, avg 15.95
  - A. Wilson (2x): 7/20 = 35%, avg 10.79
  - E. Williams (3.3x/3.1x): 7/20 = 35%, avg 10.51
  - S. Cunningham (3.5x/3.7x/3.3x): 6/20 = 30%, avg 10.12
  - M. Siegrist (2.9x/3.3x): 4/20 = 20%, avg 8.71
  - D. Malonga (4.3x/3.7x): 4/20 = 20%, avg 9.66

### Outcome Classification

**(A) Correctly priced** (14 players):
  - C. Gray (LVA, 1.1x, 199 drafts) = 4.44 -- High-draft player delivered as expected
  - J. Quinerly (DAL, 2.6x, 1 drafts) = 2.82 -- Outcome roughly matched draft position and signals
  - C. Zandalasini (GSV, 1.2x, 106 drafts) = 4.06 -- High-draft player delivered as expected
  - S. Diggins (CHI, 0.5x, 153 drafts) = 5.16 -- High-draft player delivered as expected
  - E. Williams (CHI, 1.5x, 23 drafts) = 3.27 -- Mid-draft player with mid outcome -- no edge either way
  - S. Cunningham (IND, 1.9x, 46 drafts) = 2.92 -- Mid-draft player with mid outcome -- no edge either way
  - A. Wilson (LVA, 0.0x, 3600 drafts) = 5.4 -- High-draft player delivered as expected
  - D. Malonga (SEA, 2.3x, 12 drafts) = 2.51 -- Mid-draft player with mid outcome -- no edge either way
  - K. Plum (LAS, 0.2x, 339 drafts) = 4.85 -- High-draft player delivered as expected
  - P. Bueckers (DAL, 0.2x, 355 drafts) = 4.79 -- High-draft player delivered as expected
  - D. Hamby (LAS, 0.2x, 210 drafts) = 4.64 -- High-draft player delivered as expected
  - B. Jones (ATL, 0.7x, 142 drafts) = 3.6 -- High-draft player delivered as expected
  - M. Hines-Allen (IND, 2.0x, 9 drafts) = 2.43 -- Outcome roughly matched draft position and signals
  - M. Siegrist (DAL, 1.5x, 11 drafts) = 2.72 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (5 players):
  - J. Allemand (TOR, 1.6x, 9 drafts) = 5.04 -- Above-expectation outcome, ambiguous whether knowable
  - E. Engstler (POR, 3.0x, 3 drafts) = 3.26 -- High-boost low-draft player who overperformed
  - S. Sabally (NYL, 0.5x, 34 drafts) = 5.38 -- Above-expectation outcome, ambiguous whether knowable
  - I. Rupert (GSV, 2.1x, 1 drafts) = 3.12 -- Above-expectation outcome, ambiguous whether knowable
  - J. Salaün (GSV, 1.4x, 6 drafts) = 3.15 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 5 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-16

**Players**: 18 HV
 | **Score range**: 0.00 -- 4.39 (median 2.39)

**Leaderboard**: top score 43.70, floor 40.37, median 41.08

**Winner** (score 43.70):
  - C. Williams (2.4x) = 10.53
  - J. Shepard (3.4000000000000004x) = 11.99
  - A. Smith (2.2x) = 7.79
  - N. Hiedeman (3.4x) = 8.33
  - K. McBride (1.9x) = 5.05
  - **Game stack**: team 5: 2 players, team 12: 2 players

**Field ownership** (top-20 entries):
  - J. Shepard (3x/3.6x/2.8x/3.2x/3.4x): 20/20 = 100%, avg 11.32
  - C. Williams (1.6x/2.4x/2x/1.8x/2.2x): 15/20 = 75%, avg 9.48
  - A. Smith (2.6x/2.4x/2x/1.8x/2.2x): 15/20 = 75%, avg 8.36
  - N. Hiedeman (3.2x/3.4x/3.8x/3.6x): 15/20 = 75%, avg 8.24
  - K. McBride (1.9x/2.3x/2.7x/2.1x/2.5x): 10/20 = 50%, avg 6.06
  - L. Fiebich (3.5x/2.9x/3.1x): 8/20 = 40%, avg 7.76
  - J. Jones (2.1x/2.3x/2.5x): 5/20 = 25%, avg 5.83
  - M. Johannes (3.7x/3.9x): 3/20 = 15%, avg 4.85

### Outcome Classification

**(A) Correctly priced** (18 players):
  - J. Shepard (DAL, 1.6x, 98 drafts) = 3.53 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.4x, 498 drafts) = 4.39 -- High-draft player delivered as expected
  - N. Hiedeman (SEA, 2.0x, 63 drafts) = 2.45 -- Outcome roughly matched draft position and signals
  - A. Smith (DAL, 0.6x, 391 drafts) = 3.54 -- High-draft player delivered as expected
  - L. Fiebich (NYL, 1.5x, 81 drafts) = 2.48 -- Outcome roughly matched draft position and signals
  - N. Cloud (CHI, 0.8x, 175 drafts) = 2.58 -- Outcome roughly matched draft position and signals
  - K. McBride (MIN, 0.7x, 273 drafts) = 2.66 -- Outcome roughly matched draft position and signals
  - K. Burke (CON, 1.9x, 62 drafts) = 1.77 -- Outcome roughly matched draft position and signals
  - J. Jones (NYL, 0.5x, 528 drafts) = 2.58 -- Outcome roughly matched draft position and signals
  - M. Johannes (NYL, 2.5x, 67 drafts) = 1.29 -- High-draft player underperformed -- field took the loss equally
  - S. Ionescu (NYL, 0.2x, 2200 drafts) = 2.39 -- Outcome roughly matched draft position and signals
  - M. Kliundikova (TOR, 3.0x, 60 drafts) = 0.91 -- High-draft player underperformed -- field took the loss equally
  - D. Carrington (CHI, 1.4x, 199 drafts) = 0.86 -- High-draft player underperformed -- field took the loss equally
  - B. Carleton (POR, 1.8x, 87 drafts) = 0.74 -- High-draft player underperformed -- field took the loss equally
  - N. Collier (MIN, 0.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - S. Talbot (LVA, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - R. Gardner (NYL, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - B. Stewart (NYL, 0.2x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-08-17

**Players**: 19 HV
 | **Score range**: 2.48 -- 6.88 (median 4.16)

**Leaderboard**: top score 64.33, floor 56.52, median 56.52

**Winner** (score 64.33):
  - A. Wilson (2x) = 13.77
  - M. Siegrist (3.2x) = 17.65
  - K. Bell (4.6x) = 18.41
  - M. Caldwell (3.6999999999999997x) = 7.09
  - E. Engstler (4.1x) = 7.41
  - **Game stack**: team 1: 2 players

**Field ownership** (top-20 entries):
  - A. Wilson (2x): 20/20 = 100%, avg 13.77
  - M. Siegrist (3.2x/3x): 20/20 = 100%, avg 17.54
  - E. Engstler (4.3x/4.1x): 20/20 = 100%, avg 7.44
  - M. Caldwell (3.7x/3.9x): 19/20 = 95%, avg 7.13
  - A. Morrow (3.7x): 15/20 = 75%, avg 10.60
  - C. Gray (2.8x/2.2x): 2/20 = 10%, avg 11.58
  - K. Bell (4.6x): 1/20 = 5%, avg 18.41
  - A. Clark (4.2x): 1/20 = 5%, avg 13.26

### Outcome Classification

**(A) Correctly priced** (14 players):
  - K. Bell (LVA, 3.0x, 18 drafts) = 4.0 -- Mid-draft player with mid outcome -- no edge either way
  - C. Gray (LVA, 1.0x, 105 drafts) = 4.63 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 3300 drafts) = 6.88 -- High-draft player delivered as expected
  - J. Melbourne (SEA, 3.0x, 2 drafts) = 2.6 -- Outcome roughly matched draft position and signals
  - K. Mitchell (IND, 0.4x, 130 drafts) = 5.31 -- High-draft player delivered as expected
  - D. Hamby (LAS, 0.2x, 189 drafts) = 5.79 -- High-draft player delivered as expected
  - T. Paopao (ATL, 3.0x, 21 drafts) = 2.48 -- Mid-draft player with mid outcome -- no edge either way
  - A. Morrow (CON, 2.1x, 3 drafts) = 2.87 -- Outcome roughly matched draft position and signals
  - S. Rivers (CON, 1.4x, 11 drafts) = 3.44 -- Mid-draft player with mid outcome -- no edge either way
  - S. Citron (WAS, 0.7x, 161 drafts) = 4.16 -- High-draft player delivered as expected
  - K. Plum (LAS, 0.2x, 274 drafts) = 5.0 -- High-draft player delivered as expected
  - N. Smith (LVA, 2.1x, 4 drafts) = 2.51 -- Outcome roughly matched draft position and signals
  - A. Thomas (PHO, 0.0x, 567 drafts) = 5.09 -- High-draft player delivered as expected
  - N. Ogwumike (LAS, 0.3x, 179 drafts) = 4.28 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (5 players):
  - M. Siegrist (DAL, 1.4x, 20 drafts) = 5.52 -- Above-expectation outcome, ambiguous whether knowable
  - A. Clark (DAL, 3.0x, 1 drafts) = 3.16 -- High-boost low-draft player who overperformed
  - L. Lacan (CON, 1.2x, 1 drafts) = 4.44 -- Above-expectation outcome, ambiguous whether knowable
  - M. Mabrey (TOR, 1.1x, 5 drafts) = 3.51 -- Above-expectation outcome, ambiguous whether knowable
  - O. Sims (DAL, 1.4x, 1 drafts) = 3.08 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 5 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-19

**Players**: 20 HV
 | **Score range**: 2.25 -- 7.61 (median 3.57)

**Leaderboard**: top score 60.19, floor 53.18, median 54.64

**Winner** (score 60.19):
  - A. Wilson (2x) = 15.22
  - B. Griner (3.4000000000000004x) = 13.75
  - D. Malonga (3.9x) = 11.64
  - E. Engstler (4.199999999999999x) = 7.31
  - K. Martin (4.2x) = 12.27

**Field ownership** (top-20 entries):
  - A. Wilson (2x/1.4x): 20/20 = 100%, avg 14.53
  - V. Burton (2.4x/2x/2.2x): 13/20 = 65%, avg 14.74
  - B. Griner (3.4x/3x/2.8x): 7/20 = 35%, avg 12.48
  - S. Ionescu (1.8x/2x/2.2x): 7/20 = 35%, avg 9.03
  - S. Diggins (1.6x/1.8x/2x/2.2x): 6/20 = 30%, avg 9.54
  - C. Gray (2.8x/2.2x/2.6x): 6/20 = 30%, avg 8.44
  - D. Malonga (3.5x/3.9x): 5/20 = 25%, avg 10.69
  - K. Martin (4.4x/4.6x/4.2x): 4/20 = 20%, avg 13.00

### Outcome Classification

**(A) Correctly priced** (14 players):
  - V. Burton (GSV, 0.6x, 183 drafts) = 6.65 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 4100 drafts) = 7.61 -- High-draft player delivered as expected
  - K. Martin (LAS, 3.0x, 4 drafts) = 2.92 -- Outcome roughly matched draft position and signals
  - B. Griner (CON, 1.6x, 16 drafts) = 4.04 -- Mid-draft player with mid outcome -- no edge either way
  - D. Malonga (SEA, 2.3x, 6 drafts) = 2.99 -- Outcome roughly matched draft position and signals
  - S. Diggins (CHI, 0.4x, 142 drafts) = 4.85 -- High-draft player delivered as expected
  - J. Jones (NYL, 0.5x, 21 drafts) = 4.63 -- Mid-draft player with mid outcome -- no edge either way
  - K. Nurse (TOR, 3.0x, 1 drafts) = 2.28 -- Outcome roughly matched draft position and signals
  - A. Edwards (CON, 3.0x, 1 drafts) = 2.26 -- Outcome roughly matched draft position and signals
  - M. Kliundikova (TOR, 3.0x, 1 drafts) = 2.25 -- Outcome roughly matched draft position and signals
  - C. Gray (LVA, 1.0x, 188 drafts) = 3.56 -- High-draft player delivered as expected
  - S. Ionescu (NYL, 0.2x, 498 drafts) = 4.45 -- High-draft player delivered as expected
  - L. Fiebich (NYL, 1.5x, 5 drafts) = 2.77 -- Outcome roughly matched draft position and signals
  - N. Ogwumike (LAS, 0.0x, 220 drafts) = 4.08 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (6 players):
  - C. Leite (POR, 2.9x, 8 drafts) = 3.2 -- Above-expectation outcome, ambiguous whether knowable
  - E. Williams (CHI, 1.5x, 3 drafts) = 3.6 -- Above-expectation outcome, ambiguous whether knowable
  - N. Mack (PHO, 1.9x, 1 drafts) = 3.56 -- Above-expectation outcome, ambiguous whether knowable
  - O. Nelson-Ododa (CON, 1.4x, 2 drafts) = 3.57 -- Above-expectation outcome, ambiguous whether knowable
  - K. Copper (PHO, 1.1x, 8 drafts) = 3.82 -- Above-expectation outcome, ambiguous whether knowable
  - A. Atkins (LAS, 0.9x, 1 drafts) = 3.24 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 6 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-20

**Players**: 17 HV
 | **Score range**: -0.22 -- 9.85 (median 1.81)

**Leaderboard**: top score 61.27, floor 55.19, median 57.65

**Winner** (score 61.27):
  - G. Berger (5x) = 17.76
  - P. Bueckers (2x) = 19.70
  - R. Jackson (2.6x) = 11.12
  - M. Siegrist (2.5999999999999996x) = 7.00
  - J. Allemand (2.7x) = 5.68
  - **Game stack**: team 12: 2 players

**Field ownership** (top-20 entries):
  - P. Bueckers (2x/2.2x): 20/20 = 100%, avg 21.28
  - G. Berger (4.4x/5x/4.2x/4.8x): 17/20 = 85%, avg 15.30
  - R. Jackson (2.4x/2.8x/2.6x): 13/20 = 65%, avg 11.12
  - M. Siegrist (2.4x/2.8x/3x/2.6x): 13/20 = 65%, avg 7.54
  - L. Geiselsöder (3.1x/3.7x/3.5x/3.3x): 9/20 = 45%, avg 8.47
  - J. Allemand (2.9x/2.7x/3.3x): 7/20 = 35%, avg 6.10
  - K. Plum (2x/2.2x): 5/20 = 25%, avg 6.66
  - H. Jones (4x/4.2x): 4/20 = 20%, avg 3.12

### Outcome Classification

**(A) Correctly priced** (17 players):
  - P. Bueckers (DAL, 0.2x, 2000 drafts) = 9.85 -- High-draft player delivered as expected
  - R. Jackson (CHI, 1.0x, 299 drafts) = 4.28 -- High-draft player delivered as expected
  - L. Geiselsöder (POR, 1.9x, 102 drafts) = 2.55 -- Outcome roughly matched draft position and signals
  - M. Siegrist (DAL, 1.2x, 227 drafts) = 2.69 -- Outcome roughly matched draft position and signals
  - C. Brink (LAS, 2.2x, 297 drafts) = 1.81 -- Outcome roughly matched draft position and signals
  - J. Allemand (TOR, 1.5x, 148 drafts) = 2.1 -- Outcome roughly matched draft position and signals
  - K. Plum (LAS, 0.2x, 1800 drafts) = 3.2 -- High-draft player delivered as expected
  - R. Burrell (LAS, 2.8x, 79 drafts) = 1.13 -- High-draft player underperformed -- field took the loss equally
  - D. Hamby (LAS, 0.2x, 1700 drafts) = 2.45 -- Outcome roughly matched draft position and signals
  - A. Stevens (CHI, 0.4x, 268 drafts) = 2.23 -- Outcome roughly matched draft position and signals
  - J. Quinerly (DAL, 2.5x, 85 drafts) = 0.85 -- High-draft player underperformed -- field took the loss equally
  - A. James (DAL, 2.3x, 14 drafts) = 0.71 -- Mid-draft player with mid outcome -- no edge either way
  - M. Hines-Allen (IND, 1.9x, 106 drafts) = 0.3 -- High-draft player underperformed -- field took the loss equally
  - D. Miller (CON, 3.0x, None drafts) = -0.22 -- Low-draft player correctly faded by the field
  - S. Barker (POR, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - E. Cannon (LAS, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - A. Ogunbowale (DAL, 0.7x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-08-21

**Players**: 19 HV
 | **Score range**: 1.80 -- 5.97 (median 2.97)

**Leaderboard**: top score 51.69, floor 45.78, median 47.48

**Winner** (score 51.69):
  - A. Gray (2.3x) = 12.94
  - K. McBride (2.6x) = 7.43
  - A. Wilson (1.6x) = 6.39
  - K. Cardoso (2.2x) = 13.13
  - J. Shepard (2.7x) = 11.81

**Field ownership** (top-20 entries):
  - K. Cardoso (2.4x/2.8x/2.2x/2.6x): 14/20 = 70%, avg 13.98
  - A. Gray (1.9x/2.1x/1.7x/2.3x): 10/20 = 50%, avg 11.93
  - A. Wilson (1.6x/1.8x/2x): 10/20 = 50%, avg 7.35
  - J. Jones (2.1x/1.7x/2.3x/2.5x): 9/20 = 45%, avg 11.16
  - J. Shepard (3.3x/2.9x/3.5x/2.7x): 8/20 = 40%, avg 13.01
  - K. McBride (2.8x/2.2x/2.6x): 5/20 = 25%, avg 7.31
  - T. Charles (2.4x/2x/2.6x): 5/20 = 25%, avg 9.29
  - A. Smith (2.4x/2x/2.2x/2.6x): 4/20 = 20%, avg 6.49

### Outcome Classification

**(A) Correctly priced** (16 players):
  - B. Carleton (POR, 1.9x, 17 drafts) = 3.98 -- Mid-draft player with mid outcome -- no edge either way
  - J. Shepard (DAL, 1.5x, 11 drafts) = 4.37 -- Mid-draft player with mid outcome -- no edge either way
  - D. Evans (LVA, 2.9x, 13 drafts) = 3.03 -- Mid-draft player with mid outcome -- no edge either way
  - A. Gray (ATL, 0.3x, 169 drafts) = 5.63 -- High-draft player delivered as expected
  - N. Smith (LVA, 2.1x, 28 drafts) = 2.43 -- Mid-draft player with mid outcome -- no edge either way
  - T. Paopao (ATL, 2.8x, 4 drafts) = 1.93 -- Outcome roughly matched draft position and signals
  - M. Johannes (NYL, 2.6x, 3 drafts) = 2.0 -- Outcome roughly matched draft position and signals
  - K. Bell (LVA, 3.0x, 11 drafts) = 1.8 -- Mid-draft player with mid outcome -- no edge either way
  - A. Reese (ATL, 0.5x, 96 drafts) = 3.58 -- High-draft player delivered as expected
  - N. Cloud (CHI, 0.9x, 120 drafts) = 2.97 -- Outcome roughly matched draft position and signals
  - K. McBride (MIN, 0.8x, 123 drafts) = 2.86 -- Outcome roughly matched draft position and signals
  - A. Wilson (LVA, 0.0x, 4000 drafts) = 3.99 -- High-draft player delivered as expected
  - M. Onyenwere (WAS, 3.0x, 2 drafts) = 1.9 -- Outcome roughly matched draft position and signals
  - O. Nelson-Ododa (CON, 1.3x, 6 drafts) = 2.38 -- Outcome roughly matched draft position and signals
  - B. Jones (ATL, 0.7x, 96 drafts) = 2.89 -- Outcome roughly matched draft position and signals
  - C. Gray (LVA, 0.9x, 167 drafts) = 2.65 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (3 players):
  - K. Cardoso (CHI, 0.8x, 13 drafts) = 5.97 -- Above-expectation outcome, ambiguous whether knowable
  - J. Jones (NYL, 0.5x, 24 drafts) = 5.67 -- Above-expectation outcome, ambiguous whether knowable
  - A. Atkins (LAS, 0.9x, 1 drafts) = 4.19 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 3 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-22

**Players**: 19 HV
 | **Score range**: 1.65 -- 7.32 (median 2.91)

**Leaderboard**: top score 75.53, floor 64.14, median 68.13

**Winner** (score 75.53):
  - P. Bueckers (2.1x) = 3.07
  - J. Shepard (3.2x) = 23.43
  - K. McBride (2.4000000000000004x) = 15.02
  - L. Hull (3.4x) = 15.44
  - D. Malonga (3.4000000000000004x) = 18.56
  - **Game stack**: team 12: 2 players

**Field ownership** (top-20 entries):
  - J. Shepard (3x/2.8x/2.9x/3.2x/3.4x/3.3x): 20/20 = 100%, avg 22.55
  - D. Malonga (3.4x/4x/4.2x/3.6x): 16/20 = 80%, avg 20.00
  - L. Hull (3.2x/3.4x/3.6x): 12/20 = 60%, avg 15.52
  - K. McBride (2.4x/2x/2.6x/2.8x): 7/20 = 35%, avg 15.56
  - P. Bueckers (1.9x/2.1x): 5/20 = 25%, avg 3.01
  - A. Thomas (2x): 5/20 = 25%, avg 11.00
  - K. Mitchell (2.4x/2.2x): 4/20 = 20%, avg 8.70
  - V. Burton (2.4x/2x/2.2x): 4/20 = 20%, avg 7.48

### Outcome Classification

**(A) Correctly priced** (18 players):
  - J. Shepard (DAL, 1.4x, 117 drafts) = 7.32 -- High-draft player delivered as expected
  - L. Hull (IND, 2.0x, 20 drafts) = 4.54 -- Mid-draft player with mid outcome -- no edge either way
  - K. McBride (MIN, 0.8x, 120 drafts) = 6.26 -- High-draft player delivered as expected
  - E. Wheeler (LAS, 1.3x, 85 drafts) = 4.07 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.0x, 1900 drafts) = 5.5 -- High-draft player delivered as expected
  - D. Bonner (PHO, 1.6x, 41 drafts) = 2.91 -- Mid-draft player with mid outcome -- no edge either way
  - K. Charles (GSV, 3.0x, 2 drafts) = 2.12 -- Outcome roughly matched draft position and signals
  - M. Akoa Makani (PHO, 2.0x, 29 drafts) = 2.33 -- Mid-draft player with mid outcome -- no edge either way
  - N. Hiedeman (SEA, 2.0x, 10 drafts) = 2.4 -- Mid-draft player with mid outcome -- no edge either way
  - K. Mitchell (IND, 0.4x, 319 drafts) = 3.7 -- High-draft player delivered as expected
  - J. Salaün (GSV, 1.4x, 32 drafts) = 2.57 -- Mid-draft player with mid outcome -- no edge either way
  - V. Burton (GSV, 0.6x, 341 drafts) = 3.32 -- High-draft player delivered as expected
  - I. Rupert (GSV, 2.0x, 2 drafts) = 2.18 -- Outcome roughly matched draft position and signals
  - K. Martin (LAS, 3.0x, 48 drafts) = 1.65 -- Mid-draft player with mid outcome -- no edge either way
  - A. Boston (IND, 0.2x, 295 drafts) = 3.36 -- High-draft player delivered as expected
  - B. Carleton (POR, 1.8x, 7 drafts) = 1.77 -- Outcome roughly matched draft position and signals
  - L. Amihere (GSV, 2.0x, 39 drafts) = 1.65 -- Mid-draft player with mid outcome -- no edge either way
  - A. Smith (DAL, 0.6x, 136 drafts) = 2.54 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - D. Malonga (SEA, 2.2x, 25 drafts) = 5.46 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-23

**Players**: 18 HV
 | **Score range**: 1.66 -- 6.54 (median 3.30)

**Leaderboard**: top score 59.55, floor 52.39, median 53.65

**Winner** (score 59.55):
  - A. Wilson (2x) = 13.09
  - T. Charles (2.6x) = 9.83
  - S. Rivers (3x) = 10.84
  - D. Evans (4.1x) = 19.73
  - E. Engstler (4x) = 6.06
  - **Game stack**: team 1: 2 players

**Field ownership** (top-20 entries):
  - A. Wilson (1.6x/1.8x/2x): 18/20 = 90%, avg 12.72
  - D. Evans (4.3x/4.1x/3.9x): 17/20 = 85%, avg 19.22
  - S. Rivers (3.2x/3x/2.8x): 7/20 = 35%, avg 11.05
  - J. Young (2.4x/1.8x/2.2x): 6/20 = 30%, avg 7.25
  - T. Charles (2.4x/2.2x/2.6x): 5/20 = 25%, avg 9.38
  - J. Loyd (2.4x/2.8x/2.6x): 5/20 = 25%, avg 6.27
  - C. Gray (2.9x/2.3x/2.5x/2.7x): 4/20 = 20%, avg 7.59
  - A. Gray (1.6x/1.8x/2x/2.2x): 4/20 = 20%, avg 6.20

### Outcome Classification

**(A) Correctly priced** (17 players):
  - M. Mabrey (TOR, 1.0x, 58 drafts) = 5.35 -- High-draft player delivered as expected
  - K. Nurse (TOR, 3.0x, 12 drafts) = 3.16 -- Mid-draft player with mid outcome -- no edge either way
  - A. Wilson (LVA, 0.0x, 3400 drafts) = 6.54 -- High-draft player delivered as expected
  - S. Rivers (CON, 1.4x, 49 drafts) = 3.61 -- Mid-draft player with mid outcome -- no edge either way
  - B. Jones (ATL, 0.7x, 107 drafts) = 3.94 -- High-draft player delivered as expected
  - K. Iriafen (WAS, 0.9x, 169 drafts) = 3.5 -- High-draft player delivered as expected
  - S. Austin (WAS, 0.9x, 108 drafts) = 3.42 -- High-draft player delivered as expected
  - T. Paopao (ATL, 2.8x, 5 drafts) = 1.97 -- Outcome roughly matched draft position and signals
  - N. Hillmon (ATL, 1.3x, 66 drafts) = 2.77 -- Outcome roughly matched draft position and signals
  - K. Burke (CON, 1.9x, 1 drafts) = 2.19 -- Outcome roughly matched draft position and signals
  - C. Gray (LVA, 0.9x, 141 drafts) = 2.92 -- Outcome roughly matched draft position and signals
  - M. Caldwell (MIN, 2.3x, 2 drafts) = 1.99 -- Outcome roughly matched draft position and signals
  - R. Howard (ATL, 0.3x, 139 drafts) = 3.54 -- High-draft player delivered as expected
  - A. Reese (ATL, 0.5x, 293 drafts) = 3.21 -- High-draft player delivered as expected
  - J. Young (LVA, 0.4x, 203 drafts) = 3.3 -- High-draft player delivered as expected
  - J. Loyd (LVA, 1.2x, 98 drafts) = 2.37 -- Outcome roughly matched draft position and signals
  - M. Johannes (NYL, 2.5x, 11 drafts) = 1.66 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (1 players):
  - D. Evans (LVA, 2.7x, 2 drafts) = 4.81 -- High-boost low-draft player who overperformed

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-24

**Players**: 16 HV
 | **Score range**: 2.20 -- 8.16 (median 3.78)

**Leaderboard**: top score 64.48, floor 58.06, median 59.15

**Winner** (score 64.48):
  - N. Ogwumike (2.3x) = 18.76
  - V. Burton (2.4x) = 15.31
  - S. Austin (2.5x) = 11.65
  - J. Salaün (2.8x) = 6.46
  - D. Malonga (3.0999999999999996x) = 12.30
  - **Game stack**: team 14: 2 players

**Field ownership** (top-20 entries):
  - V. Burton (2.6x/2.4x/2x/1.8x/2.2x): 19/20 = 95%, avg 14.23
  - N. Ogwumike (1.9x/2.1x/1.7x/2.3x): 18/20 = 90%, avg 17.40
  - D. Malonga (3.3x/3.1x): 8/20 = 40%, avg 12.60
  - S. Diggins (1.6x/2.4x/2x/2.2x): 8/20 = 40%, avg 11.78
  - C. Williams (1.9x/2.1x/2.3x): 7/20 = 35%, avg 9.92
  - N. Collier (1.6x/2x/1.4x): 6/20 = 30%, avg 11.24
  - S. Austin (2.1x/2.3x/2.5x): 4/20 = 20%, avg 10.49
  - J. Salaün (2.8x/3x/2.6x): 3/20 = 15%, avg 6.46

### Outcome Classification

**(A) Correctly priced** (15 players):
  - N. Ogwumike (LAS, 0.3x, 268 drafts) = 8.16 -- High-draft player delivered as expected
  - V. Burton (GSV, 0.6x, 301 drafts) = 6.38 -- High-draft player delivered as expected
  - D. Malonga (SEA, 1.9x, 58 drafts) = 3.97 -- High-draft player delivered as expected
  - M. Kliundikova (TOR, 3.0x, 20 drafts) = 2.88 -- Mid-draft player with mid outcome -- no edge either way
  - S. Dolson (SEA, 3.0x, 3 drafts) = 2.76 -- Outcome roughly matched draft position and signals
  - S. Austin (WAS, 0.9x, 98 drafts) = 4.66 -- High-draft player delivered as expected
  - S. Diggins (CHI, 0.4x, 154 drafts) = 5.54 -- High-draft player delivered as expected
  - K. Charles (GSV, 3.0x, 3 drafts) = 2.61 -- Outcome roughly matched draft position and signals
  - N. Collier (MIN, 0.0x, 480 drafts) = 6.13 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.5x, 278 drafts) = 4.79 -- High-draft player delivered as expected
  - M. Siegrist (DAL, 1.2x, 26 drafts) = 3.52 -- Mid-draft player with mid outcome -- no edge either way
  - K. Martin (LAS, 3.0x, 4 drafts) = 2.2 -- Outcome roughly matched draft position and signals
  - M. Hines-Allen (IND, 2.0x, 22 drafts) = 2.66 -- Mid-draft player with mid outcome -- no edge either way
  - A. Okonkwo (ATL, 3.0x, 2 drafts) = 2.51 -- Outcome roughly matched draft position and signals
  - K. Mitchell (IND, 0.4x, 631 drafts) = 3.78 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (1 players):
  - I. Rupert (GSV, 1.9x, 3 drafts) = 3.31 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-25

**Players**: 18 HV
 | **Score range**: 1.09 -- 6.96 (median 3.04)

**Leaderboard**: top score 55.08, floor 49.12, median 50.05

**Winner** (score 55.08):
  - J. Jones (2.5x) = 13.02
  - A. Atkins (2.7x) = 15.49
  - J. Young (2x) = 13.91
  - C. Gray (2.3x) = 5.50
  - A. Reese (1.7x) = 7.16
  - **Game stack**: team 1: 2 players

**Field ownership** (top-20 entries):
  - J. Young (2.4x/2x/2.2x/1.8x): 20/20 = 100%, avg 14.88
  - A. Atkins (2.3x/2.7x/2.9x/2.1x/2.5x): 14/20 = 70%, avg 13.94
  - A. Reese (1.9x/2.3x/2.1x/1.7x/2.5x): 13/20 = 65%, avg 9.29
  - A. Wilson (1.6x/1.2x/2x/1.8x): 12/20 = 60%, avg 6.05
  - K. Cardoso (1.9x/2.1x/2.3x/2.5x): 10/20 = 50%, avg 6.63
  - J. Jones (1.9x/2.3x/2.1x/1.7x/2.5x): 9/20 = 45%, avg 11.17
  - C. Gray (2.1x/2.3x/2.7x): 6/20 = 30%, avg 5.50
  - A. Morrow (3.2x/3.4x): 6/20 = 30%, avg 12.67

### Outcome Classification

**(A) Correctly priced** (15 players):
  - J. Young (LVA, 0.4x, 222 drafts) = 6.96 -- High-draft player delivered as expected
  - J. Jones (NYL, 0.5x, 208 drafts) = 5.21 -- High-draft player delivered as expected
  - A. Reese (ATL, 0.5x, 403 drafts) = 4.21 -- High-draft player delivered as expected
  - K. Burke (CON, 1.9x, 2 drafts) = 2.58 -- Outcome roughly matched draft position and signals
  - K. Cardoso (CHI, 0.7x, 159 drafts) = 3.1 -- High-draft player delivered as expected
  - M. Mabrey (TOR, 0.9x, 156 drafts) = 2.76 -- Outcome roughly matched draft position and signals
  - N. Smith (LVA, 2.1x, 88 drafts) = 1.87 -- Outcome roughly matched draft position and signals
  - C. Gray (LVA, 0.9x, 169 drafts) = 2.39 -- Outcome roughly matched draft position and signals
  - S. Ionescu (NYL, 0.2x, 236 drafts) = 3.04 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 4500 drafts) = 3.21 -- High-draft player delivered as expected
  - J. Loyd (LVA, 1.1x, 125 drafts) = 2.05 -- Outcome roughly matched draft position and signals
  - D. Evans (LVA, 2.5x, 21 drafts) = 1.28 -- Mid-draft player with mid outcome -- no edge either way
  - B. Stewart (NYL, 0.2x, 176 drafts) = 2.6 -- Outcome roughly matched draft position and signals
  - L. Fiebich (NYL, 1.5x, 74 drafts) = 1.4 -- High-draft player underperformed -- field took the loss equally
  - R. Banham (CHI, 2.1x, 104 drafts) = 1.09 -- High-draft player underperformed -- field took the loss equally

**(C) Unknowable / winners' edge** (3 players):
  - A. Atkins (LAS, 0.9x, 27 drafts) = 5.74 -- Above-expectation outcome, ambiguous whether knowable
  - A. Morrow (CON, 2.0x, 9 drafts) = 3.92 -- Above-expectation outcome, ambiguous whether knowable
  - L. Lacan (CON, 1.1x, 2 drafts) = 3.31 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 3 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-26

**Players**: 19 HV
 | **Score range**: 1.18 -- 5.52 (median 2.74)

**Leaderboard**: top score 46.74, floor 43.69, median 45.07

**Winner** (score 46.74):
  - A. Thomas (2x) = 11.04
  - D. Hamby (2x) = 9.62
  - R. Jackson (2.5x) = 7.71
  - S. Sabally (1.9x) = 6.39
  - S. Whitcomb (3x) = 11.99
  - **Game stack**: team 6: 2 players

**Field ownership** (top-20 entries):
  - S. Whitcomb (3.2x/3x/3.6x/3.4x): 20/20 = 100%, avg 12.83
  - A. Thomas (1.6x/1.2x/2x): 14/20 = 70%, avg 9.94
  - D. Hamby (1.6x/1.8x/2x/2.2x): 13/20 = 65%, avg 9.39
  - R. Jackson (2.3x/2.7x/2.9x/2.1x/2.5x): 13/20 = 65%, avg 7.47
  - S. Sabally (1.9x/2.1x/2.3x): 9/20 = 45%, avg 7.06
  - D. Bonner (3.2x/2.8x/3x/3.6x): 7/20 = 35%, avg 9.10
  - A. Boston (1.8x/2x/2.2x/1.4x): 6/20 = 30%, avg 9.47
  - K. Plum (1.8x/2x/1.4x): 5/20 = 25%, avg 5.17

### Outcome Classification

**(A) Correctly priced** (18 players):
  - S. Whitcomb (PHO, 1.8x, 106 drafts) = 4.0 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.0x, 2700 drafts) = 5.52 -- High-draft player delivered as expected
  - A. Boston (IND, 0.2x, 431 drafts) = 4.99 -- High-draft player delivered as expected
  - D. Hamby (LAS, 0.2x, 437 drafts) = 4.81 -- High-draft player delivered as expected
  - D. Bonner (PHO, 1.6x, 33 drafts) = 2.87 -- Mid-draft player with mid outcome -- no edge either way
  - R. Jackson (CHI, 0.9x, 229 drafts) = 3.08 -- High-draft player delivered as expected
  - S. Sabally (NYL, 0.5x, 192 drafts) = 3.36 -- High-draft player delivered as expected
  - N. Howard (MIN, 1.0x, 104 drafts) = 2.67 -- Outcome roughly matched draft position and signals
  - D. Malonga (SEA, 1.8x, 187 drafts) = 1.81 -- Outcome roughly matched draft position and signals
  - K. Mitchell (IND, 0.4x, 431 drafts) = 2.74 -- Outcome roughly matched draft position and signals
  - K. Plum (LAS, 0.2x, 841 drafts) = 2.81 -- Outcome roughly matched draft position and signals
  - L. Hull (IND, 1.8x, 144 drafts) = 1.59 -- Outcome roughly matched draft position and signals
  - B. Turner (LVA, 3.0x, 1 drafts) = 1.21 -- Low-draft player correctly faded by the field
  - R. Burrell (LAS, 2.8x, 21 drafts) = 1.18 -- Mid-draft player with mid outcome -- no edge either way
  - N. Mack (PHO, 1.8x, 15 drafts) = 1.47 -- Mid-draft player with mid outcome -- no edge either way
  - E. Magbegor (SEA, 0.9x, 84 drafts) = 1.86 -- Outcome roughly matched draft position and signals
  - N. Ogwumike (LAS, 0.3x, 568 drafts) = 2.35 -- Outcome roughly matched draft position and signals
  - K. Copper (PHO, 1.1x, 51 drafts) = 1.73 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - O. Sims (DAL, 1.5x, 3 drafts) = 4.19 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-27

**Players**: 16 HV
 | **Score range**: 1.26 -- 6.60 (median 3.20)

**Leaderboard**: top score 62.23, floor 54.97, median 56.12

**Winner** (score 62.23):
  - H. Jones (4.6x) = 13.78
  - G. Berger (4.1x) = 10.79
  - M. Hines-Allen (3.6x) = 11.46
  - A. Okonkwo (3.5x) = 9.25
  - A. James (3.7x) = 16.95
  - **Game stack**: team None: 2 players

**Field ownership** (top-20 entries):
  - A. James (4.3x/4.1x/3.7x/3.9x): 16/20 = 80%, avg 17.70
  - A. Wilson (1.6x/2x): 14/20 = 70%, avg 13.01
  - L. Lacan (3x/2.8x/2.6x/2.4x/2.2x): 13/20 = 65%, avg 13.86
  - A. Morrow (3.5x/3.7x/3.3x/3.1x): 9/20 = 45%, avg 11.14
  - H. Jones (4x/3.8x/4.6x/4.2x): 8/20 = 40%, avg 12.06
  - G. Berger (4.1x/3.5x/4.3x/3.7x/3.9x): 6/20 = 30%, avg 10.18
  - N. Hillmon (2.9x/3.1x/2.7x/3.3x): 6/20 = 30%, avg 9.80
  - M. Siegrist (2.9x/2.7x/3.1x): 4/20 = 20%, avg 6.20

### Outcome Classification

**(A) Correctly priced** (15 players):
  - A. James (DAL, 2.5x, 11 drafts) = 4.58 -- Mid-draft player with mid outcome -- no edge either way
  - A. Wilson (LVA, 0.0x, 3900 drafts) = 6.6 -- High-draft player delivered as expected
  - M. Hines-Allen (IND, 2.0x, 89 drafts) = 3.18 -- High-draft player delivered as expected
  - A. Morrow (CON, 1.9x, 113 drafts) = 3.2 -- High-draft player delivered as expected
  - B. Jones (ATL, 0.6x, 159 drafts) = 4.43 -- High-draft player delivered as expected
  - N. Hillmon (ATL, 1.3x, 102 drafts) = 3.3 -- High-draft player delivered as expected
  - A. Okonkwo (ATL, 2.1x, 3 drafts) = 2.64 -- Outcome roughly matched draft position and signals
  - R. Howard (ATL, 0.3x, 205 drafts) = 3.94 -- High-draft player delivered as expected
  - J. Young (LVA, 0.3x, 255 drafts) = 3.77 -- High-draft player delivered as expected
  - C. Gray (LVA, 0.9x, 178 drafts) = 2.84 -- Outcome roughly matched draft position and signals
  - M. Mabrey (TOR, 0.9x, 166 drafts) = 2.81 -- Outcome roughly matched draft position and signals
  - J. Loyd (LVA, 1.2x, 89 drafts) = 2.25 -- Outcome roughly matched draft position and signals
  - K. Bell (LVA, 3.0x, 3 drafts) = 1.37 -- Low-draft player correctly faded by the field
  - M. Siegrist (DAL, 1.1x, 85 drafts) = 2.14 -- Outcome roughly matched draft position and signals
  - M. Caldwell (MIN, 2.3x, 1 drafts) = 1.26 -- Low-draft player correctly faded by the field

**(C) Unknowable / winners' edge** (1 players):
  - L. Lacan (CON, 1.0x, 27 drafts) = 5.39 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-28

**Players**: 19 HV
 | **Score range**: 1.69 -- 5.11 (median 3.21)

**Leaderboard**: top score 53.41, floor 48.43, median 49.99

**Winner** (score 53.41):
  - A. Reese (2.4x) = 9.96
  - K. Cardoso (2.5x) = 7.73
  - D. Malonga (3.4000000000000004x) = 10.82
  - M. Johannes (4x) = 10.38
  - S. Talbot (4.2x) = 14.52

**Field ownership** (top-20 entries):
  - K. Copper (2.9x/3.1x/2.5x/2.7x): 11/20 = 55%, avg 12.65
  - N. Mack (3.2x/3.4x/3x/3.6x): 11/20 = 55%, avg 15.21
  - A. Reese (1.6x/2.4x/2.2x): 9/20 = 45%, avg 9.31
  - A. Thomas (1.8x/2x/1.4x): 9/20 = 45%, avg 7.58
  - D. Malonga (3x/3.6x/3.2x/3.8x/3.4x): 8/20 = 40%, avg 10.82
  - K. Nurse (4.4x/4.2x/4.8x): 8/20 = 40%, avg 14.27
  - D. Bonner (2.9x/3.1x/3.3x): 5/20 = 25%, avg 7.70
  - M. Johannes (4x/3.8x): 4/20 = 20%, avg 10.12

### Outcome Classification

**(A) Correctly priced** (17 players):
  - N. Mack (PHO, 1.8x, 17 drafts) = 4.73 -- Mid-draft player with mid outcome -- no edge either way
  - K. Nurse (TOR, 3.0x, 12 drafts) = 3.21 -- Mid-draft player with mid outcome -- no edge either way
  - K. Copper (PHO, 1.1x, 37 drafts) = 4.68 -- Mid-draft player with mid outcome -- no edge either way
  - C. Williams (MIN, 0.4x, 161 drafts) = 5.11 -- High-draft player delivered as expected
  - D. Malonga (SEA, 1.8x, 25 drafts) = 3.18 -- Mid-draft player with mid outcome -- no edge either way
  - M. Johannes (NYL, 2.6x, 6 drafts) = 2.6 -- Outcome roughly matched draft position and signals
  - S. Diggins (CHI, 0.4x, 138 drafts) = 4.9 -- High-draft player delivered as expected
  - S. Citron (WAS, 0.8x, 159 drafts) = 3.64 -- High-draft player delivered as expected
  - A. Reese (ATL, 0.4x, 445 drafts) = 4.15 -- High-draft player delivered as expected
  - K. McBride (MIN, 0.7x, 141 drafts) = 3.56 -- High-draft player delivered as expected
  - E. Wheeler (LAS, 1.3x, 72 drafts) = 2.76 -- Outcome roughly matched draft position and signals
  - K. Iriafen (WAS, 0.9x, 123 drafts) = 3.08 -- High-draft player delivered as expected
  - D. Bonner (PHO, 1.5x, 22 drafts) = 2.52 -- Mid-draft player with mid outcome -- no edge either way
  - E. Magbegor (SEA, 1.0x, 96 drafts) = 2.93 -- Outcome roughly matched draft position and signals
  - A. Clark (DAL, 3.0x, 4 drafts) = 1.69 -- Outcome roughly matched draft position and signals
  - K. Cardoso (CHI, 0.7x, 181 drafts) = 3.09 -- High-draft player delivered as expected
  - G. Williams (GSV, 0.6x, 107 drafts) = 3.06 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (2 players):
  - S. Talbot (LVA, 3.0x, 2 drafts) = 3.46 -- High-boost low-draft player who overperformed
  - I. Harrison (TOR, 2.8x, 2 drafts) = 3.33 -- High-boost low-draft player who overperformed

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-29

**Players**: 18 HV
 | **Score range**: 1.26 -- 6.35 (median 2.90)

**Leaderboard**: top score 63.84, floor 57.77, median 60.56

**Winner** (score 63.84):
  - A. Stevens (2.5x) = 12.73
  - M. Siegrist (2.9000000000000004x) = 13.12
  - O. Sims (2.9000000000000004x) = 11.88
  - G. Berger (3.5x) = 8.03
  - T. Paopao (3.9000000000000004x) = 18.07
  - **Game stack**: team 12: 2 players

**Field ownership** (top-20 entries):
  - T. Paopao (4.3x/4.1x/4.5x/3.9x): 20/20 = 100%, avg 18.91
  - M. Siegrist (2.9x/2.5x/3.1x/2.7x): 19/20 = 95%, avg 13.22
  - O. Sims (2.9x/3.1x/2.7x/3.3x): 13/20 = 65%, avg 12.14
  - A. Boston (2x/2.2x): 12/20 = 60%, avg 11.74
  - G. Berger (3.5x/3.7x/4.1x): 9/20 = 45%, avg 8.24
  - D. Miller (4.2x): 7/20 = 35%, avg 5.30
  - L. Hull (3.2x/3.4x): 5/20 = 25%, avg 9.51
  - B. Jones (1.8x/2.2x/2.4x): 4/20 = 20%, avg 6.45

### Outcome Classification

**(A) Correctly priced** (17 players):
  - R. Howard (ATL, 0.3x, 229 drafts) = 6.35 -- High-draft player delivered as expected
  - M. Siegrist (DAL, 1.1x, 343 drafts) = 4.53 -- High-draft player delivered as expected
  - O. Sims (DAL, 1.3x, 47 drafts) = 4.1 -- Mid-draft player with mid outcome -- no edge either way
  - A. Stevens (CHI, 0.5x, 172 drafts) = 5.09 -- High-draft player delivered as expected
  - A. Boston (IND, 0.2x, 951 drafts) = 5.38 -- High-draft player delivered as expected
  - L. Hull (IND, 1.8x, 191 drafts) = 2.9 -- Outcome roughly matched draft position and signals
  - A. Gray (ATL, 0.3x, 574 drafts) = 4.39 -- High-draft player delivered as expected
  - M. Hines-Allen (IND, 1.9x, 207 drafts) = 2.21 -- Outcome roughly matched draft position and signals
  - N. Coffey (MIN, 3.0x, 2 drafts) = 1.7 -- Outcome roughly matched draft position and signals
  - J. Allemand (TOR, 1.5x, 40 drafts) = 2.35 -- Mid-draft player with mid outcome -- no edge either way
  - B. Jones (ATL, 0.6x, 239 drafts) = 3.15 -- High-draft player delivered as expected
  - M. Caldwell (MIN, 2.3x, 1 drafts) = 1.81 -- Outcome roughly matched draft position and signals
  - A. Okonkwo (ATL, 1.5x, 16 drafts) = 2.06 -- Mid-draft player with mid outcome -- no edge either way
  - R. Burrell (LAS, 2.9x, 28 drafts) = 1.39 -- Mid-draft player with mid outcome -- no edge either way
  - P. Bueckers (DAL, 0.2x, 638 drafts) = 2.9 -- Outcome roughly matched draft position and signals
  - D. Miller (CON, 3.0x, 7 drafts) = 1.26 -- Low-draft player correctly faded by the field
  - B. Griner (CON, 1.7x, 119 drafts) = 1.69 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - T. Paopao (ATL, 2.7x, 9 drafts) = 4.63 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-30

**Players**: 17 HV
 | **Score range**: 1.61 -- 5.04 (median 3.22)

**Leaderboard**: top score 49.35, floor 41.41, median 43.99

**Winner** (score 49.35):
  - N. Collier (2x) = 10.08
  - E. Magbegor (2.8x) = 9.01
  - I. Rupert (3.3x) = 6.90
  - N. Mack (3.0999999999999996x) = 11.40
  - K. Charles (4x) = 11.95
  - **Game stack**: team 14: 2 players

**Field ownership** (top-20 entries):
  - N. Collier (1.6x/1.8x/2x): 17/20 = 85%, avg 9.91
  - K. Charles (4.4x/4x/4.2x): 15/20 = 75%, avg 12.15
  - V. Burton (2.1x/2.3x/2.5x): 10/20 = 50%, avg 8.03
  - I. Rupert (2.9x/3.1x/3.5x/3.3x): 8/20 = 40%, avg 6.58
  - N. Mack (3.3x/3.1x): 4/20 = 20%, avg 11.59
  - K. McBride (2.3x/2.5x): 4/20 = 20%, avg 7.83
  - K. Martin (4.4x/4.6x/4.2x/4.8x): 4/20 = 20%, avg 9.97
  - A. Morrow (3.2x/3.4x/3.6x): 4/20 = 20%, avg 4.75

### Outcome Classification

**(A) Correctly priced** (14 players):
  - K. Charles (GSV, 2.8x, 2 drafts) = 2.99 -- Outcome roughly matched draft position and signals
  - N. Mack (PHO, 1.7x, 14 drafts) = 3.68 -- Mid-draft player with mid outcome -- no edge either way
  - K. Martin (LAS, 3.0x, 4 drafts) = 2.22 -- Outcome roughly matched draft position and signals
  - N. Collier (MIN, 0.0x, 2600 drafts) = 5.04 -- High-draft player delivered as expected
  - E. Magbegor (SEA, 1.0x, 113 drafts) = 3.22 -- High-draft player delivered as expected
  - A. Edwards (CON, 3.0x, 2 drafts) = 1.79 -- Outcome roughly matched draft position and signals
  - A. Smith (DAL, 0.6x, 89 drafts) = 3.39 -- High-draft player delivered as expected
  - V. Burton (GSV, 0.5x, 314 drafts) = 3.49 -- High-draft player delivered as expected
  - K. McBride (MIN, 0.7x, 125 drafts) = 3.19 -- High-draft player delivered as expected
  - J. Salaün (GSV, 1.4x, 14 drafts) = 2.52 -- Mid-draft player with mid outcome -- no edge either way
  - N. Ogwumike (LAS, 0.3x, 299 drafts) = 3.67 -- High-draft player delivered as expected
  - N. Cloud (CHI, 0.9x, 34 drafts) = 2.82 -- Mid-draft player with mid outcome -- no edge either way
  - A. Reese (ATL, 0.4x, 437 drafts) = 3.37 -- High-draft player delivered as expected
  - L. Olsen (WAS, 3.0x, 1 drafts) = 1.61 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (3 players):
  - C. Leite (POR, 2.7x, 2 drafts) = 3.75 -- High-boost low-draft player who overperformed
  - D. Carrington (CHI, 1.7x, 6 drafts) = 3.66 -- Above-expectation outcome, ambiguous whether knowable
  - L. Amihere (GSV, 2.2x, 1 drafts) = 3.08 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 3 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-08-31

**Players**: 19 HV
 | **Score range**: 1.07 -- 4.11 (median 1.90)

**Leaderboard**: top score 48.52, floor 40.78, median 42.47

**Winner** (score 48.52):
  - K. Iriafen (3x) = 11.51
  - J. Salaün (3.2x) = 5.56
  - I. Rupert (3.3x) = 12.78
  - K. Charles (4.1x) = 7.28
  - A. Powers (4.2x) = 11.39
  - **Game stack**: team 14: 3 players

**Field ownership** (top-20 entries):
  - I. Rupert (2.9x/3.7x/3.3x/3.1x): 17/20 = 85%, avg 12.19
  - V. Burton (2.1x/2.3x/2.5x): 15/20 = 75%, avg 9.73
  - K. Charles (4.1x/4.5x/3.9x): 13/20 = 65%, avg 7.28
  - K. Iriafen (3x/2.8x/2.6x/2.4x/2.2x): 9/20 = 45%, avg 10.41
  - J. Salaün (3.2x/3x/2.8x): 7/20 = 35%, avg 5.26
  - A. Powers (4.4x/4.6x/4.2x/5x): 6/20 = 30%, avg 12.20
  - K. Martin (4.4x/4.1x): 6/20 = 30%, avg 7.06
  - D. Hamby (1.8x/2.2x): 6/20 = 30%, avg 8.64

### Outcome Classification

**(A) Correctly priced** (18 players):
  - S. Dolson (SEA, 3.0x, 2 drafts) = 2.32 -- Outcome roughly matched draft position and signals
  - K. Iriafen (WAS, 1.0x, 228 drafts) = 3.84 -- High-draft player delivered as expected
  - V. Burton (GSV, 0.5x, 605 drafts) = 4.11 -- High-draft player delivered as expected
  - J. Melbourne (SEA, 3.0x, 5 drafts) = 1.78 -- Outcome roughly matched draft position and signals
  - D. Hamby (LAS, 0.2x, 1100 drafts) = 4.05 -- High-draft player delivered as expected
  - L. Olsen (WAS, 3.0x, 5 drafts) = 1.78 -- Outcome roughly matched draft position and signals
  - K. Martin (LAS, 2.9x, 21 drafts) = 1.7 -- Mid-draft player with mid outcome -- no edge either way
  - K. Charles (GSV, 2.7x, 23 drafts) = 1.77 -- Mid-draft player with mid outcome -- no edge either way
  - K. Plum (LAS, 0.2x, 947 drafts) = 3.36 -- High-draft player delivered as expected
  - S. Citron (WAS, 0.8x, 228 drafts) = 2.23 -- Outcome roughly matched draft position and signals
  - J. Allemand (TOR, 1.5x, 103 drafts) = 1.77 -- Outcome roughly matched draft position and signals
  - A. Stevens (CHI, 0.4x, 220 drafts) = 2.56 -- Outcome roughly matched draft position and signals
  - R. Jackson (CHI, 1.0x, 38 drafts) = 2.03 -- Mid-draft player with mid outcome -- no edge either way
  - J. Salaün (GSV, 1.4x, 135 drafts) = 1.74 -- Outcome roughly matched draft position and signals
  - R. Burrell (LAS, 2.8x, 2 drafts) = 1.22 -- Low-draft player correctly faded by the field
  - S. Austin (WAS, 0.9x, 136 drafts) = 1.9 -- Outcome roughly matched draft position and signals
  - O. Sims (DAL, 1.2x, 65 drafts) = 1.7 -- Outcome roughly matched draft position and signals
  - E. Engstler (POR, 3.0x, 1 drafts) = 1.07 -- Low-draft player correctly faded by the field

**(C) Unknowable / winners' edge** (1 players):
  - I. Rupert (GSV, 1.7x, 5 drafts) = 3.87 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-09-01

**Players**: 18 HV
 | **Score range**: 1.76 -- 5.66 (median 3.68)

**Leaderboard**: top score 56.60, floor 51.68, median 52.85

**Winner** (score 56.60):
  - D. Hamby (2.2x) = 12.46
  - R. Howard (2.1x) = 9.74
  - N. Hillmon (2.9000000000000004x) = 13.54
  - M. Hines-Allen (3.3x) = 5.03
  - N. Hiedeman (3.2x) = 15.83
  - **Game stack**: team 2: 2 players

**Field ownership** (top-20 entries):
  - N. Hiedeman (4x/3.2x/3.8x/3.6x/3.4x): 18/20 = 90%, avg 17.26
  - S. Diggins (2.4x/2x/2.2x/1.8x): 14/20 = 70%, avg 11.25
  - C. Williams (1.6x/2.4x/2x/1.8x/2.2x): 12/20 = 60%, avg 9.78
  - D. Hamby (1.6x/2x/2.2x/1.4x): 11/20 = 55%, avg 10.71
  - E. Magbegor (2.9x/2.3x/2.5x/2.7x): 6/20 = 30%, avg 9.19
  - N. Ogwumike (1.9x/2.3x/1.5x/2.1x/1.7x): 6/20 = 30%, avg 9.12
  - N. Hillmon (2.9x/2.5x/3.1x): 5/20 = 25%, avg 12.60
  - N. Collier (1.8x/2x/1.4x): 5/20 = 25%, avg 9.24

### Outcome Classification

**(A) Correctly priced** (17 players):
  - N. Hiedeman (SEA, 2.0x, 37 drafts) = 4.95 -- Mid-draft player with mid outcome -- no edge either way
  - N. Hillmon (ATL, 1.3x, 64 drafts) = 4.67 -- High-draft player delivered as expected
  - S. Diggins (CHI, 0.4x, 214 drafts) = 5.4 -- High-draft player delivered as expected
  - D. Hamby (LAS, 0.2x, 361 drafts) = 5.66 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.4x, 219 drafts) = 4.59 -- High-draft player delivered as expected
  - N. Ogwumike (LAS, 0.3x, 367 drafts) = 4.72 -- High-draft player delivered as expected
  - R. Howard (ATL, 0.3x, 136 drafts) = 4.64 -- High-draft player delivered as expected
  - E. Magbegor (SEA, 0.9x, 135 drafts) = 3.58 -- High-draft player delivered as expected
  - D. Miller (CON, 3.0x, 13 drafts) = 2.07 -- Mid-draft player with mid outcome -- no edge either way
  - N. Collier (MIN, 0.0x, 3400 drafts) = 5.02 -- High-draft player delivered as expected
  - R. Burrell (LAS, 2.9x, 11 drafts) = 2.0 -- Mid-draft player with mid outcome -- no edge either way
  - B. Jones (ATL, 0.6x, 92 drafts) = 3.68 -- High-draft player delivered as expected
  - S. Rivers (CON, 1.4x, 8 drafts) = 2.42 -- Outcome roughly matched draft position and signals
  - M. Siegrist (DAL, 1.0x, 65 drafts) = 2.6 -- Outcome roughly matched draft position and signals
  - R. Jackson (CHI, 1.0x, 78 drafts) = 2.5 -- Outcome roughly matched draft position and signals
  - A. Okonkwo (ATL, 1.5x, 59 drafts) = 2.07 -- Outcome roughly matched draft position and signals
  - A. Morrow (CON, 1.8x, 7 drafts) = 1.76 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - L. Lacan (CON, 1.0x, 6 drafts) = 3.29 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-09-02

**Players**: 19 HV
 | **Score range**: 1.26 -- 5.41 (median 2.63)

**Leaderboard**: top score 50.90, floor 47.08, median 48.46

**Winner** (score 50.90):
  - K. Mitchell (2.4x) = 12.99
  - N. Cloud (2.7x) = 9.80
  - S. Whitcomb (3.3x) = 9.77
  - T. Fágbénlé (3.2x) = 11.06
  - M. Akoa Makani (3.2x) = 7.28
  - **Game stack**: team 6: 2 players

**Field ownership** (top-20 entries):
  - T. Fágbénlé (3x/3.2x/3.8x/3.6x/3.4x): 19/20 = 95%, avg 11.82
  - K. Mitchell (1.6x/2.4x/2x/1.8x/2.2x): 18/20 = 90%, avg 10.70
  - M. Akoa Makani (3.2x/3.6x/3.4x): 13/20 = 65%, avg 7.49
  - S. Whitcomb (3.1x/3.7x/2.9x/3.3x): 12/20 = 60%, avg 9.63
  - L. Hull (3x/3.2x/3.8x/3.6x/3.4x): 12/20 = 60%, avg 9.24
  - D. Bonner (3.1x/3.5x/3.3x/2.7x): 10/20 = 50%, avg 9.14
  - A. Thomas (1.8x/2x): 8/20 = 40%, avg 8.88
  - N. Cloud (2.9x/2.3x/2.5x/2.7x): 6/20 = 30%, avg 9.07

### Outcome Classification

**(A) Correctly priced** (19 players):
  - T. Fágbénlé (TOR, 1.8x, 95 drafts) = 3.46 -- High-draft player delivered as expected
  - K. Mitchell (IND, 0.4x, 576 drafts) = 5.41 -- High-draft player delivered as expected
  - S. Whitcomb (PHO, 1.7x, 86 drafts) = 2.96 -- Outcome roughly matched draft position and signals
  - N. Cloud (CHI, 0.9x, 191 drafts) = 3.63 -- High-draft player delivered as expected
  - D. Bonner (PHO, 1.5x, 131 drafts) = 2.93 -- Outcome roughly matched draft position and signals
  - L. Hull (IND, 1.8x, 182 drafts) = 2.63 -- Outcome roughly matched draft position and signals
  - K. Charles (GSV, 2.6x, 9 drafts) = 2.01 -- Outcome roughly matched draft position and signals
  - A. Thomas (PHO, 0.0x, 2500 drafts) = 4.56 -- High-draft player delivered as expected
  - M. Akoa Makani (PHO, 2.0x, 118 drafts) = 2.28 -- Outcome roughly matched draft position and signals
  - B. Turner (LVA, 3.0x, 5 drafts) = 1.62 -- Outcome roughly matched draft position and signals
  - V. Burton (GSV, 0.5x, 818 drafts) = 3.16 -- High-draft player delivered as expected
  - N. Mack (PHO, 1.6x, 15 drafts) = 2.15 -- Mid-draft player with mid outcome -- no edge either way
  - A. Boston (IND, 0.2x, 617 drafts) = 3.28 -- High-draft player delivered as expected
  - K. Martin (LAS, 2.9x, 11 drafts) = 1.43 -- Mid-draft player with mid outcome -- no edge either way
  - B. Stewart (NYL, 0.2x, 821 drafts) = 2.67 -- Outcome roughly matched draft position and signals
  - M. Johannes (NYL, 2.6x, 12 drafts) = 1.26 -- Mid-draft player with mid outcome -- no edge either way
  - D. Dantas (IND, 3.0x, 9 drafts) = 1.26 -- Low-draft player correctly faded by the field
  - S. Sabally (NYL, 0.5x, 293 drafts) = 2.04 -- Outcome roughly matched draft position and signals
  - K. Copper (PHO, 1.0x, 71 drafts) = 1.62 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-09-03

**Players**: 18 HV
 | **Score range**: 1.40 -- 4.56 (median 2.91)

**Leaderboard**: top score 45.62, floor 43.43, median 44.28

**Winner** (score 45.62):
  - J. Canada (2.7x) = 12.01
  - A. Reese (2.2x) = 10.02
  - K. Plum (1.8x) = 7.11
  - M. Caldwell (3.6999999999999997x) = 12.20
  - J. Allemand (2.8x) = 4.28
  - **Game stack**: team 2: 2 players

**Field ownership** (top-20 entries):
  - J. Canada (1.9x/2.3x/2.7x/2.1x/2.5x): 18/20 = 90%, avg 10.47
  - K. Cardoso (1.9x/2.3x/2.7x/2.1x/2.5x): 16/20 = 80%, avg 9.42
  - A. Reese (1.6x/1.8x/2.2x/2.4x): 15/20 = 75%, avg 9.90
  - N. Hillmon (2.4x/3.2x/2.6x/2.8x): 10/20 = 50%, avg 7.85
  - B. Jones (1.8x/2.2x/2.6x/2.4x): 10/20 = 50%, avg 9.39
  - S. Rivers (3.2x/2.8x/2.6x): 6/20 = 30%, avg 7.04
  - R. Howard (1.9x/1.5x/2.3x): 6/20 = 30%, avg 7.30
  - K. Plum (1.6x/1.8x/2.2x): 4/20 = 20%, avg 7.31

### Outcome Classification

**(A) Correctly priced** (17 players):
  - J. Canada (ATL, 0.7x, 125 drafts) = 4.45 -- High-draft player delivered as expected
  - A. Reese (ATL, 0.4x, 956 drafts) = 4.56 -- High-draft player delivered as expected
  - K. Cardoso (CHI, 0.7x, 227 drafts) = 4.03 -- High-draft player delivered as expected
  - B. Jones (ATL, 0.6x, 216 drafts) = 4.15 -- High-draft player delivered as expected
  - N. Hillmon (ATL, 1.2x, 134 drafts) = 2.91 -- Outcome roughly matched draft position and signals
  - M. Onyenwere (WAS, 3.0x, 6 drafts) = 1.8 -- Outcome roughly matched draft position and signals
  - R. Banham (CHI, 2.1x, 97 drafts) = 2.15 -- Outcome roughly matched draft position and signals
  - K. Plum (LAS, 0.2x, 1000 drafts) = 3.95 -- High-draft player delivered as expected
  - R. Howard (ATL, 0.3x, 961 drafts) = 3.71 -- High-draft player delivered as expected
  - S. Rivers (CON, 1.4x, 111 drafts) = 2.49 -- Outcome roughly matched draft position and signals
  - T. Paopao (ATL, 2.6x, 7 drafts) = 1.65 -- Outcome roughly matched draft position and signals
  - D. Hamby (LAS, 0.2x, 1400 drafts) = 3.36 -- High-draft player delivered as expected
  - R. Allen (NYL, 3.0x, 16 drafts) = 1.47 -- Mid-draft player with mid outcome -- no edge either way
  - E. Williams (CHI, 1.6x, 102 drafts) = 1.96 -- Outcome roughly matched draft position and signals
  - K. Nurse (TOR, 3.0x, 10 drafts) = 1.4 -- Mid-draft player with mid outcome -- no edge either way
  - B. Griner (CON, 1.7x, 114 drafts) = 1.56 -- Outcome roughly matched draft position and signals
  - J. Allemand (TOR, 1.6x, 5 drafts) = 1.53 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - M. Caldwell (MIN, 2.3x, 2 drafts) = 3.3 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-09-04

**Players**: 18 HV
 | **Score range**: 1.64 -- 6.55 (median 2.89)

**Leaderboard**: top score 64.37, floor 53.19, median 54.61

**Winner** (score 64.37):
  - P. Bueckers (2.2x) = 11.93
  - M. Siegrist (2.8x) = 8.32
  - N. Hiedeman (3.4000000000000004x) = 18.01
  - H. Jones (3.9x) = 20.89
  - K. McBride (1.9x) = 5.22
  - **Game stack**: team 12: 2 players

**Field ownership** (top-20 entries):
  - N. Hiedeman (3.2x/3.4x/3x/3.6x): 17/20 = 85%, avg 17.45
  - A. Wilson (1.6x/1.4x/1.2x/2x/1.8x): 16/20 = 80%, avg 11.96
  - P. Bueckers (1.8x/2x/2.2x): 13/20 = 65%, avg 11.17
  - J. Young (1.9x/2.3x/1.5x/2.1x/1.7x): 9/20 = 45%, avg 8.93
  - H. Jones (4.1x/3.7x/3.9x): 6/20 = 30%, avg 20.71
  - C. Gray (2.3x/2.5x/2.7x): 5/20 = 25%, avg 6.45
  - M. Siegrist (2.8x/3x/2.6x): 3/20 = 15%, avg 8.32
  - K. McBride (1.9x/2.3x): 3/20 = 15%, avg 5.58

### Outcome Classification

**(A) Correctly priced** (16 players):
  - N. Hiedeman (SEA, 1.8x, 94 drafts) = 5.3 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 2900 drafts) = 6.55 -- High-draft player delivered as expected
  - P. Bueckers (DAL, 0.2x, 541 drafts) = 5.42 -- High-draft player delivered as expected
  - C. Leite (POR, 2.6x, 1 drafts) = 2.43 -- Outcome roughly matched draft position and signals
  - S. Austin (WAS, 0.9x, 83 drafts) = 3.75 -- High-draft player delivered as expected
  - M. Hines-Allen (IND, 1.9x, 6 drafts) = 2.78 -- Outcome roughly matched draft position and signals
  - M. Billings (IND, 2.0x, 2 drafts) = 2.79 -- Outcome roughly matched draft position and signals
  - J. Young (LVA, 0.3x, 191 drafts) = 4.59 -- High-draft player delivered as expected
  - B. Carleton (POR, 1.9x, 106 drafts) = 2.52 -- Outcome roughly matched draft position and signals
  - A. Clark (DAL, 3.0x, 2 drafts) = 1.96 -- Outcome roughly matched draft position and signals
  - I. Rupert (GSV, 1.6x, 2 drafts) = 2.68 -- Outcome roughly matched draft position and signals
  - M. Siegrist (DAL, 1.0x, 22 drafts) = 2.97 -- Mid-draft player with mid outcome -- no edge either way
  - D. Bonner (PHO, 1.5x, 7 drafts) = 2.54 -- Outcome roughly matched draft position and signals
  - K. Iriafen (WAS, 0.9x, 111 drafts) = 2.89 -- Outcome roughly matched draft position and signals
  - S. Whitcomb (PHO, 1.7x, 91 drafts) = 2.21 -- Outcome roughly matched draft position and signals
  - K. Martin (LAS, 2.9x, 11 drafts) = 1.64 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (2 players):
  - N. Mack (PHO, 1.6x, 2 drafts) = 3.5 -- Above-expectation outcome, ambiguous whether knowable
  - K. Copper (PHO, 1.0x, 5 drafts) = 3.28 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-09-05

**Players**: 19 HV
 | **Score range**: 1.63 -- 8.50 (median 3.58)

**Leaderboard**: top score 60.41, floor 54.85, median 56.72

**Winner** (score 60.41):
  - R. Howard (2.3x) = 19.55
  - D. Hamby (2x) = 11.00
  - K. Cardoso (2.3x) = 7.42
  - M. Caldwell (3.6x) = 13.13
  - A. Powers (4.2x) = 9.30

**Field ownership** (top-20 entries):
  - R. Howard (2.1x/2.3x): 20/20 = 100%, avg 19.13
  - M. Caldwell (3.4x/3.8x/3.6x): 10/20 = 50%, avg 13.06
  - D. Hamby (1.8x/2x/2.2x/1.4x): 9/20 = 45%, avg 11.00
  - N. Howard (2.4x/2.2x/2.6x): 7/20 = 35%, avg 11.34
  - E. Williams (3.2x/2.8x/3x): 6/20 = 30%, avg 7.40
  - N. Hillmon (2.8x/3x/2.6x): 6/20 = 30%, avg 7.97
  - K. Cardoso (1.9x/2.1x/2.3x): 5/20 = 25%, avg 7.04
  - A. Powers (4.4x/4.2x): 5/20 = 25%, avg 9.39

### Outcome Classification

**(A) Correctly priced** (18 players):
  - R. Howard (ATL, 0.3x, 1200 drafts) = 8.5 -- High-draft player delivered as expected
  - L. Fiebich (NYL, 1.6x, 43 drafts) = 3.87 -- Mid-draft player with mid outcome -- no edge either way
  - N. Howard (MIN, 1.0x, 157 drafts) = 4.62 -- High-draft player delivered as expected
  - D. Hamby (LAS, 0.2x, 758 drafts) = 5.5 -- High-draft player delivered as expected
  - T. Paopao (ATL, 2.5x, 7 drafts) = 2.53 -- Outcome roughly matched draft position and signals
  - B. Stewart (NYL, 0.2x, 852 drafts) = 5.06 -- High-draft player delivered as expected
  - K. Burke (CON, 2.0x, 28 drafts) = 2.51 -- Mid-draft player with mid outcome -- no edge either way
  - N. Cloud (CHI, 0.8x, 196 drafts) = 3.58 -- High-draft player delivered as expected
  - K. Mitchell (IND, 0.4x, 472 drafts) = 4.08 -- High-draft player delivered as expected
  - R. Jackson (CHI, 1.0x, 16 drafts) = 3.09 -- Mid-draft player with mid outcome -- no edge either way
  - N. Hillmon (ATL, 1.2x, 13 drafts) = 2.85 -- Mid-draft player with mid outcome -- no edge either way
  - E. Williams (CHI, 1.6x, 11 drafts) = 2.47 -- Mid-draft player with mid outcome -- no edge either way
  - S. Diggins (CHI, 0.4x, 303 drafts) = 3.7 -- High-draft player delivered as expected
  - B. Jones (ATL, 0.6x, 204 drafts) = 3.37 -- High-draft player delivered as expected
  - N. Ogwumike (LAS, 0.3x, 520 drafts) = 3.81 -- High-draft player delivered as expected
  - E. Wheeler (LAS, 1.3x, 38 drafts) = 2.65 -- Mid-draft player with mid outcome -- no edge either way
  - K. Cardoso (CHI, 0.7x, 267 drafts) = 3.23 -- High-draft player delivered as expected
  - M. Onyenwere (WAS, 3.0x, 2 drafts) = 1.63 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - M. Caldwell (MIN, 2.2x, 1 drafts) = 3.65 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-09-06

**Players**: 19 HV
 | **Score range**: 1.66 -- 4.98 (median 2.54)

**Leaderboard**: top score 55.20, floor 52.48, median 53.05

**Winner** (score 55.20):
  - N. Collier (2x) = 6.69
  - N. Hiedeman (3.5x) = 17.45
  - J. Salaün (3x) = 7.61
  - K. Charles (4x) = 12.19
  - J. Shepard (2.5999999999999996x) = 11.26
  - **Game stack**: team 14: 2 players

**Field ownership** (top-20 entries):
  - N. Hiedeman (3.5x/3.1x/2.9x/3.7x/3.3x): 20/20 = 100%, avg 16.45
  - J. Shepard (3x/2.8x/2.6x/3.2x/3.4x): 20/20 = 100%, avg 13.30
  - K. Charles (4.4x/4.6x/4x/3.8x): 11/20 = 55%, avg 12.25
  - M. Mabrey (2.4x/2.8x/2.2x/2.6x): 8/20 = 40%, avg 8.86
  - J. Salaün (3.2x/3x/2.8x): 7/20 = 35%, avg 7.83
  - N. Collier (2x): 6/20 = 30%, avg 6.69
  - T. Charles (2.8x/2.2x/2.6x): 4/20 = 20%, avg 10.81
  - K. Martin (4.1x/4.5x): 4/20 = 20%, avg 3.92

### Outcome Classification

**(A) Correctly priced** (18 players):
  - N. Hiedeman (SEA, 1.7x, 152 drafts) = 4.98 -- High-draft player delivered as expected
  - J. Shepard (DAL, 1.4x, 123 drafts) = 4.33 -- High-draft player delivered as expected
  - K. Charles (GSV, 2.6x, 47 drafts) = 3.05 -- Mid-draft player with mid outcome -- no edge either way
  - M. Mabrey (TOR, 1.0x, 86 drafts) = 3.65 -- High-draft player delivered as expected
  - A. Morrow (CON, 1.9x, 16 drafts) = 2.56 -- Mid-draft player with mid outcome -- no edge either way
  - J. Salaün (GSV, 1.4x, 145 drafts) = 2.54 -- Outcome roughly matched draft position and signals
  - A. Thomas (PHO, 0.0x, 856 drafts) = 3.94 -- High-draft player delivered as expected
  - S. Rivers (CON, 1.4x, 74 drafts) = 2.27 -- Outcome roughly matched draft position and signals
  - M. Akoa Makani (PHO, 2.0x, 72 drafts) = 1.79 -- Outcome roughly matched draft position and signals
  - S. Whitcomb (PHO, 1.7x, 59 drafts) = 1.82 -- Outcome roughly matched draft position and signals
  - N. Collier (MIN, 0.0x, 3500 drafts) = 3.35 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.4x, 317 drafts) = 2.78 -- Outcome roughly matched draft position and signals
  - D. Bonner (PHO, 1.4x, 87 drafts) = 1.95 -- Outcome roughly matched draft position and signals
  - N. Mack (PHO, 1.5x, 7 drafts) = 1.86 -- Outcome roughly matched draft position and signals
  - B. Carleton (POR, 1.9x, 126 drafts) = 1.66 -- Outcome roughly matched draft position and signals
  - K. Copper (PHO, 1.0x, 26 drafts) = 2.1 -- Mid-draft player with mid outcome -- no edge either way
  - V. Burton (GSV, 0.5x, 348 drafts) = 2.47 -- Outcome roughly matched draft position and signals
  - S. Sabally (NYL, 0.6x, 156 drafts) = 2.01 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - I. Rupert (GSV, 1.5x, 8 drafts) = 3.19 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-09-07

**Players**: 17 HV
 | **Score range**: 1.42 -- 8.02 (median 3.13)

**Leaderboard**: top score 71.13, floor 60.32, median 61.83

**Winner** (score 71.13):
  - A. Wilson (2x) = 16.03
  - J. Young (2.1x) = 11.91
  - J. Allemand (3.2x) = 20.08
  - A. Powers (4.1x) = 16.52
  - G. Berger (3.2x) = 6.58
  - **Game stack**: team 1: 2 players, team None: 2 players

**Field ownership** (top-20 entries):
  - J. Allemand (3x/2.8x/3.2x/3.6x/3.4x): 20/20 = 100%, avg 20.15
  - A. Wilson (1.6x/2x): 18/20 = 90%, avg 15.85
  - M. Hines-Allen (3.2x/3.4x/3x/3.6x): 14/20 = 70%, avg 13.85
  - J. Young (1.9x/2.1x): 7/20 = 35%, avg 11.26
  - P. Bueckers (1.6x/2x): 6/20 = 30%, avg 6.71
  - K. Cardoso (1.9x/2.1x/2.3x/2.5x): 5/20 = 25%, avg 6.62
  - A. Powers (4.3x/4.1x/3.9x): 4/20 = 20%, avg 16.52
  - M. Siegrist (2.4x/2.6x): 4/20 = 20%, avg 5.52

### Outcome Classification

**(A) Correctly priced** (15 players):
  - A. Wilson (LVA, 0.0x, 3900 drafts) = 8.02 -- High-draft player delivered as expected
  - M. Hines-Allen (IND, 1.8x, 45 drafts) = 4.22 -- Mid-draft player with mid outcome -- no edge either way
  - J. Young (LVA, 0.3x, 229 drafts) = 5.67 -- High-draft player delivered as expected
  - C. Brink (LAS, 2.8x, 189 drafts) = 2.38 -- Outcome roughly matched draft position and signals
  - N. Howard (MIN, 1.0x, 109 drafts) = 3.13 -- High-draft player delivered as expected
  - A. Stevens (CHI, 0.5x, 121 drafts) = 3.39 -- High-draft player delivered as expected
  - D. Hamby (LAS, 0.2x, 264 drafts) = 3.76 -- High-draft player delivered as expected
  - K. Cardoso (CHI, 0.7x, 183 drafts) = 3.04 -- High-draft player delivered as expected
  - O. Sims (DAL, 1.3x, 7 drafts) = 2.43 -- Outcome roughly matched draft position and signals
  - A. Boston (IND, 0.2x, 211 drafts) = 3.62 -- High-draft player delivered as expected
  - P. Bueckers (DAL, 0.2x, 612 drafts) = 3.59 -- High-draft player delivered as expected
  - C. Gray (LVA, 0.9x, 213 drafts) = 2.64 -- Outcome roughly matched draft position and signals
  - R. Banham (CHI, 2.2x, 45 drafts) = 1.79 -- Mid-draft player with mid outcome -- no edge either way
  - E. Williams (CHI, 1.5x, 69 drafts) = 2.07 -- Outcome roughly matched draft position and signals
  - D. Dantas (IND, 3.0x, 3 drafts) = 1.42 -- Low-draft player correctly faded by the field

**(C) Unknowable / winners' edge** (2 players):
  - J. Allemand (TOR, 1.6x, 31 drafts) = 6.28 -- Above-expectation outcome, ambiguous whether knowable
  - R. Burrell (LAS, 2.9x, 2 drafts) = 3.05 -- High-boost low-draft player who overperformed

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-09-08

**Players**: 14 HV
 | **Score range**: 0.31 -- 3.97 (median 2.31)

**Leaderboard**: top score 46.44, floor 42.97, median 46.39

**Winner** (score 46.44):
  - R. Howard (2.2x) = 8.74
  - N. Hillmon (3x) = 11.09
  - S. Rivers (3x) = 9.46
  - M. Caldwell (3.5x) = 9.45
  - A. Morrow (3.0999999999999996x) = 7.70
  - **Game stack**: team 2: 2 players, team 11: 2 players

**Field ownership** (top-20 entries):
  - N. Hillmon (3.2x/2.8x/3x/2.6x): 20/20 = 100%, avg 11.01
  - S. Rivers (3x/2.8x/2.6x/3.2x/3.4x): 20/20 = 100%, avg 9.55
  - A. Morrow (3.5x/3.1x/3.7x/3.9x/3.3x): 20/20 = 100%, avg 8.25
  - M. Caldwell (3.5x/3.7x/4.1x/3.3x): 19/20 = 95%, avg 9.42
  - R. Howard (2x/2.2x): 14/20 = 70%, avg 8.69
  - T. Paopao (3.7x): 3/20 = 15%, avg 3.16
  - A. Edwards (4.2x): 1/20 = 5%, avg 4.36
  - J. Canada (2.4x): 1/20 = 5%, avg 5.55

### Outcome Classification

**(A) Correctly priced** (14 players):
  - N. Hillmon (ATL, 1.2x, 321 drafts) = 3.7 -- High-draft player delivered as expected
  - M. Caldwell (MIN, 2.1x, 131 drafts) = 2.7 -- Outcome roughly matched draft position and signals
  - S. Rivers (CON, 1.4x, 163 drafts) = 3.15 -- High-draft player delivered as expected
  - A. Morrow (CON, 1.9x, 146 drafts) = 2.48 -- Outcome roughly matched draft position and signals
  - R. Howard (ATL, 0.2x, 3000 drafts) = 3.97 -- High-draft player delivered as expected
  - B. Griner (CON, 1.7x, 207 drafts) = 1.99 -- Outcome roughly matched draft position and signals
  - A. Gray (ATL, 0.3x, 584 drafts) = 2.76 -- Outcome roughly matched draft position and signals
  - J. Canada (ATL, 0.6x, 123 drafts) = 2.31 -- Outcome roughly matched draft position and signals
  - A. Edwards (CON, 3.0x, 131 drafts) = 1.04 -- High-draft player underperformed -- field took the loss equally
  - B. Jones (ATL, 0.6x, 545 drafts) = 1.95 -- Outcome roughly matched draft position and signals
  - M. Mabrey (TOR, 1.0x, 282 drafts) = 1.44 -- High-draft player underperformed -- field took the loss equally
  - T. Paopao (ATL, 2.5x, 148 drafts) = 0.85 -- High-draft player underperformed -- field took the loss equally
  - N. Coffey (MIN, 3.0x, 89 drafts) = 0.42 -- High-draft player underperformed -- field took the loss equally
  - S. Koné (ATL, 3.0x, 4 drafts) = 0.31 -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-09-09

**Players**: 19 HV
 | **Score range**: 1.92 -- 5.32 (median 3.48)

**Leaderboard**: top score 52.85, floor 46.84, median 49.13

**Winner** (score 52.85):
  - A. Thomas (2x) = 8.49
  - S. Sabally (2.4x) = 12.38
  - K. Cardoso (2.3x) = 6.27
  - J. Salaün (2.8x) = 12.84
  - D. Evans (3.7x) = 12.87

**Field ownership** (top-20 entries):
  - A. Wilson (2x): 11/20 = 55%, avg 5.93
  - R. Burrell (4.1x/3.9x): 11/20 = 55%, avg 17.78
  - K. Charles (4x/3.8x/3.6x/4.2x): 10/20 = 50%, avg 11.41
  - S. Sabally (2.6x/2.4x/2x/1.8x/2.2x): 7/20 = 35%, avg 11.64
  - J. Salaün (3.2x/2.8x/3x/2.6x): 7/20 = 35%, avg 13.50
  - V. Burton (2.1x/2.3x/2.5x): 7/20 = 35%, avg 8.98
  - D. Hamby (2x/2.2x): 5/20 = 25%, avg 11.07
  - T. Fágbénlé (3.4x/3x): 4/20 = 20%, avg 11.18

### Outcome Classification

**(A) Correctly priced** (15 players):
  - J. Salaün (GSV, 1.4x, 13 drafts) = 4.59 -- Mid-draft player with mid outcome -- no edge either way
  - S. Sabally (NYL, 0.6x, 57 drafts) = 5.16 -- High-draft player delivered as expected
  - D. Hamby (LAS, 0.2x, 261 drafts) = 5.32 -- High-draft player delivered as expected
  - J. Loyd (LVA, 1.2x, 23 drafts) = 3.53 -- Mid-draft player with mid outcome -- no edge either way
  - E. Wheeler (LAS, 1.3x, 22 drafts) = 3.26 -- Mid-draft player with mid outcome -- no edge either way
  - J. Young (LVA, 0.3x, 217 drafts) = 4.41 -- High-draft player delivered as expected
  - J. Shepard (DAL, 1.3x, 22 drafts) = 3.03 -- Mid-draft player with mid outcome -- no edge either way
  - M. Kliundikova (TOR, 3.0x, 2 drafts) = 1.99 -- Outcome roughly matched draft position and signals
  - V. Burton (GSV, 0.5x, 191 drafts) = 3.9 -- High-draft player delivered as expected
  - C. Gray (LVA, 0.9x, 173 drafts) = 3.23 -- High-draft player delivered as expected
  - N. Smith (LVA, 2.1x, 1 drafts) = 2.25 -- Outcome roughly matched draft position and signals
  - K. Westbeld (PHO, 3.0x, 2 drafts) = 1.92 -- Outcome roughly matched draft position and signals
  - S. Citron (WAS, 0.8x, 17 drafts) = 3.11 -- Mid-draft player with mid outcome -- no edge either way
  - A. Thomas (PHO, 0.0x, 492 drafts) = 4.25 -- High-draft player delivered as expected
  - L. Hull (IND, 1.8x, 4 drafts) = 2.21 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (4 players):
  - R. Burrell (LAS, 2.7x, 2 drafts) = 4.44 -- High-boost low-draft player who overperformed
  - D. Evans (LVA, 2.5x, 1 drafts) = 3.48 -- High-boost low-draft player who overperformed
  - K. Charles (GSV, 2.4x, 3 drafts) = 3.03 -- Above-expectation outcome, ambiguous whether knowable
  - T. Fágbénlé (TOR, 1.8x, 1 drafts) = 3.49 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 4 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-09-10

**Players**: 14 HV
 | **Score range**: 0.00 -- 3.68 (median 2.25)

**Leaderboard**: top score 48.86, floor 44.05, median 45.79

**Winner** (score 48.86):
  - B. Griner (3.7x) = 13.62
  - A. Edwards (4.8x) = 12.01
  - T. Paopao (4.1x) = 9.74
  - N. Coffey (4.4x) = 8.26
  - S. Rivers (2.5x) = 5.23
  - **Game stack**: team 11: 3 players

**Field ownership** (top-20 entries):
  - B. Griner (3.5x/3.1x/2.9x/3.7x/3.3x): 20/20 = 100%, avg 12.52
  - A. Edwards (4.8x/4.6x/4.2x/4.4x/5x): 20/20 = 100%, avg 11.39
  - T. Paopao (4.1x/4.3x/3.7x/4.5x/3.9x): 15/20 = 75%, avg 9.58
  - S. Rivers (3.3x/2.9x/2.5x/2.7x): 8/20 = 40%, avg 5.96
  - A. Morrow (3x/3.2x/3.8x/3.6x/3.4x): 8/20 = 40%, avg 7.71
  - M. Mabrey (2.4x/2.8x/3x/2.6x): 8/20 = 40%, avg 6.55
  - N. Coffey (4.4x/5x/4.8x): 6/20 = 30%, avg 8.88
  - R. Howard (1.6x/2x/2.2x): 6/20 = 30%, avg 6.47

### Outcome Classification

**(A) Correctly priced** (14 players):
  - B. Griner (CON, 1.7x, 143 drafts) = 3.68 -- High-draft player delivered as expected
  - A. Edwards (CON, 3.0x, 94 drafts) = 2.5 -- Outcome roughly matched draft position and signals
  - T. Paopao (ATL, 2.5x, 136 drafts) = 2.38 -- Outcome roughly matched draft position and signals
  - N. Coffey (MIN, 3.0x, 94 drafts) = 1.88 -- Outcome roughly matched draft position and signals
  - A. Morrow (CON, 1.8x, 155 drafts) = 2.25 -- Outcome roughly matched draft position and signals
  - M. Mabrey (TOR, 1.0x, 206 drafts) = 2.5 -- Outcome roughly matched draft position and signals
  - R. Howard (ATL, 0.2x, 2300 drafts) = 3.18 -- High-draft player delivered as expected
  - S. Rivers (CON, 1.3x, 180 drafts) = 2.09 -- Outcome roughly matched draft position and signals
  - A. Gray (ATL, 0.3x, 975 drafts) = 2.79 -- Outcome roughly matched draft position and signals
  - B. Jones (ATL, 0.6x, 344 drafts) = 1.98 -- Outcome roughly matched draft position and signals
  - N. Hillmon (ATL, 1.1x, 418 drafts) = 1.51 -- Outcome roughly matched draft position and signals
  - M. Caldwell (MIN, 2.0x, 112 drafts) = 1.04 -- High-draft player underperformed -- field took the loss equally
  - J. Canada (ATL, 0.6x, 214 drafts) = 0.94 -- High-draft player underperformed -- field took the loss equally
  - O. Nelson-Ododa (CON, 1.5x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-09-11

**Players**: 20 HV
 | **Score range**: 2.10 -- 7.25 (median 4.08)

**Leaderboard**: top score 65.29, floor 57.26, median 58.99

**Winner** (score 65.29):
  - A. Wilson (2x) = 14.51
  - J. Young (2.1x) = 11.67
  - N. Hiedeman (3.2x) = 12.52
  - K. Charles (3.6999999999999997x) = 5.06
  - M. Westbeld (4.2x) = 21.54
  - **Game stack**: team 1: 2 players

**Field ownership** (top-20 entries):
  - A. Wilson (1.8x/2x/1.4x/1.2x): 19/20 = 95%, avg 13.59
  - C. Gray (2.1x/2.9x/2.3x/2.5x): 13/20 = 65%, avg 15.57
  - J. Young (1.9x/2.1x/2.3x): 12/20 = 60%, avg 11.76
  - J. Loyd (2.9x/2.5x/2.7x): 7/20 = 35%, avg 9.90
  - N. Hiedeman (3.2x/3.4x/2.8x): 6/20 = 30%, avg 12.13
  - M. Westbeld (4.4x/4.2x): 5/20 = 25%, avg 21.74
  - M. Hines-Allen (3.5x/3.1x): 5/20 = 25%, avg 9.67
  - K. Charles (3.7x): 4/20 = 20%, avg 5.06

### Outcome Classification

**(A) Correctly priced** (15 players):
  - C. Gray (LVA, 0.9x, 168 drafts) = 6.35 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 3300 drafts) = 7.25 -- High-draft player delivered as expected
  - N. Hiedeman (SEA, 1.6x, 19 drafts) = 3.91 -- Mid-draft player with mid outcome -- no edge either way
  - P. Bueckers (DAL, 0.2x, 472 drafts) = 5.89 -- High-draft player delivered as expected
  - J. Young (LVA, 0.3x, 211 drafts) = 5.56 -- High-draft player delivered as expected
  - J. Loyd (LVA, 1.1x, 63 drafts) = 3.83 -- High-draft player delivered as expected
  - B. Stewart (NYL, 0.2x, 234 drafts) = 5.26 -- High-draft player delivered as expected
  - J. Shepard (DAL, 1.3x, 24 drafts) = 3.47 -- Mid-draft player with mid outcome -- no edge either way
  - K. Cardoso (CHI, 0.7x, 138 drafts) = 4.14 -- High-draft player delivered as expected
  - S. Barker (POR, 3.0x, 19 drafts) = 2.16 -- Mid-draft player with mid outcome -- no edge either way
  - M. Hines-Allen (IND, 1.7x, 29 drafts) = 2.89 -- Mid-draft player with mid outcome -- no edge either way
  - N. Smith (LVA, 2.1x, 34 drafts) = 2.42 -- Mid-draft player with mid outcome -- no edge either way
  - N. Collier (MIN, 0.0x, 109 drafts) = 4.8 -- High-draft player delivered as expected
  - D. Miller (CON, 3.0x, 9 drafts) = 2.1 -- Outcome roughly matched draft position and signals
  - S. Sabally (NYL, 0.6x, 136 drafts) = 3.4 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (5 players):
  - M. Westbeld (CHI, 3.0x, 1 drafts) = 5.13 -- No enrichment data available -- cannot assess if knowable
  - A. James (DAL, 2.4x, 6 drafts) = 4.08 -- Above-expectation outcome, ambiguous whether knowable
  - A. Okonkwo (ATL, 2.1x, 3 drafts) = 4.69 -- Above-expectation outcome, ambiguous whether knowable
  - R. Gardner (NYL, 3.0x, 1 drafts) = 3.25 -- High-boost low-draft player who overperformed
  - R. Banham (CHI, 2.2x, 1 drafts) = 3.31 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 5 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-09-14

**Players**: 20 HV
 | **Score range**: 1.76 -- 5.35 (median 3.12)

**Leaderboard**: top score 56.26, floor 47.53, median 48.71

**Winner** (score 56.26):
  - N. Hiedeman (3.5x) = 10.59
  - N. Smith (3.8x) = 11.84
  - N. Hillmon (2.8x) = 13.10
  - D. Malonga (3.0999999999999996x) = 9.50
  - N. Cloud (2.1x) = 11.23
  - **Game stack**: team 10: 2 players

**Field ownership** (top-20 entries):
  - N. Smith (3.6x/4x/3.2x/3.8x/3.4x): 17/20 = 85%, avg 10.52
  - A. Wilson (1.8x/2x): 15/20 = 75%, avg 9.88
  - N. Hillmon (3.2x/2.8x/3x/2.6x): 11/20 = 55%, avg 13.01
  - D. Malonga (2.9x/3.5x/3.1x/3.3x): 11/20 = 55%, avg 9.66
  - J. Young (1.9x/2.1x): 7/20 = 35%, avg 9.64
  - J. Loyd (2.9x/2.3x/2.5x/2.7x): 6/20 = 30%, avg 8.00
  - D. Evans (3.8x/3.6x): 6/20 = 30%, avg 12.66
  - N. Cloud (2.1x/2.3x/2.5x): 5/20 = 25%, avg 12.73

### Outcome Classification

**(A) Correctly priced** (18 players):
  - D. Evans (LVA, 2.4x, 11 drafts) = 3.48 -- Mid-draft player with mid outcome -- no edge either way
  - N. Hillmon (ATL, 1.2x, 14 drafts) = 4.68 -- Mid-draft player with mid outcome -- no edge either way
  - N. Smith (LVA, 2.0x, 25 drafts) = 3.12 -- Mid-draft player with mid outcome -- no edge either way
  - D. Malonga (SEA, 1.7x, 22 drafts) = 3.06 -- Mid-draft player with mid outcome -- no edge either way
  - J. Young (LVA, 0.3x, 174 drafts) = 4.72 -- High-draft player delivered as expected
  - N. Hiedeman (SEA, 1.5x, 11 drafts) = 3.03 -- Mid-draft player with mid outcome -- no edge either way
  - K. Mitchell (IND, 0.4x, 170 drafts) = 4.24 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 3900 drafts) = 5.01 -- High-draft player delivered as expected
  - J. Loyd (LVA, 1.1x, 72 drafts) = 3.0 -- Outcome roughly matched draft position and signals
  - A. Gray (ATL, 0.3x, 189 drafts) = 3.9 -- High-draft player delivered as expected
  - K. Martin (LAS, 3.0x, 1 drafts) = 1.76 -- Outcome roughly matched draft position and signals
  - D. Bonner (PHO, 1.5x, 3 drafts) = 2.46 -- Outcome roughly matched draft position and signals
  - B. Stewart (NYL, 0.2x, 294 drafts) = 3.76 -- High-draft player delivered as expected
  - S. Whitcomb (PHO, 1.7x, 14 drafts) = 2.15 -- Mid-draft player with mid outcome -- no edge either way
  - T. Fágbénlé (TOR, 1.7x, 2 drafts) = 2.12 -- Outcome roughly matched draft position and signals
  - B. Jones (ATL, 0.6x, 118 drafts) = 2.97 -- Outcome roughly matched draft position and signals
  - C. Gray (LVA, 0.8x, 190 drafts) = 2.68 -- Outcome roughly matched draft position and signals
  - J. Jones (NYL, 0.6x, 19 drafts) = 2.82 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (2 players):
  - N. Cloud (CHI, 0.9x, 42 drafts) = 5.35 -- Above-expectation outcome, ambiguous whether knowable
  - J. Shepard (DAL, 1.3x, 2 drafts) = 3.39 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-09-16

**Players**: 20 HV
 | **Score range**: 0.96 -- 4.94 (median 2.32)

**Leaderboard**: top score 46.05, floor 43.40, median 45.15

**Winner** (score 46.05):
  - A. Wilson (2x) = 9.89
  - J. Young (2.1x) = 9.85
  - S. Diggins (2x) = 9.05
  - D. Malonga (3.0999999999999996x) = 9.84
  - N. Smith (3.2x) = 7.43
  - **Game stack**: team 1: 3 players

**Field ownership** (top-20 entries):
  - A. Wilson (1.8x/2x): 20/20 = 100%, avg 9.79
  - J. Young (1.9x/2.1x/1.7x/1.5x): 20/20 = 100%, avg 9.43
  - D. Malonga (3.5x/3.1x/2.9x/3.7x/3.3x): 18/20 = 90%, avg 10.06
  - N. Smith (3.2x/3.4x): 15/20 = 75%, avg 7.52
  - N. Ogwumike (1.9x/2.3x/1.5x/2.1x/1.7x): 11/20 = 55%, avg 8.84
  - S. Diggins (1.6x/1.8x/2x): 9/20 = 45%, avg 8.44
  - E. Wheeler (2.9x/2.7x): 4/20 = 20%, avg 7.07
  - K. Mitchell (2x): 2/20 = 10%, avg 6.39

### Outcome Classification

**(A) Correctly priced** (20 players):
  - D. Malonga (SEA, 1.7x, 32 drafts) = 3.18 -- Mid-draft player with mid outcome -- no edge either way
  - S. Diggins (CHI, 0.4x, 170 drafts) = 4.52 -- High-draft player delivered as expected
  - N. Ogwumike (LAS, 0.3x, 246 drafts) = 4.7 -- High-draft player delivered as expected
  - J. Young (LVA, 0.3x, 290 drafts) = 4.69 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 5200 drafts) = 4.94 -- High-draft player delivered as expected
  - N. Smith (LVA, 2.0x, 36 drafts) = 2.32 -- Mid-draft player with mid outcome -- no edge either way
  - E. Wheeler (LAS, 1.3x, 103 drafts) = 2.48 -- Outcome roughly matched draft position and signals
  - K. Mitchell (IND, 0.4x, 298 drafts) = 3.2 -- High-draft player delivered as expected
  - M. Timpson (IND, 3.0x, 3 drafts) = 1.56 -- Outcome roughly matched draft position and signals
  - T. Paopao (ATL, 2.4x, 5 drafts) = 1.67 -- Outcome roughly matched draft position and signals
  - C. Gray (LVA, 0.8x, 225 drafts) = 2.39 -- Outcome roughly matched draft position and signals
  - B. Turner (LVA, 3.0x, 2 drafts) = 1.33 -- Low-draft player correctly faded by the field
  - N. Howard (MIN, 1.0x, 100 drafts) = 2.17 -- Outcome roughly matched draft position and signals
  - J. Loyd (LVA, 1.1x, 164 drafts) = 2.09 -- Outcome roughly matched draft position and signals
  - E. Magbegor (SEA, 1.0x, 112 drafts) = 1.85 -- Outcome roughly matched draft position and signals
  - A. Boston (IND, 0.2x, 266 drafts) = 2.52 -- Outcome roughly matched draft position and signals
  - N. Hillmon (ATL, 1.2x, 158 drafts) = 1.51 -- Outcome roughly matched draft position and signals
  - K. Bell (LVA, 3.0x, 15 drafts) = 0.96 -- Mid-draft player with mid outcome -- no edge either way
  - J. Canada (ATL, 0.7x, 74 drafts) = 1.71 -- Outcome roughly matched draft position and signals
  - A. Gray (ATL, 0.3x, 258 drafts) = 1.97 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-09-17

**Players**: 20 HV
 | **Score range**: 1.46 -- 4.57 (median 2.21)

**Leaderboard**: top score 41.90, floor 39.25, median 40.42

**Winner** (score 41.90):
  - M. Billings (4x) = 10.95
  - V. Burton (2.3x) = 10.52
  - K. Charles (3.9x) = 9.03
  - B. Carleton (3.3x) = 5.90
  - J. Salaün (2.5x) = 5.52
  - **Game stack**: team 14: 3 players

**Field ownership** (top-20 entries):
  - V. Burton (1.9x/2.1x/2.3x/2.5x): 19/20 = 95%, avg 10.37
  - D. Bonner (2.9x/3.1x/3.5x/2.7x): 14/20 = 70%, avg 10.03
  - K. McBride (1.9x/2.3x/2.5x/2.7x): 11/20 = 55%, avg 8.75
  - N. Collier (1.2x/2x/1.8x): 11/20 = 55%, avg 7.43
  - S. Sabally (2.4x/2x/1.8x/2.2x): 8/20 = 40%, avg 8.03
  - J. Salaün (2.9x/3.1x/2.5x/2.7x): 7/20 = 35%, avg 6.15
  - N. Hiedeman (2.9x/3.1x/2.7x): 7/20 = 35%, avg 5.19
  - M. Billings (3.2x/4x/3.6x/3.4x): 4/20 = 20%, avg 9.72

### Outcome Classification

**(A) Correctly priced** (20 players):
  - D. Bonner (PHO, 1.5x, 81 drafts) = 3.48 -- High-draft player delivered as expected
  - V. Burton (GSV, 0.5x, 288 drafts) = 4.57 -- High-draft player delivered as expected
  - M. Billings (IND, 2.0x, 24 drafts) = 2.74 -- Mid-draft player with mid outcome -- no edge either way
  - K. Westbeld (PHO, 3.0x, 1 drafts) = 2.11 -- Outcome roughly matched draft position and signals
  - S. Sabally (NYL, 0.6x, 150 drafts) = 3.87 -- High-draft player delivered as expected
  - K. Charles (GSV, 2.3x, 27 drafts) = 2.31 -- Mid-draft player with mid outcome -- no edge either way
  - K. McBride (MIN, 0.7x, 162 drafts) = 3.66 -- High-draft player delivered as expected
  - N. Collier (MIN, 0.0x, 3900 drafts) = 4.05 -- High-draft player delivered as expected
  - J. Salaün (GSV, 1.3x, 120 drafts) = 2.21 -- Outcome roughly matched draft position and signals
  - B. Carleton (POR, 1.9x, 106 drafts) = 1.79 -- Outcome roughly matched draft position and signals
  - A. Thomas (PHO, 0.1x, 737 drafts) = 3.24 -- High-draft player delivered as expected
  - S. Whitcomb (PHO, 1.7x, 76 drafts) = 1.82 -- Outcome roughly matched draft position and signals
  - K. Copper (PHO, 1.1x, 13 drafts) = 2.08 -- Mid-draft player with mid outcome -- no edge either way
  - N. Hiedeman (SEA, 1.5x, 218 drafts) = 1.79 -- Outcome roughly matched draft position and signals
  - J. Jones (NYL, 0.6x, 150 drafts) = 2.29 -- Outcome roughly matched draft position and signals
  - M. Akoa Makani (PHO, 2.0x, 59 drafts) = 1.46 -- High-draft player underperformed -- field took the loss equally
  - N. Mack (PHO, 1.6x, 1 drafts) = 1.61 -- Outcome roughly matched draft position and signals
  - C. Zandalasini (GSV, 1.3x, 8 drafts) = 1.72 -- Outcome roughly matched draft position and signals
  - I. Rupert (GSV, 1.5x, 21 drafts) = 1.57 -- Mid-draft player with mid outcome -- no edge either way
  - D. Carrington (CHI, 1.7x, 34 drafts) = 1.47 -- Mid-draft player with mid outcome -- no edge either way

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-09-18

**Players**: 20 HV
 | **Score range**: 1.58 -- 7.11 (median 2.99)

**Leaderboard**: top score 46.09, floor 43.33, median 43.83

**Winner** (score 46.09):
  - A. Wilson (2x) = 14.23
  - A. Boston (2x) = 8.79
  - O. Sims (2.9000000000000004x) = 11.30
  - B. Jones (2x) = 5.97
  - A. Gray (1.5x) = 5.81
  - **Game stack**: team 2: 2 players

**Field ownership** (top-20 entries):
  - A. Wilson (2x): 20/20 = 100%, avg 14.23
  - A. Boston (1.8x/2x): 15/20 = 75%, avg 8.73
  - C. Gray (2x/2.2x/2.6x): 12/20 = 60%, avg 6.94
  - K. Mitchell (1.6x/1.8x/2x/2.2x): 12/20 = 60%, avg 6.95
  - J. Canada (1.9x/2.1x/2.3x/2.5x): 10/20 = 50%, avg 8.38
  - O. Sims (2.9x/3.1x/2.5x/2.7x): 7/20 = 35%, avg 10.63
  - A. Gray (1.9x/2.1x/1.5x/1.7x): 7/20 = 35%, avg 6.70
  - B. Jones (1.8x/2x/2.2x): 6/20 = 30%, avg 6.07

### Outcome Classification

**(A) Correctly priced** (19 players):
  - A. Wilson (LVA, 0.0x, 5400 drafts) = 7.11 -- High-draft player delivered as expected
  - J. Canada (ATL, 0.7x, 83 drafts) = 3.81 -- High-draft player delivered as expected
  - A. Boston (IND, 0.2x, 237 drafts) = 4.39 -- High-draft player delivered as expected
  - C. Gray (LVA, 0.8x, 198 drafts) = 3.25 -- High-draft player delivered as expected
  - K. Mitchell (IND, 0.4x, 249 drafts) = 3.72 -- High-draft player delivered as expected
  - A. Gray (ATL, 0.3x, 204 drafts) = 3.87 -- High-draft player delivered as expected
  - B. Turner (LVA, 3.0x, 1 drafts) = 1.74 -- Outcome roughly matched draft position and signals
  - B. Jones (ATL, 0.6x, 101 drafts) = 2.99 -- Outcome roughly matched draft position and signals
  - E. Wheeler (LAS, 1.3x, 109 drafts) = 2.35 -- Outcome roughly matched draft position and signals
  - S. Diggins (CHI, 0.4x, 198 drafts) = 3.13 -- High-draft player delivered as expected
  - J. Young (LVA, 0.3x, 269 drafts) = 3.12 -- High-draft player delivered as expected
  - N. Howard (MIN, 1.0x, 95 drafts) = 2.24 -- Outcome roughly matched draft position and signals
  - N. Ogwumike (LAS, 0.3x, 297 drafts) = 2.86 -- Outcome roughly matched draft position and signals
  - L. Hull (IND, 1.8x, 114 drafts) = 1.58 -- Outcome roughly matched draft position and signals
  - J. Loyd (LVA, 1.1x, 151 drafts) = 1.93 -- Outcome roughly matched draft position and signals
  - E. Magbegor (SEA, 1.0x, 112 drafts) = 1.99 -- Outcome roughly matched draft position and signals
  - N. Hillmon (ATL, 1.2x, 100 drafts) = 1.79 -- Outcome roughly matched draft position and signals
  - R. Howard (ATL, 0.2x, 177 drafts) = 2.61 -- Outcome roughly matched draft position and signals
  - G. Williams (GSV, 0.7x, 169 drafts) = 1.95 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - O. Sims (DAL, 1.3x, 3 drafts) = 3.9 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-09-19

**Players**: 18 HV
 | **Score range**: 0.00 -- 6.25 (median 1.70)

**Leaderboard**: top score 43.04, floor 42.07, median 42.22

**Winner** (score 43.04):
  - A. Thomas (2.1x) = 9.23
  - B. Stewart (2x) = 12.50
  - S. Sabally (2.2x) = 9.96
  - D. Bonner (2.9x) = 5.40
  - S. Whitcomb (2.9x) = 5.94
  - **Game stack**: team 6: 3 players, team 4: 2 players

**Field ownership** (top-20 entries):
  - A. Thomas (1.9x/2.1x/1.5x/1.7x): 20/20 = 100%, avg 7.70
  - B. Stewart (1.8x/2x/2.2x): 20/20 = 100%, avg 13.07
  - S. Sabally (2.6x/2.4x/2x/1.8x/2.2x): 20/20 = 100%, avg 9.96
  - S. Ionescu (1.6x/1.8x/2x/2.2x): 18/20 = 90%, avg 6.13
  - S. Whitcomb (2.9x/3.1x): 12/20 = 60%, avg 5.98
  - D. Bonner (2.9x/2.7x): 6/20 = 30%, avg 5.09
  - K. Burke (3.3x): 3/20 = 15%, avg 5.61
  - N. Cloud (2.3x): 1/20 = 5%, avg 4.10

### Outcome Classification

**(A) Correctly priced** (18 players):
  - B. Stewart (NYL, 0.2x, 969 drafts) = 6.25 -- High-draft player delivered as expected
  - S. Sabally (NYL, 0.6x, 410 drafts) = 4.53 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.1x, 3000 drafts) = 4.4 -- High-draft player delivered as expected
  - S. Whitcomb (PHO, 1.7x, 94 drafts) = 2.05 -- Outcome roughly matched draft position and signals
  - S. Ionescu (NYL, 0.2x, 1300 drafts) = 3.27 -- High-draft player delivered as expected
  - K. Burke (CON, 2.1x, 62 drafts) = 1.7 -- Outcome roughly matched draft position and signals
  - D. Bonner (PHO, 1.5x, 155 drafts) = 1.86 -- Outcome roughly matched draft position and signals
  - K. Copper (PHO, 1.1x, 178 drafts) = 1.69 -- Outcome roughly matched draft position and signals
  - N. Cloud (CHI, 0.9x, 285 drafts) = 1.78 -- Outcome roughly matched draft position and signals
  - J. Jones (NYL, 0.6x, 277 drafts) = 1.91 -- Outcome roughly matched draft position and signals
  - M. Akoa Makani (PHO, 2.0x, 76 drafts) = 0.94 -- High-draft player underperformed -- field took the loss equally
  - K. Westbeld (PHO, 3.0x, 72 drafts) = 0.64 -- High-draft player underperformed -- field took the loss equally
  - N. Mack (PHO, 1.6x, 70 drafts) = 0.66 -- High-draft player underperformed -- field took the loss equally
  - L. Fiebich (NYL, 1.6x, 96 drafts) = 0.42 -- High-draft player underperformed -- field took the loss equally
  - M. Johannes (NYL, 2.6x, None drafts) = None -- Low-draft player correctly faded by the field
  - S. Talbot (LVA, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - I. Harrison (TOR, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - R. Gardner (NYL, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-09-21

**Players**: 20 HV
 | **Score range**: 1.02 -- 5.34 (median 2.66)

**Leaderboard**: top score 43.92, floor 40.65, median 41.36

**Winner** (score 43.92):
  - K. Mitchell (2.4x) = 10.79
  - K. McBride (2.5x) = 9.05
  - N. Howard (2.6x) = 8.51
  - C. Williams (1.7999999999999998x) = 9.61
  - A. Thomas (1.3x) = 5.97
  - **Game stack**: team 5: 3 players

**Field ownership** (top-20 entries):
  - C. Williams (1.6x/2.4x/2x/1.8x/2.2x): 19/20 = 95%, avg 10.96
  - K. McBride (1.9x/2.3x/2.7x/2.1x/2.5x): 13/20 = 65%, avg 8.16
  - A. Thomas (1.9x/1.5x/1.3x/2.1x/1.7x): 13/20 = 65%, avg 7.88
  - K. Mitchell (1.6x/2.4x/1.8x/2.2x): 12/20 = 60%, avg 9.82
  - N. Howard (3x/2.2x/2.6x/2.8x): 12/20 = 60%, avg 8.51
  - B. Carleton (3.9x/3.3x): 6/20 = 30%, avg 6.13
  - N. Collier (1.6x/1.8x/2x): 6/20 = 30%, avg 6.12
  - K. Copper (2.3x/2.5x): 4/20 = 20%, avg 6.82

### Outcome Classification

**(A) Correctly priced** (19 players):
  - C. Williams (MIN, 0.4x, 219 drafts) = 5.34 -- High-draft player delivered as expected
  - D. Evans (LVA, 2.4x, 2 drafts) = 2.49 -- Outcome roughly matched draft position and signals
  - K. Mitchell (IND, 0.4x, 211 drafts) = 4.5 -- High-draft player delivered as expected
  - N. Howard (MIN, 1.0x, 95 drafts) = 3.27 -- High-draft player delivered as expected
  - K. McBride (MIN, 0.7x, 175 drafts) = 3.62 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.1x, 381 drafts) = 4.6 -- High-draft player delivered as expected
  - K. Copper (PHO, 1.1x, 44 drafts) = 2.84 -- Mid-draft player with mid outcome -- no edge either way
  - M. Kliundikova (TOR, 3.0x, 15 drafts) = 1.74 -- Mid-draft player with mid outcome -- no edge either way
  - N. Collier (MIN, 0.0x, 1800 drafts) = 3.53 -- High-draft player delivered as expected
  - B. Carleton (POR, 1.9x, 112 drafts) = 1.8 -- Outcome roughly matched draft position and signals
  - S. Sabally (NYL, 0.6x, 219 drafts) = 2.66 -- Outcome roughly matched draft position and signals
  - C. Gray (LVA, 0.8x, 131 drafts) = 2.43 -- Outcome roughly matched draft position and signals
  - A. Wilson (LVA, 0.0x, 3900 drafts) = 3.31 -- High-draft player delivered as expected
  - J. Young (LVA, 0.3x, 168 drafts) = 2.41 -- Outcome roughly matched draft position and signals
  - L. Hull (IND, 1.8x, 130 drafts) = 1.39 -- High-draft player underperformed -- field took the loss equally
  - B. Turner (LVA, 3.0x, 1 drafts) = 1.02 -- Low-draft player correctly faded by the field
  - A. Boston (IND, 0.2x, 228 drafts) = 2.14 -- Outcome roughly matched draft position and signals
  - N. Mack (PHO, 1.6x, 21 drafts) = 1.26 -- Mid-draft player with mid outcome -- no edge either way
  - D. Bonner (PHO, 1.5x, 37 drafts) = 1.18 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (1 players):
  - O. Sims (DAL, 1.3x, 8 drafts) = 3.15 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2025-09-23

**Players**: 20 HV
 | **Score range**: 1.21 -- 5.06 (median 2.63)

**Leaderboard**: top score 48.31, floor 45.16, median 46.20

**Winner** (score 48.31):
  - A. Wilson (2x) = 10.11
  - S. Sabally (2.4x) = 9.68
  - L. Hull (3.4000000000000004x) = 8.73
  - S. Whitcomb (3.0999999999999996x) = 9.13
  - N. Smith (3.2x) = 10.65
  - **Game stack**: team 1: 2 players

**Field ownership** (top-20 entries):
  - N. Smith (3.2x/4x/3.6x/3.4x): 19/20 = 95%, avg 11.32
  - A. Wilson (1.8x/2x): 13/20 = 65%, avg 9.95
  - S. Sabally (2.4x/2x/2.2x): 11/20 = 55%, avg 8.95
  - L. Hull (3.2x/3.4x/3x/3.6x): 11/20 = 55%, avg 8.27
  - S. Whitcomb (3.5x/3.1x/2.9x/3.7x/3.3x): 11/20 = 55%, avg 9.61
  - A. Smith (1.9x/2.3x/2.7x/2.1x/2.5x): 10/20 = 50%, avg 8.67
  - N. Collier (1.6x/1.8x/2x): 7/20 = 35%, avg 8.19
  - K. McBride (1.9x/2.1x/2.3x/2.7x): 5/20 = 25%, avg 7.30

### Outcome Classification

**(A) Correctly priced** (20 players):
  - N. Smith (LVA, 2.0x, 117 drafts) = 3.33 -- High-draft player delivered as expected
  - K. Westbeld (PHO, 3.0x, 2 drafts) = 2.34 -- Outcome roughly matched draft position and signals
  - S. Whitcomb (PHO, 1.7x, 85 drafts) = 2.94 -- Outcome roughly matched draft position and signals
  - S. Sabally (NYL, 0.6x, 198 drafts) = 4.03 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 5000 drafts) = 5.06 -- High-draft player delivered as expected
  - A. Smith (DAL, 0.7x, 118 drafts) = 3.71 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.1x, 356 drafts) = 4.7 -- High-draft player delivered as expected
  - L. Hull (IND, 1.8x, 157 drafts) = 2.57 -- Outcome roughly matched draft position and signals
  - C. Williams (MIN, 0.4x, 188 drafts) = 3.93 -- High-draft player delivered as expected
  - D. Evans (LVA, 2.4x, 27 drafts) = 2.1 -- Mid-draft player with mid outcome -- no edge either way
  - N. Collier (MIN, 0.0x, 1300 drafts) = 4.55 -- High-draft player delivered as expected
  - K. McBride (MIN, 0.7x, 168 drafts) = 3.29 -- High-draft player delivered as expected
  - C. Gray (LVA, 0.8x, 179 drafts) = 2.63 -- Outcome roughly matched draft position and signals
  - O. Sims (DAL, 1.3x, 58 drafts) = 1.94 -- Outcome roughly matched draft position and signals
  - B. Carleton (POR, 1.9x, 80 drafts) = 1.56 -- Outcome roughly matched draft position and signals
  - K. Bell (LVA, 3.0x, 25 drafts) = 1.21 -- Mid-draft player with mid outcome -- no edge either way
  - N. Mack (PHO, 1.6x, 8 drafts) = 1.87 -- Outcome roughly matched draft position and signals
  - J. Young (LVA, 0.3x, 244 drafts) = 2.53 -- Outcome roughly matched draft position and signals
  - K. Copper (PHO, 1.1x, 10 drafts) = 1.82 -- Mid-draft player with mid outcome -- no edge either way
  - A. Boston (IND, 0.2x, 341 drafts) = 2.48 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-09-26

**Players**: 20 HV
 | **Score range**: 1.20 -- 5.80 (median 3.16)

**Leaderboard**: top score 49.33, floor 46.10, median 47.36

**Winner** (score 49.33):
  - L. Hull (3.8x) = 14.75
  - A. Thomas (1.9000000000000001x) = 11.03
  - N. Smith (3.6x) = 12.19
  - K. McBride (2.0999999999999996x) = 6.15
  - C. Williams (1.6x) = 5.22
  - **Game stack**: team 5: 2 players

**Field ownership** (top-20 entries):
  - N. Smith (4x/3.2x/3.8x/3.6x/3.4x): 18/20 = 90%, avg 11.85
  - L. Hull (3x/3.6x/3.2x/3.8x/3.4x): 17/20 = 85%, avg 13.06
  - A. Thomas (1.9x/2.1x/1.5x): 14/20 = 70%, avg 10.61
  - N. Hiedeman (3.1x/2.9x/3.3x/2.7x): 7/20 = 35%, avg 10.07
  - A. Wilson (1.6x/2x): 6/20 = 30%, avg 6.11
  - S. Sabally (2.2x): 5/20 = 25%, avg 5.99
  - N. Collier (1.6x/1.2x/2x/1.4x): 5/20 = 25%, avg 5.51
  - K. McBride (2.1x/2.3x/2.5x/2.7x): 4/20 = 20%, avg 7.02

### Outcome Classification

**(A) Correctly priced** (20 players):
  - L. Hull (IND, 1.8x, 63 drafts) = 3.88 -- High-draft player delivered as expected
  - M. Kliundikova (TOR, 3.0x, 15 drafts) = 2.77 -- Mid-draft player with mid outcome -- no edge either way
  - N. Smith (LVA, 2.0x, 106 drafts) = 3.39 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.1x, 459 drafts) = 5.8 -- High-draft player delivered as expected
  - K. Copper (PHO, 1.1x, 42 drafts) = 3.72 -- Mid-draft player with mid outcome -- no edge either way
  - N. Hiedeman (SEA, 1.5x, 97 drafts) = 3.25 -- High-draft player delivered as expected
  - C. Gray (LVA, 0.8x, 127 drafts) = 3.35 -- High-draft player delivered as expected
  - J. Young (LVA, 0.3x, 181 drafts) = 3.89 -- High-draft player delivered as expected
  - K. McBride (MIN, 0.7x, 202 drafts) = 2.93 -- Outcome roughly matched draft position and signals
  - C. Williams (MIN, 0.4x, 216 drafts) = 3.26 -- High-draft player delivered as expected
  - D. Evans (LVA, 2.4x, 8 drafts) = 1.64 -- Outcome roughly matched draft position and signals
  - D. Bonner (PHO, 1.5x, 31 drafts) = 2.06 -- Mid-draft player with mid outcome -- no edge either way
  - S. Sabally (NYL, 0.6x, 284 drafts) = 2.72 -- Outcome roughly matched draft position and signals
  - M. Akoa Makani (PHO, 2.0x, 23 drafts) = 1.74 -- Mid-draft player with mid outcome -- no edge either way
  - M. Timpson (IND, 3.0x, 1 drafts) = 1.37 -- Low-draft player correctly faded by the field
  - N. Collier (MIN, 0.0x, 2000 drafts) = 3.36 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 4100 drafts) = 3.16 -- High-draft player delivered as expected
  - K. Mitchell (IND, 0.4x, 260 drafts) = 2.63 -- Outcome roughly matched draft position and signals
  - K. Westbeld (PHO, 3.0x, 16 drafts) = 1.2 -- Mid-draft player with mid outcome -- no edge either way
  - A. Boston (IND, 0.2x, 222 drafts) = 2.67 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-09-28

**Players**: 19 HV
 | **Score range**: 1.15 -- 6.72 (median 2.89)

**Leaderboard**: top score 51.33, floor 48.98, median 49.40

**Winner** (score 51.33):
  - A. Wilson (2x) = 13.45
  - A. Boston (2x) = 11.20
  - C. Williams (2x) = 8.15
  - K. McBride (2.0999999999999996x) = 10.46
  - D. Bonner (2.7x) = 8.07
  - **Game stack**: team 5: 2 players

**Field ownership** (top-20 entries):
  - A. Wilson (1.8x/2x): 20/20 = 100%, avg 13.38
  - A. Boston (1.6x/1.8x/2x): 20/20 = 100%, avg 10.58
  - K. McBride (1.9x/2.3x/2.7x/2.1x/2.5x): 20/20 = 100%, avg 11.15
  - J. Young (1.9x/2.1x/1.5x/1.7x): 12/20 = 60%, avg 8.27
  - C. Williams (1.6x/1.8x/2x/2.2x): 10/20 = 50%, avg 7.26
  - S. Sabally (1.8x/2x): 8/20 = 40%, avg 6.50
  - L. Hull (3.2x/3x): 4/20 = 20%, avg 6.49
  - J. Shepard (2.5x): 2/20 = 10%, avg 6.75

### Outcome Classification

**(A) Correctly priced** (19 players):
  - A. Wilson (LVA, 0.0x, 3800 drafts) = 6.72 -- High-draft player delivered as expected
  - K. McBride (MIN, 0.7x, 299 drafts) = 4.98 -- High-draft player delivered as expected
  - A. Boston (IND, 0.2x, 208 drafts) = 5.6 -- High-draft player delivered as expected
  - D. Bonner (PHO, 1.5x, 47 drafts) = 2.99 -- Mid-draft player with mid outcome -- no edge either way
  - J. Young (LVA, 0.3x, 215 drafts) = 4.51 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.4x, 409 drafts) = 4.08 -- High-draft player delivered as expected
  - J. Shepard (DAL, 1.3x, 156 drafts) = 2.7 -- Outcome roughly matched draft position and signals
  - A. Thomas (PHO, 0.1x, 1200 drafts) = 4.19 -- High-draft player delivered as expected
  - S. Sabally (NYL, 0.6x, 491 drafts) = 3.33 -- High-draft player delivered as expected
  - O. Sims (DAL, 1.3x, 5 drafts) = 2.56 -- Outcome roughly matched draft position and signals
  - C. Gray (LVA, 0.8x, 148 drafts) = 2.89 -- Outcome roughly matched draft position and signals
  - L. Hull (IND, 1.8x, 177 drafts) = 2.13 -- Outcome roughly matched draft position and signals
  - K. Mitchell (IND, 0.4x, 201 drafts) = 3.13 -- High-draft player delivered as expected
  - M. Kliundikova (TOR, 3.0x, 28 drafts) = 1.3 -- Mid-draft player with mid outcome -- no edge either way
  - A. Smith (DAL, 0.7x, 221 drafts) = 2.34 -- Outcome roughly matched draft position and signals
  - S. Whitcomb (PHO, 1.7x, 138 drafts) = 1.61 -- Outcome roughly matched draft position and signals
  - B. Carleton (POR, 1.9x, 129 drafts) = 1.15 -- High-draft player underperformed -- field took the loss equally
  - N. Mack (PHO, 1.6x, 32 drafts) = 1.22 -- Mid-draft player with mid outcome -- no edge either way
  - N. Hiedeman (SEA, 1.5x, 169 drafts) = 1.24 -- High-draft player underperformed -- field took the loss equally

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-09-30

**Players**: 18 HV
 | **Score range**: 0.00 -- 7.50 (median 1.41)

**Leaderboard**: top score 56.83, floor 54.42, median 54.42

**Winner** (score 56.83):
  - A. Wilson (2x) = 15.00
  - J. Young (2.1x) = 14.93
  - C. Gray (2.4000000000000004x) = 10.65
  - O. Sims (2.7x) = 9.61
  - N. Howard (2.2x) = 6.65
  - **Game stack**: team 1: 3 players

**Field ownership** (top-20 entries):
  - A. Wilson (2x): 20/20 = 100%, avg 15.00
  - J. Young (1.9x/2.1x/1.7x/1.5x): 20/20 = 100%, avg 14.43
  - C. Gray (2.4x/2x/2.2x/2.6x): 20/20 = 100%, avg 10.65
  - O. Sims (2.9x/2.5x/2.7x): 19/20 = 95%, avg 9.53
  - L. Hull (3.2x/3x): 12/20 = 60%, avg 4.26
  - N. Howard (2.4x/2.8x/2.2x/2.6x): 7/20 = 35%, avg 7.43
  - S. Peddy (4.2x): 1/20 = 5%, avg 9.64
  - B. Turner (4.2x): 1/20 = 5%, avg 4.24

### Outcome Classification

**(A) Correctly priced** (18 players):
  - J. Young (LVA, 0.3x, 294 drafts) = 7.11 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 6000 drafts) = 7.5 -- High-draft player delivered as expected
  - C. Gray (LVA, 0.8x, 259 drafts) = 4.44 -- High-draft player delivered as expected
  - O. Sims (DAL, 1.3x, 113 drafts) = 3.56 -- High-draft player delivered as expected
  - N. Howard (MIN, 1.0x, 145 drafts) = 3.02 -- High-draft player delivered as expected
  - M. Gustafson (POR, 3.0x, 1 drafts) = 1.28 -- Low-draft player correctly faded by the field
  - A. Boston (IND, 0.2x, 419 drafts) = 2.86 -- Outcome roughly matched draft position and signals
  - J. Loyd (LVA, 1.1x, 158 drafts) = 1.79 -- Outcome roughly matched draft position and signals
  - L. Hull (IND, 1.8x, 240 drafts) = 1.41 -- High-draft player underperformed -- field took the loss equally
  - N. Smith (LVA, 2.0x, 161 drafts) = 1.31 -- High-draft player underperformed -- field took the loss equally
  - B. Turner (LVA, 3.0x, 4 drafts) = 1.01 -- Low-draft player correctly faded by the field
  - K. Mitchell (IND, 0.4x, 401 drafts) = 1.91 -- Outcome roughly matched draft position and signals
  - D. Evans (LVA, 2.4x, 87 drafts) = 0.06 -- High-draft player underperformed -- field took the loss equally
  - A. Nye (ATL, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - K. Bell (LVA, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - M. Timpson (IND, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - K. Stokes (GSV, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - S. Cunningham (IND, 1.8x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-10-03

**Players**: 19 HV
 | **Score range**: 0.00 -- 5.23 (median 2.06)

**Leaderboard**: top score 56.08, floor 54.38, median 54.56

**Winner** (score 56.08):
  - A. Wilson (2x) = 10.46
  - D. Evans (4.2x) = 19.91
  - C. Gray (2.4000000000000004x) = 8.26
  - D. Bonner (2.9x) = 7.18
  - K. Copper (2.3x) = 10.27
  - **Game stack**: team 1: 3 players, team 6: 2 players

**Field ownership** (top-20 entries):
  - D. Evans (3.8x/4x/4.2x/3.6x): 20/20 = 100%, avg 17.68
  - K. Copper (2.3x/3.1x/2.7x/2.9x/2.5x): 20/20 = 100%, avg 11.65
  - A. Wilson (1.8x/2x/1.4x): 18/20 = 90%, avg 10.11
  - S. Sabally (2.6x/2.4x/2x/1.8x/2.2x): 12/20 = 60%, avg 7.72
  - A. Thomas (1.9x/2.1x/1.3x): 10/20 = 50%, avg 7.75
  - C. Gray (2.8x/2.6x/2.4x/2x/2.2x): 9/20 = 45%, avg 8.42
  - D. Bonner (2.9x/3.1x/3.3x): 8/20 = 40%, avg 7.61
  - J. Loyd (2.3x/2.7x): 3/20 = 15%, avg 6.48

### Outcome Classification

**(A) Correctly priced** (19 players):
  - D. Evans (LVA, 2.4x, 73 drafts) = 4.74 -- High-draft player delivered as expected
  - K. Copper (PHO, 1.1x, 176 drafts) = 4.46 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 6700 drafts) = 5.23 -- High-draft player delivered as expected
  - C. Gray (LVA, 0.8x, 246 drafts) = 3.44 -- High-draft player delivered as expected
  - S. Sabally (NYL, 0.6x, 318 drafts) = 3.53 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.1x, 553 drafts) = 4.17 -- High-draft player delivered as expected
  - D. Bonner (PHO, 1.5x, 118 drafts) = 2.47 -- Outcome roughly matched draft position and signals
  - M. Akoa Makani (PHO, 2.0x, 71 drafts) = 2.06 -- Outcome roughly matched draft position and signals
  - J. Loyd (LVA, 1.1x, 157 drafts) = 2.53 -- Outcome roughly matched draft position and signals
  - J. Young (LVA, 0.3x, 377 drafts) = 2.47 -- Outcome roughly matched draft position and signals
  - N. Smith (LVA, 2.0x, 113 drafts) = 1.17 -- High-draft player underperformed -- field took the loss equally
  - N. Mack (PHO, 1.6x, 85 drafts) = 1.3 -- High-draft player underperformed -- field took the loss equally
  - S. Whitcomb (PHO, 1.7x, 77 drafts) = 1.2 -- High-draft player underperformed -- field took the loss equally
  - K. Bell (LVA, 3.0x, 62 drafts) = 0.69 -- High-draft player underperformed -- field took the loss equally
  - M. Gustafson (POR, 3.0x, 2 drafts) = 0.57 -- Low-draft player correctly faded by the field
  - K. Westbeld (PHO, 3.0x, 63 drafts) = 0.53 -- High-draft player underperformed -- field took the loss equally
  - A. Nye (ATL, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - L. Held (PHO, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - K. Stokes (GSV, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-10-05

**Players**: 18 HV
 | **Score range**: 0.09 -- 5.61 (median 2.01)

**Leaderboard**: top score 47.32, floor 46.24, median 46.71

**Winner** (score 47.32):
  - A. Wilson (2x) = 10.05
  - J. Young (2.1x) = 11.77
  - C. Gray (2.4000000000000004x) = 11.20
  - K. Copper (2.5x) = 7.96
  - J. Loyd (2.3x) = 6.34
  - **Game stack**: team 1: 4 players

**Field ownership** (top-20 entries):
  - A. Wilson (1.6x/1.8x/2x): 20/20 = 100%, avg 9.85
  - J. Young (1.9x/2.1x/2.3x): 20/20 = 100%, avg 11.44
  - C. Gray (2.8x/2.6x/2.4x/2x/2.2x): 20/20 = 100%, avg 11.01
  - K. Copper (2.9x/2.3x/2.5x/2.7x): 20/20 = 100%, avg 7.83
  - J. Loyd (2.9x/2.3x/2.5x/2.7x): 13/20 = 65%, avg 6.85
  - S. Sabally (1.8x/2x): 4/20 = 20%, avg 5.75
  - N. Mack (2.8x): 2/20 = 10%, avg 5.64
  - M. Akoa Makani (3.8x): 1/20 = 5%, avg 8.42

### Outcome Classification

**(A) Correctly priced** (18 players):
  - C. Gray (LVA, 0.8x, 194 drafts) = 4.67 -- High-draft player delivered as expected
  - J. Young (LVA, 0.3x, 250 drafts) = 5.61 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 5400 drafts) = 5.03 -- High-draft player delivered as expected
  - K. Copper (PHO, 1.1x, 185 drafts) = 3.18 -- High-draft player delivered as expected
  - M. Akoa Makani (PHO, 2.0x, 79 drafts) = 2.22 -- Outcome roughly matched draft position and signals
  - J. Loyd (LVA, 1.1x, 143 drafts) = 2.76 -- Outcome roughly matched draft position and signals
  - S. Sabally (NYL, 0.6x, 263 drafts) = 2.95 -- Outcome roughly matched draft position and signals
  - N. Mack (PHO, 1.6x, 85 drafts) = 2.01 -- Outcome roughly matched draft position and signals
  - A. Thomas (PHO, 0.1x, 433 drafts) = 2.55 -- Outcome roughly matched draft position and signals
  - N. Smith (LVA, 2.0x, 96 drafts) = 1.03 -- High-draft player underperformed -- field took the loss equally
  - D. Evans (LVA, 2.4x, 114 drafts) = 0.86 -- High-draft player underperformed -- field took the loss equally
  - D. Bonner (PHO, 1.5x, 89 drafts) = 0.81 -- High-draft player underperformed -- field took the loss equally
  - S. Whitcomb (PHO, 1.7x, 99 drafts) = 0.42 -- High-draft player underperformed -- field took the loss equally
  - K. Williams (PHO, 2.5x, 4 drafts) = 0.32 -- Low-draft player correctly faded by the field
  - K. Westbeld (PHO, 3.0x, 58 drafts) = 0.27 -- High-draft player underperformed -- field took the loss equally
  - K. Bell (LVA, 3.0x, 68 drafts) = 0.26 -- High-draft player underperformed -- field took the loss equally
  - M. Gustafson (POR, 3.0x, 1 drafts) = 0.22 -- Low-draft player correctly faded by the field
  - C. Parker-Tyus (LVA, 3.0x, 17 drafts) = 0.09 -- Mid-draft player with mid outcome -- no edge either way

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-10-08

**Players**: 19 HV
 | **Score range**: 0.00 -- 6.92 (median 1.16)

**Leaderboard**: top score 55.92, floor 53.78, median 55.17

**Winner** (score 55.92):
  - A. Wilson (2x) = 13.84
  - J. Young (2.1x) = 12.20
  - D. Bonner (3.1x) = 13.78
  - C. Gray (2.2x) = 8.35
  - J. Loyd (2.3x) = 7.75
  - **Game stack**: team 1: 4 players

**Field ownership** (top-20 entries):
  - A. Wilson (1.8x/2x/1.4x): 20/20 = 100%, avg 13.49
  - J. Young (1.9x/2.3x/1.5x/2.1x/1.7x): 20/20 = 100%, avg 11.73
  - D. Bonner (3.5x/2.7x/3.1x/2.9x/3.3x): 20/20 = 100%, avg 13.15
  - C. Gray (2.4x/2x/2.2x/2.6x): 18/20 = 90%, avg 8.61
  - J. Loyd (2.3x/3.1x/2.7x/2.9x/2.5x): 16/20 = 80%, avg 8.51
  - S. Sabally (1.8x/2x): 6/20 = 30%, avg 6.49

### Outcome Classification

**(A) Correctly priced** (19 players):
  - D. Bonner (PHO, 1.5x, 126 drafts) = 4.44 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 6600 drafts) = 6.92 -- High-draft player delivered as expected
  - J. Young (LVA, 0.3x, 399 drafts) = 5.81 -- High-draft player delivered as expected
  - C. Gray (LVA, 0.8x, 288 drafts) = 3.8 -- High-draft player delivered as expected
  - J. Loyd (LVA, 1.1x, 182 drafts) = 3.37 -- High-draft player delivered as expected
  - S. Sabally (NYL, 0.6x, 224 drafts) = 3.3 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.1x, 514 drafts) = 3.92 -- High-draft player delivered as expected
  - K. Copper (PHO, 1.1x, 265 drafts) = 2.3 -- Outcome roughly matched draft position and signals
  - N. Smith (LVA, 2.0x, 97 drafts) = 1.6 -- Outcome roughly matched draft position and signals
  - D. Evans (LVA, 2.4x, 100 drafts) = 1.16 -- High-draft player underperformed -- field took the loss equally
  - S. Whitcomb (PHO, 1.7x, 108 drafts) = 0.64 -- High-draft player underperformed -- field took the loss equally
  - M. Akoa Makani (PHO, 2.0x, 78 drafts) = 0.57 -- High-draft player underperformed -- field took the loss equally
  - K. Bell (LVA, 3.0x, 66 drafts) = 0.44 -- High-draft player underperformed -- field took the loss equally
  - K. Westbeld (PHO, 3.0x, 78 drafts) = 0.42 -- High-draft player underperformed -- field took the loss equally
  - N. Mack (PHO, 1.6x, 97 drafts) = 0.57 -- High-draft player underperformed -- field took the loss equally
  - M. Gustafson (POR, 3.0x, 2 drafts) = 0.06 -- Low-draft player correctly faded by the field
  - L. Held (PHO, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - K. Stokes (GSV, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - A. Nye (ATL, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2025-10-10

**Players**: 18 HV
 | **Score range**: 0.00 -- 6.04 (median 1.81)

**Leaderboard**: top score 46.52, floor 46.35, median 46.35

**Winner** (score 46.52):
  - A. Wilson (2x) = 12.09
  - C. Gray (2.6x) = 11.23
  - J. Young (1.9000000000000001x) = 7.78
  - K. Copper (2.5x) = 8.80
  - M. Akoa Makani (3.2x) = 6.63
  - **Game stack**: team 1: 3 players, team 6: 2 players

**Field ownership** (top-20 entries):
  - A. Wilson (2x): 20/20 = 100%, avg 12.09
  - C. Gray (2.4x/2.6x): 20/20 = 100%, avg 10.41
  - J. Young (1.9x/2.1x): 20/20 = 100%, avg 8.56
  - K. Copper (2.5x): 20/20 = 100%, avg 8.80
  - D. Evans (3.6x): 11/20 = 55%, avg 6.50
  - M. Akoa Makani (3.2x): 9/20 = 45%, avg 6.63

### Outcome Classification

**(A) Correctly priced** (18 players):
  - C. Gray (LVA, 0.8x, 245 drafts) = 4.32 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 7000 drafts) = 6.04 -- High-draft player delivered as expected
  - K. Copper (PHO, 1.1x, 222 drafts) = 3.52 -- High-draft player delivered as expected
  - J. Young (LVA, 0.3x, 331 drafts) = 4.09 -- High-draft player delivered as expected
  - J. Loyd (LVA, 1.1x, 203 drafts) = 2.72 -- Outcome roughly matched draft position and signals
  - M. Akoa Makani (PHO, 2.0x, 82 drafts) = 2.07 -- Outcome roughly matched draft position and signals
  - D. Evans (LVA, 2.4x, 104 drafts) = 1.81 -- Outcome roughly matched draft position and signals
  - D. Bonner (PHO, 1.5x, 182 drafts) = 2.25 -- Outcome roughly matched draft position and signals
  - A. Thomas (PHO, 0.1x, 423 drafts) = 3.03 -- High-draft player delivered as expected
  - N. Smith (LVA, 2.0x, 109 drafts) = 1.11 -- High-draft player underperformed -- field took the loss equally
  - K. Bell (LVA, 3.0x, 65 drafts) = 0.68 -- High-draft player underperformed -- field took the loss equally
  - K. Westbeld (PHO, 3.0x, 64 drafts) = 0.59 -- High-draft player underperformed -- field took the loss equally
  - S. Whitcomb (PHO, 1.7x, 112 drafts) = 0.78 -- High-draft player underperformed -- field took the loss equally
  - L. Held (PHO, 3.0x, 64 drafts) = 0.41 -- High-draft player underperformed -- field took the loss equally
  - M. Gustafson (POR, 3.0x, 1 drafts) = 0.09 -- Low-draft player correctly faded by the field
  - N. Mack (PHO, 1.6x, None drafts) = None -- Low-draft player correctly faded by the field
  - A. Nye (ATL, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - K. Stokes (GSV, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2026-05-08

**Players**: 19 HV
 | **Score range**: 2.00 -- 5.67 (median 2.86)

**Leaderboard**: top score 37.14, floor 35.53, median 36.01

**Winner** (score 37.14):
  - S. Citron (2x) = 10.62
  - B. Stewart (1.8x) = 10.21
  - V. Burton (1.6x) = 6.28
  - M. Mabrey (1.4x) = 4.96
  - S. Austin (1.2x) = 5.06
  - **Game stack**: team 7: 2 players

**Field ownership** (top-20 entries):
  - S. Citron (1.6x/1.8x/2x/1.4x): 20/20 = 100%, avg 8.86
  - B. Stewart (1.6x/1.8x/2x/1.4x): 20/20 = 100%, avg 10.90
  - V. Burton (1.6x/1.4x/1.2x/2x/1.8x): 19/20 = 95%, avg 6.28
  - K. Iriafen (1.6x/1.2x): 12/20 = 60%, avg 3.96
  - S. Austin (1.2x/2x/1.8x/1.4x): 11/20 = 55%, avg 5.83
  - M. Mabrey (1.6x/1.2x/1.8x/1.4x): 8/20 = 40%, avg 5.23
  - M. Johannes (1.2x/1.8x): 6/20 = 30%, avg 6.24
  - J. Salaün (1.6x/1.4x): 2/20 = 10%, avg 5.06

### Outcome Classification

**(A) Correctly priced** (19 players):
  - B. Stewart (NYL, 0.0x, 3600 drafts) = 5.67 -- High-draft player delivered as expected
  - S. Citron (WAS, 0.0x, 412 drafts) = 5.31 -- High-draft player delivered as expected
  - S. Austin (WAS, 0.0x, 145 drafts) = 4.22 -- High-draft player delivered as expected
  - V. Burton (GSV, 0.0x, 634 drafts) = 3.92 -- High-draft player delivered as expected
  - M. Johannes (NYL, 0.0x, 23 drafts) = 3.9 -- Mid-draft player with mid outcome -- no edge either way
  - M. Mabrey (TOR, 0.0x, 174 drafts) = 3.55 -- High-draft player delivered as expected
  - J. Salaün (GSV, 0.0x, 172 drafts) = 3.37 -- High-draft player delivered as expected
  - K. Iriafen (WAS, 0.0x, 296 drafts) = 3.05 -- High-draft player delivered as expected
  - D. Malonga (SEA, 0.0x, 134 drafts) = 2.87 -- Outcome roughly matched draft position and signals
  - J. Melbourne (SEA, 0.0x, 57 drafts) = 2.86 -- Outcome roughly matched draft position and signals
  - K. Stokes (GSV, 0.0x, 75 drafts) = 2.52 -- Outcome roughly matched draft position and signals
  - K. Chen (GSV, 0.0x, 37 drafts) = 2.46 -- Mid-draft player with mid outcome -- no edge either way
  - K. Thornton (GSV, 0.0x, 109 drafts) = 2.44 -- Outcome roughly matched draft position and signals
  - Z. Cooke (SEA, 0.0x, 90 drafts) = 2.43 -- Outcome roughly matched draft position and signals
  - B. Sykes (TOR, 0.0x, 303 drafts) = 2.32 -- Outcome roughly matched draft position and signals
  - N. Sabally (TOR, 0.0x, 3 drafts) = 2.25 -- Outcome roughly matched draft position and signals
  - G. Williams (GSV, 0.0x, 376 drafts) = 2.1 -- Outcome roughly matched draft position and signals
  - J. Jones (NYL, 0.0x, 328 drafts) = 2.02 -- Outcome roughly matched draft position and signals
  - B. Griner (CON, 0.0x, 485 drafts) = 2.0 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2026-05-09

**Players**: 20 HV
 | **Score range**: 2.98 -- 5.86 (median 3.55)

**Leaderboard**: top score 40.77, floor 36.00, median 36.27

**Winner** (score 40.77):
  - S. Diggins (2x) = 11.73
  - P. Bueckers (1.8x) = 7.68
  - A. Thomas (1.6x) = 8.69
  - A. Boston (1.4x) = 6.78
  - K. Mitchell (1.2x) = 5.90
  - **Game stack**: team 3: 2 players

**Field ownership** (top-20 entries):
  - A. Thomas (1.6x/1.8x/2x/1.4x): 19/20 = 95%, avg 9.32
  - A. Boston (1.6x/1.4x/1.2x/2x/1.8x): 17/20 = 85%, avg 7.40
  - P. Bueckers (1.6x/1.4x/1.2x/2x/1.8x): 16/20 = 80%, avg 6.93
  - K. Mitchell (1.6x/1.2x/1.8x/1.4x): 16/20 = 80%, avg 6.39
  - A. Wilson (1.8x/2x): 15/20 = 75%, avg 6.91
  - S. Diggins (1.2x/2x/1.4x/1.8x): 7/20 = 35%, avg 8.71
  - A. Gray (1.6x/1.2x/1.8x): 4/20 = 20%, avg 5.72
  - R. Howard (1.8x/1.4x/1.2x): 3/20 = 15%, avg 5.20

### Outcome Classification

**(A) Correctly priced** (16 players):
  - S. Diggins (CHI, 0.0x, 58 drafts) = 5.86 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.0x, 295 drafts) = 5.43 -- High-draft player delivered as expected
  - K. Mitchell (IND, 0.0x, 14 drafts) = 4.92 -- Mid-draft player with mid outcome -- no edge either way
  - A. Boston (IND, 0.0x, 33 drafts) = 4.84 -- Mid-draft player with mid outcome -- no edge either way
  - P. Bueckers (DAL, 0.0x, 352 drafts) = 4.27 -- High-draft player delivered as expected
  - K. Cardoso (CHI, 0.0x, 42 drafts) = 3.94 -- Mid-draft player with mid outcome -- no edge either way
  - A. Gray (ATL, 0.0x, 212 drafts) = 3.69 -- High-draft player delivered as expected
  - R. Howard (ATL, 0.0x, 85 drafts) = 3.55 -- High-draft player delivered as expected
  - J. Sheldon (CHI, 0.0x, 21 drafts) = 3.49 -- Mid-draft player with mid outcome -- no edge either way
  - A. Wilson (LVA, 0.0x, 4800 drafts) = 3.48 -- High-draft player delivered as expected
  - N. Hillmon (ATL, 0.0x, 43 drafts) = 3.44 -- Mid-draft player with mid outcome -- no edge either way
  - A. Reese (ATL, 0.0x, 699 drafts) = 3.38 -- High-draft player delivered as expected
  - O. Sims (DAL, 0.0x, 58 drafts) = 3.2 -- High-draft player delivered as expected
  - R. Jackson (CHI, 0.0x, 51 drafts) = 3.16 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.0x, 114 drafts) = 3.13 -- High-draft player delivered as expected
  - C. Clark (IND, 0.0x, 1000 drafts) = 2.98 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (4 players):
  - J. Shepard (DAL, 0.0x, 2 drafts) = 4.44 -- Above-expectation outcome, ambiguous whether knowable
  - O. Miles (MIN, 0.0x, 9 drafts) = 4.34 -- Above-expectation outcome, ambiguous whether knowable
  - N. Mack (PHO, 0.0x, 1 drafts) = 3.46 -- Above-expectation outcome, ambiguous whether knowable
  - D. Bonner (PHO, 0.0x, 2 drafts) = 3.33 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 4 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2026-05-10

**Players**: 20 HV
 | **Score range**: 1.90 -- 5.33 (median 3.63)

**Leaderboard**: top score 72.42, floor 64.23, median 64.56

**Winner** (score 72.42):
  - A. Morrow (5x) = 16.91
  - C. Carter (4.5x) = 16.33
  - F. Johnson (3.7x) = 12.16
  - J. Young (3.3x) = 17.60
  - G. Williams (2.5x) = 9.43
  - **Game stack**: team 1: 2 players

**Field ownership** (top-20 entries):
  - A. Morrow (4.4x/4.6x/5x/4.2x): 20/20 = 100%, avg 15.01
  - J. Young (3.5x/3.7x/3.9x/3.3x): 20/20 = 100%, avg 20.32
  - F. Johnson (3.7x/3.9x): 17/20 = 85%, avg 12.74
  - K. Copper (4.4x/4.6x/4.2x): 15/20 = 75%, avg 7.29
  - C. Gray (4.4x/4x/4.2x): 13/20 = 65%, avg 8.72
  - G. Williams (2.9x/2.5x/3.3x/2.7x): 5/20 = 25%, avg 11.09
  - C. Carter (4.3x/4.5x): 3/20 = 15%, avg 16.09
  - K. Iriafen (2.1x): 2/20 = 10%, avg 9.01

### Outcome Classification

**(A) Correctly priced** (19 players):
  - J. Young (LVA, 1.9x, 828 drafts) = 5.33 -- High-draft player delivered as expected
  - L. Amihere (GSV, 3.0x, 17 drafts) = 3.71 -- Mid-draft player with mid outcome -- no edge either way
  - C. Carter (LVA, 2.7x, 42 drafts) = 3.63 -- Mid-draft player with mid outcome -- no edge either way
  - A. Morrow (CON, 3.0x, 16 drafts) = 3.38 -- Mid-draft player with mid outcome -- no edge either way
  - F. Johnson (SEA, 2.1x, 21 drafts) = 3.29 -- Mid-draft player with mid outcome -- no edge either way
  - G. Williams (GSV, 1.3x, 98 drafts) = 3.77 -- High-draft player delivered as expected
  - S. Talbot (LVA, 3.0x, 1 drafts) = 2.27 -- Outcome roughly matched draft position and signals
  - V. Burton (GSV, 0.2x, 279 drafts) = 5.11 -- High-draft player delivered as expected
  - J. Melbourne (SEA, 0.7x, 61 drafts) = 4.15 -- High-draft player delivered as expected
  - B. Turner (LVA, 3.0x, 5 drafts) = 2.25 -- Outcome roughly matched draft position and signals
  - K. Iriafen (WAS, 0.5x, 152 drafts) = 4.29 -- High-draft player delivered as expected
  - J. Salaün (GSV, 0.4x, 149 drafts) = 4.41 -- High-draft player delivered as expected
  - G. Amoore (WAS, 3.0x, 5 drafts) = 2.04 -- Outcome roughly matched draft position and signals
  - C. Gray (LVA, 2.8x, 293 drafts) = 2.05 -- Outcome roughly matched draft position and signals
  - N. Smith (LVA, 1.1x, 36 drafts) = 3.13 -- Mid-draft player with mid outcome -- no edge either way
  - B. Griner (CON, 1.5x, 11 drafts) = 2.7 -- Mid-draft player with mid outcome -- no edge either way
  - K. Thornton (GSV, 1.0x, 82 drafts) = 3.15 -- High-draft player delivered as expected
  - M. Johannes (NYL, 0.2x, 125 drafts) = 4.21 -- High-draft player delivered as expected
  - R. Gardner (NYL, 2.8x, 2 drafts) = 1.9 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - P. Astier (NYL, 1.5x, 2 drafts) = 4.69 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2026-05-12

**Players**: 20 HV
 | **Score range**: 1.78 -- 4.98 (median 3.32)

**Leaderboard**: top score 65.06, floor 62.96, median 63.74

**Winner** (score 65.06):
  - J. Jones (3.3x) = 11.26
  - J. Canada (3.2x) = 15.94
  - R. Gardner (3.7x) = 8.88
  - K. Copper (4.4x) = 18.70
  - N. Howard (4.2x) = 10.28
  - **Game stack**: team 4: 2 players

**Field ownership** (top-20 entries):
  - J. Jones (3.1x/3.3x): 20/20 = 100%, avg 10.92
  - J. Canada (3.2x/3x): 20/20 = 100%, avg 15.39
  - K. Copper (4.4x/4.6x/4.2x): 20/20 = 100%, avg 18.87
  - N. Howard (4.4x/4.2x): 20/20 = 100%, avg 10.37
  - B. Stewart (1.8x/2x): 11/20 = 55%, avg 9.16
  - R. Gardner (3.7x): 2/20 = 10%, avg 8.88
  - N. Coffey (2.9x/2.7x): 2/20 = 10%, avg 7.42
  - B. Laney-Hamilton (3.8x): 2/20 = 10%, avg 5.54

### Outcome Classification

**(A) Correctly priced** (20 players):
  - K. Copper (PHO, 3.0x, 123 drafts) = 4.25 -- High-draft player delivered as expected
  - J. Canada (ATL, 1.4x, 39 drafts) = 4.98 -- Mid-draft player with mid outcome -- no edge either way
  - N. Howard (MIN, 3.0x, 19 drafts) = 2.45 -- Mid-draft player with mid outcome -- no edge either way
  - B. Carleton (POR, 0.6x, 30 drafts) = 4.56 -- Mid-draft player with mid outcome -- no edge either way
  - C. Leite (POR, 0.8x, 39 drafts) = 4.1 -- Mid-draft player with mid outcome -- no edge either way
  - J. Jones (NYL, 1.3x, 765 drafts) = 3.41 -- High-draft player delivered as expected
  - P. Astier (NYL, 0.4x, 231 drafts) = 4.45 -- High-draft player delivered as expected
  - R. Gardner (NYL, 2.1x, 204 drafts) = 2.4 -- Outcome roughly matched draft position and signals
  - B. Stewart (NYL, 0.0x, 2400 drafts) = 4.62 -- High-draft player delivered as expected
  - D. Bonner (PHO, 0.8x, 226 drafts) = 3.28 -- High-draft player delivered as expected
  - N. Mack (PHO, 0.8x, 188 drafts) = 3.18 -- High-draft player delivered as expected
  - K. Linskens (PHO, 3.0x, 2 drafts) = 1.78 -- Outcome roughly matched draft position and signals
  - N. Coffey (MIN, 1.3x, 12 drafts) = 2.65 -- Mid-draft player with mid outcome -- no edge either way
  - A. Gray (ATL, 0.2x, 324 drafts) = 3.82 -- High-draft player delivered as expected
  - M. Johannes (NYL, 0.1x, 310 drafts) = 3.94 -- High-draft player delivered as expected
  - L. Geiselsöder (POR, 1.2x, 7 drafts) = 2.5 -- Outcome roughly matched draft position and signals
  - A. Reese (ATL, 0.4x, 719 drafts) = 3.32 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.5x, 67 drafts) = 3.07 -- High-draft player delivered as expected
  - E. Cechova (MIN, 1.6x, 2 drafts) = 2.1 -- Outcome roughly matched draft position and signals
  - E. Engstler (POR, 2.2x, 4 drafts) = 1.78 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2026-05-13

**Players**: 20 HV
 | **Score range**: 1.98 -- 5.80 (median 3.32)

**Leaderboard**: top score 58.22, floor 50.18, median 51.02

**Winner** (score 58.22):
  - M. Mabrey (2.3x) = 12.42
  - C. Clark (2.4x) = 10.14
  - C. Carter (2.5x) = 14.51
  - D. Hamby (4.4x) = 10.65
  - S. Cunningham (3.9000000000000004x) = 10.49
  - **Game stack**: team 3: 2 players

**Field ownership** (top-20 entries):
  - D. Hamby (4.4x/4.6x/4.2x/4.8x): 17/20 = 85%, avg 10.79
  - C. Clark (2.4x/2.6x): 13/20 = 65%, avg 10.66
  - S. Cunningham (4.3x/4.1x/4.5x/3.9x): 12/20 = 60%, avg 11.43
  - C. Carter (2.3x/2.7x/2.9x/2.1x/2.5x): 11/20 = 55%, avg 14.51
  - C. Gray (3.2x/3.4x/4x/3.8x): 9/20 = 45%, avg 7.71
  - A. Wilson (2.4x/2.2x): 9/20 = 45%, avg 9.89
  - K. Charles (4.4x/5x/4.2x): 8/20 = 40%, avg 9.90
  - R. Burrell (4.2x): 4/20 = 20%, avg 6.67

### Outcome Classification

**(A) Correctly priced** (18 players):
  - C. Carter (LVA, 0.9x, 150 drafts) = 5.8 -- High-draft player delivered as expected
  - K. Stokes (GSV, 2.2x, 16 drafts) = 3.45 -- Mid-draft player with mid outcome -- no edge either way
  - C. Parker-Tyus (LVA, 3.0x, 1 drafts) = 2.59 -- Outcome roughly matched draft position and signals
  - S. Cunningham (IND, 2.7x, 24 drafts) = 2.69 -- Mid-draft player with mid outcome -- no edge either way
  - D. Hamby (LAS, 3.0x, 260 drafts) = 2.42 -- Outcome roughly matched draft position and signals
  - B. Sykes (TOR, 1.1x, 112 drafts) = 3.87 -- High-draft player delivered as expected
  - S. Dolson (SEA, 3.0x, 1 drafts) = 2.36 -- Outcome roughly matched draft position and signals
  - O. Nelson-Ododa (CON, 3.0x, 4 drafts) = 2.3 -- Outcome roughly matched draft position and signals
  - D. Malonga (SEA, 1.0x, 363 drafts) = 3.78 -- High-draft player delivered as expected
  - K. Charles (GSV, 3.0x, 23 drafts) = 2.25 -- Mid-draft player with mid outcome -- no edge either way
  - C. Clark (IND, 0.6x, 1800 drafts) = 4.23 -- High-draft player delivered as expected
  - K. Rice (TOR, 3.0x, 2 drafts) = 2.05 -- Outcome roughly matched draft position and signals
  - A. Wilson (LVA, 0.4x, 2400 drafts) = 4.16 -- High-draft player delivered as expected
  - J. Allemand (TOR, 3.0x, 3 drafts) = 1.98 -- Outcome roughly matched draft position and signals
  - R. Jackson (CHI, 0.5x, 33 drafts) = 3.58 -- Mid-draft player with mid outcome -- no edge either way
  - C. Gray (LVA, 2.0x, 386 drafts) = 2.16 -- Outcome roughly matched draft position and signals
  - S. Diggins (CHI, 0.0x, 361 drafts) = 4.17 -- High-draft player delivered as expected
  - N. Sabally (TOR, 1.2x, 2 drafts) = 2.59 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (2 players):
  - M. Conde (TOR, 3.0x, 2 drafts) = 3.32 -- High-boost low-draft player who overperformed
  - M. Mabrey (TOR, 0.3x, 44 drafts) = 5.4 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2026-05-14

**Players**: 18 HV
 | **Score range**: 1.86 -- 5.15 (median 2.97)

**Leaderboard**: top score 61.54, floor 56.37, median 56.37

**Winner** (score 61.54):
  - P. Bueckers (2.3x) = 10.92
  - N. Howard (4.2x) = 18.34
  - B. Laney-Hamilton (4.2x) = 7.81
  - M. Siegrist (4.4x) = 15.27
  - A. Smith (3.9000000000000004x) = 9.20
  - **Game stack**: team 12: 3 players

**Field ownership** (top-20 entries):
  - N. Howard (4x/4.2x/4.4x/3.8x/3.6x): 20/20 = 100%, avg 16.77
  - P. Bueckers (2.3x): 18/20 = 90%, avg 10.92
  - B. Laney-Hamilton (4.4x/3.8x/4.2x): 15/20 = 75%, avg 7.26
  - R. Gardner (3.2x/3x): 14/20 = 70%, avg 9.90
  - C. Williams (2.3x): 13/20 = 65%, avg 11.84
  - M. Siegrist (4.4x/4.6x/4.2x/4.8x): 7/20 = 35%, avg 15.27
  - A. Smith (4.3x/4.1x/3.9x/4.7x): 7/20 = 35%, avg 9.87
  - E. Engstler (3.6x): 2/20 = 10%, avg 7.29

### Outcome Classification

**(A) Correctly priced** (17 players):
  - N. Howard (MIN, 2.4x, 25 drafts) = 4.37 -- Mid-draft player with mid outcome -- no edge either way
  - C. Williams (MIN, 0.5x, 219 drafts) = 5.15 -- High-draft player delivered as expected
  - N. Puoch (POR, 3.0x, 27 drafts) = 2.48 -- Mid-draft player with mid outcome -- no edge either way
  - N. Coffey (MIN, 1.0x, 121 drafts) = 4.02 -- High-draft player delivered as expected
  - R. Gardner (NYL, 1.6x, 164 drafts) = 3.11 -- High-draft player delivered as expected
  - A. Smith (DAL, 2.7x, 11 drafts) = 2.36 -- Mid-draft player with mid outcome -- no edge either way
  - P. Bueckers (DAL, 0.3x, 1300 drafts) = 4.75 -- High-draft player delivered as expected
  - M. Gustafson (POR, 3.0x, 39 drafts) = 2.06 -- Mid-draft player with mid outcome -- no edge either way
  - B. Laney-Hamilton (NYL, 2.6x, 166 drafts) = 1.86 -- Outcome roughly matched draft position and signals
  - P. Astier (NYL, 0.2x, 370 drafts) = 3.87 -- High-draft player delivered as expected
  - E. Engstler (POR, 2.0x, 150 drafts) = 2.03 -- Outcome roughly matched draft position and signals
  - O. Sims (DAL, 1.1x, 147 drafts) = 2.5 -- Outcome roughly matched draft position and signals
  - O. Miles (MIN, 0.2x, 358 drafts) = 3.04 -- High-draft player delivered as expected
  - K. McBride (MIN, 1.0x, 218 drafts) = 2.11 -- Outcome roughly matched draft position and signals
  - M. Johannes (NYL, 0.1x, 468 drafts) = 2.94 -- Outcome roughly matched draft position and signals
  - B. Stewart (NYL, 0.0x, 3900 drafts) = 2.97 -- Outcome roughly matched draft position and signals
  - J. Jones (NYL, 0.9x, 302 drafts) = 1.99 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - M. Siegrist (DAL, 3.0x, 3 drafts) = 3.47 -- High-boost low-draft player who overperformed

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2026-05-15

**Players**: 20 HV
 | **Score range**: 2.16 -- 9.48 (median 3.82)

**Leaderboard**: top score 73.32, floor 67.28, median 69.12

**Winner** (score 73.32):
  - A. Wilson (2.3x) = 21.81
  - D. Hamby (3.5x) = 14.32
  - C. Gray (3.3x) = 11.67
  - E. Wheeler (4.4x) = 10.99
  - S. Rivers (4.2x) = 14.53
  - **Game stack**: team 1: 2 players, team 9: 2 players

**Field ownership** (top-20 entries):
  - A. Wilson (2.1x/2.3x): 20/20 = 100%, avg 21.62
  - D. Hamby (3.5x/2.9x/3.1x/3.3x): 20/20 = 100%, avg 13.38
  - S. Rivers (4.4x/4.2x): 14/20 = 70%, avg 14.73
  - C. Gray (3.5x/3.1x/2.9x/3.7x/3.3x): 13/20 = 65%, avg 11.40
  - K. Copper (2.8x/3x): 8/20 = 40%, avg 8.82
  - C. Clark (2.1x/1.7x): 7/20 = 35%, avg 10.53
  - E. Wheeler (4.4x/4.2x): 5/20 = 25%, avg 10.69
  - K. Plum (2.1x/2.3x/2.5x): 5/20 = 25%, avg 14.42

### Outcome Classification

**(A) Correctly priced** (18 players):
  - A. Wilson (LVA, 0.3x, 1900 drafts) = 9.48 -- High-draft player delivered as expected
  - M. Billings (IND, 2.3x, 122 drafts) = 4.03 -- High-draft player delivered as expected
  - K. Plum (LAS, 0.5x, 418 drafts) = 6.38 -- High-draft player delivered as expected
  - D. Hamby (LAS, 1.7x, 371 drafts) = 4.09 -- High-draft player delivered as expected
  - C. Gray (LVA, 1.7x, 191 drafts) = 3.54 -- High-draft player delivered as expected
  - S. Citron (WAS, 0.1x, 235 drafts) = 6.11 -- High-draft player delivered as expected
  - E. Wheeler (LAS, 3.0x, 3 drafts) = 2.5 -- Outcome roughly matched draft position and signals
  - J. Nogic (PHO, 1.0x, 134 drafts) = 4.16 -- High-draft player delivered as expected
  - C. Clark (IND, 0.3x, 1000 drafts) = 5.3 -- High-draft player delivered as expected
  - N. Cloud (CHI, 3.0x, 2 drafts) = 2.39 -- Outcome roughly matched draft position and signals
  - K. Burke (CON, 2.5x, 3 drafts) = 2.64 -- Outcome roughly matched draft position and signals
  - N. Sabally (TOR, 1.0x, 39 drafts) = 3.82 -- Mid-draft player with mid outcome -- no edge either way
  - R. Jackson (CHI, 0.4x, 173 drafts) = 4.75 -- High-draft player delivered as expected
  - B. Sykes (TOR, 0.5x, 60 drafts) = 4.51 -- High-draft player delivered as expected
  - H. Van Lith (CON, 2.2x, 34 drafts) = 2.66 -- Mid-draft player with mid outcome -- no edge either way
  - C. Leger-Walker (CON, 3.0x, 1 drafts) = 2.33 -- Outcome roughly matched draft position and signals
  - L. Hull (IND, 3.0x, 1 drafts) = 2.16 -- Outcome roughly matched draft position and signals
  - N. Ogwumike (LAS, 0.8x, 55 drafts) = 3.81 -- High-draft player delivered as expected

**(C) Unknowable / winners' edge** (2 players):
  - S. Rivers (CON, 3.0x, 2 drafts) = 3.46 -- High-boost low-draft player who overperformed
  - L. Juškaitė (TOR, 0.0x, 1 drafts) = 3.49 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2026-05-17

**Players**: 20 HV
 | **Score range**: 1.92 -- 5.65 (median 3.10)

**Leaderboard**: top score 57.85, floor 51.87, median 52.30

**Winner** (score 57.85):
  - C. Gray (3.1x) = 16.59
  - S. Dolson (3.9000000000000004x) = 6.29
  - N. Cloud (4x) = 8.60
  - K. Rice (4.199999999999999x) = 13.32
  - T. Paopao (4.2x) = 13.04

**Field ownership** (top-20 entries):
  - K. Rice (4x/4.2x/4.8x): 18/20 = 90%, avg 13.25
  - N. Cloud (3.8x/4x/4.2x): 10/20 = 50%, avg 8.73
  - C. Gray (2.9x/2.3x/2.7x/3.1x): 8/20 = 40%, avg 15.25
  - T. Paopao (4.2x): 8/20 = 40%, avg 13.04
  - D. Hamby (2.4x/2.8x/2.6x): 7/20 = 35%, avg 11.81
  - M. Hines-Allen (4.1x/3.7x/3.9x): 7/20 = 35%, avg 9.91
  - K. McBride (2.9x/3.1x/2.7x): 6/20 = 30%, avg 11.02
  - A. Wilson (2x): 5/20 = 25%, avg 5.29

### Outcome Classification

**(A) Correctly priced** (19 players):
  - C. Gray (LVA, 1.1x, 194 drafts) = 5.35 -- High-draft player delivered as expected
  - K. Rice (TOR, 2.8x, 10 drafts) = 3.17 -- Mid-draft player with mid outcome -- no edge either way
  - B. Sykes (TOR, 0.3x, 218 drafts) = 5.65 -- High-draft player delivered as expected
  - D. Hamby (LAS, 0.8x, 82 drafts) = 4.54 -- High-draft player delivered as expected
  - K. McBride (MIN, 1.1x, 25 drafts) = 3.89 -- Mid-draft player with mid outcome -- no edge either way
  - M. Okot (ATL, 3.0x, 3 drafts) = 2.83 -- Outcome roughly matched draft position and signals
  - N. Howard (MIN, 1.0x, 75 drafts) = 3.72 -- High-draft player delivered as expected
  - M. Hines-Allen (IND, 2.3x, 6 drafts) = 2.56 -- Outcome roughly matched draft position and signals
  - N. Hiedeman (SEA, 2.4x, 5 drafts) = 2.48 -- Outcome roughly matched draft position and signals
  - F. Johnson (SEA, 1.5x, 38 drafts) = 2.98 -- Mid-draft player with mid outcome -- no edge either way
  - G. Jaquez (CHI, 1.6x, 19 drafts) = 2.88 -- Mid-draft player with mid outcome -- no edge either way
  - K. Cardoso (CHI, 0.9x, 51 drafts) = 3.53 -- High-draft player delivered as expected
  - S. Cunningham (IND, 1.8x, 17 drafts) = 2.69 -- Mid-draft player with mid outcome -- no edge either way
  - Z. Cooke (SEA, 2.6x, 2 drafts) = 2.16 -- Outcome roughly matched draft position and signals
  - N. Smith (LVA, 1.6x, 5 drafts) = 2.72 -- Outcome roughly matched draft position and signals
  - C. Clark (IND, 0.1x, 1400 drafts) = 4.56 -- High-draft player delivered as expected
  - K. Plum (LAS, 0.1x, 544 drafts) = 4.53 -- High-draft player delivered as expected
  - N. Cloud (CHI, 2.4x, 14 drafts) = 2.15 -- Mid-draft player with mid outcome -- no edge either way
  - G. VanSlooten (IND, 3.0x, 3 drafts) = 1.92 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - T. Paopao (ATL, 3.0x, 3 drafts) = 3.1 -- High-boost low-draft player who overperformed

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2026-05-18

**Players**: 19 HV
 | **Score range**: 1.16 -- 4.10 (median 2.80)

**Leaderboard**: top score 52.90, floor 48.72, median 50.29

**Winner** (score 52.90):
  - A. Morrow (3x) = 10.73
  - E. Engstler (3.6x) = 10.09
  - S. Barker (3.4000000000000004x) = 11.79
  - S. Rivers (3.6999999999999997x) = 12.93
  - J. Shepard (1.7999999999999998x) = 7.37
  - **Game stack**: team 11: 2 players, team 15: 2 players

**Field ownership** (top-20 entries):
  - S. Rivers (3.5x/4.1x/4.3x/3.7x/3.9x): 20/20 = 100%, avg 13.31
  - S. Barker (3.2x/3.4x/3x/3.8x): 15/20 = 75%, avg 11.93
  - E. Engstler (3x/3.6x/3.2x/3.8x/3.4x): 14/20 = 70%, avg 9.77
  - A. Morrow (2.4x/2.8x/3x/2.6x): 11/20 = 55%, avg 9.95
  - A. Ogunbowale (3.1x/2.9x/2.5x/3.3x): 7/20 = 35%, avg 9.35
  - B. Carleton (1.9x/1.7x/2.3x/2.5x): 6/20 = 30%, avg 7.57
  - J. Shepard (1.8x/2.6x/2.4x): 5/20 = 25%, avg 9.01
  - S. Sutton (2.9x/2.3x/2.7x): 5/20 = 25%, avg 6.47

### Outcome Classification

**(A) Correctly priced** (18 players):
  - S. Rivers (CON, 2.3x, 179 drafts) = 3.49 -- High-draft player delivered as expected
  - S. Barker (POR, 1.8x, 184 drafts) = 3.47 -- High-draft player delivered as expected
  - A. Fudd (DAL, 3.0x, 25 drafts) = 2.48 -- Mid-draft player with mid outcome -- no edge either way
  - A. Edwards (CON, 3.0x, 4 drafts) = 2.39 -- Outcome roughly matched draft position and signals
  - A. Ogunbowale (DAL, 1.3x, 339 drafts) = 3.26 -- High-draft player delivered as expected
  - A. Morrow (CON, 1.0x, 751 drafts) = 3.58 -- High-draft player delivered as expected
  - J. Shepard (DAL, 0.6x, 182 drafts) = 4.1 -- High-draft player delivered as expected
  - E. Engstler (POR, 1.8x, 247 drafts) = 2.8 -- Outcome roughly matched draft position and signals
  - B. Griner (CON, 1.1x, 70 drafts) = 3.09 -- High-draft player delivered as expected
  - B. Carleton (POR, 0.5x, 425 drafts) = 3.66 -- High-draft player delivered as expected
  - P. Bueckers (DAL, 0.2x, 2300 drafts) = 3.67 -- High-draft player delivered as expected
  - N. Puoch (POR, 2.3x, 43 drafts) = 1.72 -- Mid-draft player with mid outcome -- no edge either way
  - A. James (DAL, 2.7x, 7 drafts) = 1.53 -- Outcome roughly matched draft position and signals
  - L. Betts (WAS, 3.0x, 13 drafts) = 1.4 -- Mid-draft player with mid outcome -- no edge either way
  - M. Siegrist (DAL, 1.9x, 152 drafts) = 1.69 -- Outcome roughly matched draft position and signals
  - H. Van Lith (CON, 1.7x, 448 drafts) = 1.65 -- Outcome roughly matched draft position and signals
  - C. Prosper (WAS, 3.0x, 1 drafts) = 1.16 -- Low-draft player correctly faded by the field
  - L. Olsen (WAS, 3.0x, 8 drafts) = 1.26 -- Low-draft player correctly faded by the field

**(C) Unknowable / winners' edge** (1 players):
  - A. Kuier (DAL, 3.0x, 1 drafts) = 3.31 -- High-boost low-draft player who overperformed

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2026-05-19

**Players**: 20 HV
 | **Score range**: 0.00 -- 6.17 (median 1.21)

**Leaderboard**: top score 50.92, floor 50.79, median 50.82

**Winner** (score 50.92):
  - B. Sykes (2.1x) = 12.97
  - M. Mabrey (2.4x) = 12.28
  - A. Thomas (1.8x) = 8.26
  - K. Rice (3.2x) = 11.09
  - N. Mack (1.9x) = 6.34
  - **Game stack**: team 16: 3 players, team 6: 2 players

**Field ownership** (top-20 entries):
  - B. Sykes (2.1x): 20/20 = 100%, avg 12.97
  - M. Mabrey (2.4x/2.2x): 20/20 = 100%, avg 11.61
  - A. Thomas (1.8x/2x): 20/20 = 100%, avg 8.85
  - K. Rice (3.2x/3x): 20/20 = 100%, avg 10.60
  - N. Mack (1.9x/2.1x): 20/20 = 100%, avg 6.81

### Outcome Classification

**(A) Correctly priced** (20 players):
  - M. Mabrey (TOR, 0.6x, 577 drafts) = 5.11 -- High-draft player delivered as expected
  - K. Rice (TOR, 1.8x, 330 drafts) = 3.46 -- High-draft player delivered as expected
  - B. Sykes (TOR, 0.1x, 2600 drafts) = 6.17 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.2x, 2500 drafts) = 4.59 -- High-draft player delivered as expected
  - N. Mack (PHO, 0.7x, 322 drafts) = 3.34 -- High-draft player delivered as expected
  - K. Copper (PHO, 1.0x, 428 drafts) = 2.28 -- Outcome roughly matched draft position and signals
  - V. Ayayi (PHO, 3.0x, 129 drafts) = 1.21 -- High-draft player underperformed -- field took the loss equally
  - N. Brochant (PHO, 3.0x, 109 drafts) = 1.2 -- High-draft player underperformed -- field took the loss equally
  - D. Bonner (PHO, 0.9x, 357 drafts) = 2.06 -- Outcome roughly matched draft position and signals
  - L. Juškaitė (TOR, 1.4x, 147 drafts) = 1.44 -- High-draft player underperformed -- field took the loss equally
  - K. Williams (PHO, 3.0x, 139 drafts) = 0.93 -- High-draft player underperformed -- field took the loss equally
  - J. Nogic (PHO, 0.7x, 292 drafts) = 1.52 -- Outcome roughly matched draft position and signals
  - M. Conde (TOR, 2.6x, 135 drafts) = 0.88 -- High-draft player underperformed -- field took the loss equally
  - K. Linskens (PHO, 3.0x, 119 drafts) = 0.58 -- High-draft player underperformed -- field took the loss equally
  - N. Milic (TOR, 3.0x, 77 drafts) = 0.51 -- High-draft player underperformed -- field took the loss equally
  - T. Key (TOR, 3.0x, 126 drafts) = 0.28 -- High-draft player underperformed -- field took the loss equally
  - K. Nurse (TOR, 3.0x, 149 drafts) = 0.27 -- High-draft player underperformed -- field took the loss equally
  - L. Held (TOR, 0.0x, 13 drafts) = 0.45 -- Mid-draft player with mid outcome -- no edge either way
  - Q. Carter (PHO, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field
  - N. Sabally (TOR, 0.8x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2026-05-20

**Players**: 20 HV
 | **Score range**: 1.61 -- 6.14 (median 3.21)

**Leaderboard**: top score 64.95, floor 53.83, median 55.39

**Winner** (score 64.95):
  - J. Horston (5x) = 2.92
  - M. Holmes (4.8x) = 21.54
  - N. Angloma (4.6x) = 14.65
  - C. Leger-Walker (4.4x) = 14.11
  - R. Beers (4.2x) = 11.71
  - **Game stack**: team 10: 2 players, team 11: 3 players

**Field ownership** (top-20 entries):
  - K. Cardoso (2.3x/2.5x/2.7x): 14/20 = 70%, avg 15.88
  - N. Hiedeman (3.1x/3.7x/3.9x/3.3x): 11/20 = 55%, avg 12.67
  - K. Burke (3.6x/4x/3.2x/3.8x/3.4x): 10/20 = 50%, avg 12.92
  - A. Ogunbowale (2.4x/2.8x/2.2x/2.6x): 8/20 = 40%, avg 9.67
  - M. Holmes (4.4x/5x/4.2x/4.8x): 7/20 = 35%, avg 20.77
  - C. Leger-Walker (4.4x/5x/4.2x/4.8x): 6/20 = 30%, avg 14.86
  - N. Cloud (3.5x/3.1x): 6/20 = 30%, avg 11.62
  - A. Boston (2.3x/2.5x/2.7x): 4/20 = 20%, avg 11.29

### Outcome Classification

**(A) Correctly priced** (17 players):
  - K. Cardoso (CHI, 0.7x, 263 drafts) = 6.14 -- High-draft player delivered as expected
  - C. Leger-Walker (CON, 3.0x, 12 drafts) = 3.21 -- Mid-draft player with mid outcome -- no edge either way
  - N. Hiedeman (SEA, 1.9x, 91 drafts) = 3.8 -- High-draft player delivered as expected
  - K. Burke (CON, 2.0x, 142 drafts) = 3.59 -- High-draft player delivered as expected
  - R. Beers (CON, 3.0x, 9 drafts) = 2.79 -- Outcome roughly matched draft position and signals
  - N. Cloud (CHI, 1.9x, 15 drafts) = 3.52 -- Mid-draft player with mid outcome -- no edge either way
  - L. Yueru (DAL, 3.0x, 1 drafts) = 2.48 -- Outcome roughly matched draft position and signals
  - J. Shepard (DAL, 0.4x, 259 drafts) = 5.1 -- High-draft player delivered as expected
  - A. Boston (IND, 0.7x, 330 drafts) = 4.43 -- High-draft player delivered as expected
  - A. Ogunbowale (DAL, 1.0x, 488 drafts) = 3.68 -- High-draft player delivered as expected
  - T. Harris (IND, 3.0x, 1 drafts) = 1.88 -- Outcome roughly matched draft position and signals
  - A. Smith (DAL, 2.4x, 11 drafts) = 2.07 -- Mid-draft player with mid outcome -- no edge either way
  - K. Mitchell (IND, 0.4x, 416 drafts) = 3.6 -- High-draft player delivered as expected
  - E. Williams (CHI, 3.0x, 4 drafts) = 1.64 -- Outcome roughly matched draft position and signals
  - M. Gustafson (POR, 3.0x, 1 drafts) = 1.61 -- Outcome roughly matched draft position and signals
  - A. Fudd (DAL, 2.6x, 46 drafts) = 1.66 -- Mid-draft player with mid outcome -- no edge either way
  - G. Jaquez (CHI, 1.3x, 266 drafts) = 2.21 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (3 players):
  - M. Holmes (SEA, 3.0x, 5 drafts) = 4.49 -- Above-expectation outcome, ambiguous whether knowable
  - N. Angloma (CON, 3.0x, 1 drafts) = 3.19 -- High-boost low-draft player who overperformed
  - L. Hull (IND, 2.6x, 4 drafts) = 3.16 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 3 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2026-05-21

**Players**: 20 HV
 | **Score range**: 1.49 -- 6.48 (median 2.86)

**Leaderboard**: top score 57.90, floor 46.61, median 51.24

**Winner** (score 57.90):
  - A. Atkins (5x) = 12.73
  - M. Caldwell (4.8x) = 17.26
  - K. Nurse (4.6x) = 15.40
  - B. Stewart (1.4x) = 4.67
  - K. Charles (3.4000000000000004x) = 7.83

**Field ownership** (top-20 entries):
  - A. Atkins (4.8x/4.6x/4.2x/4.4x/5x): 19/20 = 95%, avg 12.06
  - K. Nurse (4.4x/4.6x/4.8x): 12/20 = 60%, avg 15.90
  - M. Caldwell (4.4x/4.6x/4.8x): 10/20 = 50%, avg 16.04
  - D. Hamby (2.1x/2.3x/2.5x): 9/20 = 45%, avg 15.33
  - A. Kosu (4.6x/4.2x): 9/20 = 45%, avg 6.24
  - H. Xu (4.2x): 7/20 = 35%, avg 2.37
  - R. Burrell (4.4x/4.6x/4.2x): 5/20 = 25%, avg 6.81
  - K. Copper (2.8x/3x/2.6x/2.2x): 4/20 = 20%, avg 5.72

### Outcome Classification

**(A) Correctly priced** (18 players):
  - D. Hamby (LAS, 0.5x, 281 drafts) = 6.48 -- High-draft player delivered as expected
  - A. Atkins (LAS, 3.0x, 51 drafts) = 2.55 -- Outcome roughly matched draft position and signals
  - K. Charles (GSV, 2.2x, 1 drafts) = 2.3 -- Outcome roughly matched draft position and signals
  - K. Thornton (GSV, 1.3x, 74 drafts) = 2.86 -- Outcome roughly matched draft position and signals
  - A. Thomas (PHO, 0.1x, 691 drafts) = 4.39 -- High-draft player delivered as expected
  - K. Rice (TOR, 1.3x, 35 drafts) = 2.78 -- Mid-draft player with mid outcome -- no edge either way
  - J. Jones (NYL, 1.0x, 22 drafts) = 2.77 -- Mid-draft player with mid outcome -- no edge either way
  - N. Mack (PHO, 0.6x, 170 drafts) = 3.09 -- High-draft player delivered as expected
  - R. Burrell (LAS, 3.0x, 37 drafts) = 1.56 -- Mid-draft player with mid outcome -- no edge either way
  - V. Burton (GSV, 0.3x, 241 drafts) = 3.26 -- High-draft player delivered as expected
  - K. Plum (LAS, 0.0x, 1100 drafts) = 3.7 -- High-draft player delivered as expected
  - K. McBride (MIN, 0.8x, 85 drafts) = 2.62 -- Outcome roughly matched draft position and signals
  - J. Nogic (PHO, 0.9x, 185 drafts) = 2.52 -- Outcome roughly matched draft position and signals
  - O. Miles (MIN, 0.4x, 217 drafts) = 3.02 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.3x, 191 drafts) = 3.14 -- High-draft player delivered as expected
  - T. Hayes (GSV, 3.0x, 6 drafts) = 1.49 -- Low-draft player correctly faded by the field
  - N. Ogwumike (LAS, 0.7x, 235 drafts) = 2.61 -- Outcome roughly matched draft position and signals
  - G. Williams (GSV, 0.7x, 24 drafts) = 2.55 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (2 players):
  - M. Caldwell (MIN, 3.0x, 1 drafts) = 3.6 -- High-boost low-draft player who overperformed
  - K. Nurse (TOR, 3.0x, 3 drafts) = 3.35 -- High-boost low-draft player who overperformed

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2026-05-22

**Players**: 20 HV
 | **Score range**: 1.57 -- 6.01 (median 2.85)

**Leaderboard**: top score 56.11, floor 48.34, median 48.34

**Winner** (score 56.11):
  - R. Howard (2.4x) = 14.43
  - N. Hiedeman (3.1x) = 6.71
  - F. Johnson (3x) = 9.81
  - A. Edwards (3.6x) = 9.66
  - T. Hayes (4.2x) = 15.51
  - **Game stack**: team 10: 2 players

**Field ownership** (top-20 entries):
  - T. Hayes (4.2x): 19/20 = 95%, avg 15.51
  - R. Howard (2.4x): 18/20 = 90%, avg 14.43
  - N. Hiedeman (2.9x/3.1x): 18/20 = 90%, avg 6.68
  - F. Johnson (3x): 17/20 = 85%, avg 9.81
  - N. Hillmon (3.4x/3.8x): 15/20 = 75%, avg 1.90
  - A. Edwards (3.8x/3.6x): 5/20 = 25%, avg 9.77
  - Z. Cooke (4x/3.8x): 2/20 = 10%, avg 15.11
  - A. Reese (2.8x): 1/20 = 5%, avg 5.48

### Outcome Classification

**(A) Correctly priced** (18 players):
  - Z. Cooke (SEA, 2.6x, 40 drafts) = 3.88 -- Mid-draft player with mid outcome -- no edge either way
  - K. Chen (GSV, 3.0x, 11 drafts) = 3.29 -- Mid-draft player with mid outcome -- no edge either way
  - R. Howard (ATL, 0.4x, 192 drafts) = 6.01 -- High-draft player delivered as expected
  - A. James (DAL, 2.8x, 3 drafts) = 2.85 -- Outcome roughly matched draft position and signals
  - A. Kuier (DAL, 2.7x, 3 drafts) = 2.86 -- Outcome roughly matched draft position and signals
  - A. Boston (IND, 0.4x, 341 drafts) = 4.92 -- High-draft player delivered as expected
  - A. Edwards (CON, 2.2x, 48 drafts) = 2.68 -- Mid-draft player with mid outcome -- no edge either way
  - F. Johnson (SEA, 1.4x, 219 drafts) = 3.27 -- High-draft player delivered as expected
  - D. Miller (CON, 3.0x, 38 drafts) = 1.83 -- Mid-draft player with mid outcome -- no edge either way
  - J. Horston (SEA, 3.0x, 1 drafts) = 1.66 -- Outcome roughly matched draft position and signals
  - C. Leger-Walker (CON, 2.7x, 51 drafts) = 1.71 -- Outcome roughly matched draft position and signals
  - S. Dolson (SEA, 2.3x, 52 drafts) = 1.82 -- Outcome roughly matched draft position and signals
  - A. Fudd (DAL, 2.4x, 30 drafts) = 1.74 -- Mid-draft player with mid outcome -- no edge either way
  - N. Hiedeman (SEA, 1.3x, 381 drafts) = 2.16 -- Outcome roughly matched draft position and signals
  - C. Clark (IND, 0.0x, 852 drafts) = 3.55 -- High-draft player delivered as expected
  - V. Burton (GSV, 0.3x, 282 drafts) = 2.67 -- Outcome roughly matched draft position and signals
  - A. Gray (ATL, 0.3x, 575 drafts) = 2.79 -- Outcome roughly matched draft position and signals
  - S. Cunningham (IND, 1.8x, 41 drafts) = 1.57 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (2 players):
  - T. Hayes (GSV, 3.0x, 3 drafts) = 3.69 -- High-boost low-draft player who overperformed
  - O. Sims (DAL, 1.9x, 4 drafts) = 3.23 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2026-05-23

**Players**: 20 HV
 | **Score range**: 1.66 -- 8.73 (median 3.32)

**Leaderboard**: top score 61.64, floor 57.96, median 59.29

**Winner** (score 61.64):
  - A. Wilson (2x) = 11.23
  - K. Plum (1.9000000000000001x) = 16.58
  - N. Smith (3x) = 14.47
  - E. Wheeler (3.6x) = 12.83
  - C. Brink (3x) = 6.53
  - **Game stack**: team 1: 2 players, team 9: 3 players

**Field ownership** (top-20 entries):
  - A. Wilson (1.6x/1.8x/2x): 16/20 = 80%, avg 10.95
  - K. Plum (1.9x/2.1x/1.7x): 16/20 = 80%, avg 17.02
  - N. Smith (3.2x/2.8x/3x/2.6x): 15/20 = 75%, avg 13.89
  - K. Rice (2.4x/2.8x/3x/2.6x): 14/20 = 70%, avg 10.30
  - E. Wheeler (3.4x/4x/3.6x): 9/20 = 45%, avg 12.51
  - M. Mabrey (1.9x/2.3x/2.5x/2.7x): 8/20 = 40%, avg 9.79
  - E. Engstler (3.5x/3.9x/3.3x): 6/20 = 30%, avg 11.50
  - C. Brink (3.2x/3x): 5/20 = 25%, avg 6.70

### Outcome Classification

**(A) Correctly priced** (20 players):
  - K. Plum (LAS, 0.1x, 510 drafts) = 8.73 -- High-draft player delivered as expected
  - N. Smith (LVA, 1.4x, 56 drafts) = 4.82 -- High-draft player delivered as expected
  - N. Howard (MIN, 0.8x, 98 drafts) = 5.59 -- High-draft player delivered as expected
  - E. Wheeler (LAS, 2.2x, 53 drafts) = 3.56 -- High-draft player delivered as expected
  - E. Engstler (POR, 1.9x, 33 drafts) = 3.32 -- Mid-draft player with mid outcome -- no edge either way
  - M. Gustafson (POR, 3.0x, 2 drafts) = 2.69 -- Outcome roughly matched draft position and signals
  - K. Rice (TOR, 1.2x, 184 drafts) = 3.94 -- High-draft player delivered as expected
  - M. Mabrey (TOR, 0.7x, 174 drafts) = 4.21 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 4000 drafts) = 5.61 -- High-draft player delivered as expected
  - C. Carter (LVA, 0.4x, 272 drafts) = 4.4 -- High-draft player delivered as expected
  - S. Williams (POR, 3.0x, 2 drafts) = 1.92 -- Outcome roughly matched draft position and signals
  - C. Williams (MIN, 0.4x, 125 drafts) = 3.83 -- High-draft player delivered as expected
  - C. Leite (POR, 1.1x, 266 drafts) = 2.96 -- Outcome roughly matched draft position and signals
  - K. McBride (MIN, 0.8x, 124 drafts) = 3.01 -- High-draft player delivered as expected
  - R. Burrell (LAS, 2.8x, 14 drafts) = 1.75 -- Mid-draft player with mid outcome -- no edge either way
  - C. Brink (LAS, 1.8x, 247 drafts) = 2.18 -- Outcome roughly matched draft position and signals
  - J. Loyd (LVA, 2.8x, 27 drafts) = 1.66 -- Mid-draft player with mid outcome -- no edge either way
  - C. Gray (LVA, 0.6x, 261 drafts) = 2.92 -- Outcome roughly matched draft position and signals
  - A. Atkins (LAS, 2.0x, 51 drafts) = 1.89 -- Outcome roughly matched draft position and signals
  - S. Barker (POR, 1.4x, 52 drafts) = 2.11 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2026-05-24

**Players**: 20 HV
 | **Score range**: 1.69 -- 5.93 (median 3.12)

**Leaderboard**: top score 72.69, floor 72.13, median 72.13

**Winner** (score 72.69):
  - A. Reese (3x) = 12.84
  - A. Fudd (4.1x) = 24.30
  - S. Dolson (3.8000000000000003x) = 11.85
  - S. Sabally (4.4x) = 12.89
  - G. Amoore (4.2x) = 10.80

**Field ownership** (top-20 entries):
  - A. Reese (3x): 20/20 = 100%, avg 12.84
  - A. Fudd (4.1x/3.9x): 20/20 = 100%, avg 23.18
  - S. Dolson (4x/3.8x): 20/20 = 100%, avg 12.44
  - S. Sabally (4.4x): 20/20 = 100%, avg 12.89
  - G. Amoore (4.2x): 20/20 = 100%, avg 10.80

### Outcome Classification

**(A) Correctly priced** (18 players):
  - N. Hiedeman (SEA, 1.3x, 177 drafts) = 4.74 -- High-draft player delivered as expected
  - S. Sabally (NYL, 3.0x, 27 drafts) = 2.93 -- Mid-draft player with mid outcome -- no edge either way
  - S. Dolson (SEA, 2.2x, 41 drafts) = 3.12 -- Mid-draft player with mid outcome -- no edge either way
  - G. Amoore (WAS, 3.0x, 25 drafts) = 2.57 -- Mid-draft player with mid outcome -- no edge either way
  - A. Reese (ATL, 1.0x, 466 drafts) = 4.28 -- High-draft player delivered as expected
  - A. Dugalić (WAS, 3.0x, 15 drafts) = 2.43 -- Mid-draft player with mid outcome -- no edge either way
  - A. Ogunbowale (DAL, 1.2x, 146 drafts) = 3.27 -- High-draft player delivered as expected
  - N. Brochant (PHO, 3.0x, 2 drafts) = 2.0 -- Outcome roughly matched draft position and signals
  - A. Thomas (PHO, 0.1x, 598 drafts) = 4.61 -- High-draft player delivered as expected
  - K. Linskens (PHO, 3.0x, 1 drafts) = 1.97 -- Outcome roughly matched draft position and signals
  - P. Bueckers (DAL, 0.4x, 969 drafts) = 3.86 -- High-draft player delivered as expected
  - J. Shepard (DAL, 0.4x, 161 drafts) = 3.7 -- High-draft player delivered as expected
  - A. Kuier (DAL, 2.0x, 2 drafts) = 2.13 -- Outcome roughly matched draft position and signals
  - F. Johnson (SEA, 1.1x, 231 drafts) = 2.58 -- Outcome roughly matched draft position and signals
  - J. Jones (NYL, 0.9x, 29 drafts) = 2.65 -- Mid-draft player with mid outcome -- no edge either way
  - R. Howard (ATL, 0.1x, 95 drafts) = 3.58 -- High-draft player delivered as expected
  - K. Copper (PHO, 1.1x, 238 drafts) = 2.4 -- Outcome roughly matched draft position and signals
  - L. Brown (SEA, 2.2x, 22 drafts) = 1.69 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (2 players):
  - A. Fudd (DAL, 2.3x, 38 drafts) = 5.93 -- Above-expectation outcome, ambiguous whether knowable
  - J. Canada (ATL, 0.5x, 9 drafts) = 5.14 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2026-05-25

**Players**: 20 HV
 | **Score range**: 1.26 -- 3.75 (median 2.23)

**Leaderboard**: top score 40.60, floor 38.30, median 39.14

**Winner** (score 40.60):
  - E. Engstler (3.5x) = 12.40
  - J. Jones (2.7x) = 9.90
  - S. Barker (3x) = 5.32
  - M. Johannes (2.0999999999999996x) = 5.12
  - K. Charles (3.3x) = 7.86
  - **Game stack**: team 15: 2 players, team 4: 2 players

**Field ownership** (top-20 entries):
  - J. Jones (2.3x/2.7x/2.9x/2.1x/2.5x): 18/20 = 90%, avg 9.29
  - E. Engstler (3.5x/3.1x/2.7x/2.9x/3.3x): 17/20 = 85%, avg 10.69
  - B. Stewart (1.9x/2.1x/1.5x/1.3x): 17/20 = 85%, avg 7.38
  - V. Burton (2.4x/1.8x/2.2x): 10/20 = 50%, avg 6.97
  - G. Williams (2.1x/2.3x/2.7x): 6/20 = 30%, avg 6.13
  - M. Johannes (2.1x/2.3x/2.5x): 5/20 = 25%, avg 5.71
  - A. Morrow (3.2x/2.8x/3x): 5/20 = 25%, avg 6.71
  - K. Charles (3.5x/3.7x/3.3x): 4/20 = 20%, avg 8.34

### Outcome Classification

**(A) Correctly priced** (20 players):
  - E. Engstler (POR, 1.5x, 131 drafts) = 3.54 -- High-draft player delivered as expected
  - J. Jones (NYL, 0.9x, 245 drafts) = 3.67 -- High-draft player delivered as expected
  - H. Xu (NYL, 3.0x, 4 drafts) = 2.23 -- Outcome roughly matched draft position and signals
  - L. Amihere (GSV, 2.2x, 30 drafts) = 2.55 -- Mid-draft player with mid outcome -- no edge either way
  - K. Charles (GSV, 2.1x, 28 drafts) = 2.38 -- Mid-draft player with mid outcome -- no edge either way
  - B. Stewart (NYL, 0.1x, 2900 drafts) = 3.75 -- High-draft player delivered as expected
  - L. Geiselsöder (POR, 2.7x, 6 drafts) = 1.81 -- Outcome roughly matched draft position and signals
  - N. Puoch (POR, 3.0x, 4 drafts) = 1.65 -- Outcome roughly matched draft position and signals
  - V. Burton (GSV, 0.4x, 811 drafts) = 3.17 -- High-draft player delivered as expected
  - A. Morrow (CON, 1.4x, 231 drafts) = 2.24 -- Outcome roughly matched draft position and signals
  - G. Williams (GSV, 0.9x, 563 drafts) = 2.52 -- Outcome roughly matched draft position and signals
  - K. Chen (GSV, 2.3x, 50 drafts) = 1.68 -- Outcome roughly matched draft position and signals
  - C. Leger-Walker (CON, 2.6x, 131 drafts) = 1.54 -- Outcome roughly matched draft position and signals
  - M. Johannes (NYL, 0.7x, 216 drafts) = 2.44 -- Outcome roughly matched draft position and signals
  - O. Nelson-Ododa (CON, 2.5x, 1 drafts) = 1.59 -- Outcome roughly matched draft position and signals
  - K. Thornton (GSV, 1.3x, 212 drafts) = 1.92 -- Outcome roughly matched draft position and signals
  - M. Gustafson (POR, 2.4x, 3 drafts) = 1.44 -- Low-draft player correctly faded by the field
  - G. Kneepkens (CON, 3.0x, 9 drafts) = 1.26 -- Low-draft player correctly faded by the field
  - T. Hayes (GSV, 1.7x, 158 drafts) = 1.68 -- Outcome roughly matched draft position and signals
  - S. Barker (POR, 1.4x, 168 drafts) = 1.77 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2026-05-27

**Players**: 20 HV
 | **Games**: 10 (WAS@SEA, POR@CON, CON@POR, PHO@NYL, ATL@MIN, NYL@PHO)
 | **Score range**: 1.76 -- 6.79 (median 3.75)

**Leaderboard**: top score 59.01, floor 54.85, median 55.55

**Winner** (score 59.01):
  - B. Sykes (2.3x) = 8.19
  - S. Diggins (2.3x) = 13.02
  - N. Sabally (2.5x) = 16.98
  - M. Mabrey (2x) = 10.86
  - M. Johannes (2x) = 9.97
  - **Game stack**: team 16: 3 players

**Field ownership** (top-20 entries):
  - N. Sabally (2.1x/2.3x/2.5x/2.7x): 16/20 = 80%, avg 17.15
  - A. Stevens (4.4x/4.6x/4.2x): 14/20 = 70%, avg 7.77
  - N. Hillmon (4.4x/4.6x/4.2x): 13/20 = 65%, avg 10.94
  - N. Cloud (3.2x/3x/3.6x/2.8x): 12/20 = 60%, avg 14.81
  - M. Mabrey (2.4x/2x/1.8x/2.6x): 10/20 = 50%, avg 12.60
  - A. Thomas (2.1x): 6/20 = 30%, avg 7.39
  - G. Amoore (4x): 6/20 = 30%, avg 2.83
  - N. Howard (1.9x/2.5x): 5/20 = 25%, avg 12.44

### Model Performance

**Our frozen lineup**:
  - Player 617 (ATL, 3.0x boost) -- pred p50=2.726243231332118
  - Player 4322873 (POR, 3.0x boost) -- pred p50=1.7864
  - Player 4322915 (CON, 3.0x boost) -- pred p50=1.7864
  - Player 515 (MIN, 3.0x boost) -- pred p50=1.7864
  - Player 129 (TOR, 3.0x boost) -- pred p50=1.7864

**Leverage** (ownership differentiation):
  - Player 617: field ownership 0% [DIFFERENTIATED]
  - Player 4322873: field ownership 0% [DIFFERENTIATED]
  - Player 4322915: field ownership 0% [DIFFERENTIATED]
  - Player 515: field ownership 0% [DIFFERENTIATED]
  - Player 129: field ownership 0% [DIFFERENTIATED]

**Our game stacks**: none (diversified)

### Outcome Classification

**(A) Correctly priced** (15 players):
  - N. Cloud (CHI, 1.6x, 450 drafts) = 4.34 -- High-draft player delivered as expected
  - M. Mabrey (TOR, 0.6x, 279 drafts) = 5.43 -- High-draft player delivered as expected
  - M. Johannes (NYL, 0.8x, 216 drafts) = 4.98 -- High-draft player delivered as expected
  - N. Howard (MIN, 0.5x, 293 drafts) = 5.5 -- High-draft player delivered as expected
  - M. Onyenwere (WAS, 3.0x, 1 drafts) = 2.57 -- Outcome roughly matched draft position and signals
  - N. Hillmon (ATL, 3.0x, 4 drafts) = 2.54 -- Outcome roughly matched draft position and signals
  - J. Jones (NYL, 0.8x, 255 drafts) = 4.53 -- High-draft player delivered as expected
  - S. Austin (WAS, 0.5x, 41 drafts) = 4.8 -- Mid-draft player with mid outcome -- no edge either way
  - A. Morrow (CON, 1.4x, 166 drafts) = 3.48 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.3x, 344 drafts) = 4.7 -- High-draft player delivered as expected
  - K. Rice (TOR, 0.9x, 335 drafts) = 3.6 -- High-draft player delivered as expected
  - O. Miles (MIN, 0.5x, 296 drafts) = 3.75 -- High-draft player delivered as expected
  - L. Juškaitė (TOR, 2.3x, 1 drafts) = 2.13 -- Outcome roughly matched draft position and signals
  - O. Nelson-Ododa (CON, 2.4x, 1 drafts) = 2.11 -- Outcome roughly matched draft position and signals
  - A. Stevens (CHI, 3.0x, 12 drafts) = 1.76 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (5 players):
  - N. Sabally (TOR, 0.9x, 16 drafts) = 6.79 -- Above-expectation outcome, ambiguous whether knowable
  - S. Taylor (CHI, 3.0x, 1 drafts) = 3.63 -- High-boost low-draft player who overperformed
  - E. Williams (CHI, 3.0x, 2 drafts) = 3.07 -- High-boost low-draft player who overperformed
  - S. Diggins (CHI, 0.5x, 33 drafts) = 5.66 -- Above-expectation outcome, ambiguous whether knowable
  - N. Coffey (MIN, 1.3x, 9 drafts) = 3.36 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 5 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2026-05-28

**Players**: 20 HV
 | **Games**: 4 (GSV@IND, DAL@LVA, IND@GSV, LVA@DAL)
 | **Score range**: 1.26 -- 5.65 (median 2.70)

**Leaderboard**: top score 53.13, floor 49.91, median 50.65

**Winner** (score 53.13):
  - A. Fudd (3.1x) = 12.46
  - G. Williams (2.7x) = 11.28
  - J. Shepard (2x) = 11.30
  - V. Burton (1.7999999999999998x) = 9.95
  - M. Siegrist (4.2x) = 8.14
  - **Game stack**: team 12: 3 players, team 14: 2 players

**Field ownership** (top-20 entries):
  - J. Shepard (1.6x/2.4x/2x/1.8x/2.2x): 17/20 = 85%, avg 12.03
  - A. Fudd (2.3x/3.1x/2.7x/2.9x/2.5x): 15/20 = 75%, avg 10.69
  - G. Williams (2.3x/2.7x/2.9x/2.1x/2.5x): 14/20 = 70%, avg 10.63
  - V. Burton (1.6x/2.4x/2x/1.8x/2.2x): 14/20 = 70%, avg 11.45
  - J. Salaün (2.4x/2.8x/3x/2.6x): 11/20 = 55%, avg 11.35
  - J. Young (2.5x): 5/20 = 25%, avg 8.54
  - A. Wilson (1.8x/2x): 4/20 = 20%, avg 7.01
  - P. Bueckers (1.7x/2.3x): 4/20 = 20%, avg 8.63

### Model Performance

**Our frozen lineup**:
  - Player 765 (DAL, 3.0x boost) -- pred p50=2.5024405805151404
  - Player 657 (GSV, 3.0x boost) -- pred p50=2.3688518714088254
  - Player 608 (LVA, 3.0x boost) -- pred p50=1.76198
  - Player 4322862 (IND, 3.0x boost) -- pred p50=1.70768
  - Player 4322893 (IND, 3.0x boost) -- pred p50=1.70768

**Leverage** (ownership differentiation):
  - Player 765: field ownership 0% [DIFFERENTIATED]
  - Player 657: field ownership 0% [DIFFERENTIATED]
  - Player 608: field ownership 0% [DIFFERENTIATED]
  - Player 4322862: field ownership 0% [DIFFERENTIATED]
  - Player 4322893: field ownership 0% [DIFFERENTIATED]

**Our game stacks**: {'IND': ['Player 4322862', 'Player 4322893']}

### Outcome Classification

**(A) Correctly priced** (20 players):
  - R. Johnson (IND, 3.0x, 19 drafts) = 2.88 -- Mid-draft player with mid outcome -- no edge either way
  - J. Salaün (GSV, 1.2x, 135 drafts) = 4.31 -- High-draft player delivered as expected
  - J. Shepard (DAL, 0.4x, 174 drafts) = 5.65 -- High-draft player delivered as expected
  - V. Burton (GSV, 0.4x, 302 drafts) = 5.53 -- High-draft player delivered as expected
  - A. Fudd (DAL, 1.1x, 332 drafts) = 4.02 -- High-draft player delivered as expected
  - G. Williams (GSV, 0.9x, 205 drafts) = 4.18 -- High-draft player delivered as expected
  - M. Timpson (IND, 3.0x, 12 drafts) = 2.32 -- Mid-draft player with mid outcome -- no edge either way
  - J. Young (LVA, 0.9x, 173 drafts) = 3.42 -- High-draft player delivered as expected
  - M. Siegrist (DAL, 3.0x, 9 drafts) = 1.94 -- Outcome roughly matched draft position and signals
  - P. Bueckers (DAL, 0.3x, 282 drafts) = 4.02 -- High-draft player delivered as expected
  - J. Loyd (LVA, 2.6x, 9 drafts) = 1.75 -- Outcome roughly matched draft position and signals
  - N. Smith (LVA, 0.9x, 124 drafts) = 2.7 -- Outcome roughly matched draft position and signals
  - A. Kuier (DAL, 1.9x, 123 drafts) = 1.99 -- Outcome roughly matched draft position and signals
  - A. Wilson (LVA, 0.0x, 4300 drafts) = 3.59 -- High-draft player delivered as expected
  - C. Gray (LVA, 0.6x, 205 drafts) = 2.69 -- Outcome roughly matched draft position and signals
  - S. Cunningham (IND, 1.9x, 56 drafts) = 1.78 -- Outcome roughly matched draft position and signals
  - C. Parker-Tyus (LVA, 3.0x, 1 drafts) = 1.35 -- Low-draft player correctly faded by the field
  - M. Billings (IND, 1.8x, 24 drafts) = 1.67 -- Mid-draft player with mid outcome -- no edge either way
  - K. Stokes (GSV, 1.7x, 125 drafts) = 1.67 -- Outcome roughly matched draft position and signals
  - C. Zandalasini (GSV, 3.0x, 4 drafts) = 1.26 -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2026-05-29

**Players**: 20 HV
 | **Games**: 8 (CHI@MIN, PHO@NYL, NYL@PHO, POR@ATL, WAS@LAS, LAS@WAS)
 | **Score range**: 1.87 -- 4.42 (median 3.57)

**Leaderboard**: top score 49.45, floor 44.08, median 46.35

**Winner** (score 49.45):
  - S. Austin (2.4x) = 9.53
  - N. Ogwumike (2.5x) = 10.02
  - N. Hillmon (4x) = 16.19
  - E. Wheeler (3x) = 11.32
  - T. Paopao (4.1x) = 2.38
  - **Game stack**: team 9: 2 players, team 2: 2 players

**Field ownership** (top-20 entries):
  - N. Hillmon (4x/4.2x/4.4x/3.8x/3.6x): 19/20 = 95%, avg 15.34
  - E. Wheeler (3.2x/3.4x/3x): 7/20 = 35%, avg 12.08
  - N. Coffey (2.9x/2.5x/3.1x/2.7x): 7/20 = 35%, avg 12.04
  - A. Reese (1.9x/2.3x/2.7x/2.1x/2.5x): 7/20 = 35%, avg 8.55
  - J. Jones (2.4x/1.8x/2.6x): 5/20 = 25%, avg 6.20
  - C. Brink (2.9x/3.1x/3.3x): 5/20 = 25%, avg 7.88
  - R. Howard (1.9x/2.1x/1.5x/2.3x): 5/20 = 25%, avg 8.07
  - N. Ogwumike (2.1x/2.3x/2.5x): 4/20 = 20%, avg 9.22

### Model Performance

**Our frozen lineup**:
  - Player 617 (ATL, 2.4x boost) -- pred p50=2.5946554147424212
  - Player 647 (NYL, 2.9x boost) -- pred p50=2.260287442482477
  - Player 4322730 (WAS, 3.0x boost) -- pred p50=1.7864
  - Player 4322904 (PHO, 3.0x boost) -- pred p50=1.7576
  - Player 4322873 (POR, 3.0x boost) -- pred p50=1.714

**Leverage** (ownership differentiation):
  - Player 617: field ownership 0% [DIFFERENTIATED]
  - Player 647: field ownership 0% [DIFFERENTIATED]
  - Player 4322730: field ownership 0% [DIFFERENTIATED]
  - Player 4322904: field ownership 0% [DIFFERENTIATED]
  - Player 4322873: field ownership 0% [DIFFERENTIATED]

**Our game stacks**: none (diversified)

### Outcome Classification

**(A) Correctly priced** (20 players):
  - N. Hillmon (ATL, 2.4x, 41 drafts) = 4.05 -- Mid-draft player with mid outcome -- no edge either way
  - E. Wheeler (LAS, 1.6x, 191 drafts) = 3.77 -- High-draft player delivered as expected
  - N. Coffey (MIN, 1.1x, 15 drafts) = 4.19 -- Mid-draft player with mid outcome -- no edge either way
  - A. Dugalić (WAS, 3.0x, 1 drafts) = 2.38 -- Outcome roughly matched draft position and signals
  - N. Ogwumike (LAS, 0.7x, 15 drafts) = 4.01 -- Mid-draft player with mid outcome -- no edge either way
  - D. Hamby (LAS, 0.3x, 327 drafts) = 4.42 -- High-draft player delivered as expected
  - A. Reese (ATL, 0.7x, 853 drafts) = 3.72 -- High-draft player delivered as expected
  - P. Astier (NYL, 0.8x, 132 drafts) = 3.57 -- High-draft player delivered as expected
  - R. Howard (ATL, 0.3x, 210 drafts) = 4.34 -- High-draft player delivered as expected
  - H. Xu (NYL, 3.0x, 9 drafts) = 1.98 -- Outcome roughly matched draft position and signals
  - S. Citron (WAS, 0.4x, 316 drafts) = 4.08 -- High-draft player delivered as expected
  - B. Laney-Hamilton (NYL, 2.3x, 1 drafts) = 2.38 -- Outcome roughly matched draft position and signals
  - M. Akoa Makani (PHO, 1.9x, 1 drafts) = 2.5 -- Outcome roughly matched draft position and signals
  - S. Austin (WAS, 0.4x, 188 drafts) = 3.97 -- High-draft player delivered as expected
  - H. Winterburn (POR, 3.0x, 24 drafts) = 1.87 -- Mid-draft player with mid outcome -- no edge either way
  - C. Brink (LAS, 1.7x, 259 drafts) = 2.48 -- Outcome roughly matched draft position and signals
  - O. Miles (MIN, 0.4x, 257 drafts) = 3.49 -- High-draft player delivered as expected
  - M. Gustafson (POR, 2.3x, 28 drafts) = 1.94 -- Mid-draft player with mid outcome -- no edge either way
  - N. Howard (MIN, 0.3x, 505 drafts) = 3.44 -- High-draft player delivered as expected
  - N. Mack (PHO, 0.7x, 145 drafts) = 2.9 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2026-05-30

**Players**: 20 HV
 | **Games**: 6 (LAS@CON, POR@IND, CON@LAS, TOR@SEA, IND@POR, SEA@TOR)
 | **Score range**: 1.56 -- 5.59 (median 3.11)

**Leaderboard**: top score 63.82, floor 57.99, median 60.08

**Winner** (score 63.82):
  - M. Gustafson (4.2x) = 17.15
  - K. Burke (4x) = 13.69
  - E. Engstler (3.2x) = 17.87
  - N. Ogwumike (2x) = 4.98
  - C. Leite (2.4x) = 10.14
  - **Game stack**: team 15: 3 players

**Field ownership** (top-20 entries):
  - M. Gustafson (4x/4.2x/3.4x/3.8x/3.6x): 18/20 = 90%, avg 15.56
  - E. Engstler (3x/2.8x/3.2x/3.6x/3.4x): 17/20 = 85%, avg 17.87
  - C. Leite (3.2x/2.4x/2.8x/3x): 11/20 = 55%, avg 11.98
  - K. Burke (3.4x/4x/3.8x/3.6x): 10/20 = 50%, avg 12.66
  - A. Morrow (2.4x/3.2x/3x): 7/20 = 35%, avg 10.65
  - E. Wheeler (2.4x/3x): 6/20 = 30%, avg 6.45
  - S. Barker (3.2x/3.4x/3x): 6/20 = 30%, avg 8.62
  - A. Atkins (3.5x/3.9x/3.3x): 3/20 = 15%, avg 12.81

### Model Performance

**Our frozen lineup**:
  - Player 620 (POR, 3.0x boost) -- pred p50=1.748
  - Player 4322715 (POR, 3.0x boost) -- pred p50=1.748
  - Player 4322879 (TOR, 3.0x boost) -- pred p50=1.748
  - Player 739 (SEA, 3.0x boost) -- pred p50=1.70768
  - Player 4322893 (IND, 3.0x boost) -- pred p50=1.70768

**Leverage** (ownership differentiation):
  - Player 620: field ownership 0% [DIFFERENTIATED]
  - Player 4322715: field ownership 0% [DIFFERENTIATED]
  - Player 4322879: field ownership 0% [DIFFERENTIATED]
  - Player 739: field ownership 0% [DIFFERENTIATED]
  - Player 4322893: field ownership 0% [DIFFERENTIATED]

**Our game stacks**: {'POR': ['Player 620', 'Player 4322715']}

### Outcome Classification

**(A) Correctly priced** (19 players):
  - E. Engstler (POR, 1.6x, 155 drafts) = 5.59 -- High-draft player delivered as expected
  - M. Gustafson (POR, 2.2x, 85 drafts) = 4.08 -- High-draft player delivered as expected
  - A. Atkins (LAS, 1.9x, 195 drafts) = 3.59 -- High-draft player delivered as expected
  - J. Horston (SEA, 3.0x, 2 drafts) = 2.88 -- Outcome roughly matched draft position and signals
  - K. Burke (CON, 2.2x, 66 drafts) = 3.42 -- High-draft player delivered as expected
  - C. Leite (POR, 1.2x, 240 drafts) = 4.22 -- High-draft player delivered as expected
  - M. Conde (TOR, 3.0x, 1 drafts) = 2.6 -- Outcome roughly matched draft position and signals
  - M. Timpson (IND, 3.0x, 15 drafts) = 2.5 -- Mid-draft player with mid outcome -- no edge either way
  - A. Morrow (CON, 1.2x, 343 drafts) = 3.62 -- High-draft player delivered as expected
  - R. Burrell (LAS, 2.9x, 4 drafts) = 2.28 -- Outcome roughly matched draft position and signals
  - N. Hiedeman (SEA, 1.1x, 93 drafts) = 3.56 -- High-draft player delivered as expected
  - D. Miller (CON, 3.0x, 4 drafts) = 2.2 -- Outcome roughly matched draft position and signals
  - S. Barker (POR, 1.6x, 155 drafts) = 2.69 -- Outcome roughly matched draft position and signals
  - S. Cunningham (IND, 1.9x, 112 drafts) = 2.44 -- Outcome roughly matched draft position and signals
  - B. Carleton (POR, 0.6x, 45 drafts) = 3.5 -- Mid-draft player with mid outcome -- no edge either way
  - K. Rice (TOR, 0.8x, 203 drafts) = 3.11 -- High-draft player delivered as expected
  - S. Dolson (SEA, 2.0x, 4 drafts) = 2.15 -- Outcome roughly matched draft position and signals
  - E. Wheeler (LAS, 1.2x, 429 drafts) = 2.3 -- Outcome roughly matched draft position and signals
  - F. Buhner (POR, 3.0x, 15 drafts) = 1.56 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (1 players):
  - L. Juškaitė (TOR, 2.1x, 1 drafts) = 3.12 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2026-05-31

**Players**: 20 HV
 | **Games**: 2 (GSV@LVA, LVA@GSV)
 | **Score range**: -0.20 -- 6.29 (median 1.26)

**Leaderboard**: top score 52.98, floor 47.79, median 49.50

**Winner** (score 52.98):
  - A. Wilson (2x) = 12.58
  - J. Salaün (2.7x) = 7.22
  - G. Williams (2.3x) = 7.01
  - J. Young (2.2x) = 12.60
  - S. Talbot (4.2x) = 13.57
  - **Game stack**: team 1: 3 players, team 14: 2 players

**Field ownership** (top-20 entries):
  - J. Young (2.8x/2.6x/2.4x/2x/2.2x): 20/20 = 100%, avg 13.80
  - S. Talbot (4.8x/4.6x/4.2x/4.4x/5x): 20/20 = 100%, avg 14.31
  - A. Wilson (1.6x/1.8x/2x): 17/20 = 85%, avg 12.21
  - J. Salaün (2.1x/2.3x/2.5x/2.7x): 10/20 = 50%, avg 6.68
  - V. Burton (2.1x): 5/20 = 25%, avg 4.12
  - G. Williams (2.1x/2.3x): 4/20 = 20%, avg 6.71
  - K. Thornton (3.3x/3.7x/3.1x): 4/20 = 20%, avg 7.17
  - C. Zandalasini (4.4x/4.6x/4.2x): 4/20 = 20%, avg 5.16

### Model Performance

**Our frozen lineup**:

**Our game stacks**: none (diversified)

### Outcome Classification

**(A) Correctly priced** (20 players):
  - S. Talbot (LVA, 3.0x, 87 drafts) = 3.23 -- High-draft player delivered as expected
  - J. Young (LVA, 0.8x, 208 drafts) = 5.73 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 4100 drafts) = 6.29 -- High-draft player delivered as expected
  - N. Smith (LVA, 0.9x, 131 drafts) = 2.98 -- Outcome roughly matched draft position and signals
  - G. Williams (GSV, 0.7x, 239 drafts) = 3.05 -- High-draft player delivered as expected
  - K. Thornton (GSV, 1.7x, 107 drafts) = 2.17 -- Outcome roughly matched draft position and signals
  - J. Salaün (GSV, 0.9x, 128 drafts) = 2.67 -- Outcome roughly matched draft position and signals
  - C. Zandalasini (GSV, 3.0x, 62 drafts) = 1.19 -- High-draft player underperformed -- field took the loss equally
  - K. Bell (LVA, 3.0x, 54 drafts) = 1.11 -- High-draft player underperformed -- field took the loss equally
  - K. Chen (GSV, 2.4x, 86 drafts) = 1.26 -- High-draft player underperformed -- field took the loss equally
  - V. Burton (GSV, 0.3x, 391 drafts) = 1.96 -- Outcome roughly matched draft position and signals
  - B. Turner (LVA, 3.0x, 64 drafts) = 0.9 -- High-draft player underperformed -- field took the loss equally
  - C. Gray (LVA, 0.7x, 231 drafts) = 1.57 -- Outcome roughly matched draft position and signals
  - J. Jocytė (GSV, 3.0x, 5 drafts) = 0.84 -- Low-draft player correctly faded by the field
  - L. Amihere (GSV, 2.1x, 78 drafts) = 0.89 -- High-draft player underperformed -- field took the loss equally
  - K. Stokes (GSV, 1.8x, 81 drafts) = 0.84 -- High-draft player underperformed -- field took the loss equally
  - T. Hayes (GSV, 1.8x, 94 drafts) = 0.69 -- High-draft player underperformed -- field took the loss equally
  - C. Carter (LVA, 0.4x, 225 drafts) = 1.05 -- High-draft player underperformed -- field took the loss equally
  - K. Charles (GSV, 1.9x, None drafts) = -0.2 -- Low-draft player correctly faded by the field
  - C. Parker-Tyus (LVA, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2026-06-01

**Players**: 20 HV
 | **Games**: 4 (SEA@DAL, DAL@SEA, PHO@MIN, MIN@PHO)
 | **Score range**: 1.29 -- 6.40 (median 2.39)

**Leaderboard**: top score 51.14, floor 45.13, median 47.11

**Winner** (score 51.14):
  - C. Williams (2.3x) = 14.72
  - O. Miles (2.2x) = 11.40
  - M. Akoa Makani (2.9000000000000004x) = 4.88
  - A. Delaere (4.4x) = 14.09
  - N. Brochant (4.2x) = 6.05
  - **Game stack**: team 5: 3 players, team 6: 2 players

**Field ownership** (top-20 entries):
  - A. Kosu (4.4x/4.6x/4.2x/4.8x): 15/20 = 75%, avg 14.78
  - A. Delaere (4.8x/4.6x/4.2x/4.4x/5x): 13/20 = 65%, avg 14.73
  - C. Williams (1.9x/1.5x/2.3x): 11/20 = 55%, avg 13.33
  - O. Miles (1.6x/2.4x/2x/1.8x/2.2x): 11/20 = 55%, avg 10.83
  - K. Linskens (4.4x/4.2x/4.8x): 7/20 = 35%, avg 6.80
  - M. Caldwell (4.4x/4.6x/4.8x/5x): 6/20 = 30%, avg 3.29
  - K. Copper (2.9x/2.3x/2.7x): 5/20 = 25%, avg 5.17
  - A. Thomas (1.5x/1.3x): 5/20 = 25%, avg 1.81

### Model Performance

**Our frozen lineup**:
  - Jessica Shepard (DAL, 0.2x boost) -- pred p50=3.989075079350421
  - Joyner Holmes (SEA, 3.0x boost) -- pred p50=1.7659200000000002
  - Maddy Siegrist (DAL, 2.8x boost) -- pred p50=1.795715622081361
  - Jordan Horston (SEA, 3.0x boost) -- pred p50=1.794344712217033
  - Teaira McCowan (MIN, 3.0x boost) -- pred p50=1.7928000000000002

**Prediction accuracy**:
  - Jessica Shepard: pred 3.99 vs actual 2.50 (error -1.49) [IN BAND]
  - Maddy Siegrist: pred 1.80 vs actual 2.71 (error +0.91) [IN BAND]
  - Jordan Horston: pred 1.79 vs actual 1.29 (error -0.51) [IN BAND]
  - **MAE**: 0.97 | **In-band rate**: 3/3

**Rank correlation** (our picks vs realized): 0.500

**Leverage** (ownership differentiation):
  - Jessica Shepard: field ownership 5% [DIFFERENTIATED]
  - Joyner Holmes: field ownership 0% [DIFFERENTIATED]
  - Maddy Siegrist: field ownership 5% [DIFFERENTIATED]
  - Jordan Horston: field ownership 10% [DIFFERENTIATED]
  - Teaira McCowan: field ownership 0% [DIFFERENTIATED]

**Our game stacks**: {'DAL': ['Jessica Shepard', 'Maddy Siegrist'], 'SEA': ['Joyner Holmes', 'Jordan Horston']}

### Outcome Classification

**(A) Correctly priced** (20 players):
  - A. Kosu (MIN, 3.0x, 13 drafts) = 3.31 -- Mid-draft player with mid outcome -- no edge either way
  - A. Delaere (MIN, 3.0x, 17 drafts) = 3.2 -- Mid-draft player with mid outcome -- no edge either way
  - C. Williams (MIN, 0.3x, 384 drafts) = 6.4 -- High-draft player delivered as expected
  - A. James (DAL, 2.9x, 6 drafts) = 2.94 -- Outcome roughly matched draft position and signals
  - M. Siegrist (DAL, 2.8x, 8 drafts) = 2.71 -- Outcome roughly matched draft position and signals
  - O. Miles (MIN, 0.4x, 344 drafts) = 5.18 -- High-draft player delivered as expected
  - A. Fam (SEA, 3.0x, 17 drafts) = 2.19 -- Mid-draft player with mid outcome -- no edge either way
  - A. Clark (DAL, 3.0x, 1 drafts) = 1.74 -- Outcome roughly matched draft position and signals
  - K. Linskens (PHO, 3.0x, 15 drafts) = 1.48 -- Mid-draft player with mid outcome -- no edge either way
  - N. Brochant (PHO, 3.0x, 22 drafts) = 1.44 -- Mid-draft player with mid outcome -- no edge either way
  - F. Johnson (SEA, 1.2x, 141 drafts) = 2.18 -- Outcome roughly matched draft position and signals
  - N. Coffey (MIN, 0.9x, 195 drafts) = 2.33 -- Outcome roughly matched draft position and signals
  - N. Howard (MIN, 0.3x, 417 drafts) = 2.94 -- Outcome roughly matched draft position and signals
  - P. Bueckers (DAL, 0.3x, 1800 drafts) = 2.92 -- Outcome roughly matched draft position and signals
  - K. McBride (MIN, 0.8x, 218 drafts) = 2.39 -- Outcome roughly matched draft position and signals
  - J. Horston (SEA, 3.0x, 9 drafts) = 1.29 -- Low-draft player correctly faded by the field
  - K. Copper (PHO, 1.1x, 248 drafts) = 2.0 -- Outcome roughly matched draft position and signals
  - M. Akoa Makani (PHO, 1.3x, 24 drafts) = 1.68 -- Mid-draft player with mid outcome -- no edge either way
  - J. Shepard (DAL, 0.2x, 1000 drafts) = 2.5 -- Outcome roughly matched draft position and signals
  - A. Ogunbowale (DAL, 1.3x, 161 drafts) = 1.61 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2026-06-02

**Players**: 20 HV
 | **Games**: 8 (WAS@CHI, LAS@LVA, LVA@LAS, CHI@WAS, CON@ATL, ATL@CON)
 | **Score range**: 2.31 -- 6.77 (median 3.64)

**Leaderboard**: top score 53.41, floor 50.62, median 51.08

**Winner** (score 53.41):
  - A. Wilson (2x) = 11.38
  - A. Reese (2.4x) = 8.73
  - A. Morrow (2.6x) = 11.05
  - R. Burrell (3.9x) = 10.65
  - K. Thornton (2.9x) = 11.59

**Field ownership** (top-20 entries):
  - A. Morrow (2.4x/2.8x/2.2x/2.6x): 15/20 = 75%, avg 10.65
  - A. Wilson (2x): 14/20 = 70%, avg 11.38
  - E. Engstler (2.9x/2.3x/2.5x/2.7x): 12/20 = 60%, avg 8.43
  - R. Howard (1.8x/2x/2.2x): 12/20 = 60%, avg 13.77
  - C. Gray (2.4x/2.2x/2.6x): 6/20 = 30%, avg 8.68
  - A. Reese (2.4x/2x/2.2x): 5/20 = 25%, avg 8.00
  - K. Thornton (2.9x/3.5x/3.3x): 5/20 = 25%, avg 13.03
  - C. Zandalasini (4.4x/4.2x): 5/20 = 25%, avg 10.72

### Model Performance

**Our frozen lineup**:
  - A'ja Wilson (LVA, 0.0x boost) -- pred p50=4.855037831933824
  - Jackie Young (LVA, 0.5x boost) -- pred p50=4.09012269316015
  - Elizabeth Williams (CHI, 2.5x boost) -- pred p50=1.9487143256277077
  - Sydney Taylor (CHI, 2.1x boost) -- pred p50=1.859669300754173
  - Rae Burrell (LAS, 2.5x boost) -- pred p50=1.660649239005508

**Prediction accuracy**:
  - A'ja Wilson: pred 4.86 vs actual 5.69 (error +0.84) [IN BAND]
  - Jackie Young: pred 4.09 vs actual 3.78 (error -0.31) [IN BAND]
  - Elizabeth Williams: pred 1.95 vs actual 2.68 (error +0.74) [IN BAND]
  - Rae Burrell: pred 1.66 vs actual 2.73 (error +1.07) [IN BAND]
  - **MAE**: 0.74 | **In-band rate**: 4/4

**Rank correlation** (our picks vs realized): 0.800

**Leverage** (ownership differentiation):
  - A'ja Wilson: field ownership 70% [chalk]
  - Jackie Young: field ownership 10% [DIFFERENTIATED]
  - Elizabeth Williams: field ownership 0% [DIFFERENTIATED]
  - Sydney Taylor: field ownership 0% [DIFFERENTIATED]
  - Rae Burrell: field ownership 10% [DIFFERENTIATED]

**Our game stacks**: {'LVA': ["A'ja Wilson", 'Jackie Young'], 'CHI': ['Elizabeth Williams', 'Sydney Taylor']}

### Outcome Classification

**(A) Correctly priced** (20 players):
  - R. Howard (ATL, 0.2x, 238 drafts) = 6.77 -- High-draft player delivered as expected
  - K. Thornton (GSV, 1.7x, 33 drafts) = 4.0 -- Mid-draft player with mid outcome -- no edge either way
  - C. McMahon (WAS, 3.0x, 1 drafts) = 2.73 -- Outcome roughly matched draft position and signals
  - A. Morrow (CON, 1.0x, 149 drafts) = 4.25 -- High-draft player delivered as expected
  - C. Zandalasini (GSV, 3.0x, 4 drafts) = 2.48 -- Outcome roughly matched draft position and signals
  - R. Burrell (LAS, 2.5x, 12 drafts) = 2.73 -- Mid-draft player with mid outcome -- no edge either way
  - E. Williams (CHI, 2.5x, 8 drafts) = 2.68 -- Outcome roughly matched draft position and signals
  - A. Wilson (LVA, 0.0x, 4400 drafts) = 5.69 -- High-draft player delivered as expected
  - A. Gray (ATL, 0.6x, 30 drafts) = 4.29 -- Mid-draft player with mid outcome -- no edge either way
  - K. Cardoso (CHI, 0.6x, 157 drafts) = 4.26 -- High-draft player delivered as expected
  - M. Onyenwere (WAS, 2.7x, 182 drafts) = 2.31 -- Outcome roughly matched draft position and signals
  - K. Stokes (GSV, 2.0x, 26 drafts) = 2.66 -- Mid-draft player with mid outcome -- no edge either way
  - C. Gray (LVA, 0.8x, 254 drafts) = 3.78 -- High-draft player delivered as expected
  - E. Engstler (POR, 1.1x, 282 drafts) = 3.26 -- High-draft player delivered as expected
  - C. Brink (LAS, 1.9x, 298 drafts) = 2.52 -- Outcome roughly matched draft position and signals
  - J. Canada (ATL, 0.6x, 118 drafts) = 3.71 -- High-draft player delivered as expected
  - A. Reese (ATL, 0.6x, 397 drafts) = 3.64 -- High-draft player delivered as expected
  - J. Young (LVA, 0.5x, 273 drafts) = 3.78 -- High-draft player delivered as expected
  - V. Burton (GSV, 0.4x, 58 drafts) = 3.64 -- High-draft player delivered as expected
  - J. Salaün (GSV, 0.9x, 41 drafts) = 3.01 -- Mid-draft player with mid outcome -- no edge either way

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2026-06-03

**Players**: 20 HV
 | **Games**: 4 (PHO@SEA, TOR@NYL, SEA@PHO, NYL@TOR)
 | **Score range**: 1.30 -- 6.40 (median 2.70)

**Leaderboard**: top score 55.41, floor 50.56, median 51.31

**Winner** (score 55.41):
  - J. Jones (2.6x) = 16.64
  - A. Fam (4.3x) = 13.71
  - M. Conde (4.2x) = 6.89
  - L. Fiebich (4.4x) = 14.09
  - J. Horston (4.2x) = 4.08
  - **Game stack**: team 4: 2 players, team 10: 2 players

**Field ownership** (top-20 entries):
  - A. Fam (4.3x/4.1x/3.7x/3.9x): 19/20 = 95%, avg 12.77
  - J. Jones (2.4x/1.8x/2.6x): 17/20 = 85%, avg 15.44
  - S. Sabally (4.4x/4.2x): 14/20 = 70%, avg 6.99
  - K. Copper (2.9x/2.7x): 11/20 = 55%, avg 7.31
  - B. Stewart (2.3x): 10/20 = 50%, avg 8.64
  - L. Fiebich (4.4x/4.2x/4.8x): 8/20 = 40%, avg 13.85
  - N. Mack (2.4x/2.6x): 5/20 = 25%, avg 11.81
  - J. Horston (4.4x/4.2x): 4/20 = 20%, avg 4.13

### Model Performance

**Our frozen lineup**:
  - Jonquel Jones (NYL, 0.6x boost) -- pred p50=2.6669969163138
  - Kiki Rice (TOR, 0.8x boost) -- pred p50=2.5176484045011005
  - Betnijah Laney-Hamilton (NYL, 2.0x boost) -- pred p50=1.6869430107540886
  - Maria Conde (TOR, 2.6x boost) -- pred p50=1.4542370946942325
  - Jordan Horston (SEA, 3.0x boost) -- pred p50=1.4078415619515139

**Prediction accuracy**:
  - Jonquel Jones: pred 2.67 vs actual 6.40 (error +3.73) [IN BAND]
  - Maria Conde: pred 1.45 vs actual 1.64 (error +0.19) [IN BAND]
  - **MAE**: 1.96 | **In-band rate**: 2/2

**Leverage** (ownership differentiation):
  - Jonquel Jones: field ownership 85% [chalk]
  - Kiki Rice: field ownership 0% [DIFFERENTIATED]
  - Betnijah Laney-Hamilton: field ownership 0% [DIFFERENTIATED]
  - Maria Conde: field ownership 15% [DIFFERENTIATED]
  - Jordan Horston: field ownership 20% [DIFFERENTIATED]

**Our game stacks**: {'NYL': ['Jonquel Jones', 'Betnijah Laney-Hamilton'], 'TOR': ['Kiki Rice', 'Maria Conde']}

### Outcome Classification

**(A) Correctly priced** (19 players):
  - J. Jones (NYL, 0.6x, 467 drafts) = 6.4 -- High-draft player delivered as expected
  - A. Fam (SEA, 2.5x, 65 drafts) = 3.19 -- High-draft player delivered as expected
  - N. Mack (PHO, 0.8x, 228 drafts) = 4.61 -- High-draft player delivered as expected
  - N. Hiedeman (SEA, 1.1x, 215 drafts) = 3.3 -- High-draft player delivered as expected
  - B. Stewart (NYL, 0.3x, 1600 drafts) = 3.76 -- High-draft player delivered as expected
  - K. Copper (PHO, 1.1x, 455 drafts) = 2.69 -- Outcome roughly matched draft position and signals
  - S. Sabally (NYL, 3.0x, 30 drafts) = 1.64 -- Mid-draft player with mid outcome -- no edge either way
  - M. Akoa Makani (PHO, 1.5x, 37 drafts) = 2.17 -- Mid-draft player with mid outcome -- no edge either way
  - M. Conde (TOR, 2.6x, 7 drafts) = 1.64 -- Outcome roughly matched draft position and signals
  - L. Juškaitė (TOR, 1.8x, 152 drafts) = 1.98 -- Outcome roughly matched draft position and signals
  - J. Allemand (TOR, 2.2x, 2 drafts) = 1.77 -- Outcome roughly matched draft position and signals
  - M. Johannes (NYL, 0.7x, 249 drafts) = 2.73 -- Outcome roughly matched draft position and signals
  - P. Astier (NYL, 0.7x, 197 drafts) = 2.7 -- Outcome roughly matched draft position and signals
  - M. Mabrey (TOR, 0.4x, 483 drafts) = 2.97 -- Outcome roughly matched draft position and signals
  - B. Sykes (TOR, 0.4x, 371 drafts) = 2.86 -- Outcome roughly matched draft position and signals
  - M. Holmes (SEA, 2.4x, 146 drafts) = 1.5 -- Outcome roughly matched draft position and signals
  - N. Brochant (PHO, 3.0x, 29 drafts) = 1.3 -- Mid-draft player with mid outcome -- no edge either way
  - N. Sabally (TOR, 0.6x, 176 drafts) = 2.36 -- Outcome roughly matched draft position and signals
  - D. Bonner (PHO, 1.6x, 175 drafts) = 1.66 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - L. Fiebich (NYL, 3.0x, 9 drafts) = 3.2 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2026-06-04

**Players**: 20 HV
 | **Games**: 4 (ATL@IND, MIN@GSV, IND@ATL, GSV@MIN)
 | **Score range**: 1.19 -- 7.33 (median 2.60)

**Leaderboard**: top score 53.25, floor 48.53, median 49.21

**Winner** (score 53.25):
  - C. Zandalasini (4.5x) = 13.06
  - O. Miles (2.1x) = 15.39
  - N. Coffey (2.5x) = 6.68
  - T. Hayes (3.6999999999999997x) = 12.23
  - K. Stokes (3x) = 5.89
  - **Game stack**: team 14: 3 players, team 5: 2 players

**Field ownership** (top-20 entries):
  - O. Miles (1.9x/2.3x/1.5x/2.1x/1.7x): 19/20 = 95%, avg 15.39
  - C. Zandalasini (4.5x/3.9x/3.7x): 12/20 = 60%, avg 11.47
  - T. Hayes (4.1x/3.7x/3.9x/3.5x): 10/20 = 50%, avg 12.49
  - K. Chen (4.4x/3.6x): 10/20 = 50%, avg 7.42
  - N. Hillmon (3.2x/3.4x): 8/20 = 40%, avg 7.64
  - J. Salaün (2.8x/2.6x/2.4x/2x/2.2x): 7/20 = 35%, avg 8.41
  - C. Clark (2.3x): 7/20 = 35%, avg 7.54
  - N. Coffey (2.1x/2.5x/2.7x): 6/20 = 30%, avg 6.59

### Model Performance

**Our frozen lineup**:
  - Rhyne Howard (ATL, 0.1x boost) -- pred p50=3.870937466130351
  - Janelle Salaün (GSV, 0.8x boost) -- pred p50=2.784296370570095
  - Sophie Cunningham (IND, 1.7x boost) -- pred p50=2.1188050993944065
  - Cecilia Zandalasini (GSV, 2.5x boost) -- pred p50=1.5574715002329624
  - Makayla Timpson (IND, 3.0x boost) -- pred p50=1.3695702796924583

**Prediction accuracy**:
  - Janelle Salaün: pred 2.78 vs actual 3.59 (error +0.81) [IN BAND]
  - Cecilia Zandalasini: pred 1.56 vs actual 2.90 (error +1.35) [IN BAND]
  - **MAE**: 1.08 | **In-band rate**: 2/2

**Leverage** (ownership differentiation):
  - Rhyne Howard: field ownership 0% [DIFFERENTIATED]
  - Janelle Salaün: field ownership 35% [chalk]
  - Sophie Cunningham: field ownership 0% [DIFFERENTIATED]
  - Cecilia Zandalasini: field ownership 60% [chalk]
  - Makayla Timpson: field ownership 0% [DIFFERENTIATED]

**Our game stacks**: {'GSV': ['Janelle Salaün', 'Cecilia Zandalasini'], 'IND': ['Sophie Cunningham', 'Makayla Timpson']}

### Outcome Classification

**(A) Correctly priced** (20 players):
  - O. Miles (MIN, 0.3x, 630 drafts) = 7.33 -- High-draft player delivered as expected
  - T. Hayes (GSV, 2.3x, 14 drafts) = 3.3 -- Mid-draft player with mid outcome -- no edge either way
  - C. Zandalasini (GSV, 2.5x, 36 drafts) = 2.9 -- Mid-draft player with mid outcome -- no edge either way
  - K. Mitchell (IND, 0.6x, 231 drafts) = 4.67 -- High-draft player delivered as expected
  - J. Salaün (GSV, 0.8x, 161 drafts) = 3.59 -- High-draft player delivered as expected
  - K. McBride (MIN, 0.9x, 182 drafts) = 3.24 -- High-draft player delivered as expected
  - M. Hines-Allen (IND, 2.9x, 3 drafts) = 1.89 -- Outcome roughly matched draft position and signals
  - K. Chen (GSV, 2.4x, 124 drafts) = 2.02 -- Outcome roughly matched draft position and signals
  - N. Hillmon (ATL, 1.8x, 93 drafts) = 2.26 -- Outcome roughly matched draft position and signals
  - R. Johnson (IND, 3.0x, 8 drafts) = 1.58 -- Outcome roughly matched draft position and signals
  - N. Coffey (MIN, 0.9x, 199 drafts) = 2.67 -- Outcome roughly matched draft position and signals
  - C. Clark (IND, 0.3x, 968 drafts) = 3.28 -- High-draft player delivered as expected
  - M. Okot (ATL, 3.0x, 1 drafts) = 1.49 -- Low-draft player correctly faded by the field
  - K. Stokes (GSV, 1.8x, 129 drafts) = 1.96 -- Outcome roughly matched draft position and signals
  - A. Kosu (MIN, 3.0x, 12 drafts) = 1.42 -- Mid-draft player with mid outcome -- no edge either way
  - A. Boston (IND, 0.4x, 319 drafts) = 2.95 -- Outcome roughly matched draft position and signals
  - J. Canada (ATL, 0.5x, 143 drafts) = 2.6 -- Outcome roughly matched draft position and signals
  - G. Williams (GSV, 0.8x, 299 drafts) = 2.32 -- Outcome roughly matched draft position and signals
  - M. Caldwell (MIN, 3.0x, 17 drafts) = 1.19 -- Mid-draft player with mid outcome -- no edge either way
  - A. Reese (ATL, 0.5x, 566 drafts) = 2.35 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2026-06-05

**Players**: 20 HV
 | **Games**: 6 (PHO@POR, POR@PHO, DAL@LAS, LAS@DAL, CON@CHI, CHI@CON)
 | **Score range**: 1.95 -- 5.48 (median 3.21)

**Leaderboard**: top score 68.67, floor 62.91, median 63.94

**Winner** (score 68.67):
  - P. Bueckers (2.3x) = 12.60
  - A. Ogunbowale (3.2x) = 16.73
  - D. Bonner (3.3x) = 16.16
  - M. Siegrist (3.8x) = 14.39
  - N. Brochant (4.2x) = 8.78
  - **Game stack**: team 12: 3 players, team 6: 2 players

**Field ownership** (top-20 entries):
  - M. Siegrist (4x/3.8x/3.6x): 20/20 = 100%, avg 14.50
  - A. Ogunbowale (3.2x/3x/3.4x): 19/20 = 95%, avg 16.29
  - P. Bueckers (2.3x): 16/20 = 80%, avg 12.60
  - A. Morrow (2.7x): 10/20 = 50%, avg 8.93
  - D. Miller (4.2x): 10/20 = 50%, avg 11.30
  - D. Bonner (3.1x/3.3x): 6/20 = 30%, avg 15.67
  - N. Brochant (4.2x): 6/20 = 30%, avg 8.78
  - A. Stevens (4.4x/4.2x): 5/20 = 25%, avg 11.64

### Model Performance

**Our frozen lineup**:
  - Jessica Shepard (DAL, 0.3x boost) -- pred p50=3.6633992311170585
  - Aneesah Morrow (CON, 0.9x boost) -- pred p50=2.878126948868144
  - Maddy Siegrist (DAL, 2.4x boost) -- pred p50=2.2420459900882483
  - Sydney Taylor (CHI, 2.0x boost) -- pred p50=1.9178756265812398
  - Elizabeth Williams (CHI, 2.2x boost) -- pred p50=1.8797940974696963

**Prediction accuracy**:
  - Jessica Shepard: pred 3.66 vs actual 4.98 (error +1.32) [IN BAND]
  - Aneesah Morrow: pred 2.88 vs actual 3.31 (error +0.43) [IN BAND]
  - Maddy Siegrist: pred 2.24 vs actual 3.79 (error +1.54) [IN BAND]
  - Elizabeth Williams: pred 1.88 vs actual 2.64 (error +0.76) [IN BAND]
  - **MAE**: 1.01 | **In-band rate**: 4/4

**Rank correlation** (our picks vs realized): 0.800

**Leverage** (ownership differentiation):
  - Jessica Shepard: field ownership 0% [DIFFERENTIATED]
  - Aneesah Morrow: field ownership 50% [chalk]
  - Maddy Siegrist: field ownership 100% [chalk]
  - Sydney Taylor: field ownership 0% [DIFFERENTIATED]
  - Elizabeth Williams: field ownership 0% [DIFFERENTIATED]

**Our game stacks**: {'DAL': ['Jessica Shepard', 'Maddy Siegrist'], 'CHI': ['Sydney Taylor', 'Elizabeth Williams']}

### Outcome Classification

**(A) Correctly priced** (18 players):
  - D. Bonner (PHO, 1.7x, 39 drafts) = 4.9 -- Mid-draft player with mid outcome -- no edge either way
  - A. Ogunbowale (DAL, 1.4x, 210 drafts) = 5.23 -- High-draft player delivered as expected
  - D. Miller (CON, 3.0x, 5 drafts) = 2.69 -- Outcome roughly matched draft position and signals
  - A. Stevens (CHI, 3.0x, 7 drafts) = 2.67 -- Outcome roughly matched draft position and signals
  - P. Bueckers (DAL, 0.3x, 2500 drafts) = 5.48 -- High-draft player delivered as expected
  - J. Shepard (DAL, 0.3x, 646 drafts) = 4.98 -- High-draft player delivered as expected
  - S. Rivers (CON, 2.4x, 8 drafts) = 2.6 -- Outcome roughly matched draft position and signals
  - A. Atkins (LAS, 1.5x, 84 drafts) = 3.21 -- High-draft player delivered as expected
  - E. Williams (CHI, 2.2x, 1 drafts) = 2.64 -- Outcome roughly matched draft position and signals
  - K. Samuelson (POR, 3.0x, 2 drafts) = 2.51 -- Outcome roughly matched draft position and signals
  - N. Brochant (PHO, 3.0x, 3 drafts) = 2.09 -- Outcome roughly matched draft position and signals
  - J. Nogic (PHO, 1.8x, 147 drafts) = 2.74 -- Outcome roughly matched draft position and signals
  - N. Ogwumike (LAS, 0.6x, 273 drafts) = 3.98 -- High-draft player delivered as expected
  - S. Barker (POR, 1.5x, 153 drafts) = 2.91 -- Outcome roughly matched draft position and signals
  - R. Banham (CHI, 3.0x, 1 drafts) = 1.95 -- Outcome roughly matched draft position and signals
  - A. Morrow (CON, 0.9x, 743 drafts) = 3.31 -- High-draft player delivered as expected
  - S. Diggins (CHI, 0.5x, 244 drafts) = 3.79 -- High-draft player delivered as expected
  - M. Akoa Makani (PHO, 1.4x, 15 drafts) = 2.72 -- Mid-draft player with mid outcome -- no edge either way

**(B) Knowable misses** (1 players):
  - **M. Siegrist** (DAL, 2.4x, 7 drafts) = 3.79 -- Strong signals (high_total, low_boost) but under-drafted

**(C) Unknowable / winners' edge** (1 players):
  - B. Griner (CON, 1.1x, 4 drafts) = 4.16 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 knowable misses and 1 unknowable outcomes. Mixed slate.

---

## 2026-06-06

**Players**: 20 HV
 | **Games**: 8 (WAS@ATL, GSV@LVA, NYL@IND, LVA@GSV, ATL@WAS, IND@NYL)
 | **Score range**: 1.63 -- 5.64 (median 3.36)

**Leaderboard**: top score 51.44, floor 47.25, median 47.68

**Winner** (score 51.44):
  - A. Wilson (2x) = 11.28
  - M. Billings (4.2x) = 14.15
  - A. Reese (2.2x) = 9.70
  - N. Howard (1.7999999999999998x) = 9.46
  - N. Hiedeman (2.2x) = 6.86

**Field ownership** (top-20 entries):
  - A. Wilson (1.8x/2x): 19/20 = 95%, avg 11.22
  - A. Reese (2.4x/2x/2.2x): 17/20 = 85%, avg 9.28
  - J. Young (1.9x/2.3x/2.1x/1.7x/2.5x): 16/20 = 80%, avg 10.96
  - N. Howard (1.8x/2x/2.2x/2.4x): 10/20 = 50%, avg 10.72
  - G. Williams (2.4x/2x/2.2x): 10/20 = 50%, avg 9.73
  - B. Stewart (1.9x/2.1x/1.7x/1.5x): 9/20 = 45%, avg 9.11
  - C. Gray (2.1x/2.3x): 4/20 = 20%, avg 6.63
  - N. Hiedeman (2.2x): 3/20 = 15%, avg 6.86

### Model Performance

**Our frozen lineup**:
  - Jackie Young (LVA, 0.5x boost) -- pred p50=4.124191311858593
  - Chelsea Gray (LVA, 0.7x boost) -- pred p50=3.5046437856914863
  - Kelsey Mitchell (IND, 0.5x boost) -- pred p50=3.390232964674219
  - Sophie Cunningham (IND, 1.9x boost) -- pred p50=2.055345653037445
  - Cecilia Zandalasini (GSV, 2.0x boost) -- pred p50=1.8090087703554234

**Prediction accuracy**:
  - Jackie Young: pred 4.12 vs actual 5.19 (error +1.07) [IN BAND]
  - Chelsea Gray: pred 3.50 vs actual 3.01 (error -0.49) [IN BAND]
  - **MAE**: 0.78 | **In-band rate**: 2/2

**Leverage** (ownership differentiation):
  - Jackie Young: field ownership 80% [chalk]
  - Chelsea Gray: field ownership 20% [DIFFERENTIATED]
  - Kelsey Mitchell: field ownership 10% [DIFFERENTIATED]
  - Sophie Cunningham: field ownership 0% [DIFFERENTIATED]
  - Cecilia Zandalasini: field ownership 0% [DIFFERENTIATED]

**Our game stacks**: {'LVA': ['Jackie Young', 'Chelsea Gray'], 'IND': ['Kelsey Mitchell', 'Sophie Cunningham']}

### Outcome Classification

**(A) Correctly priced** (19 players):
  - M. Billings (IND, 2.4x, 31 drafts) = 3.37 -- Mid-draft player with mid outcome -- no edge either way
  - G. Williams (GSV, 0.8x, 38 drafts) = 4.72 -- Mid-draft player with mid outcome -- no edge either way
  - J. Young (LVA, 0.5x, 146 drafts) = 5.19 -- High-draft player delivered as expected
  - N. Howard (MIN, 0.4x, 116 drafts) = 5.26 -- High-draft player delivered as expected
  - A. Reese (ATL, 0.6x, 290 drafts) = 4.41 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 2900 drafts) = 5.64 -- High-draft player delivered as expected
  - B. Stewart (NYL, 0.3x, 526 drafts) = 4.68 -- High-draft player delivered as expected
  - S. Koné (ATL, 3.0x, 1 drafts) = 2.44 -- Outcome roughly matched draft position and signals
  - O. Miles (MIN, 0.2x, 464 drafts) = 4.28 -- High-draft player delivered as expected
  - N. Hiedeman (SEA, 1.0x, 14 drafts) = 3.12 -- Mid-draft player with mid outcome -- no edge either way
  - R. Howard (ATL, 0.2x, 239 drafts) = 4.08 -- High-draft player delivered as expected
  - K. Thornton (GSV, 1.4x, 7 drafts) = 2.57 -- Outcome roughly matched draft position and signals
  - T. Paopao (ATL, 3.0x, 1 drafts) = 1.87 -- Outcome roughly matched draft position and signals
  - K. Iriafen (WAS, 0.5x, 61 drafts) = 3.33 -- High-draft player delivered as expected
  - S. Sabally (NYL, 3.0x, 37 drafts) = 1.63 -- Mid-draft player with mid outcome -- no edge either way
  - C. Gray (LVA, 0.7x, 142 drafts) = 3.01 -- High-draft player delivered as expected
  - L. Fiebich (NYL, 2.2x, 9 drafts) = 1.94 -- Outcome roughly matched draft position and signals
  - S. Talbot (LVA, 2.8x, 3 drafts) = 1.65 -- Outcome roughly matched draft position and signals
  - L. Hull (IND, 2.7x, 14 drafts) = 1.65 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (1 players):
  - N. Coffey (MIN, 0.9x, 3 drafts) = 3.36 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2026-06-07

**Players**: 20 HV
 | **Games**: 4 (CHI@TOR, POR@LAS, TOR@CHI, LAS@POR)
 | **Score range**: 1.22 -- 4.86 (median 1.70)

**Leaderboard**: top score 47.16, floor 43.22, median 43.75

**Winner** (score 47.16):
  - K. Plum (2x) = 9.59
  - D. Hamby (2.2x) = 10.68
  - N. Sabally (2.2x) = 6.74
  - M. Gustafson (3.2x) = 10.26
  - A. Stevens (3.5x) = 9.89
  - **Game stack**: team 9: 2 players

**Field ownership** (top-20 entries):
  - N. Ogwumike (1.9x/2.3x/2.1x/1.7x/2.5x): 19/20 = 95%, avg 10.57
  - K. Plum (1.6x/1.4x/1.2x/2x/1.8x): 17/20 = 85%, avg 8.35
  - D. Hamby (1.8x/2x/2.2x): 16/20 = 80%, avg 10.08
  - M. Gustafson (3x/3.2x/3.8x/3.6x/3.4x): 12/20 = 60%, avg 10.64
  - N. Sabally (1.8x/2x/2.2x): 10/20 = 50%, avg 6.01
  - B. Sykes (1.6x/2.4x/2x/1.8x/2.2x): 10/20 = 50%, avg 9.02
  - A. Stevens (3.5x/3.7x): 5/20 = 25%, avg 10.11
  - E. Williams (3.4x): 2/20 = 10%, avg 5.74

### Model Performance

**Our frozen lineup**:
  - Bridget Carleton (POR, 0.8x boost) -- pred p50=2.7069954964458924
  - Cameron Brink (LAS, 1.8x boost) -- pred p50=1.7573489226317154
  - Rae Burrell (LAS, 2.2x boost) -- pred p50=1.6990030789297268
  - Julie Allemand (TOR, 2.1x boost) -- pred p50=1.457151720285948
  - Jacy Sheldon (CHI, 2.1x boost) -- pred p50=1.3082584608702787

**Prediction accuracy**:
  - Rae Burrell: pred 1.70 vs actual 1.70 (error +0.00) [IN BAND]
  - Julie Allemand: pred 1.46 vs actual 1.51 (error +0.05) [IN BAND]
  - **MAE**: 0.03 | **In-band rate**: 2/2

**Leverage** (ownership differentiation):
  - Bridget Carleton: field ownership 0% [DIFFERENTIATED]
  - Cameron Brink: field ownership 0% [DIFFERENTIATED]
  - Rae Burrell: field ownership 5% [DIFFERENTIATED]
  - Julie Allemand: field ownership 0% [DIFFERENTIATED]
  - Jacy Sheldon: field ownership 0% [DIFFERENTIATED]

**Our game stacks**: {'LAS': ['Cameron Brink', 'Rae Burrell']}

### Outcome Classification

**(A) Correctly priced** (20 players):
  - M. Gustafson (POR, 1.8x, 149 drafts) = 3.21 -- High-draft player delivered as expected
  - A. Stevens (CHI, 2.3x, 9 drafts) = 2.83 -- Outcome roughly matched draft position and signals
  - N. Ogwumike (LAS, 0.5x, 401 drafts) = 4.72 -- High-draft player delivered as expected
  - D. Hamby (LAS, 0.4x, 386 drafts) = 4.86 -- High-draft player delivered as expected
  - B. Sykes (TOR, 0.4x, 564 drafts) = 4.34 -- High-draft player delivered as expected
  - K. Plum (LAS, 0.0x, 3100 drafts) = 4.79 -- High-draft player delivered as expected
  - N. Sabally (TOR, 0.6x, 159 drafts) = 3.06 -- High-draft player delivered as expected
  - F. Buhner (POR, 3.0x, 27 drafts) = 1.43 -- Mid-draft player with mid outcome -- no edge either way
  - R. Burrell (LAS, 2.2x, 48 drafts) = 1.7 -- Mid-draft player with mid outcome -- no edge either way
  - E. Williams (CHI, 2.0x, 77 drafts) = 1.69 -- Outcome roughly matched draft position and signals
  - K. Samuelson (POR, 3.0x, 11 drafts) = 1.26 -- Mid-draft player with mid outcome -- no edge either way
  - J. Allemand (TOR, 2.1x, 52 drafts) = 1.51 -- Outcome roughly matched draft position and signals
  - K. Martin (LAS, 3.0x, 2 drafts) = 1.22 -- Low-draft player correctly faded by the field
  - L. Juškaitė (TOR, 1.7x, 96 drafts) = 1.64 -- Outcome roughly matched draft position and signals
  - M. Mabrey (TOR, 0.4x, 351 drafts) = 2.5 -- Outcome roughly matched draft position and signals
  - E. Wheeler (LAS, 1.5x, 137 drafts) = 1.69 -- Outcome roughly matched draft position and signals
  - M. Conde (TOR, 2.6x, 1 drafts) = 1.25 -- Low-draft player correctly faded by the field
  - I. Harrison (TOR, 0.0x, 1 drafts) = 3.0 -- Outcome roughly matched draft position and signals
  - S. Barker (POR, 1.4x, 38 drafts) = 1.55 -- Mid-draft player with mid outcome -- no edge either way
  - G. Jaquez (CHI, 1.4x, 1 drafts) = 1.49 -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2026-06-08

**Players**: 20 HV
 | **Games**: 6 (NYL@CON, SEA@LVA, CON@NYL, WAS@IND, IND@WAS, LVA@SEA)
 | **Score range**: 1.53 -- 8.26 (median 2.96)

**Leaderboard**: top score 61.77, floor 57.00, median 57.24

**Winner** (score 61.77):
  - A. Wilson (2x) = 16.51
  - B. Stewart (2.1x) = 10.40
  - J. Young (2x) = 10.01
  - O. Nelson-Ododa (3.9x) = 12.41
  - H. Xu (4.2x) = 12.43
  - **Game stack**: team 1: 2 players, team 4: 2 players

**Field ownership** (top-20 entries):
  - A. Wilson (2x): 20/20 = 100%, avg 16.51
  - O. Nelson-Ododa (4.1x/3.7x/3.9x): 20/20 = 100%, avg 12.92
  - H. Xu (4.2x): 19/20 = 95%, avg 12.43
  - D. Miller (4.1x): 17/20 = 85%, avg 7.03
  - L. Lacan (3.9x): 16/20 = 80%, avg 8.21
  - B. Stewart (2.1x/1.7x): 4/20 = 20%, avg 9.90
  - J. Young (2x/2.2x): 2/20 = 10%, avg 10.51
  - A. Boston (2.1x): 1/20 = 5%, avg 6.17

### Model Performance

**Our frozen lineup**:
  - A'ja Wilson (LVA, 0.0x boost) -- pred p50=3.9094866730347784
  - Aliyah Boston (IND, 0.5x boost) -- pred p50=3.152433985451444
  - Shakira Austin (WAS, 0.5x boost) -- pred p50=3.227027515666722
  - Flau'jae Johnson (SEA, 1.3x boost) -- pred p50=1.9203537064375462
  - Leila Lacan (CON, 2.1x boost) -- pred p50=1.7857196290995847

**Prediction accuracy**:
  - A'ja Wilson: pred 3.91 vs actual 8.26 (error +4.35) [IN BAND]
  - Flau'jae Johnson: pred 1.92 vs actual 3.20 (error +1.28) [IN BAND]
  - Leila Lacan: pred 1.79 vs actual 2.11 (error +0.32) [IN BAND]
  - **MAE**: 1.98 | **In-band rate**: 3/3

**Rank correlation** (our picks vs realized): 1.000

**Leverage** (ownership differentiation):
  - A'ja Wilson: field ownership 100% [chalk]
  - Aliyah Boston: field ownership 5% [DIFFERENTIATED]
  - Shakira Austin: field ownership 0% [DIFFERENTIATED]
  - Flau'jae Johnson: field ownership 5% [DIFFERENTIATED]
  - Leila Lacan: field ownership 80% [chalk]

**Our game stacks**: none (diversified)

### Outcome Classification

**(A) Correctly priced** (19 players):
  - A. Wilson (LVA, 0.0x, 5100 drafts) = 8.26 -- High-draft player delivered as expected
  - H. Xu (NYL, 3.0x, 3 drafts) = 2.96 -- Outcome roughly matched draft position and signals
  - G. Amoore (WAS, 3.0x, 6 drafts) = 2.56 -- Outcome roughly matched draft position and signals
  - J. Young (LVA, 0.4x, 314 drafts) = 5.0 -- High-draft player delivered as expected
  - A. Edwards (CON, 2.4x, 2 drafts) = 2.63 -- Outcome roughly matched draft position and signals
  - B. Stewart (NYL, 0.3x, 447 drafts) = 4.95 -- High-draft player delivered as expected
  - M. Onyenwere (WAS, 2.8x, 2 drafts) = 2.35 -- Outcome roughly matched draft position and signals
  - N. Hiedeman (SEA, 1.0x, 157 drafts) = 3.63 -- High-draft player delivered as expected
  - F. Johnson (SEA, 1.3x, 197 drafts) = 3.2 -- High-draft player delivered as expected
  - N. Smith (LVA, 1.1x, 162 drafts) = 3.36 -- High-draft player delivered as expected
  - S. Rivers (CON, 2.2x, 11 drafts) = 2.44 -- Mid-draft player with mid outcome -- no edge either way
  - D. Malonga (SEA, 1.0x, 38 drafts) = 3.13 -- Mid-draft player with mid outcome -- no edge either way
  - C. Gray (LVA, 0.7x, 260 drafts) = 3.25 -- High-draft player delivered as expected
  - A. Dugalić (WAS, 3.0x, 1 drafts) = 1.73 -- Outcome roughly matched draft position and signals
  - L. Lacan (CON, 2.1x, 71 drafts) = 2.11 -- Outcome roughly matched draft position and signals
  - S. Cunningham (IND, 2.1x, 9 drafts) = 2.04 -- Outcome roughly matched draft position and signals
  - A. Fam (SEA, 2.0x, 111 drafts) = 2.06 -- Outcome roughly matched draft position and signals
  - D. Miller (CON, 2.7x, 8 drafts) = 1.71 -- Outcome roughly matched draft position and signals
  - L. Betts (WAS, 3.0x, 3 drafts) = 1.53 -- Outcome roughly matched draft position and signals

**(C) Unknowable / winners' edge** (1 players):
  - O. Nelson-Ododa (CON, 2.5x, 4 drafts) = 3.18 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 1 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2026-06-09

**Players**: 20 HV
 | **Games**: 6 (PHO@GSV, DAL@MIN, CHI@IND, ATL@CHI, MIN@DAL, GSV@PHO)
 | **Score range**: 1.74 -- 5.05 (median 3.78)

**Leaderboard**: top score 53.56, floor 48.28, median 49.25

**Winner** (score 53.56):
  - O. Miles (2.2x) = 9.91
  - V. Burton (2.2x) = 10.62
  - A. Ogunbowale (2.6x) = 10.76
  - N. Cloud (2.7x) = 13.10
  - N. Hillmon (2.9x) = 9.17

**Field ownership** (top-20 entries):
  - K. McBride (2.3x/2.7x/2.9x/2.1x/2.5x): 17/20 = 85%, avg 13.10
  - A. Ogunbowale (3x/2.8x/2.6x/2.4x/2.2x): 15/20 = 75%, avg 10.48
  - V. Burton (1.6x/2.4x/2x/1.8x/2.2x): 11/20 = 55%, avg 9.92
  - A. Reese (1.9x/2.1x/1.7x/2.5x): 10/20 = 50%, avg 7.72
  - O. Miles (1.8x/2x/2.2x): 8/20 = 40%, avg 9.12
  - K. Cardoso (2.4x/2x/2.2x): 8/20 = 40%, avg 8.96
  - N. Cloud (3.1x/2.5x/2.7x): 7/20 = 35%, avg 12.97
  - N. Howard (2.1x): 4/20 = 20%, avg 9.29

### Model Performance

**Our frozen lineup**:
  - Angel Reese (ATL, 0.5x boost) -- pred p50=3.2586835355014143
  - Kayla McBride (MIN, 0.9x boost) -- pred p50=2.932484273076298
  - Naz Hillmon (ATL, 1.7x boost) -- pred p50=2.2311870534000557
  - Elizabeth Williams (CHI, 2.0x boost) -- pred p50=1.847781987522044
  - Cecilia Zandalasini (GSV, 2.3x boost) -- pred p50=1.4339220340874022

**Prediction accuracy**:
  - Angel Reese: pred 3.26 vs actual 3.78 (error +0.52) [IN BAND]
  - Kayla McBride: pred 2.93 vs actual 5.05 (error +2.12) [IN BAND]
  - Naz Hillmon: pred 2.23 vs actual 3.16 (error +0.93) [IN BAND]
  - Elizabeth Williams: pred 1.85 vs actual 3.49 (error +1.64) [IN BAND]
  - **MAE**: 1.30 | **In-band rate**: 4/4

**Rank correlation** (our picks vs realized): 0.564

**Leverage** (ownership differentiation):
  - Angel Reese: field ownership 50% [chalk]
  - Kayla McBride: field ownership 85% [chalk]
  - Naz Hillmon: field ownership 5% [DIFFERENTIATED]
  - Elizabeth Williams: field ownership 20% [DIFFERENTIATED]
  - Cecilia Zandalasini: field ownership 0% [DIFFERENTIATED]

**Our game stacks**: {'ATL': ['Angel Reese', 'Naz Hillmon']}

### Outcome Classification

**(A) Correctly priced** (18 players):
  - N. Brochant (PHO, 3.0x, 17 drafts) = 2.94 -- Mid-draft player with mid outcome -- no edge either way
  - K. McBride (MIN, 0.9x, 139 drafts) = 5.05 -- High-draft player delivered as expected
  - A. Ogunbowale (DAL, 1.0x, 187 drafts) = 4.14 -- High-draft player delivered as expected
  - M. Akoa Makani (PHO, 1.3x, 30 drafts) = 3.64 -- Mid-draft player with mid outcome -- no edge either way
  - V. Burton (GSV, 0.4x, 365 drafts) = 4.83 -- High-draft player delivered as expected
  - A. Thomas (PHO, 0.3x, 297 drafts) = 4.73 -- High-draft player delivered as expected
  - K. Cardoso (CHI, 0.6x, 155 drafts) = 3.98 -- High-draft player delivered as expected
  - N. Howard (MIN, 0.3x, 443 drafts) = 4.42 -- High-draft player delivered as expected
  - O. Miles (MIN, 0.2x, 1700 drafts) = 4.5 -- High-draft player delivered as expected
  - A. Reese (ATL, 0.5x, 927 drafts) = 3.78 -- High-draft player delivered as expected
  - G. Williams (GSV, 0.7x, 276 drafts) = 3.49 -- High-draft player delivered as expected
  - A. Kosu (MIN, 3.0x, 2 drafts) = 1.81 -- Outcome roughly matched draft position and signals
  - K. Thornton (GSV, 1.3x, 53 drafts) = 2.62 -- Outcome roughly matched draft position and signals
  - R. Howard (ATL, 0.2x, 373 drafts) = 3.8 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.3x, 301 drafts) = 3.55 -- High-draft player delivered as expected
  - K. Charles (GSV, 2.2x, 15 drafts) = 1.75 -- Mid-draft player with mid outcome -- no edge either way
  - A. Gray (ATL, 0.6x, 286 drafts) = 2.62 -- Outcome roughly matched draft position and signals
  - M. Siegrist (DAL, 1.9x, 24 drafts) = 1.74 -- Mid-draft player with mid outcome -- no edge either way

**(B) Knowable misses** (2 players):
  - **N. Cloud** (CHI, 1.3x, 6 drafts) = 4.85 -- Strong signals (high_minutes, high_total, low_boost) but under-drafted
  - **N. Hillmon** (ATL, 1.7x, 8 drafts) = 3.16 -- Strong signals (starter, high_minutes, low_boost) but under-drafted

**Takeaway**: 2 knowable misses vs 0 unknowable outcomes. This slate had actionable signal the model or field left on the table.

---

## 2026-06-10

**Players**: 20 HV
 | **Games**: 4 (TOR@CON, LAS@SEA, SEA@LAS, CON@TOR)
 | **Score range**: 1.22 -- 6.74 (median 3.05)

**Leaderboard**: top score 65.69, floor 63.56, median 63.56

**Winner** (score 65.69):
  - C. Brink (4.1x) = 15.81
  - F. Johnson (3x) = 12.16
  - S. Rivers (3.6x) = 15.11
  - A. Fam (3.3x) = 8.65
  - L. Juškaitė (2.9x) = 13.96
  - **Game stack**: team 10: 2 players

**Field ownership** (top-20 entries):
  - F. Johnson (2.8x/3x): 20/20 = 100%, avg 12.04
  - A. Fam (3.5x/3.3x): 19/20 = 95%, avg 8.68
  - B. Sykes (2.3x): 18/20 = 90%, avg 15.49
  - L. Lacan (3.2x/3x/3.6x/3.4x): 18/20 = 90%, avg 15.52
  - A. Edwards (3.3x): 16/20 = 80%, avg 11.63
  - S. Rivers (3.2x/3.8x/3.6x): 4/20 = 20%, avg 14.48
  - C. Brink (4.1x): 2/20 = 10%, avg 15.81
  - L. Juškaitė (2.9x/3.5x): 2/20 = 10%, avg 15.41

### Model Performance

**Our frozen lineup**:
  - Marina Mabrey (TOR, 0.5x boost) -- pred p50=2.782768698488172
  - Flau'jae Johnson (SEA, 1.2x boost) -- pred p50=2.3179445820270272
  - Leila Lacan (CON, 1.8x boost) -- pred p50=2.203006913769019
  - Awa Fam (SEA, 1.9x boost) -- pred p50=1.7915879114931514
  - Cameron Brink (LAS, 2.1x boost) -- pred p50=1.5913880996423808

**Prediction accuracy**:
  - Marina Mabrey: pred 2.78 vs actual 2.54 (error -0.24) [IN BAND]
  - Flau'jae Johnson: pred 2.32 vs actual 4.05 (error +1.74) [IN BAND]
  - Leila Lacan: pred 2.20 vs actual 4.59 (error +2.39) [IN BAND]
  - Awa Fam: pred 1.79 vs actual 2.62 (error +0.83) [IN BAND]
  - Cameron Brink: pred 1.59 vs actual 3.86 (error +2.27) [IN BAND]
  - **MAE**: 1.49 | **In-band rate**: 5/5

**Rank correlation** (our picks vs realized): -0.200

**Leverage** (ownership differentiation):
  - Marina Mabrey: field ownership 0% [DIFFERENTIATED]
  - Flau'jae Johnson: field ownership 100% [chalk]
  - Leila Lacan: field ownership 90% [chalk]
  - Awa Fam: field ownership 95% [chalk]
  - Cameron Brink: field ownership 10% [DIFFERENTIATED]

**Our game stacks**: {'SEA': ["Flau'jae Johnson", 'Awa Fam']}

### Outcome Classification

**(A) Correctly priced** (20 players):
  - L. Juškaitė (TOR, 1.7x, 109 drafts) = 4.81 -- High-draft player delivered as expected
  - L. Lacan (CON, 1.8x, 33 drafts) = 4.59 -- Mid-draft player with mid outcome -- no edge either way
  - S. Rivers (CON, 2.0x, 193 drafts) = 4.2 -- High-draft player delivered as expected
  - C. Brink (LAS, 2.1x, 320 drafts) = 3.86 -- High-draft player delivered as expected
  - B. Sykes (TOR, 0.3x, 1100 drafts) = 6.74 -- High-draft player delivered as expected
  - J. Horston (SEA, 3.0x, 31 drafts) = 3.05 -- Mid-draft player with mid outcome -- no edge either way
  - A. Edwards (CON, 2.1x, 27 drafts) = 3.52 -- Mid-draft player with mid outcome -- no edge either way
  - F. Johnson (SEA, 1.2x, 238 drafts) = 4.05 -- High-draft player delivered as expected
  - A. Fam (SEA, 1.9x, 196 drafts) = 2.62 -- Outcome roughly matched draft position and signals
  - K. Burke (CON, 2.1x, 91 drafts) = 2.47 -- Outcome roughly matched draft position and signals
  - N. Ogwumike (LAS, 0.4x, 525 drafts) = 3.87 -- High-draft player delivered as expected
  - K. Plum (LAS, 0.0x, 3300 drafts) = 4.63 -- High-draft player delivered as expected
  - A. Atkins (LAS, 1.5x, 196 drafts) = 2.57 -- Outcome roughly matched draft position and signals
  - N. Hiedeman (SEA, 0.9x, 287 drafts) = 2.92 -- Outcome roughly matched draft position and signals
  - O. Nelson-Ododa (CON, 2.1x, 16 drafts) = 1.96 -- Mid-draft player with mid outcome -- no edge either way
  - N. Sabally (TOR, 0.6x, 179 drafts) = 3.01 -- High-draft player delivered as expected
  - D. Miller (CON, 2.6x, 119 drafts) = 1.58 -- Outcome roughly matched draft position and signals
  - J. Allemand (TOR, 2.2x, 2 drafts) = 1.54 -- Outcome roughly matched draft position and signals
  - M. Mabrey (TOR, 0.5x, 375 drafts) = 2.54 -- Outcome roughly matched draft position and signals
  - C. Gray (LAS, 3.0x, 25 drafts) = 1.22 -- Mid-draft player with mid outcome -- no edge either way

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2026-06-11

**Players**: 20 HV
 | **Games**: 8 (NYL@ATL, POR@LVA, LVA@POR, IND@CHI, PHO@DAL, ATL@NYL)
 | **Score range**: 1.91 -- 7.22 (median 4.48)

**Leaderboard**: top score 61.36, floor 58.81, median 59.76

**Winner** (score 61.36):
  - A. Boston (2.5x) = 16.08
  - A. Wilson (1.8x) = 9.81
  - J. Young (1.9000000000000001x) = 12.04
  - P. Bueckers (1.7x) = 12.27
  - L. Hull (3.9000000000000004x) = 11.17
  - **Game stack**: team 3: 2 players, team 1: 2 players

**Field ownership** (top-20 entries):
  - P. Bueckers (1.9x/2.3x/1.5x/2.1x/1.7x): 19/20 = 95%, avg 14.40
  - A. Boston (1.9x/2.3x/2.1x/1.7x/2.5x): 14/20 = 70%, avg 13.14
  - A. Wilson (1.6x/1.8x/2x/1.4x): 10/20 = 50%, avg 10.14
  - J. Shepard (1.9x/2.3x/1.5x/2.1x/1.7x): 10/20 = 50%, avg 10.42
  - J. Young (1.9x/2.1x/1.5x): 9/20 = 45%, avg 11.90
  - C. Gray (1.8x/2.6x): 8/20 = 40%, avg 13.34
  - C. Clark (1.6x/2.4x/2x/2.2x): 8/20 = 40%, avg 11.01
  - L. Hull (4.3x/3.9x): 4/20 = 20%, avg 11.45

### Model Performance

**Our frozen lineup**:
  - Caitlin Clark (IND, 0.4x boost) -- pred p50=3.5482000339446564
  - Aliyah Boston (IND, 0.5x boost) -- pred p50=3.396082773361124
  - Skylar Diggins (CHI, 0.6x boost) -- pred p50=2.675727037026342
  - Elizabeth Williams (CHI, 2.1x boost) -- pred p50=1.8627034272037484
  - Leonie Fiebich (NYL, 2.3x boost) -- pred p50=1.4380699993423653

**Prediction accuracy**:
  - Caitlin Clark: pred 3.55 vs actual 5.18 (error +1.63) [IN BAND]
  - Aliyah Boston: pred 3.40 vs actual 6.43 (error +3.03) [IN BAND]
  - **MAE**: 2.33 | **In-band rate**: 2/2

**Leverage** (ownership differentiation):
  - Caitlin Clark: field ownership 40% [chalk]
  - Aliyah Boston: field ownership 70% [chalk]
  - Skylar Diggins: field ownership 0% [DIFFERENTIATED]
  - Elizabeth Williams: field ownership 0% [DIFFERENTIATED]
  - Leonie Fiebich: field ownership 0% [DIFFERENTIATED]

**Our game stacks**: {'IND': ['Caitlin Clark', 'Aliyah Boston'], 'CHI': ['Skylar Diggins', 'Elizabeth Williams']}

### Outcome Classification

**(A) Correctly priced** (17 players):
  - P. Bueckers (DAL, 0.3x, 472 drafts) = 7.22 -- High-draft player delivered as expected
  - A. Boston (IND, 0.5x, 150 drafts) = 6.43 -- High-draft player delivered as expected
  - J. Young (LVA, 0.3x, 219 drafts) = 6.34 -- High-draft player delivered as expected
  - C. Gray (LVA, 0.6x, 169 drafts) = 5.56 -- High-draft player delivered as expected
  - S. Sabally (NYL, 2.9x, 3 drafts) = 2.9 -- Outcome roughly matched draft position and signals
  - L. Hull (IND, 2.7x, 4 drafts) = 2.86 -- Outcome roughly matched draft position and signals
  - J. Shepard (DAL, 0.3x, 196 drafts) = 5.79 -- High-draft player delivered as expected
  - L. Held (PHO, 3.0x, 1 drafts) = 2.91 -- Outcome roughly matched draft position and signals
  - C. Clark (IND, 0.4x, 294 drafts) = 5.18 -- High-draft player delivered as expected
  - T. Oblak (POR, 2.6x, 8 drafts) = 2.57 -- Outcome roughly matched draft position and signals
  - P. Astier (NYL, 0.9x, 117 drafts) = 3.95 -- High-draft player delivered as expected
  - A. Fudd (DAL, 1.2x, 55 drafts) = 3.55 -- High-draft player delivered as expected
  - A. Reese (ATL, 0.5x, 270 drafts) = 4.48 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 4800 drafts) = 5.45 -- High-draft player delivered as expected
  - R. Howard (ATL, 0.2x, 133 drafts) = 4.68 -- High-draft player delivered as expected
  - J. Jones (NYL, 0.5x, 115 drafts) = 3.99 -- High-draft player delivered as expected
  - M. Hines-Allen (IND, 3.0x, 10 drafts) = 1.91 -- Mid-draft player with mid outcome -- no edge either way

**(B) Knowable misses** (2 players):
  - **C. Leite** (POR, 1.2x, 4 drafts) = 4.5 -- Strong signals (high_total, low_boost) but under-drafted
  - **A. Stevens** (CHI, 1.9x, 9 drafts) = 3.37 -- Strong signals (high_total, low_boost) but under-drafted

**(C) Unknowable / winners' edge** (1 players):
  - S. Talbot (LVA, 2.8x, 7 drafts) = 3.22 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 2 knowable misses vs 1 unknowable outcomes. This slate had actionable signal the model or field left on the table.

---

## 2026-06-12

**Players**: 20 HV
 | **Games**: 4 (GSV@SEA, TOR@WAS, SEA@GSV, WAS@TOR)
 | **Score range**: 1.17 -- 4.97 (median 2.83)

**Leaderboard**: top score 52.41, floor 46.98, median 49.11

**Winner** (score 52.41):
  - J. Allemand (4.2x) = 8.96
  - M. Onyenwere (4.1x) = 12.87
  - C. McMahon (4.6x) = 9.54
  - A. Dugalić (4.3x) = 5.86
  - L. Betts (4.2x) = 15.18
  - **Game stack**: team 7: 4 players

**Field ownership** (top-20 entries):
  - N. Hiedeman (2.9x/2.3x/2.5x/2.7x): 17/20 = 85%, avg 13.31
  - M. Onyenwere (4.3x/4.1x/3.9x/3.5x): 10/20 = 50%, avg 12.37
  - A. Dugalić (4.3x/4.1x): 10/20 = 50%, avg 5.73
  - J. Horston (4.4x/4.2x): 10/20 = 50%, avg 10.33
  - L. Betts (4.6x/4.2x): 9/20 = 45%, avg 15.34
  - M. Mabrey (1.9x/2.1x/2.3x/2.5x): 7/20 = 35%, avg 8.99
  - B. Sykes (2.2x): 7/20 = 35%, avg 6.22
  - V. Burton (2.4x/1.8x/2.2x): 6/20 = 30%, avg 8.04

### Model Performance

**Our frozen lineup**:
  - Shakira Austin (WAS, 0.5x boost) -- pred p50=2.950721955978444
  - Flau'jae Johnson (SEA, 1.1x boost) -- pred p50=1.8856994488954242
  - Julie Allemand (TOR, 2.2x boost) -- pred p50=1.429366717723259
  - Awa Fam (SEA, 1.7x boost) -- pred p50=1.425030984102519
  - Michaela Onyenwere (WAS, 2.3x boost) -- pred p50=1.1150342700032878

**Prediction accuracy**:
  - Julie Allemand: pred 1.43 vs actual 2.13 (error +0.70) [IN BAND]
  - Awa Fam: pred 1.43 vs actual 1.60 (error +0.17) [IN BAND]
  - Michaela Onyenwere: pred 1.12 vs actual 3.14 (error +2.02) [IN BAND]
  - **MAE**: 0.96 | **In-band rate**: 3/3

**Rank correlation** (our picks vs realized): -0.500

**Leverage** (ownership differentiation):
  - Shakira Austin: field ownership 0% [DIFFERENTIATED]
  - Flau'jae Johnson: field ownership 0% [DIFFERENTIATED]
  - Julie Allemand: field ownership 20% [DIFFERENTIATED]
  - Awa Fam: field ownership 5% [DIFFERENTIATED]
  - Michaela Onyenwere: field ownership 50% [chalk]

**Our game stacks**: {'WAS': ['Shakira Austin', 'Michaela Onyenwere'], 'SEA': ["Flau'jae Johnson", 'Awa Fam']}

### Outcome Classification

**(A) Correctly priced** (17 players):
  - N. Hiedeman (SEA, 0.9x, 301 drafts) = 4.97 -- High-draft player delivered as expected
  - J. Horston (SEA, 3.0x, 117 drafts) = 2.39 -- Outcome roughly matched draft position and signals
  - T. Hayes (GSV, 2.0x, 34 drafts) = 2.86 -- Mid-draft player with mid outcome -- no edge either way
  - J. Salaün (GSV, 0.9x, 248 drafts) = 3.79 -- High-draft player delivered as expected
  - C. McMahon (WAS, 3.0x, 2 drafts) = 2.07 -- Outcome roughly matched draft position and signals
  - M. Mabrey (TOR, 0.5x, 422 drafts) = 4.06 -- High-draft player delivered as expected
  - J. Allemand (TOR, 2.2x, 3 drafts) = 2.13 -- Outcome roughly matched draft position and signals
  - V. Burton (GSV, 0.4x, 1100 drafts) = 3.55 -- High-draft player delivered as expected
  - S. Citron (WAS, 0.5x, 453 drafts) = 3.35 -- High-draft player delivered as expected
  - T. Key (TOR, 3.0x, 2 drafts) = 1.75 -- Outcome roughly matched draft position and signals
  - G. Williams (GSV, 0.6x, 558 drafts) = 2.65 -- Outcome roughly matched draft position and signals
  - A. Dugalić (WAS, 2.9x, 10 drafts) = 1.36 -- Mid-draft player with mid outcome -- no edge either way
  - M. Conde (TOR, 2.7x, 4 drafts) = 1.4 -- Low-draft player correctly faded by the field
  - D. Malonga (SEA, 1.0x, 75 drafts) = 2.18 -- Outcome roughly matched draft position and signals
  - B. Sykes (TOR, 0.2x, 2500 drafts) = 2.83 -- Outcome roughly matched draft position and signals
  - A. Fam (SEA, 1.7x, 68 drafts) = 1.6 -- Outcome roughly matched draft position and signals
  - K. Samuelson (SEA, 3.0x, 20 drafts) = 1.17 -- Mid-draft player with mid outcome -- no edge either way

**(B) Knowable misses** (2 players):
  - **M. Onyenwere** (WAS, 2.3x, 5 drafts) = 3.14 -- Strong signals (high_total, low_boost) but under-drafted
  - **I. Harrison** (TOR, 1.3x, 5 drafts) = 3.5 -- Strong signals (high_total, low_boost) but under-drafted

**(C) Unknowable / winners' edge** (1 players):
  - L. Betts (WAS, 3.0x, 8 drafts) = 3.61 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 2 knowable misses vs 1 unknowable outcomes. This slate had actionable signal the model or field left on the table.

---

## 2026-06-13

**Players**: 20 HV
 | **Games**: 8 (POR@DAL, CON@IND, LVA@MIN, IND@CON, MIN@LVA, PHO@LAS)
 | **Score range**: 2.29 -- 7.44 (median 3.83)

**Leaderboard**: top score 74.05, floor 63.86, median 66.45

**Winner** (score 74.05):
  - K. Plum (2x) = 14.89
  - N. Ogwumike (2.2x) = 12.25
  - K. Copper (2.9000000000000004x) = 21.13
  - R. Burrell (3.6x) = 20.53
  - L. Held (4.2x) = 5.24
  - **Game stack**: team 9: 3 players, team 6: 2 players

**Field ownership** (top-20 entries):
  - K. Copper (2.7x/3.1x/2.9x/2.5x/3.3x): 18/20 = 90%, avg 20.89
  - K. Plum (1.8x/2x): 16/20 = 80%, avg 14.79
  - R. Burrell (3.4x/4x/3.8x/3.6x): 14/20 = 70%, avg 19.88
  - C. Brink (3.5x/3.1x/2.9x/3.7x/3.3x): 10/20 = 50%, avg 10.33
  - A. Thomas (1.9x/2.3x/1.5x/2.1x/1.7x): 9/20 = 45%, avg 7.87
  - N. Ogwumike (1.8x/2x/2.2x): 5/20 = 25%, avg 11.58
  - A. Fudd (2.7x): 4/20 = 20%, avg 10.33
  - D. Hamby (2x/2.2x): 4/20 = 20%, avg 3.70

### Model Performance

**Our frozen lineup**:
  - A'ja Wilson (LVA, 0.0x boost) -- pred p50=4.646807838871401
  - Alyssa Thomas (PHO, 0.3x boost) -- pred p50=3.2102547076947627
  - Kahleah Copper (PHO, 1.3x boost) -- pred p50=2.543511853585849
  - Saniya Rivers (CON, 1.7x boost) -- pred p50=1.7144206680723286
  - Cameron Brink (LAS, 1.7x boost) -- pred p50=1.6375739473580615

**Prediction accuracy**:
  - A'ja Wilson: pred 4.65 vs actual 5.06 (error +0.42) [IN BAND]
  - Kahleah Copper: pred 2.54 vs actual 7.29 (error +4.74) [OUTSIDE]
  - Saniya Rivers: pred 1.71 vs actual 2.55 (error +0.84) [IN BAND]
  - Cameron Brink: pred 1.64 vs actual 3.21 (error +1.57) [IN BAND]
  - **MAE**: 1.89 | **In-band rate**: 3/4

**Rank correlation** (our picks vs realized): 0.600

**Leverage** (ownership differentiation):
  - A'ja Wilson: field ownership 5% [DIFFERENTIATED]
  - Alyssa Thomas: field ownership 45% [chalk]
  - Kahleah Copper: field ownership 90% [chalk]
  - Saniya Rivers: field ownership 5% [DIFFERENTIATED]
  - Cameron Brink: field ownership 50% [chalk]

**Our game stacks**: {'PHO': ['Alyssa Thomas', 'Kahleah Copper']}

**Regime**: top_20 | expected payout: 1.393

### Outcome Classification

**(A) Correctly priced** (15 players):
  - K. Plum (LAS, 0.0x, 680 drafts) = 7.44 -- High-draft player delivered as expected
  - N. Mack (PHO, 0.7x, 138 drafts) = 4.97 -- High-draft player delivered as expected
  - N. Ogwumike (LAS, 0.4x, 174 drafts) = 5.57 -- High-draft player delivered as expected
  - M. Gustafson (POR, 1.6x, 10 drafts) = 3.68 -- Mid-draft player with mid outcome -- no edge either way
  - C. Gray (LVA, 0.5x, 151 drafts) = 4.86 -- High-draft player delivered as expected
  - J. Loyd (LVA, 2.7x, 2 drafts) = 2.54 -- Outcome roughly matched draft position and signals
  - C. Brink (LAS, 1.7x, 213 drafts) = 3.21 -- High-draft player delivered as expected
  - A. Fudd (DAL, 1.1x, 93 drafts) = 3.83 -- High-draft player delivered as expected
  - N. Howard (MIN, 0.3x, 175 drafts) = 4.89 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 4400 drafts) = 5.06 -- High-draft player delivered as expected
  - E. Engstler (POR, 1.2x, 23 drafts) = 3.14 -- Mid-draft player with mid outcome -- no edge either way
  - S. Rivers (CON, 1.7x, 8 drafts) = 2.55 -- Outcome roughly matched draft position and signals
  - J. Young (LVA, 0.2x, 194 drafts) = 4.27 -- High-draft player delivered as expected
  - A. Kuier (DAL, 2.1x, 2 drafts) = 2.29 -- Outcome roughly matched draft position and signals
  - K. McBride (MIN, 0.7x, 131 drafts) = 3.47 -- High-draft player delivered as expected

**(B) Knowable misses** (4 players):
  - **K. Copper** (PHO, 1.3x, 33 drafts) = 7.29 -- Strong signals (high_minutes, high_fpts, high_total, low_boost) but under-drafted
  - **R. Burrell** (LAS, 2.2x, 11 drafts) = 5.7 -- Strong signals (high_total, low_boost) but under-drafted
  - **M. Billings** (IND, 2.3x, 3 drafts) = 3.07 -- Strong signals (high_total, low_boost) but under-drafted
  - **L. Lacan** (CON, 1.1x, 6 drafts) = 3.48 -- Strong signals (starter, high_total, low_boost) but under-drafted

**(C) Unknowable / winners' edge** (1 players):
  - A. James (DAL, 2.3x, 6 drafts) = 3.35 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 4 knowable misses vs 1 unknowable outcomes. This slate had actionable signal the model or field left on the table.

---

## 2026-06-14

**Players**: 20 HV
 | **Games**: 4 (TOR@IND, WAS@, ATL@, NYL@)
 | **Score range**: 1.24 -- 6.01 (median 2.59)

**Leaderboard**: top score 53.94, floor 49.36, median 50.13

**Winner** (score 53.94):
  - A. Gray (2.6x) = 15.62
  - J. Jones (2.2x) = 8.41
  - J. Allemand (3.6x) = 15.22
  - M. Conde (4.1x) = 8.71
  - C. McMahon (4.2x) = 5.98
  - **Game stack**: team 16: 2 players

**Field ownership** (top-20 entries):
  - J. Allemand (3.6x/4x/3.2x/3.8x/3.4x): 20/20 = 100%, avg 15.73
  - M. Onyenwere (3.5x/3.1x/3.7x/3.9x/3.3x): 18/20 = 90%, avg 10.38
  - M. Conde (4.3x/4.1x): 17/20 = 85%, avg 9.03
  - C. McMahon (4.4x/4.2x): 14/20 = 70%, avg 6.08
  - L. Fiebich (4x/4.2x): 9/20 = 45%, avg 8.17
  - L. Betts (4.2x): 7/20 = 35%, avg 7.15
  - A. Gray (2.4x/2x/2.6x): 4/20 = 20%, avg 14.42
  - A. Reese (2.4x/2.2x): 4/20 = 20%, avg 9.00

**Enrichment gaps** (43 players without vegas): Madina Okot, Breanna Stewart, Jonquel Jones, Pauline Astier, Shakira Austin, Sonia Citron, Marine Johannes, Kiki Iriafen, Rebekah Gardner, Han Xu

### Outcome Classification

**(A) Correctly priced** (20 players):
  - J. Allemand (TOR, 2.0x, 70 drafts) = 4.23 -- High-draft player delivered as expected
  - A. Gray (ATL, 0.6x, 244 drafts) = 6.01 -- High-draft player delivered as expected
  - I. Borlase (ATL, 3.0x, 1 drafts) = 2.66 -- Outcome roughly matched draft position and signals
  - M. Onyenwere (WAS, 1.9x, 210 drafts) = 2.75 -- Outcome roughly matched draft position and signals
  - M. Conde (TOR, 2.7x, 69 drafts) = 2.12 -- Outcome roughly matched draft position and signals
  - R. Howard (ATL, 0.1x, 561 drafts) = 4.65 -- High-draft player delivered as expected
  - L. Fiebich (NYL, 2.8x, 3 drafts) = 1.96 -- Outcome roughly matched draft position and signals
  - A. Reese (ATL, 0.4x, 682 drafts) = 3.83 -- High-draft player delivered as expected
  - J. Jones (NYL, 0.4x, 193 drafts) = 3.82 -- High-draft player delivered as expected
  - J. Canada (ATL, 0.7x, 122 drafts) = 3.39 -- High-draft player delivered as expected
  - B. Stewart (NYL, 0.2x, 1800 drafts) = 4.07 -- High-draft player delivered as expected
  - L. Betts (WAS, 3.0x, 23 drafts) = 1.7 -- Mid-draft player with mid outcome -- no edge either way
  - N. Hillmon (ATL, 1.6x, 113 drafts) = 2.23 -- Outcome roughly matched draft position and signals
  - T. Fágbénlé (TOR, 3.0x, 1 drafts) = 1.58 -- Outcome roughly matched draft position and signals
  - I. Harrison (TOR, 0.9x, 5 drafts) = 2.59 -- Outcome roughly matched draft position and signals
  - C. McMahon (WAS, 3.0x, 1 drafts) = 1.42 -- Low-draft player correctly faded by the field
  - P. Astier (NYL, 0.8x, 135 drafts) = 2.28 -- Outcome roughly matched draft position and signals
  - A. Flórez (WAS, 2.2x, 5 drafts) = 1.53 -- Outcome roughly matched draft position and signals
  - S. Sabally (NYL, 2.3x, 23 drafts) = 1.24 -- Mid-draft player with mid outcome -- no edge either way
  - M. Johannes (NYL, 1.0x, 158 drafts) = 1.68 -- Outcome roughly matched draft position and signals

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2026-06-15

**Players**: 20 HV
 | **Games**: 6 (MIN@POR, POR@MIN, GSV@LAS, DAL@LVA, LVA@DAL, LAS@GSV)
 | **Score range**: 1.46 -- 5.22 (median 2.83)

**Leaderboard**: top score 53.73, floor 44.46, median 46.14

**Winner** (score 53.73):
  - K. Charles (4.3x) = 14.71
  - J. Loyd (4.2x) = 13.67
  - A. Ogunbowale (2.6x) = 13.28
  - A. Fudd (2.3x) = 7.56
  - S. Talbot (3.7x) = 4.51
  - **Game stack**: team 1: 2 players, team 12: 2 players

**Field ownership** (top-20 entries):
  - A. Ogunbowale (3x/2.8x/2.6x/2.4x/2.2x): 10/20 = 50%, avg 13.38
  - A. Kosu (4.4x/4.2x): 10/20 = 50%, avg 10.55
  - A. Fudd (2.3x/2.5x/2.7x): 8/20 = 40%, avg 8.21
  - M. Caldwell (4.4x/4.6x/4.2x): 8/20 = 40%, avg 12.39
  - A. Delaere (5x/4.8x): 7/20 = 35%, avg 13.69
  - C. Parker-Tyus (5x/4.8x): 7/20 = 35%, avg 7.04
  - A. Smith (4.6x): 6/20 = 30%, avg 2.51
  - J. Shepard (1.8x/2x/2.2x): 5/20 = 25%, avg 10.43

### Outcome Classification

**(A) Correctly priced** (18 players):
  - N. Coffey (MIN, 1.0x, 97 drafts) = 4.95 -- High-draft player delivered as expected
  - K. Charles (GSV, 2.3x, 14 drafts) = 3.42 -- Mid-draft player with mid outcome -- no edge either way
  - M. Caldwell (MIN, 3.0x, 3 drafts) = 2.83 -- Outcome roughly matched draft position and signals
  - A. Delaere (MIN, 3.0x, 6 drafts) = 2.75 -- Outcome roughly matched draft position and signals
  - A. Kosu (MIN, 3.0x, 9 drafts) = 2.48 -- Outcome roughly matched draft position and signals
  - J. Shepard (DAL, 0.2x, 169 drafts) = 5.22 -- High-draft player delivered as expected
  - C. Zandalasini (GSV, 2.8x, 11 drafts) = 2.25 -- Mid-draft player with mid outcome -- no edge either way
  - A. James (DAL, 2.0x, 5 drafts) = 2.6 -- Outcome roughly matched draft position and signals
  - A. Fudd (DAL, 0.9x, 51 drafts) = 3.29 -- High-draft player delivered as expected
  - L. Geiselsöder (POR, 3.0x, 2 drafts) = 1.76 -- Outcome roughly matched draft position and signals
  - T. Oblak (POR, 2.4x, 2 drafts) = 1.96 -- Outcome roughly matched draft position and signals
  - K. Stokes (GSV, 2.0x, 15 drafts) = 1.94 -- Mid-draft player with mid outcome -- no edge either way
  - R. Burrell (LAS, 1.6x, 21 drafts) = 2.15 -- Mid-draft player with mid outcome -- no edge either way
  - P. Bueckers (DAL, 0.2x, 257 drafts) = 3.41 -- High-draft player delivered as expected
  - C. Parker-Tyus (LVA, 3.0x, 3 drafts) = 1.46 -- Low-draft player correctly faded by the field
  - O. Miles (MIN, 0.2x, 411 drafts) = 3.23 -- High-draft player delivered as expected
  - K. Thornton (GSV, 1.4x, 30 drafts) = 2.09 -- Mid-draft player with mid outcome -- no edge either way
  - V. Burton (GSV, 0.4x, 210 drafts) = 2.91 -- Outcome roughly matched draft position and signals

**(B) Knowable misses** (2 players):
  - **A. Ogunbowale** (DAL, 1.0x, 9 drafts) = 5.11 -- Strong signals (high_minutes, high_total, low_boost) but under-drafted
  - **J. Loyd** (LVA, 2.4x, 3 drafts) = 3.26 -- Strong signals (high_total, low_boost) but under-drafted

**Takeaway**: 2 knowable misses vs 0 unknowable outcomes. This slate had actionable signal the model or field left on the table.

---

## 2026-06-16

**Players**: 20 HV
 | **Games**: 2 (TOR@IND, IND@TOR)
 | **Score range**: 0.12 -- 5.07 (median 1.37)

**Leaderboard**: top score 59.91, floor 56.62, median 58.16

**Winner** (score 59.91):
  - A. Boston (2.3x) = 10.55
  - K. Mitchell (2.3x) = 10.39
  - L. Juškaitė (3.2x) = 12.78
  - S. Cunningham (3.3x) = 16.73
  - M. Conde (3.8x) = 9.47
  - **Game stack**: team 3: 3 players, team 16: 2 players

**Field ownership** (top-20 entries):
  - L. Juškaitė (3x/2.8x/3.2x/3.6x/3.4x): 20/20 = 100%, avg 11.94
  - S. Cunningham (3.5x/3.1x/3.7x/3.9x/3.3x): 20/20 = 100%, avg 17.49
  - K. Mitchell (1.9x/2.3x/2.1x/1.7x/2.5x): 19/20 = 95%, avg 9.77
  - A. Boston (1.9x/2.3x/1.5x/2.1x/1.7x): 15/20 = 75%, avg 8.83
  - C. Clark (1.9x/2.3x): 14/20 = 70%, avg 10.90
  - M. Conde (4.6x/3.8x): 5/20 = 25%, avg 9.87
  - I. Harrison (2.1x/2.3x/2.5x/2.7x): 5/20 = 25%, avg 7.04
  - M. Mabrey (2.3x/2.5x): 2/20 = 10%, avg 8.34

### Outcome Classification

**(A) Correctly priced** (20 players):
  - S. Cunningham (IND, 1.9x, 304 drafts) = 5.07 -- High-draft player delivered as expected
  - L. Juškaitė (TOR, 1.6x, 139 drafts) = 3.99 -- High-draft player delivered as expected
  - M. Conde (TOR, 2.6x, 102 drafts) = 2.49 -- Outcome roughly matched draft position and signals
  - K. Mitchell (IND, 0.5x, 544 drafts) = 4.52 -- High-draft player delivered as expected
  - C. Clark (IND, 0.3x, 3000 drafts) = 4.86 -- High-draft player delivered as expected
  - A. Boston (IND, 0.3x, 1000 drafts) = 4.59 -- High-draft player delivered as expected
  - M. Mabrey (TOR, 0.5x, 484 drafts) = 3.48 -- High-draft player delivered as expected
  - I. Harrison (TOR, 0.9x, 211 drafts) = 2.96 -- Outcome roughly matched draft position and signals
  - T. Pouye (TOR, 3.0x, 3 drafts) = 1.25 -- Low-draft player correctly faded by the field
  - M. Timpson (IND, 3.0x, 120 drafts) = 1.11 -- High-draft player underperformed -- field took the loss equally
  - M. Billings (IND, 2.0x, 124 drafts) = 1.37 -- High-draft player underperformed -- field took the loss equally
  - B. Sykes (TOR, 0.3x, 1400 drafts) = 2.13 -- Outcome roughly matched draft position and signals
  - T. Fágbénlé (TOR, 3.0x, 7 drafts) = 0.94 -- Low-draft player correctly faded by the field
  - M. Hines-Allen (IND, 2.9x, 116 drafts) = 0.89 -- High-draft player underperformed -- field took the loss equally
  - L. Hull (IND, 2.5x, 171 drafts) = 0.89 -- High-draft player underperformed -- field took the loss equally
  - K. Nurse (TOR, 3.0x, 98 drafts) = 0.76 -- High-draft player underperformed -- field took the loss equally
  - R. Johnson (IND, 3.0x, 30 drafts) = 0.74 -- Mid-draft player with mid outcome -- no edge either way
  - D. Dantas (IND, 3.0x, 1 drafts) = 0.68 -- Low-draft player correctly faded by the field
  - T. Key (TOR, 3.0x, 102 drafts) = 0.12 -- High-draft player underperformed -- field took the loss equally
  - J. Allemand (TOR, 1.5x, 221 drafts) = 0.13 -- High-draft player underperformed -- field took the loss equally

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2026-06-17

**Players**: 20 HV
 | **Games**: 12 (GSV@DAL, SEA@POR, PHO@LVA, CHI@NYL, WAS@CON, NYL@CHI)
 | **Score range**: 2.37 -- 6.97 (median 4.73)

**Leaderboard**: top score 62.96, floor 55.84, median 58.21

**Winner** (score 62.96):
  - A. Wilson (2x) = 13.94
  - D. Malonga (2.8x) = 17.52
  - M. Onyenwere (3.3x) = 11.11
  - A. Fam (3.0999999999999996x) = 9.90
  - L. Betts (4.2x) = 10.48
  - **Game stack**: team 10: 2 players, team 7: 2 players

**Field ownership** (top-20 entries):
  - A. Wilson (2x): 18/20 = 90%, avg 13.94
  - O. Miles (2x): 13/20 = 65%, avg 13.25
  - D. Malonga (3x/2.8x/2.6x/2.4x/2.2x): 8/20 = 40%, avg 16.11
  - M. Onyenwere (2.9x/3.1x/3.5x/3.3x): 7/20 = 35%, avg 10.92
  - L. Betts (4.4x/4.6x/5x/4.2x): 6/20 = 30%, avg 11.06
  - G. Williams (2.1x/2.3x): 6/20 = 30%, avg 9.87
  - S. Sabally (4x/3.6x): 6/20 = 30%, avg 11.52
  - K. Copper (2.1x/2.3x/2.5x): 6/20 = 30%, avg 8.75

### Outcome Classification

**(A) Correctly priced** (10 players):
  - O. Miles (MIN, 0.2x, 410 drafts) = 6.63 -- High-draft player delivered as expected
  - A. Wilson (LVA, 0.0x, 4200 drafts) = 6.97 -- High-draft player delivered as expected
  - J. Young (LVA, 0.3x, 191 drafts) = 5.75 -- High-draft player delivered as expected
  - K. Chen (GSV, 2.9x, 3 drafts) = 2.71 -- Outcome roughly matched draft position and signals
  - L. Betts (WAS, 3.0x, 17 drafts) = 2.5 -- Mid-draft player with mid outcome -- no edge either way
  - S. Citron (WAS, 0.5x, 25 drafts) = 4.82 -- Mid-draft player with mid outcome -- no edge either way
  - M. Caldwell (MIN, 3.0x, 1 drafts) = 2.37 -- Outcome roughly matched draft position and signals
  - G. Williams (GSV, 0.7x, 28 drafts) = 4.36 -- Mid-draft player with mid outcome -- no edge either way
  - K. Copper (PHO, 0.9x, 12 drafts) = 3.92 -- Mid-draft player with mid outcome -- no edge either way
  - A. Ogunbowale (DAL, 0.8x, 58 drafts) = 3.86 -- High-draft player delivered as expected

**(B) Knowable misses** (6 players):
  - **D. Malonga** (SEA, 1.0x, 6 drafts) = 6.26 -- Strong signals (high_fpts, low_boost) but under-drafted
  - **C. Leite** (POR, 1.1x, 11 drafts) = 5.43 -- Strong signals (starter, low_boost) but under-drafted
  - **B. Carleton** (POR, 1.0x, 7 drafts) = 5.04 -- Strong signals (high_minutes, high_fpts, low_boost) but under-drafted
  - **N. Smith** (LVA, 1.0x, 3 drafts) = 4.73 -- Strong signals (starter, high_total, low_boost) but under-drafted
  - **S. Diggins** (CHI, 0.6x, 6 drafts) = 5.12 -- Strong signals (high_minutes, high_fpts, low_boost) but under-drafted
  - **A. Fam** (SEA, 1.7x, 1 drafts) = 3.19 -- Strong signals (starter, low_boost) but under-drafted

**(C) Unknowable / winners' edge** (4 players):
  - G. Jaquez (CHI, 1.7x, 1 drafts) = 4.63 -- Above-expectation outcome, ambiguous whether knowable
  - S. Taylor (CHI, 1.3x, 1 drafts) = 4.78 -- Above-expectation outcome, ambiguous whether knowable
  - S. Sabally (NYL, 2.4x, 1 drafts) = 3.14 -- Above-expectation outcome, ambiguous whether knowable
  - M. Onyenwere (WAS, 1.7x, 5 drafts) = 3.37 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 6 knowable misses vs 4 unknowable outcomes. This slate had actionable signal the model or field left on the table.

---

## 2026-06-18

**Players**: 20 HV
 | **Games**: 2 (ATL@IND, IND@ATL)
 | **Score range**: -0.44 -- 4.18 (median 1.70)

**Leaderboard**: top score 43.57, floor 42.30, median 42.76

**Winner** (score 43.57):
  - K. Mitchell (2.5x) = 10.44
  - N. Hillmon (3.4000000000000004x) = 11.08
  - J. Canada (2.2x) = 8.58
  - M. Timpson (4.4x) = 7.47
  - A. Boston (1.5x) = 6.00
  - **Game stack**: team 3: 3 players, team 2: 2 players

**Field ownership** (top-20 entries):
  - K. Mitchell (1.9x/2.1x/2.3x/2.5x): 20/20 = 100%, avg 9.31
  - N. Hillmon (3.2x/3.4x/3x/2.8x): 20/20 = 100%, avg 9.48
  - J. Canada (1.8x/2x/2.2x/2.6x): 19/20 = 95%, avg 8.38
  - A. Boston (2.1x/1.5x/2.3x/1.7x): 17/20 = 85%, avg 8.44
  - R. Howard (2.1x/1.7x): 8/20 = 40%, avg 8.49
  - S. Cunningham (2.9x/3.1x/2.7x): 6/20 = 30%, avg 6.18
  - A. Gray (1.7x/2.3x): 4/20 = 20%, avg 6.97
  - M. Timpson (4.4x/5x): 3/20 = 15%, avg 7.81

### Model Performance

**Our frozen lineup**:
  - Angel Reese (ATL, 0.4x boost) -- pred p50=3.019141236644749
  - Allisha Gray (ATL, 0.5x boost) -- pred p50=2.6362740777474567
  - Caitlin Clark (IND, 0.2x boost) -- pred p50=2.7664910872266666
  - Naz Hillmon (ATL, 1.6x boost) -- pred p50=1.915162133991084
  - Monique Billings (IND, 2.1x boost) -- pred p50=0.7554574516148984

**Prediction accuracy**:
  - Angel Reese: pred 3.02 vs actual 3.21 (error +0.19) [IN BAND]
  - Allisha Gray: pred 2.64 vs actual 3.24 (error +0.61) [IN BAND]
  - Caitlin Clark: pred 2.77 vs actual 3.61 (error +0.84) [IN BAND]
  - Naz Hillmon: pred 1.92 vs actual 3.26 (error +1.34) [IN BAND]
  - Monique Billings: pred 0.76 vs actual 1.30 (error +0.54) [IN BAND]
  - **MAE**: 0.70 | **In-band rate**: 5/5

**Rank correlation** (our picks vs realized): 0.300

**Leverage** (ownership differentiation):
  - Angel Reese: field ownership 0% [DIFFERENTIATED]
  - Allisha Gray: field ownership 20% [DIFFERENTIATED]
  - Caitlin Clark: field ownership 0% [DIFFERENTIATED]
  - Naz Hillmon: field ownership 100% [chalk]
  - Monique Billings: field ownership 0% [DIFFERENTIATED]

**Our game stacks**: {'ATL': ['Angel Reese', 'Allisha Gray', 'Naz Hillmon'], 'IND': ['Caitlin Clark', 'Monique Billings']}

**Regime**: top_20 | expected payout: 0.651

### Outcome Classification

**(A) Correctly priced** (20 players):
  - N. Hillmon (ATL, 1.6x, 120 drafts) = 3.26 -- High-draft player delivered as expected
  - K. Mitchell (IND, 0.5x, 473 drafts) = 4.18 -- High-draft player delivered as expected
  - J. Canada (ATL, 0.6x, 166 drafts) = 3.9 -- High-draft player delivered as expected
  - A. Boston (IND, 0.3x, 756 drafts) = 4.0 -- High-draft player delivered as expected
  - R. Howard (ATL, 0.1x, 1500 drafts) = 4.14 -- High-draft player delivered as expected
  - M. Timpson (IND, 3.0x, 86 drafts) = 1.7 -- Outcome roughly matched draft position and signals
  - A. Gray (ATL, 0.5x, 386 drafts) = 3.24 -- High-draft player delivered as expected
  - C. Clark (IND, 0.2x, 2300 drafts) = 3.61 -- High-draft player delivered as expected
  - A. Reese (ATL, 0.4x, 976 drafts) = 3.21 -- High-draft player delivered as expected
  - S. Cunningham (IND, 1.5x, 326 drafts) = 2.16 -- Outcome roughly matched draft position and signals
  - I. Borlase (ATL, 3.0x, 92 drafts) = 1.51 -- Outcome roughly matched draft position and signals
  - T. Paopao (ATL, 3.0x, 105 drafts) = 1.4 -- High-draft player underperformed -- field took the loss equally
  - M. Billings (IND, 2.1x, 102 drafts) = 1.3 -- High-draft player underperformed -- field took the loss equally
  - T. Harris (IND, 3.0x, 83 drafts) = 0.72 -- High-draft player underperformed -- field took the loss equally
  - L. Hull (IND, 2.6x, 127 drafts) = 0.42 -- High-draft player underperformed -- field took the loss equally
  - S. Koné (ATL, 3.0x, 3 drafts) = 0.32 -- Low-draft player correctly faded by the field
  - M. Okot (ATL, 3.0x, 67 drafts) = 0.23 -- High-draft player underperformed -- field took the loss equally
  - M. Hines-Allen (IND, 3.0x, 85 drafts) = 0.09 -- High-draft player underperformed -- field took the loss equally
  - R. Johnson (IND, 3.0x, None drafts) = -0.44 -- Low-draft player correctly faded by the field
  - G. VanSlooten (IND, 3.0x, None drafts) = None -- Low-draft player correctly faded by the field

**Takeaway**: Clean slate. Outcomes matched expectations across the board.

---

## 2026-06-19

**Players**: 20 HV
 | **Games**: 6 (GSV@MIN, CON@TOR, NYL@LVA, WAS@NYL, TOR@CON, MIN@GSV)
 | **Score range**: 1.78 -- 6.37 (median 3.47)

**Leaderboard**: top score 65.81, floor 54.17, median 56.00

**Winner** (score 65.81):
  - M. Mabrey (2.5x) = 15.93
  - S. Ionescu (3.5x) = 4.05
  - M. Conde (4x) = 16.28
  - T. Fágbénlé (4.4x) = 21.74
  - L. Betts (4x) = 7.82
  - **Game stack**: team 16: 3 players

**Field ownership** (top-20 entries):
  - M. Conde (4x/3.8x/3.6x): 19/20 = 95%, avg 15.98
  - S. Ionescu (3.5x/3.7x): 13/20 = 65%, avg 4.14
  - T. Fágbénlé (4.4x/4.2x): 12/20 = 60%, avg 21.00
  - L. Betts (4x/4.2x/4.8x): 10/20 = 50%, avg 8.10
  - M. Mabrey (2.3x/2.5x): 9/20 = 45%, avg 15.50
  - J. Allemand (3.4x/3.6x): 7/20 = 35%, avg 7.51
  - L. Juškaitė (3.2x/3.4x/2.8x): 7/20 = 35%, avg 7.04
  - B. Stewart (2.2x): 5/20 = 25%, avg 9.58

### Model Performance

**Our frozen lineup**:
  - Sabrina Ionescu (NYL, 1.7x boost) -- pred p50=2.250591209311604
  - Kiki Iriafen (WAS, 0.7x boost) -- pred p50=2.213073827082922
  - Saniya Rivers (CON, 1.7x boost) -- pred p50=1.6004474887623172
  - Leonie Fiebich (NYL, 2.5x boost) -- pred p50=1.365975785911571
  - Maria Conde (TOR, 2.4x boost) -- pred p50=1.3284563965554688

**Prediction accuracy**:
  - Kiki Iriafen: pred 2.21 vs actual 3.24 (error +1.03) [IN BAND]
  - Leonie Fiebich: pred 1.37 vs actual 3.33 (error +1.96) [IN BAND]
  - Maria Conde: pred 1.33 vs actual 4.07 (error +2.74) [IN BAND]
  - **MAE**: 1.91 | **In-band rate**: 3/3

**Rank correlation** (our picks vs realized): -1.000

**Leverage** (ownership differentiation):
  - Sabrina Ionescu: field ownership 65% [chalk]
  - Kiki Iriafen: field ownership 0% [DIFFERENTIATED]
  - Saniya Rivers: field ownership 0% [DIFFERENTIATED]
  - Leonie Fiebich: field ownership 20% [DIFFERENTIATED]
  - Maria Conde: field ownership 95% [chalk]

**Our game stacks**: {'NYL': ['Sabrina Ionescu', 'Leonie Fiebich']}

**Regime**: top_20 | expected payout: 1.060

### Outcome Classification

**(A) Correctly priced** (15 players):
  - T. Fágbénlé (TOR, 3.0x, 106 drafts) = 4.94 -- High-draft player delivered as expected
  - C. Zandalasini (GSV, 2.9x, 19 drafts) = 4.02 -- Mid-draft player with mid outcome -- no edge either way
  - M. Mabrey (TOR, 0.5x, 381 drafts) = 6.37 -- High-draft player delivered as expected
  - N. Coffey (MIN, 0.8x, 138 drafts) = 4.64 -- High-draft player delivered as expected
  - C. Williams (MIN, 0.3x, 298 drafts) = 4.88 -- High-draft player delivered as expected
  - S. Citron (WAS, 0.4x, 321 drafts) = 4.59 -- High-draft player delivered as expected
  - G. Amoore (WAS, 3.0x, 4 drafts) = 2.03 -- Outcome roughly matched draft position and signals
  - B. Stewart (NYL, 0.2x, 1500 drafts) = 4.35 -- High-draft player delivered as expected
  - O. Nelson-Ododa (CON, 2.0x, 3 drafts) = 2.51 -- Outcome roughly matched draft position and signals
  - L. Betts (WAS, 2.8x, 7 drafts) = 1.96 -- Outcome roughly matched draft position and signals
  - K. Iriafen (WAS, 0.7x, 11 drafts) = 3.24 -- Mid-draft player with mid outcome -- no edge either way
  - A. Morrow (CON, 0.9x, 149 drafts) = 2.93 -- Outcome roughly matched draft position and signals
  - D. Miller (CON, 2.7x, 5 drafts) = 1.78 -- Outcome roughly matched draft position and signals
  - J. Allemand (TOR, 1.8x, 5 drafts) = 2.15 -- Outcome roughly matched draft position and signals
  - L. Lacan (CON, 1.0x, 23 drafts) = 2.67 -- Mid-draft player with mid outcome -- no edge either way

**(C) Unknowable / winners' edge** (5 players):
  - M. Conde (TOR, 2.4x, 7 drafts) = 4.07 -- Above-expectation outcome, ambiguous whether knowable
  - K. Burke (CON, 2.1x, 7 drafts) = 3.67 -- Above-expectation outcome, ambiguous whether knowable
  - L. Fiebich (NYL, 2.5x, 4 drafts) = 3.33 -- Above-expectation outcome, ambiguous whether knowable
  - B. Griner (CON, 1.0x, 4 drafts) = 3.47 -- Above-expectation outcome, ambiguous whether knowable
  - I. Harrison (TOR, 0.8x, 7 drafts) = 3.29 -- Above-expectation outcome, ambiguous whether knowable

**Takeaway**: 5 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---

## 2026-06-20

**Players**: 20 HV
 | **Games**: 6 (IND@PHO, CHI@DAL, ATL@, PHO@IND, DAL@CHI, SEA@)
 | **Score range**: 1.44 -- 5.06 (median 3.24)

**Leaderboard**: top score 59.05, floor 51.36, median 52.88

**Winner** (score 59.05):
  - C. Clark (2.2x) = 10.67
  - N. Hillmon (3.2x) = 13.11
  - A. Fam (3.1x) = 6.34
  - A. Stevens (3.2x) = 9.67
  - N. Brochant (4.2x) = 19.26

**Field ownership** (top-20 entries):
  - N. Brochant (4.4x/4.2x): 20/20 = 100%, avg 19.45
  - A. Stevens (3.2x/3.4x): 16/20 = 80%, avg 10.08
  - N. Hillmon (3.2x/3x/3.4x/2.8x): 14/20 = 70%, avg 13.17
  - A. Fam (3.3x/3.1x): 13/20 = 65%, avg 6.62
  - C. Clark (2x/2.2x): 5/20 = 25%, avg 10.48
  - A. Kuier (3.6x): 5/20 = 25%, avg 1.15
  - K. Copper (2.4x/2.8x/2.6x): 4/20 = 20%, avg 8.50
  - M. Timpson (4.4x): 3/20 = 15%, avg 1.40

### Model Performance

**Our frozen lineup**:
  - Paige Bueckers (DAL, 0.2x boost) -- pred p50=3.1274963081238885
  - Angel Reese (ATL, 0.4x boost) -- pred p50=3.1632967872783166
  - Flau'jae Johnson (SEA, 1.3x boost) -- pred p50=1.9525808198854504
  - Elizabeth Williams (CHI, 2.1x boost) -- pred p50=1.7880512749960793
  - Azurá Stevens (CHI, 1.8x boost) -- pred p50=1.5360697970210895

**Prediction accuracy**:
  - Paige Bueckers: pred 3.13 vs actual 4.64 (error +1.52) [IN BAND]
  - Angel Reese: pred 3.16 vs actual 3.16 (error -0.01) [IN BAND]
  - Flau'jae Johnson: pred 1.95 vs actual 1.83 (error -0.13) [IN BAND]
  - Azurá Stevens: pred 1.54 vs actual 3.02 (error +1.48) [IN BAND]
  - **MAE**: 0.79 | **In-band rate**: 4/4

**Rank correlation** (our picks vs realized): 0.600

**Leverage** (ownership differentiation):
  - Paige Bueckers: field ownership 15% [DIFFERENTIATED]
  - Angel Reese: field ownership 5% [DIFFERENTIATED]
  - Flau'jae Johnson: field ownership 5% [DIFFERENTIATED]
  - Elizabeth Williams: field ownership 0% [DIFFERENTIATED]
  - Azurá Stevens: field ownership 80% [chalk]

**Our game stacks**: {'CHI': ['Elizabeth Williams', 'Azurá Stevens']}

**Regime**: top_20 | expected payout: 1.111

**Enrichment gaps** (27 players without vegas): Jade Melbourne, Kejia Ran, Dominique Malonga, Awa Fam, Stefanie Dolson, Jordan Horston, Zia Cooke, Mackenzie Holmes, Katie Lou Samuelson, Taylor Thierry

### Outcome Classification

**(A) Correctly priced** (18 players):
  - N. Hillmon (ATL, 1.4x, 115 drafts) = 4.1 -- High-draft player delivered as expected
  - J. Canada (ATL, 0.6x, 93 drafts) = 5.06 -- High-draft player delivered as expected
  - K. Cardoso (CHI, 0.7x, 164 drafts) = 4.33 -- High-draft player delivered as expected
  - A. Stevens (CHI, 1.8x, 38 drafts) = 3.02 -- Mid-draft player with mid outcome -- no edge either way
  - C. Clark (IND, 0.2x, 873 drafts) = 4.85 -- High-draft player delivered as expected
  - P. Bueckers (DAL, 0.2x, 1300 drafts) = 4.64 -- High-draft player delivered as expected
  - A. Gray (ATL, 0.4x, 157 drafts) = 3.83 -- High-draft player delivered as expected
  - K. Copper (PHO, 0.8x, 195 drafts) = 3.27 -- High-draft player delivered as expected
  - R. Johnson (IND, 3.0x, 2 drafts) = 1.83 -- Outcome roughly matched draft position and signals
  - R. Howard (ATL, 0.1x, 707 drafts) = 4.17 -- High-draft player delivered as expected
  - N. Cloud (CHI, 1.1x, 65 drafts) = 2.76 -- Outcome roughly matched draft position and signals
  - K. Samuelson (SEA, 3.0x, 1 drafts) = 1.84 -- Outcome roughly matched draft position and signals
  - A. Fudd (DAL, 0.9x, 250 drafts) = 2.9 -- Outcome roughly matched draft position and signals
  - N. Hiedeman (SEA, 0.7x, 174 drafts) = 3.08 -- High-draft player delivered as expected
  - L. Yueru (DAL, 3.0x, 1 drafts) = 1.59 -- Outcome roughly matched draft position and signals
  - A. Reese (ATL, 0.4x, 413 drafts) = 3.16 -- High-draft player delivered as expected
  - T. Paopao (ATL, 3.0x, 1 drafts) = 1.51 -- Outcome roughly matched draft position and signals
  - S. Dolson (SEA, 3.0x, 3 drafts) = 1.44 -- Low-draft player correctly faded by the field

**(C) Unknowable / winners' edge** (2 players):
  - N. Brochant (PHO, 3.0x, 2 drafts) = 4.59 -- High-boost low-draft player who overperformed
  - V. Ayayi (PHO, 3.0x, 1 drafts) = 3.24 -- High-boost low-draft player who overperformed

**Takeaway**: 2 unknowable outcomes vs 0 knowable misses. Winning lineups on this slate were driven more by variance or private information than public signal.

---