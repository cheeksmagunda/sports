# 08 — Recent Form & Momentum

How much does the player's last 3 / 5 / 10 games predict (a) being on the winning lineup and (b) the realized slate score? Does Real Sports' card-boost pricing react fast enough to a hot streak, or does it leave money on the table for sell-low cold buys?

- **Slates analyzed:** 141 (2025-05-16 -> 2026-06-04)
- **Winning lineups:** 141 (rank-1 entries, one per slate-contest)
- **Winning picks expanded:** 705 player-slots (5 per lineup)
- **Available-pick baseline (corpus):** 4,002 slate-player rows
- **Game logs joined:** 13,456 player-games (2024-05-03 -> 2026-06-05)
- **Player-id bridge:** 178 of 180 corpus players mapped to gl ids (99%)
- **Fantasy formula (reverse engineered from the corpus per-game real_score):** `pts + 1.2*reb + 1.5*ast + 3*stl + 3*blk - tov`
- **Backing tables:** `research/players_environment/_form_winpicks.parquet`, `_form_corpus.parquet`, `_form_by_player.csv`
- **Build script:** `scripts/research/form_momentum.py`

For each winning pick we compute the player's pre-slate rolling mean fantasy score over the last 3, 5, and 10 games (strictly before `slate_date`), plus their season-to-date baseline (at least 5 prior games). We bucket each pick relative to that player's own baseline:

| Bucket  | Definition                  |
| ------- | --------------------------- |
| hot     | `r5 - base >= +3.0` pts     |
| cold    | `r5 - base <= -3.0` pts     |
| normal  | otherwise                   |
| unknown | <5 prior games (debut etc.) |

`+/- 3.0` is roughly half a sigma of the per-player rolling-vs-baseline gap and survives Wilson, Plum, Bueckers tier separation as a reasonable "noticeably hot/cold" line.

---

## 1. The headline

Winning picks **skew hot, not cold or random** — but the lift over random is moderate, and a meaningful 22.6% of winning picks come from cold streaks. Real Sports pricing is sticky and lags the streak by roughly a slate. The cold-buy edge is real but narrow; the hot-buy edge is broader and shows up most strongly in the 1.6x-2.2x and 3.1x-3.7x multiplier bands.

| Bucket (r5)   | Share of winning picks | Share of available pool | Lift     |
| ------------- | ---------------------- | ----------------------- | -------- |
| hot           | **34.5%**              | 30.7%                   | **+3.8 pp** (+12% relative) |
| normal        | 34.3%                  | 39.2%                   | -4.9 pp  |
| cold          | 22.6%                  | 24.5%                   | -1.9 pp  |
| unknown       | 8.7%                   | 5.6%                    | +3.1 pp  |

The hot bucket is overrepresented; the normal bucket is what loses share. Cold is roughly proportional (so "sell-low cold buys" do happen, but they are not the dominant winning-pick archetype). The `unknown` overweight is mostly rookies and call-ups slotted into 4x+ "everyone debuted, nobody knew" slots — Malonga, Hillmon, Allemand, Burton all show up here in their early appearances.

**Mean delta_r3 (recent 3 games vs season baseline):**

- winning picks: **+1.29 pts** (n=644)
- available pool: +0.85 pts (n=3,777)

Winners are running about half a point hotter than the pool over the 3-game window — small but consistent. Even more telling: winning lineups average **1.72 hot slots, 1.72 normal slots, 1.13 cold slots** (the unknown 0.43 is mostly the rookie/debut tail).

---

## 2. Recent form predicts realized slate score, but the season baseline is roughly as good

Correlation with realized `real_score` (on the slate the pick was made for):

| Feature                                       | Pearson r | n     |
| --------------------------------------------- | --------- | ----- |
| **r10** (last 10 games)                       | **0.494** | 3,777 |
| **r5** (last 5 games)                         | 0.475     | 3,777 |
| **season base** (all prior games this season) | 0.473     | 3,777 |
| **r3** (last 3 games)                         | 0.453     | 3,777 |
| `delta_r5` (r5 - season base)                 | **0.044** | 3,777 |

This is the core finding for the picker. The **10-game window is the single best individual predictor** of slate score — but it only beats the season baseline by 0.02 in correlation. The 3-game window is the *worst* of the three: short windows pick up too much per-game variance, including the random 0-pt blowouts.

The `delta_r5` correlation of 0.044 is the punchline: **once you condition on level, momentum adds almost nothing to forecasting absolute output**. A hot Wilson is still a Wilson; her absolute level dominates her trend. The signal is in the *bucket relative to the available pool at the same boost band*, not in the raw delta.

**Top-3 picks by r5 hit the day's actual top 3 scorers on average 0.99 of the time (33%) across 141 slates. Top-3 picks by season-base hit 1.00 of 3 (33%).** Form does not beat the season prior at picking the day's slate top.

