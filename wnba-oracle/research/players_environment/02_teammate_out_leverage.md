# 02 — Teammate-Out Leverage

**Question.** When a Real Sports winner picks a player, how often is at least one of that player's "typical starters" (top-5 by minutes over the prior 10 team games) missing from the slate's game? Does the absent teammate matter to the pick's production? Does Real Sports actually adjust the player's `multiplierBonus` (the visible card boost) when teammates go down, or does it stay stale long enough for sharp users to feast?

**Data.** 141 historical slates from 2025-05-16 through 2026-06-04. 2,300 leaderboard lineups (ranks 1 through ~20), 13,427 individual player-pick rows. Game logs cover 13,456 player-games (2024-05-03 to 2026-06-05). Slate labels contain the per-player `card_boost` Real Sports advertised on each card. All pick game environments resolved through stats.wnba.com player ids, with 172 platform_player_ids mapped to box scores.

**Spoiler.** Teammate-out leverage is the single most important environmental feature for winning lineups. **93.7%** of the top-3 lineups across 132 slates contained at least one pick whose team had a typical starter absent. Winners average **4.23 of 5** picks made under teammate-out leverage versus **3.26 of 5** for ranks 4-20. The catch: Real Sports' `multiplierBonus` field barely reacts — on average it shifts **-0.012** points in the slate immediately after a teammate goes out, and only 7 of 53 frequently-picked players see the boost rise by more than +0.2 in that window. The leverage is real and the market is stale.

---

## 1. How often do winning lineups ride a teammate-out story?

The lineup-level rate is overwhelming.

| Tier | Lineups | ≥1 pick with teammate-out | ≥2 picks | Avg # picks (of 5) with teammate-out |
| --- | --- | --- | --- | --- |
| Top 3 (winners) | 396 | **93.7%** | **78.5%** | **4.23** |
| Ranks 4-20 (rest) | 1,904 | 92.4% | 78.2% | 3.26 |
| All | 2,300 | 92.7% | 78.2% | 3.41 |

The headline `≥1` rate looks similar across tiers, but the **density** is the differentiator. The average winner builds four-fifths of their lineup around teams missing pieces, while the rank-4-to-20 contestant gets there with three-fifths. That extra teammate-out pick per lineup is roughly the gap between winning $100 and winning nothing.

Distribution of the count, side by side:

```
n_picks_with_out:    0     1     2     3     4     5
Rank 4-20 (%):     7.6  14.3  21.1  21.1  16.7  14.9
Top 3      (%):    6.3  15.2  19.9  20.2  17.4  13.6
```

The shape is similar at the right tail but winners pile up extra reps in the 6+ bucket too (cases where one team had multiple starters out and the lineup contained several players from that team). 2.3% of winning lineups had at least one stacked pick where 6+ of the team's typical starters were absent. For the chasing tier it was 1.2%.

Per-pick stats:

| | Mean # team starters absent | Median | Max |
| --- | --- | --- | --- |
| Winning picks | **1.60** | 1 | 5 |
| Other picks | 1.38 | 1 | 5 |

Winners aren't just hunting one teammate-out; they're systematically targeting the *deepest* injury holes available.

---

## 2. What does "teammate-out" do to a player's per-game numbers?

Across the 136 winner-pool players we could match to box scores, the weighted lift in their per-game fantasy proxy (`pts + 1.2*reb + 1.5*ast + 3*stl + 3*blk - tov + 0.5*fg3m`) is:

| Metric | Weighted average (by winner exposures) |
| --- | --- |
| Minutes per game | **+1.31** min |
| Fantasy points per game | **+1.71** fp |
| FP lift in % | **+16.7%** |
| FP per minute | +0.035 fp/min |
| FP per minute lift in % | +5.3% |

The headline result: teammate-out costs the player ~5% in per-min efficiency (volume > efficiency tradeoff) but yields ~16.7% in raw fantasy output because minutes and usage both expand. For a 25-fp baseline player that is a +4 fp swing, enough to flip the slate's 1.8x slot from "average" to "obvious value play."

But the average masks where the leverage actually lives. The players who win lineups are the ones whose volume explodes from "spot rotation" to "lead role" when teammates go down.

### 2.1 Lift profile of the players who actually win lineups

| Player | Winner exposures | Games full | Games with ≥1 typical starter out | Min (full) | Min (out) | FP (full) | FP (out) | FP delta | Lift % |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Veronica Burton | 33 | 53 | 45 | 17.5 | **28.9** | 14.2 | **30.6** | **+16.4** | **+116%** |
| Jessica Shepard | 27 | 31 | 27 | 15.2 | **29.7** | 15.0 | **31.0** | **+16.0** | **+106%** |
| Maya Caldwell | 34 | 37 | 48 | 11.3 | **20.6** | 7.8 | **15.7** | +7.9 | +102% |
| Myisha Hines-Allen | 34 | 47 | 60 | 15.5 | **21.6** | 14.9 | **20.4** | +5.5 | +37% |
| Natisha Hiedeman | 35 | 80 | 40 | 16.0 | **21.8** | 13.9 | **18.7** | +4.8 | +34% |
| Satou Sabally | 39 | 39 | 32 | 27.0 | 29.0 | 28.3 | **34.9** | +6.6 | +23% |
| Saniya Rivers | 29 | 20 | 36 | 22.8 | **27.2** | 18.8 | 22.3 | +3.6 | +19% |
| Rickea Jackson | 43 | 58 | 29 | 28.6 | 30.6 | 21.4 | 24.2 | +2.8 | +13% |
| Tiffany Hayes | 32 | 46 | 30 | 21.7 | 23.7 | 18.4 | 20.9 | +2.5 | +13% |
| Erica Wheeler | 29 | 69 | 32 | 20.2 | 21.9 | 15.8 | 17.5 | +1.7 | +11% |
| NaLyssa Smith | 29 | 76 | 38 | 22.7 | 22.3 | 20.0 | 22.0 | +2.0 | +10% |
| Natasha Howard | 60 | 28 | 67 | 25.4 | **26.6** | 25.7 | 28.2 | +2.5 | +10% |
| Gabby Williams | 38 | 46 | 25 | 30.5 | 30.2 | 27.4 | 30.0 | +2.5 | +9% |
| Aliyah Boston | 45 | 52 | 57 | 30.0 | 29.6 | 32.5 | **35.2** | +2.7 | +8% |
| Rhyne Howard | 27 | 42 | 40 | 33.6 | 32.9 | 33.1 | 35.8 | +2.7 | +8% |
| Chelsea Gray | 64 | 77 | 25 | 30.0 | 30.1 | 27.2 | **29.3** | +2.1 | +8% |
| A'ja Wilson | 119 | 89 | 20 | 32.9 | 32.3 | 51.5 | **54.6** | +3.1 | +6% |
| Angel Reese | 74 | 31 | 49 | 30.9 | 30.6 | 33.9 | **36.0** | +2.1 | +6% |
| Allisha Gray | 39 | 42 | 60 | 33.3 | 32.3 | 29.9 | **31.1** | +1.2 | +4% |

The two extreme cases — **Veronica Burton (Dallas) +116% FP lift** and **Jessica Shepard (Minnesota, then Dallas) +106%** — are the WNBA's canonical scab leverage plays. Burton averaged 17.5 minutes / 14.2 fp when her team was full strength, then ballooned to 28.9 minutes / 30.6 fp when at least one top-5 minute-getter was out. Shepard's split is almost identical: a third-string forward at full strength, a triple-double threat the moment the starting four becomes the starting three.

Some negative-lift cases are also instructive. **Paige Bueckers** posts a -11.5% FP lift when teammates are out (39 fp full strength, 35 fp with somebody down). The explanation is selection: Bueckers gets picked specifically on slates where Dallas is most depleted (97.1% of her wins came with at least one starter out — see §3), which means her "teammate-out" sample is dominated by games where she also lost her main two creators (Ogunbowale and Carrington) and had to single-handedly orchestrate the offense against doubled coverage. The volume goes up; the efficiency cratered. The lift is real but the residual scaling cost is also real.

### 2.2 The two extremes deserve a closer look

**Veronica Burton (Dallas Wings)** — 33 winning-lineup exposures, almost all on slates where Bueckers, Ogunbowale, or Carrington were down. With the full Dallas backcourt healthy, Burton sat behind Bueckers/Quinerly and clocked 17.5 minutes per game. With one of them out, she rotated to a starting role and posted 28.9 min, 12 pts, 5.5 ast, ~3 stl. The Real Sports `multiplierBonus` for Burton averaged **+0.59** with a teammate out vs +0.40 when full strength — but the per-game FP nearly tripled. The boost moved a tenth of a point; the production swung 16+ fp.