---

## 3. Real Sports pricing IS reactive to season level, NOT to short-term form

Card boost is the bonus multiplier Real Sports stamps on the card pre-slate. Higher boost = cheaper / more value-y card. The corr structure tells the story:

| Pair                                         | Pearson r |
| -------------------------------------------- | --------- |
| `corr(card_boost, season_base)`              | **-0.798** |
| `corr(card_boost, r5)`                       | **-0.826** |
| `corr(card_boost, delta_r5_vs_base)`         | **-0.120** |

Boost is essentially a near-monotone inverse of player tier. The pricing absorbs your season level almost perfectly (negative 0.8 corr). It **barely reacts to short-term momentum** (-0.12 corr with delta).

When we residualize realized score against the season base, the boost vs residual correlation flips strongly positive:

- `corr(card_boost, real_score - season_base)` = **+0.774**

This is the mechanical signature of a *value*-style pricer: high-boost cards mostly belong to lower-tier players, who have wider relative-to-baseline upside because their baselines are low. Whether RS is "underreacting to hot streaks" specifically is harder to claim from this corr alone, so we ran the within-boost-band test.

### Within-boost-band: is HOT a real edge after pricing?

Mean realized real_score within boost quintile (B1 = lowest boost = stars, B5 = highest boost = cheap bench):

| Boost quintile | mean boost | mean base | cold (r5) | hot (r5) | normal (r5) |
| -------------- | ---------- | --------- | --------- | -------- | ----------- |
| B1 (stars)     | 0.14       | 33.6      | 3.687     | 3.317    | 3.512       |
| B2             | 0.59       | 27.1      | 2.931     | 2.969    | 3.005       |
| B3             | 1.16       | 22.5      | 2.636     | 2.616    | 2.568       |
| B4             | 2.09       | 16.8      | 2.105     | 2.258    | 2.203       |
| B5 (cheap)     | 3.00       | 11.5      | 1.416     | **1.611**| 1.280       |

At the **bottom of the price stack (B5, cheap cards)** hot **does beat** cold by **+0.20 pts** and normal by **+0.33 pts** — a +14% / +26% relative edge. RS is not catching the bench-player heat. This is exactly where you'd expect pricing lag because bench production is regime-dependent (injury fill-in, rotation change) and RS only sees the season prior.

At the **top of the stack (B1, stars)** the order **inverts** — cold stars (3.69) outperform hot stars (3.32) and normal (3.51). This is the "sell-low Wilson" pattern: the league's best players that had a 2-game dip but who are still going to be the league's best players today. Their cards stay 2x and 1.8x, and they smash the slate while looking like a "cold" pick to lazy form-chasers.

### Boost lag: does the boost actually move week-to-week?