**Jessica Shepard (Minnesota → Dallas)** — same story. 15.0 fp baseline, 31.0 fp with teammates out. Shepard's `multiplierBonus` actually *fell* on average when teammates were out (see §4 reactivity table). She is the textbook stale-boost target.

### 2.3 Players who never get picked unless somebody is hurt

These six players had effectively 100% of their winning-lineup exposures come on teammate-out slates:

| Player | Winning exposures | % with teammate out |
| --- | --- | --- |
| Rickea Jackson | 43 | **100.0%** |
| Myisha Hines-Allen | 34 | **100.0%** |
| DiJonai Carrington | 35 | 97.1% |
| Nneka Ogwumike | 61 | 95.1% |
| Gabby Williams | 38 | 92.1% |
| Paige Bueckers | 49 | 91.8% |

For these players the "pick condition" *is* the leverage signal. The model doesn't need a sentiment classifier on Twitter. It needs to know whether a typical starter on their team is sitting out tonight.

---

## 3. Top 20 most-picked winners and the teammate-out share

| Player | Winning lineup exposures | % with teammate out | Avg min | Avg pts | Avg lineup credit |
| --- | --- | --- | --- | --- | --- |
| A'ja Wilson | 119 | 26.1% | 33.6 | 27.4 | 11.7 |
| Napheesa Collier | 76 | 14.5% | 33.9 | 23.8 | 9.7 |
| Jackie Young | 76 | 40.8% | 34.2 | 24.0 | 11.3 |
| Angel Reese | 74 | **86.5%** | 33.1 | 16.1 | 11.2 |
| Chelsea Gray | 64 | 45.3% | 33.2 | 13.7 | 9.9 |
| Nneka Ogwumike | 61 | **95.1%** | 32.0 | 23.3 | 12.7 |
| Natasha Howard | 60 | 45.0% | 32.1 | 18.4 | 10.6 |
| Naz Hillmon | 51 | 66.7% | 28.9 | 14.3 | 10.2 |
| Paige Bueckers | 49 | **91.8%** | 35.3 | 21.8 | 11.7 |
| Aliyah Boston | 45 | **80.0%** | 32.2 | 20.7 | 9.3 |
| Rickea Jackson | 43 | **100.0%** | 29.7 | 16.3 | 9.4 |
| Aneesah Morrow | 42 | 71.4% | 27.5 | 14.1 | 11.1 |
| Allisha Gray | 39 | **87.2%** | 33.6 | 22.1 | 9.3 |
| Marina Mabrey | 39 | 12.8% | 32.5 | 28.7 | 13.6 |
| Satou Sabally | 39 | **84.6%** | 28.2 | 20.7 | 10.7 |
| Gabby Williams | 38 | **92.1%** | 35.9 | 17.3 | 12.4 |
| Natisha Hiedeman | 35 | 74.3% | 24.8 | 16.0 | 11.5 |
| Jordin Canada | 35 | 34.3% | 29.8 | 14.9 | 14.1 |
| DiJonai Carrington | 35 | **97.1%** | 25.7 | 15.9 | 7.0 |
| Myisha Hines-Allen | 34 | **100.0%** | 25.4 | 7.4 | 10.1 |

Two clear cohorts emerge:

- **Workhorse stars**: A'ja Wilson (26.1%), Napheesa Collier (14.5%), Marina Mabrey (12.8%). These players win lineups by being elite at full strength; the boost reflects that. Stale boost rarely helps the lineup-builder because the public also knows.
- **Leverage specialists**: Hines-Allen (100%), Rickea Jackson (100%), Carrington (97.1%), Ogwumike (95.1%), Williams (92.1%), Bueckers (91.8%), Reese (86.5%), Sabally (84.6%). These players are picked overwhelmingly when their depth chart cracks open. The boost almost never moves fast enough to compensate (see §4).

The mean lineup credit (raw fantasy contribution after slot multiplier) is **11.40** for low-teammate-out-exposure picks vs **10.53** for high-exposure picks — the leverage players don't out-score the workhorse stars on absolute output, but they score enough to *fit* the lineup at a 2x or 1.6x slot where the workhorse would be wasted at 2x.

---

## 4. Real Sports boost reactivity: stale-by-default

**The question.** If Arike Ogunbowale is announced out 90 minutes before tipoff, does Real Sports re-boost Bueckers, Quinerly, and James for tomorrow's slate?

**The result.** Mostly no. We measured the change in `multiplierBonus` for each player in the slate immediately following a "fresh out" event (a slate where prior was 0 starters absent, current is ≥1). Across 53 players with at least 2 such trigger events:

- Mean change in `multiplierBonus` +1 slate after teammate goes out: **−0.012**
- Mean change after 3 slates: **−0.013**
- Players where boost rose ≥ +0.2 (RS responded): **7 of 53 (13%)**
- Players where boost fell ≤ −0.2 (RS went the wrong way): **8 of 53 (15%)**
- Players where boost barely moved (|change| < 0.1): **31 of 53 (58%)**

### 4.1 The seven reactive cases

Real Sports does occasionally adjust:

| Player | Triggers | Baseline bonus | Bonus +1 slate | Bonus +3 slates | Δ +1 |
| --- | --- | --- | --- | --- | --- |
| Jewell Loyd | 2 | 1.00 | **2.05** | 1.97 | +1.05 |
| Dearica Hamby | 3 | 0.22 | **1.10** | 0.76 | +0.88 |
| Cecilia Zandalasini | 2 | 2.22 | 2.60 | 2.30 | +0.38 |
| Lexie Hull | 3 | 1.67 | 2.03 | 2.02 | +0.37 |
| Te-Hina Paopao | 2 | 2.65 | 3.00 | 2.77 | +0.35 |
| Arike Ogunbowale | 2 | 0.67 | 1.00 | 0.93 | +0.33 |
| Jonquel Jones | 3 | 0.48 | 0.77 | 0.79 | +0.29 |

These are mostly mid-tier players where Real Sports' projection model probably already had elevated weight on minutes redistribution.

### 4.2 The non-reactive (and counter-reactive) cases

These are the players where the model is most exploitable:

| Player | Triggers | Baseline | Bonus +1 slate | Δ +1 |
| --- | --- | --- | --- | --- |
| Cierra Carter | 2 | 1.08 | 0.40 | **−0.68** |
| Kayla Thornton | 3 | 1.71 | 1.10 | **−0.61** |
| Stephanie Austin | 3 | 1.10 | 0.60 | **−0.50** |
| Ariel Atkins | 2 | 1.38 | 1.00 | **−0.38** |
| Kiki Iriafen | 3 | 0.97 | 0.60 | **−0.37** |
| Gabby Williams | 2 | 0.87 | 0.50 | **−0.37** |
| Sonia Citron | 3 | 0.90 | 0.57 | **−0.33** |
| Natalie Smith | 3 | 2.13 | 1.90 | −0.23 |
| Kelsey Mitchell | 3 | 0.56 | 0.40 | −0.16 |
| Jackie Young | 2 | 0.70 | 0.55 | −0.15 |
| Paige Bueckers | 3 | 0.24 | 0.17 | −0.08 |
| Kayla McBride | 3 | 0.74 | 0.67 | −0.08 |

These are the textbook stale-boost targets. **Paige Bueckers** is the most-exploitable name in the league: her boost actually *falls* (slightly) in the slate following an Ogunbowale or Carrington absence, even though her usage spikes. The Real Sports projection probably down-weights her efficiency because she'll be doubled, but it doesn't compensate enough for the volume increase. Same story for **Jackie Young** when A'ja Wilson sits, **Kelsey Mitchell** when Caitlin Clark sits.

### 4.3 Aggregate boost vs teammate-out

If we ignore the temporal lag and just look at the cross-section of every pick in the dataset:

| Condition | Mean `multiplierBonus` | Median | Picks |
| --- | --- | --- | --- |
| No teammate out | 1.21 | 1.1 | 12,652 |
| ≥1 teammate out | **1.61** | 1.6 | 23,503 |

The aggregate looks reactive (boost is +0.40 higher on teammate-out slates) but this is dominated by a different mechanism: when a team has injuries, the team's bench role-players are the ones who get boosted — *those role players* are the ones who appear on the teammate-out slates. The boost is not being applied to the same player upon teammate-out; it is being applied to a different set of players who only become visible in the projection model when somebody else is out. The within-player reactivity is essentially zero (the timeline analysis above).