Across consecutive same-player rows (slate D vs same player's prior slate), boost changes are tiny (median 0). Among **hot** (r3) picks, the mean boost change between slates is **-0.05** (RS slightly bumps the price up). Among **cold** picks, the boost change is **+0.06** (RS slightly cheapens them). So pricing does drift in the right direction, but at this magnitude (0.05 of a multiplier per slate) it takes 4-6 slates of sustained heat for the boost to meaningfully catch up — plenty of room for the picker.

---

## 4. Who wins from a hot streak vs from a cold streak?

Top winning-pick players ranked by frequency, with mean pre-slate r5 and r5 minus season base. Negative delta = winner appeared while looking *cold*. Positive = winner appeared while *hot*.

| Player         | Winning picks | mean r5 | mean delta_r5 | Read |
| -------------- | -------------:| -------:| -------------:| ---- |
| A. Wilson      | 32            | 49.38   | **-2.25**     | Star who wins from any state, slightly tilted to mean-revert buys |
| J. Young       | 16            | 32.39   | +2.14         | Hot-streak winner |
| A. Reese       | 14            | 34.94   | +0.54         | Neutral / chase by reputation |
| N. Collier     | 13            | 43.09   | -1.03         | MVP-tier; the dips are noise |
| **N. Howard**  | 12            | 22.73   | **-5.46**     | **Classic sell-low cold buy** — wins after slumping |
| C. Gray        | 12            | 29.67   | +4.19         | Hot-streak winner |
| **D. Malonga** | 11            | 23.22   | **+9.62**     | **Rookie breakout, pure momentum** |
| J. Allemand    | 11            | 21.40   | +4.41         | Hot-streak rookie/role-shift |
| **V. Burton**  | 10            | 27.17   | **+10.51**    | **Strongest hot-streak winner in the dataset** |
| P. Bueckers    | 10            | 36.23   | +1.84         | Hot-ish |
| N. Hiedeman    | 10            | 19.29   | +5.73         | Hot-streak bench-tier winner |
| J. Shepard     | 9             | 22.54   | +2.19         | Mildly hot |
| E. Engstler    | 9             | 19.60   | +4.45         | Hot |
| L. Hull        | 9             | 18.28   | +3.67         | Hot |
| K. Cardoso     | 9             | 28.75   | +2.51         | Mildly hot |
| N. Hillmon     | 9             | 23.47   | +6.57         | Hot |
| N. Ogwumike    | 9             | 32.91   | -0.97         | Star, noise |
| S. Cunningham  | 9             | 18.14   | +0.32         | Neutral |
| C. Williams    | 9             | 31.71   | +3.16         | Hot |
| K. McBride     | 9             | 25.56   | +1.28         | Neutral |
| N. Smith       | 8             | 18.89   | -2.09         | Slightly cold |
| **D. Bonner**  | 8             | 18.72   | **-7.39**     | **Classic sell-low** |
| A. Morrow      | 8             | 20.69   | +4.94         | Hot |
| A. Thomas      | 8             | 38.57   | +1.10         | Star, noise |
| K. Charles     | 8             | 17.71   | +3.78         | Hot |

The split is clean:

- **Stars (Wilson, Collier, Thomas, Bueckers, Ogwumike, Reese):** show up from any form state, slight tilt to cold (sell-low). RS leaves their boost at ~0-0.4 regardless of recent dips.
- **Rookies / new role players (Malonga, Burton, Allemand, Hillmon, Hiedeman, Engstler, Hull):** *all* arrive on winning lineups while hot, deltas of +4 to +10. RS does not catch these in time.
- **Veteran bench / former-stars in new spots (Howard, Bonner, N. Smith):** flip-side sell-lows. Wins clustered in cold delta regions.

### Cold-buy winning slates — concrete examples

**A. Wilson, 2025-07-12 slate.** r5 = 38.12 (well below her 51.69 season base, delta -13.57). Took the 1.8x slot, scored 8.81 real points, walked into a winning lineup. Eight more A. Wilson winning picks across the season have delta_r5 worse than -5.

**D. Bonner, 2025-05-28 slate.** r5 = 13.96 vs 27.73 baseline (delta -13.77). Took the 4.4x slot, scored 3.66. Won because the lineup paid the 4.4x premium on a player whose card_boost was bloated by a 5-game slump that didn't reflect her actual capability.

**D. Bonner, 2025-07-14 slate.** r5 = 16.10 vs 26.94 (delta -10.84). 3.3x slot, 5.77 points, winner.

### Hot-buy winning slates — concrete examples

**V. Burton, 2025-08-24 slate.** r5 = **39.20** vs 18.07 baseline (delta +21.13). 2.4x slot, scored 6.38. The pricing was still treating her like an 18-pt player while she'd been a 39-pt player for two weeks straight.

**D. Malonga, 2025-08-28 slate.** r5 = 32.36 vs 16.03 (delta +16.33). 3.4x slot, 3.18 points. Rookie ascent that RS booked at high boost and the winners scooped.

**D. Malonga, 2025-08-05.** r5 = 26.72 vs 11.81 (delta +14.91). 4.1x slot, 2.25 points — even a moderate game was a winning slot because the 4.1x carry was that cheap relative to her now-real production rate.

**V. Burton, 2026-05-08.** r5 = 34.58 vs 20.28 (delta +14.30). Still being priced as a 20-pt player at 1.6x.

---

## 5. Multiplier tier × form bucket

Within each multiplier band, how often do winning slots come from hot / normal / cold? (`unknown` mostly omitted.)

| Mult band | hot  | normal | cold | unknown |
| --------- | ---: | -----: | ---: | ------: |
| 1.6x      | **44%** | 33% | 22% | 0% |
| 1.8x      | 31%  | 31%  | **38%** | 0% |
| 1.9x      | **75%** | 17% | 8%  | 0% |
| 2.0x      | 30%  | 34%  | **36%** | 0% |
| 2.1x      | 47%  | 37%  | 17% | 0% |
| 2.2x      | **42%** | 31% | 27% | 0% |
| 2.3x      | 40%  | 36%  | 20% | 4% |
| 2.4x      | **52%** | 30% | 19% | 0% |
| 2.6x      | 38%  | 19%  | 24% | 19% |
| 2.7x      | 39%  | 30%  | 17% | 13% |
| 3.1x      | **50%** | 25% | 19% | 6% |
| 3.4x      | **46%** | 29% | 13% | 13% |
| 3.5x      | **63%** | 19% | 6%  | 13% |
| 3.6x      | **46%** | 21% | 14% | 18% |
| 3.8x      | 15%  | **77%** | 8% | 0% |
| 4.1x      | **42%** | 37% | 5%  | 16% |
| 4.3x      | **60%** | 0%  | 0%  | 40% |
| 5.0x      | 17%  | 17%  | **50%** | 17% |

Patterns:

- **1.9x, 2.4x, 3.1x-3.6x are the "hot-streak slots."** These are mid-priced cards where RS misprices a rising player and winners pile in.
- **1.8x and 2.0x are the "cold sell-low star slots."** The big 2x cards (Wilson, Collier, Plum, Bueckers) get picked in their dip and pay off because their dip is noise on a high baseline.
- **3.8x and 5.0x are the "narrative carry slots."** Note the small samples there.
- **4.3x has 0 cold winners.** When you reach for a deep 4x+ card, it is almost always a hot rookie / call-up — never a vet in a slump.

---

## 6. Recent form vs slate top-10 hit rate

What share of the actual day's top 10 scorers fell into each pre-slate bucket?

| Bucket (r5) | Share of slate top-10 | Pool share | Hit-rate lift |
| ----------- | ---------------------: | ---------: | ------------: |
| hot         | 33.7%                  | 30.7%      | +3.0 pp       |
| normal      | 37.2%                  | 39.2%      | -2.0 pp       |
| cold        | 25.4%                  | 24.5%      | +0.9 pp       |
| unknown     | 3.7%                   | 5.6%       | -1.9 pp       |

Top-10 scorers don't lean as hard hot as winning picks do — only +3 pp. That's because the slate top is dominated by stars (B1 boost quintile) whose form barely moves the needle (corr r5 vs realized = 0.475 for the pool overall, but the *star* slice has a base correlation around 0.62 — once you're a star, you score). The hot-bucket lift inside winning lineups is more about the **2.4x-3.6x slot picks** than the 1.8x captain slot.

---

## 7. Implications for the picker

1. **Add r10 mean as a feature** alongside the season base. It's the best single predictor (corr 0.494) and is uncorrelated enough with the season prior to add information at the margin.
2. **Down-weight r3.** It's the worst of the three windows (0.453) because a single 0-pt game dominates a 3-game mean. If r3 is used, cap or winsorize.
3. **Add a "boost residual" feature.** `card_boost` reacts to season level (corr -0.80) but **not** to short-term form (corr -0.12). When `r5 > base` AND `card_boost` has not moved down in 2 slates, that is the mechanical sell-low / buy-high mispricing window. Test this as `boost - expected_boost(base)` residual.
4. **Differentiate form treatment by tier.** Within the **B1 (star) boost quintile**, cold *beats* hot (3.69 vs 3.32 pts). Within the **B5 (cheap) quintile**, hot *beats* cold (1.61 vs 1.42). A single global "fade hot" or "chase hot" rule is wrong. The interaction is the alpha.
5. **Flag rookies / new role players for momentum.** Burton, Malonga, Allemand, Hillmon, Hiedeman, Engstler all hit winning lineups while running deltas of +5 to +10. None of these are visible to the season-base feature because their baselines are stale or short. A rookie-flag * r5 interaction may capture this.
6. **The cold sell-low pattern is real but narrow.** It is concentrated in Wilson, Howard, Bonner, N. Smith — about 22% of winning picks. Don't build the whole strategy on it, but do not let the model reject them either. A "cold but career mean is high" guardrail is the right shape.

---

## 8. Caveats and follow-ups

- The +/-3.0 bucket threshold is arbitrary. The continuous `delta_r5` analysis (Section 2) is the canonical reading; the buckets are for the audience.
- 141 slates is enough to see the bias but not enough to slice by opponent, rest days, b2b, or home/away inside the form analysis. That cross is left to reports 03 (matchup), 04 (rest), and 07 (schedule context).
- The leaderboard only shows the rank-1 lineup per contest. We do not have access to all entered lineups (entry-level data) so we cannot yet say "what fraction of *all entered* lineups picked hot vs cold." The 30.7% / 39.2% / 24.5% baseline is the slate **available pool**, not the entered-lineup pool.
- Player-id bridging between the Real Sports leaderboard JSON (uses RS internal ids) and the game logs (uses the public stats-api ids) was done by `(first_initial, last_name)`. 178 of 180 corpus players resolved. The 2 unresolved are name-collision edge cases and would not materially change the aggregates.
- Real Sports may rebuild the boost daily from a private model that includes more than season-to-date; we treat boost as a black-box pricing signal and only test its *correlation* with our features, not its internal logic.

## 9. Bottom line

Winning picks lean **hot** (+12% relative over pool) but the lean is moderate, and roughly a quarter of winning picks are *cold* buys on stars whose dip is noise. Real Sports' card boost prices the season level almost perfectly and the short-term form almost not at all (corr -0.12 with delta). That gap is the picker's opening: at the **bench / B5 / 3.1x-3.6x tier, hot streaks pay**; at the **star / B1 / 1.8x-2.0x tier, cold dips on stars pay**. A momentum feature is worth adding to the picker, but only as an interaction with the boost tier and the rookie flag — not as a global "fade hot" or "chase hot" rule.