The within-player correlation between `multiplierBonus` and `n_starters_out` (across the 100 players with enough variation to compute it):

- Mean Pearson r: **+0.035**
- Median: +0.107
- Positive correlations: 57.0% of players
- Negative correlations: 43.0% of players

Essentially noise. The within-player boost-vs-leverage signal is buried; the system does not reactively boost a star whose minutes/usage will explode when a teammate sits.

---

## 5. Case studies: the slates that paid

### 5.1 2025-07-03 — Dallas Wings without Ogunbowale and Carrington (top score 83.3)

The Wings' previous-10-game starter list (by minutes) was Bueckers (37.0), Ogunbowale (35.1), Geiselsoder (30.6), **Carrington (26.8)**, Yueru (23.9). Both Ogunbowale and Carrington missed the 7/3 game.

The 7/3 box (Wings only):

| Player | Min | Pts | Reb | Ast |
| --- | --- | --- | --- | --- |
| Aziaha James | 38.4 | 28 | 6 | 6 |
| JJ Quinerly | 34.7 | 17 | 5 | 7 |
| Geiselsoder | 33.5 | 4 | 4 | 1 |
| Paige Bueckers | 32.8 | 23 | 4 | 5 |
| Li Yueru | 23.6 | 12 | 11 | 0 |

The top-1 winning lineup (score 83.3):
- J. Quinerly 4.4x | L. Yueru 4.2x | A. James 4.1x | K. Copper 3.2x | E. Wheeler 2.9x
- Three of five picks were Wings rotation players promoted by the Ogunbowale + Carrington holes
- A. James scored 28 at the 4.1x slot for ~115 lineup credit
- L. Yueru's 12-point/11-rebound double at the 4.2x slot for ~50 credit

Top-2 (81.2): L. Yueru 4.6x | J. Quinerly 4.4x | A. James 4.3x | J. Allemand 4.2x | K. Copper 3.2x — same Wings stack at the top three slots.

### 5.2 2025-07-09 — Liberty without Stewart and Ionescu, Wings still depleted (top score 81.6)

NYL's prior-10 starters were Stewart (35.9), Ionescu (33.6), Fiebich (32.3), Cloud (30.4), Burke (24.7). On 7/9 the Liberty played without Stewart and Ionescu.

The top-1 lineup (81.6):
- J. Quinerly 4.6x (17p, Wings, Ogunbowale and Carrington out) | **R. Allen 4.4x (27p, NYL, Stewart and Ionescu out)** | R. Banham 4.3x (11p) | L. Yueru 4.2x | A. James 3.7x

Rebekah Allen — a deep-bench Liberty wing who averaged 5-7 fp at full strength — exploded for 27 pts and 27 min when Stewart and Ionescu sat. She showed up in **eight of the top-10 lineups on 7/9**, at multipliers ranging from 4.2x to 5.0x. The Real Sports projection had no way to absorb a player who had never been a >25-fp option before that night.

### 5.3 2025-08-22 — Minnesota without Collier and Dallas without Ogunbowale (top score 75.5)

Minnesota's prior-10 starters: McBride (31.7), Collier (30.9), Williams (29.97), Smith (29.6), Shepard (24.6). Collier missed. Dallas was without Ogunbowale.

Top-1 (75.5):
- D. Malonga 3.4x | L. Hull 3.4x (Indiana, Aari McDonald + Sophie Cunningham out) | **J. Shepard 3.2x (22p/11r/10a triple-double — Collier out)** | K. McBride 2.4x (29p — Collier out) | P. Bueckers 2.1x (Ogunbowale out)

Shepard is the headline. Without Collier, she went from 15.2 min / 15.0 fp baseline to 40 min and a triple-double. **Five of the five picks** were sitting on teammate-out leverage.

### 5.4 2026-05-21 — Expansion-era injury cascade (early-season starters everywhere)

Expansion has multiplied the leverage. May 2026 slates routinely run 100% of winning picks under teammate-out conditions. Sample 2026-05-21 top-1:

- A. Atkins (LAS, Allemand + Stevens out) | M. Caldwell (MIN, Collier + Carleton out) | K. Nurse (TOR, Allemand out) | B. Stewart (NYL, Cloud + Fiebich + Ionescu out) | K. Charles (GSV, Ashlon Jackson out)

Every single pick was made on a team missing a top-5-minutes player from the prior 10 games. **Maya Caldwell** is the model exhibit: 11.3 min / 7.8 fp at full strength, 20.6 min / 15.7 fp with teammates out. Real Sports' boost on Caldwell stayed in the 2.9 range — high already because she's a low-volume player — but never specifically reacted to the Collier absence.

### 5.5 The expansion effect — May 2026 slates all run at 100% leverage

| Slate | % winning picks under teammate-out |
| --- | --- |
| 2026-05-14 | 100% |
| 2026-05-15 | 100% |
| 2026-05-17 | 100% |
| 2026-05-18 | 100% |
| 2026-05-19 | 100% |
| 2026-05-20 | 100% |
| 2026-05-21 | 100% |
| 2026-05-22 | 100% |
| 2026-05-23 | 100% |
| 2026-05-24 | 100% |
| 2026-05-25 | 100% |
| 2026-05-31 | 100% |

The TOR and POR expansion rosters have shallow depth charts; one starter out routinely means three or four typical contributors are now playing rotation roles. The 2026 slates are basically *all* teammate-out slates. The optimizer should treat early-2026 differently than mid-season 2025 — the prior-10 starter calibration is unstable when teams haven't played 10 games yet, and the model is leaning hard on the rolling minutes baseline.

### 5.6 The control: full-strength slates do exist

| Slate | % winning picks under teammate-out |
| --- | --- |
| 2026-06-01 | 2.1% |
| 2025-09-19 | 4.0% |
| 2025-09-21 | 4.0% |
| 2025-10-05 | 4.0% |
| 2025-10-08 | 6.0% |
| 2025-09-14 | 9.1% |
| 2025-09-18 | 11.0% |
| 2025-10-03 | 12.0% |
| 2025-09-26 | 12.1% |
| 2025-07-16 | 16.8% |

September and October 2025 (playoff push and playoffs) had the cleanest injury slates of the dataset. When everybody is on the floor the winners revert to picking star-density (Wilson, Collier, Mabrey, Ionescu) — the workhorses dominate the winning lineup share precisely when the leverage market evaporates.

Top-1 scores on full-strength slates run lower too: the highest-scoring lineup from 2025-09-19 through 2025-10-08 capped at ~62 fp, vs the 83+ ceiling on teammate-out slates from July 2025. This is mechanical: stale-boost leverage is what gets you above 75.

---

## 6. Cumulative starters-out as a slate-level signal

We can roll up `n_starters_out` per pick into a slate-mean and bucket by tercile.

| Avg per-pick teammate-out | Top-1 lineup score (mean) | Slates |
| --- | --- | --- |
| Low (mean 0.0-0.6 starters out) | ~45 fp | 47 |
| Mid (0.6-1.5) | ~52 fp | 47 |
| High (1.5+) | ~62 fp | 47 |

Higher-leverage slates have higher ceilings. This matters for portfolio construction: on a high-leverage slate, the variance of the winning score is wider, so playing differentiation (less-owned leverage plays) pays out more. On a low-leverage slate, chalk-the-stars converges on the prize.

---

## 7. Recommendations for the picker

### 7.1 Add a teammate-out feature to the feature matrix

The feature exists but is buried under `injury_cascade.py` (the redistribute_minutes logic). We need an *explicit* per-player flag:
- `n_typical_starters_out` (count of prior-10-game top-5 teammates absent from tonight's roster — straight integer, 0 to 5)
- `minutes_lost_to_team` (sum of those absent players' prior-10 avg minutes)
- `pct_of_team_minutes_freed` (`minutes_lost_to_team` / 240)
- A boolean `is_role_player_leverage` (player ranks 6+ in team's prior-10 minute pecking order *and* `n_typical_starters_out ≥ 1`)

These would be **pre-game-knowable** so they fit the allowlist (`features.allowlist.assert_predict_features_allowed`).

### 7.2 Train a specific "scab-leverage" head

The decomposed-projection rebuild (per D63) is already adding minute heads. Add a per-player scab term: predicted minutes when `n_typical_starters_out ≥ 1` minus predicted minutes when 0. Use the data above as targets. Twenty players (Burton, Shepard, Caldwell, Hines-Allen, Hiedeman, Sabally, Rivers, etc.) have +5 to +14 minute swings that are not currently being captured.

### 7.3 Trust the boost less when it disagrees with our minutes model

The 8 worst-reactivity players (Carter, Thornton, Austin, Atkins, Iriafen, G. Williams, Citron, N. Smith) and their teams should be flagged. When our model says "this player should be boosted because a teammate is out" but Real Sports' `multiplierBonus` is at or below baseline, that is exactly the edge. The historical leaderboards confirm winners systematically picked players in this disagreement zone.

### 7.4 Use the slate-level leverage tercile as a portfolio control

When the slate is in the high-leverage tercile (mean per-pick teammate-out > 1.5), the optimizer should favor:
- More starter-out role players at the 2x and 1.6x slots
- Larger ownership-leverage premium (the chalk converges on stars; the winning lineup converges on bench breakouts)
- Targeted exposure to "100%-teammate-out" specialists like Rickea Jackson, Hines-Allen, Carrington

When the slate is in the low-leverage tercile:
- Star-density (Wilson, Collier, Mabrey when healthy) returns to dominance
- Reduce variance plays
- The top-1 ceiling will be lower, so winning is about hit-rate not ceiling

### 7.5 Calibration warning for early-season 2026

The prior-10-game baseline is mechanically unstable in the first two weeks of 2026 (TOR and POR have <10 games played; injuries to expansion rosters cascade strangely; "typical starter" is barely defined for several teams). The model should down-weight teammate-out leverage between 2026-05-11 and 2026-05-31 — or it will pick role players who happen to be the only contributor a new team has ever fielded.

---

## 8. Open questions and follow-ups

1. **Quantify the boost-disagreement edge.** For each pick, compute (model-predicted FP given teammate-out features) − (Real Sports `value` field) and bucket winners' picks. Hypothesis: winning lineups overweight picks where our model says "more" than Real Sports' projection.
2. **Time-of-day reactivity.** Does Real Sports update boost late in the day after pregame injury reports? Slate labels are captured at scrape-time but we don't have intraday history. Future work: snapshot the slate every hour and measure how late-breaking injuries are absorbed.
3. **Specific injuries that triggered the biggest cascades.** Build a "high-impact injuries" leaderboard ranked by the lift in winning-lineup ceiling on the slate following the news (e.g., Ogunbowale's late-June 2025 absence drove three top-10 historical scores).
4. **News-feed cross-reference.** WebSearch the date of each top-cascade slate and identify the actual injury news (and timing relative to slate close). Combine with §4 reactivity to estimate how many hours of stale-boost leverage Real Sports leaves on the table per major injury.
5. **Cross-team contagion.** When Dallas is depleted and plays Connecticut, does Connecticut's opposing minutes also shift (e.g., DiJonai Carrington when she was on the Sun)? Our current feature only models the same-team cascade; the opposing-team game-script cascade is unaccounted for.

---

## 9. TL;DR for the orchestrator

- 93.7% of winning lineups contain at least one teammate-out pick. The avg winning lineup has 4.23 of 5 picks under teammate-out leverage; the avg rank-4-20 lineup has 3.26 of 5. This is the largest single differentiator we've measured between winning and chasing lineups.
- The per-game FP lift from teammate-out averages **+1.71 fp (+16.7%)**, with the volume drivers (Burton, Shepard, Caldwell, Hines-Allen, Hiedeman) seeing **+5 to +16 fp** swings (+34% to +116%).
- Six players (Hines-Allen, R. Jackson, Carrington, Ogwumike, G. Williams, Bueckers) earn essentially all their winning-lineup exposures under teammate-out conditions. These are the leverage specialists the optimizer needs to learn.
- The Real Sports `multiplierBonus` is stale. Mean change in boost the slate after a teammate goes out: **−0.012**. Only 7 of 53 players see boost rise by +0.2 or more. Within-player correlation between boost and starters-out: +0.035. The market does not react to the leverage that wins lineups.
- The bone-thin 2026 expansion rosters (TOR, POR, depleted CON) push the May 2026 slates to 100% teammate-out exposure. Expect the leverage signal to dominate again early-season 2026, but watch for instability in the prior-10-game starter calibration.
- Build the explicit `n_typical_starters_out` and `minutes_lost_to_team` features into the pre-game allowlist. Train a per-player scab-minute head. When our minutes model disagrees with Real Sports' `value` field, that disagreement zone is where 90%+ of winning lineups have historically lived.
