I now have comprehensive research across all 5 angles. Let me synthesize the full report.

---

# GPP Tournament Theory for Daily Fantasy Sports: A Research Report for WNBA Oracle

## 1. The Core Economics of Top-Heavy Payout Structures

### Why GPPs Are Not Median-Optimization Problems

A Guaranteed Prize Pool tournament with top-20 payouts across an 8,000-13,000 entry field is not a game of consistency. It is a game of extreme upside capture. The mathematical argument is precise: when the payout function concentrates more than 50% of the prize pool in the top 0.1% of finishes (often a single winner in large-field DraftKings Millionaire Maker style events), the expected value of your lineup is essentially synonymous with your probability of a top-N finish, not with your probability of beating the median entry.

The PlayerProfiler research synthesis states this cleanly: "DFS tournament pay structures are similar to lottery structures with a huge lean toward the jackpot winner. Most of your expected value lies within a first place outcome you will probably not hit." (PlayerProfiler, 2024). This is not hyperbole. If a $10 contest pays $1,000,000 to first and $11 to the last cash position, the EV of your lineup is determined almost entirely by top-finish probability, not by your expected finishing percentile.

This distinction has a direct mathematical consequence for lineup construction. A player who projects at 20 fantasy points with a ceiling of 35 and a floor of 8 is more valuable in a GPP than a player who projects at 21 points with a ceiling of 25 and a floor of 17, even though the second player has higher expected output. In a top-20-out-of-9,000 structure, finishing in the 99.8th percentile requires every pick to hit near ceiling simultaneously. The player with the 35-point ceiling is the correct GPP choice precisely because he can contribute to that rare but required constellation of outcomes.

### The Score Distribution Argument

From the WNBA Oracle corpus (01_winners_anatomy.md, 141 slates), the winning bar is concrete: rank-1 score median is 55.1 points, rank-20 score is 49.2 points across a roughly 9,000-entry field. That 5.9-point spread sits between the 99.8th and 99.78th percentile of entries. To reach that band, a lineup must not merely project well -- it must hit within roughly 10% of the theoretical perfect ceiling (the corpus states that "a lineup scoring 91% of the theoretical perfect ceiling wins on most slates").

This is the ceiling problem in quantitative terms. Oracle's current lineups score 1.94 points per pick on average; winners score 3.97 per pick. The per-pick projection RMSE is 1.09 points, but multiplied across five picks with slot multipliers summing to 8.0, that produces an 18-point expected gap at the lineup level (02_loss_decomposition.md). You cannot close that gap by optimizing for median outcomes. The only path to 3.97 per pick average across winners is selecting players who have meaningful probability of producing ceiling outcomes in the 4.5-6+ range.

### Industry Consensus on Ceiling Prioritization (2024-2025)

RotoGrinders' 2024-2025 tournament strategy documentation states: "Tournaments are all about upside. If a player busts and scores low points, you chalk it up as a lost lineup. You need the guy who can give you a massive 20+ fantasy point game." (RotoGrinders, 2024). Stokastic's Boom/Bust Probability framework, their primary GPP tool as of 2025, measures player-level probability of hitting ceiling vs. floor and emphasizes ceiling probability as the primary tournament selection criterion over median projections.

The 4for4 GPP Leverage Score framework formalizes this into a three-step calculation: (1) assign each player a ceiling-hit probability based on normal distribution around mean/SD projections, (2) compute implied optimal ownership from those hit probabilities, (3) compare to actual field ownership to find leverage. The metric explicitly uses players' ceiling distributions, not median projections, as its foundational input (4for4, 2024).

---

## 2. Kelly Criterion vs. Fixed Exposure for Large-Field GPPs

### Kelly Criterion: Theory and the DFS Problem

The Kelly Criterion finds the fraction f* of bankroll that maximizes the long-run geometric growth rate:

```
f* = (W * P - L) / P
```

where W is expected win multiple, P is the payout multiple, and L is the loss probability (1 - W). For a standard 50/50 cash game with a 10% rake, this yields approximately 7-8% bankroll per slate for a player with a 56% win rate.

For large-field GPPs, the formula breaks down badly for two reasons. First, win probabilities approach zero for any single entry (1-in-9,000 entries means 0.011% win probability per lineup). Second, DFS entries are not independent: submitting the same lineup to 20 contests against overlapping fields creates correlated outcomes, violating the Kelly assumption of independent sequential bets.

The DailyfantasySports101 analysis applies Kelly to GPPs as follows: with a 10% rake on a large-field contest and an estimated player edge (skill advantage over field) that implies perhaps a 1.2x expected return on investment, the Kelly fraction resolves to approximately 1-3% of total bankroll per slate for tournament play. This aligns precisely with industry practitioner consensus: RotoGrinders' game selection expert Adam Levitan recommends allocating 0-10% of weekly bankroll to large-field classic GPPs, with the high end only if accepting negative expectation in exchange for lottery upside. The MLB DFS game selection analysis found a maximum of "2-to-3% of your overall bankroll" for GPP exposure across a slate.

### Why Fixed Small Exposure Beats Full Kelly for GPPs

The arxiv paper "On Kelly Betting: Some Limitations" (Vajda, 2017) establishes that full Kelly is too aggressive when parameter estimates are uncertain. Fractional Kelly (typically half or quarter Kelly) dominates full Kelly under realistic estimation error. For DFS, where win probabilities are nearly impossible to estimate precisely for any single large-field contest, the practical implication is: cap GPP exposure at a fixed small fraction of bankroll regardless of apparent edge.

The FantasyLabs bankroll triangulation framework translates this to DFS practice: maximum 10% of bankroll per slate total, with GPP exposure comprising no more than 10% of that (i.e., 1% per slate in large-field GPPs). The rationale is variance, not expected value. As the Wizard of Vegas forum analysis noted: DFS Millionaire Maker-style tournaments have a variance of approximately 4 million units, dwarfing casino games (video poker variance ~20, multi-strike video poker ~300). The Nassim Taleb principle applied by FantasyLabs: "robustness is progress without impatience." Small fixed exposure survives downswings that would destroy full-Kelly bankroll sizing.

### Practical Calibration for WNBA Oracle

Given the WNBA Oracle context, the contest is a single 5-player pick against an 8,000-13,000 entry field paying top 20. This is an extremely top-heavy structure. The appropriate fixed-exposure heuristic from the literature is: treat each slate as a single entry into a lottery-like structure and budget accordingly. The DFS Footballers Podcast recommends 20% of weekly budget for all GPP play for intermediate players, with large-field entries comprising only a fraction of that. For a single-slate automated system, fixed-entry sizing (one lineup per slate, no multi-entry dilution) is the correct starting constraint. Kelly scaling of entries across multiple lineups is only meaningful once win probability can be reliably estimated -- which requires field simulation infrastructure to exist first.

---

## 3. How Field Size Changes Optimal Strategy: 8,000-13,000 vs. Head-to-Head

### The Fundamental Structural Difference

Head-to-head contests require beating one opponent. The distribution of that opponent's score is roughly normal around the field median. Your optimal lineup maximizes the probability of exceeding that one score, which means maximizing your own median (floor protection). The break-even win rate in H2H with 10% rake is 55.5% (DailyfantasySports101 formula: c/(c+1) = 1.25/2.25 = 55.6%).

A 9,000-entry GPP paying top 20 requires finishing in the top 0.22% of all entries. Your opponent is no longer a single random draw from the field distribution -- you must beat approximately 8,980 simultaneous opponents. This changes the optimization target entirely.

### The Ownership-as-Currency Principle

In H2H, ownership is irrelevant. Your opponent's picks have no effect on your score. In an 8,000-entry GPP, every percentage point of ownership matters because duplicated lineups cannot both finish top 20. The dfsbuild.com analysis frames it precisely: "ownership is a currency -- if spent recklessly, your lineups look like everyone else's; if spent none, they lack projection."

At 40% ownership on a player in a 9,000-entry field, 3,600 entries contain that player. If that player hits ceiling, 3,600 entries get the same boost -- and those entries are all competing for the same 20 slots. The relative advantage of holding a 40%-owned player who hits ceiling is minimal; the entire chalky section of the field moves together. The relative advantage of holding a 2%-owned player who hits ceiling is enormous: only 180 entries contain that player, so you separate from 8,820 entries simultaneously.

Stokastic's large-field GPP analysis quantifies this: "In a 1,000-entry single-entry, duplication isn't as big of a threat. In massive GPPs, every percentage point matters. That's when you need better pivots and unique roster construction to separate yourself." The threshold for the ownership calculus to dominate shifts at roughly 5,000+ entries by industry consensus.

### Contrarian Calibration in 8,000-13,000 Entry Fields

The WNBA Oracle corpus finding (02_loss_decomposition.md) that Oracle is already "90% sub-median drafts vs winners at 60%" reveals an important nuance from the literature: there exists an optimal contrarian level that is neither zero nor maximal. The DFSbuild analysis warns explicitly against going too contrarian -- "fading all chalk, forcing artificial stacks, or sacrificing projection for uniqueness alone." The winning anatomy from 01_winners_anatomy.md confirms this: winners run one chalk anchor (mean 19.4% ownership in slot 0) paired with four leverage punts (sub-5% in slots 1-4). This is the empirical calibration for the Real Sports format: one moderate-chalk anchor anchors the projection floor; four low-owned punts provide the separation that converts a good lineup into a tournament-winning lineup.

The 4for4 historical data on Millionaire Maker winners establishes that 88% of winners contained at least one player with 25%+ ownership, and 63% contained at least one with 30%+ ownership. Chalk anchoring is not optional -- it keeps projection high enough to compete. But 94% of winning lineups had two or more players priced well below median salary, implying the contrarian punts are equally non-optional for differentiation.

### Field Size and the Required Winning Score

The RotoGrinders NBA GPP analysis produced a counterintuitive finding that validates large-field strategy: "as the size of a contest increases, the score needed to cash actually decreases." The theory is that very large fields attract more casual/recreational entries with lower expected scores, pulling the cash line downward. However, the score needed to win (top 1) or finish top-20 does increase with field size because the tail of skilled lineups also grows. The FanDuel data shows an 18-point jump in winning scores between 1,000-5,000 entry and 5,000+ entry contests. For 9,000 entries, you are competing in the zone where winning thresholds are maximally elevated relative to the cash line.

---

## 4. Target Score Calibration: Percentile Thresholds in Top-20-Pays Structures

### Mathematical Derivation of the Target

For a 9,000-entry field paying top 20 spots, the target is the 99.78th percentile of lineup scores. More practically, for a top-20-out-of-9,000 structure where the score distribution has mean M and standard deviation S, the winning threshold is approximately M + 2.85*S (99.8th percentile of a normal distribution).

The WNBA Oracle corpus provides the concrete numbers: rank-1 score is 55.1, rank-20 score is 49.2. The mean winning bar is thus 49-55 points on the Real Sports scoring system. The "91% of theoretical perfect ceiling" benchmark from the corpus means that any lineup achieving 91% of the perfect hindsight selection wins on most slates. The perfect-hindsight lineup score (by definition 100% of ceiling) averages approximately 60-61 points (55.1 / 0.91 = 60.5).

The 4for4 leverage score analysis provides the DK/FD equivalents: winning lineups average more than 5.48 points per dollar of salary on DraftKings. The DraftKings "target value" for a GPP cash threshold is 5.48 pts/$, but for the top 20 in a large field, the target is substantially higher.

### Practical Scoring Implications for Oracle

The Real Sports WNBA format uses a 5-player pick with slot multipliers [2.0, 1.8, 1.6, 1.4, 1.2] summing to 8.0. If winners average 3.97 real score per pick (from the corpus), their raw lineup output is approximately 3.97 * 8.0 = 31.8 multiplier-weighted points before the slot-specific weighting. The actual weighted score at 55.1 points implies average per-slot output weighted by multiplier is approximately 55.1 / 8.0 = 6.89 effective points per multiplier unit.

The implication for Oracle: projecting individual players at their 75th-80th percentile ceiling (not their median) and selecting for the lineup that maximizes that ceiling-weighted score is the correct targeting approach. Using median projections to construct lineups and then hoping for ceiling outcomes is the losing strategy -- the optimizer should explicitly target the ceiling distribution.

### Boost Calibration as a Proxy for Ceiling

The corpus finding that winners' median sum boost is 7.5 (vs. Oracle's 12-15) translates directly to this ceiling-targeting framework. The Real Sports boost system assigns higher multipliers to players with lower expected scores -- meaning high-boost players have lower medians and (apparently) lower ceilings. The finding that "the 2.0-2.5 boost bin is the EV sweet spot" with mean real_score of 2.28 vs. 1.44 in the 2.5-3.0 bin confirms that low-boost players (stronger projection confidence) are where ceiling-achievers actually live. A sum boost of 7.5 across 5 picks means averaging 1.5 boost per pick, clustering in the 1.2-2.0 range -- the moderate-confidence tier. Oracle's 12-15 sum boost (2.4-3.0 average per pick) means chasing exclusively speculative high-boost players who have both low medians and low ceilings.

### Target Score Summary

For the Real Sports 9,000-entry top-20-pays structure:
- Target rank: top 20 of ~9,000 (99.78th percentile)
- Target raw score (Real Sports): 49-55 points
- Implied ceiling-weighted per-pick output: approximately 3.5-4.0 real score per pick
- Required sum boost calibration: 6-8 (not 12-15)
- Required anchor ownership: one player at 15-25% ownership
- Required punt ownership: 3-4 players below 5% ownership

---

## 5. Entry Fee Structure and EV Under Rake

### Rake Mathematics

The Rotogrinders rake analysis and industry data establish a clear gradient:

| Contest Type | Typical Rake |
|---|---|
| Premium high-stakes ($100+ GPP) | 10-12% |
| Mid-stakes GPP ($25-$99) | 12-14% |
| Low-stakes GPP ($1-$10) | 14-20% |
| Large overlay events | Negative rake (positive EV) |

The FanDuel $1.6M Sunday Million (2024) collected $1,904,775 in entry fees against a $1,600,000 guaranteed prize pool -- a 16% rake. The basic EV calculation for any contest: EV = (Prize Pool / Total Entry Fees) * Expected Finish Rate. At 16% rake with no skill edge, EV is $0.84 per $1 wagered. A skilled player with measurable edge over the field (better projections, better lineup construction) can overcome this rake -- but must demonstrate at least a 16% performance advantage over the average entry to break even.

### EV Calculation for 9,000-Entry Top-20 Structure

For the Real Sports WNBA format, assuming a typical 10-15% rake on a $X entry fee with top-20 payout of $Y total:

```
Break-even win rate = rake_fraction / (payout_multiple - 1)
```

If the top-20 prize pool is distributed linearly and the contest charges a 12% rake, a player must finish top-20 approximately 12/(100-12) = 13.6% more often than random chance (1/450 = 0.22%) to break even. Expressed differently: a player producing top-20 finishes 0.25% of the time (vs. the random 0.22%) barely covers rake. The edge requirement is small in absolute terms but large in percentage terms relative to baseline probability.

### Overlay Identification

The single largest positive-EV opportunity in GPP play is overlay -- contests where total entry fees fall short of guaranteed prizes. The fantasyfootballers.org overlay analysis confirms: "an overlay is when the amount of prize money at stake exceeds total entry fees generated." This creates negative-rake situations. For Oracle, as an automated system with guaranteed entry, overlay detection (monitoring whether contest fills below guarantee) would provide free positive EV.

### The Rake Implication for Strategy

High rake reinforces the ceiling-optimization mandate. When the field's baseline win rate is 0.22% (top 20 of 9,000) and rake costs 12%, the break-even requirement means Oracle needs a win rate of approximately 0.25% -- just 14% above random baseline. This sounds modest until you recognize that Oracle's current median projected score is near the 12th percentile of actual outcomes, meaning current construction is deeply sub-baseline. Closing to a 99.78th percentile target finish rate of even 0.25% requires closing most of the 18-point projection gap identified in the loss decomposition. Rake reduction matters less than projection improvement at the current stage of Oracle's development.

---

## 6. Game Stacking: Theory and Empirical Evidence

### The Correlation Argument

Game stacking in team sports DFS means selecting multiple players from the same game. The theoretical argument is straightforward: player fantasy scores within a game are positively correlated. When a game produces high aggregate fantasy output (a shootout), players on both teams benefit from extended minutes, increased scoring opportunities, and the "bring-back" effects (the opposing team's top scorer benefits from a high-total game too). Stacking concentrates exposure on this shared variance, converting one correct "this game will go over" call into multiple fantasy points across your lineup.

The PlayerProfiler best-ball research quantifies this: teams with at least one-third correlated lineup members showed a 21.5% increase in advancement equity in the regular season and a 30.1% increase in the playoff round vs. uncorrelated builds. For DFS (single-slate), the correlation benefit is more extreme because you are targeting a single slate outcome rather than distributing across weeks.

### Stacking in Tournament Winners: The Data

The Milly Maker (NFL DraftKings flagship) 2024 data shows: double stacks appeared in 44% of top-25 lineups but only 31% of losing lineups. Single stacks or no stacks appeared in 38% of top-25 lineups but 54% of losing lineups. Stacking outperformed non-stacking in tournament winners by a statistically meaningful margin across the full-season sample.

The WNBA Oracle corpus (01_winners_anatomy.md) reports 88% of top-20 lineups contain 2+ picks from a single game, and 44% contain 3+ picks from one game. Mean distinct games per top-20 lineup is 2.4 out of typically 4-7 games on a slate. These numbers match or exceed NFL/NBA stacking rates, confirming game-correlation logic is sport-agnostic and critical for WNBA GPP success.

### The Mechanism for WNBA

In WNBA basketball, game-stacking correlates through game pace, total possessions, and game closeness (close games keep starters in longer). A high-total game implies both teams play at pace, meaning guards and wings from both squads accumulate assists, rebounds, and scoring. The optimal WNBA stack is likely one top player from each side of a projected high-total, fast-paced game -- capturing the correlation while maintaining the contrarian angle on the second team's player (who may have lower ownership than the top team's star).

The Establish The Run NBA game-stacking analysis notes that the strategy works best "on mid-sized slates containing 4-6 games." A 4-7 game WNBA slate (typical) falls squarely in this range, making game stacking reliably applicable.

### Bring-Back Mechanics

The "bring-back" concept from NFL DFS (pairing the opposing team's pass-catcher with a quarterback stack) translates to WNBA as: once you identify a high-total game and stack two players from Team A, add the top scorer from Team B. This triple correlation -- three players from one high-scoring game -- appeared in 44% of top-20 WNBA lineups per the corpus. The RotoWire stacking strategy guide recommends this as "dueling wide receivers" in DFS football; the WNBA equivalent is a scoring-dependent combo (e.g., a guard who scores big from Team A + the interior scorer from Team A + the opposing guard who feeds off the same up-tempo environment).

---

## 7. Field Simulation: Why 120 Lineups Is Catastrophically Insufficient

### What Field Simulation Actually Requires

The FantasyLabs Perfect% methodology runs thousands of simulations of the contest, in each simulation drawing random player scores from each player's projected distribution (mean + standard deviation), computing the optimal lineup for that simulation's score draw, and accumulating which players appear in optimal lineups across all simulations. After 10,000 iterations, each player has a Perfect% (probability of appearing in the optimal lineup) and a SimLeverage (Perfect% minus projected ownership).

This methodology requires a field simulation model with at least three components: (1) a realistic player score distribution (not just point estimates), (2) a realistic field lineup distribution (how the 9,000 opponent entries are distributed across the player pool), and (3) sufficient simulation iterations to stabilize the tail probabilities that govern top-20 finish rates.

At 120 simulated lineups against a real field of 8,989 entries (the WNBA Oracle current state), Oracle is modeling approximately 1.3% of the actual field. The win probability estimates derived from 120 simulations are unstable noise at this sample size. To estimate 99.78th percentile outcomes reliably requires at minimum 10,000-50,000 simulation iterations (industry standard at Stokastic and FantasyLabs per their documentation).

### Field Simulation and Ownership Modeling

The RotoGrinders ownership prediction framework emphasizes that field lineup distribution is not uniform -- it clusters around chalk players and "default optimizer" outputs. The most dangerous field entries are those produced by unsophisticated optimizers taking the highest-projected player at each position, which creates heavy concentration in a small number of player combinations. The FantasyLabs SimLeverage computation is designed to identify this: players whose optimal-lineup appearance rate (Perfect%) exceeds their field rostering rate (projected ownership) are systematically undervalued by the field.

Without a realistic field distribution model, Oracle cannot compute SimLeverage or any equivalent. The 120-lineup field simulation produces ownership estimates that have no validity against the 9,000-entry real contest.

### Minimum Field Simulation Infrastructure

The industry minimum for meaningful contest simulation is:
- 1,000 field lineups (adequate for stability of ownership estimates)
- 10,000 field lineups (adequate for top-20 win probability estimation)
- 50,000 field lineups (adequate for tail analysis, top-1 win probability)

For Oracle specifically, 1,000 simulated field lineups replacing the current 120 would produce ownership estimates accurate within approximately +/- 3% per player (Poisson noise floor). 10,000 would produce win probability estimates that are meaningful inputs for lineup selection.

---

## 8. Ownership Proxy and Live Ownership Signal

### The Ownership Signal Problem

Oracle currently uses a boost-derived proxy for ownership (using the Real Sports boost score as a proxy for how popular a player will be). The corpus notes this is the substitute for "live ownership unknown at freeze." The literature is unambiguous: boost-derived ownership proxies are a distant second-best to actual field ownership data.

The Stokastic/FantasyLabs workflow at contest-mature platforms shows projected ownership updated hourly up to 30 minutes before lock, with the final pre-lock ownership projection incorporating late news, injury scratches, and betting market movement. The DraftDime ownership model explicitly incorporates "pace, matchup, usage, minutes, and recent trends -- then compare projections against live sportsbook lines to surface picks with the highest expected edge."

For Real Sports WNBA, if confirmed-starter signal is broken (404 on RotoWire WNBA URL), the alternative sources are: WNBA official injury reports (published daily), team beat reporters on X/Twitter, and the Real Sports contest lobby itself (if Oracle can scrape pre-freeze entry counts to detect lineup clustering).

### The Ownership Compression Effect

A key finding from the research: for a 5-player pick format with no salary cap (Real Sports structure), the field ownership distribution is likely even more concentrated than standard DFS because players cannot be salary-diversified. The top 3-5 WNBA stars will be in a very high percentage of lineups regardless of boost. Oracle's contrarian angle (currently at 90% sub-median ownership, which the corpus says is too contrarian) should target the 60-75% sub-median range that actual winners achieve.

---

## 9. DvP, Pace, and Participation Prior: The Missing Features

### Defensive Versus Position (DvP) Impact

DvP (defensive rating by position allowed by each team) is the primary feature used across all major DFS platforms for contextualizing player performance projections. Stokastic and Establish The Run both publish daily DvP matchup ratings. The feature quantifies how many more or fewer fantasy points a position group scores against a given defense versus league average.

For Oracle, the corpus notes: "DvP/pace/days_rest features exist in training spec but never populated live." The impact of populating these features is not speculative -- the D63 walk-forward correlation result (0.554 vs. 0.246) was achieved with available features. Adding DvP and pace would provide additional orthogonal signal. Published research on NBA DFS (quadratichq.com, 2024) finds matchup features typically contribute 8-15% additional variance explained over usage-only models.

### Participation Prior

The WNBA Oracle corpus identifies the RotoWire confirmed-starter signal as broken (404 errors, 0 matches across 11 slates). The confirmed-starter signal is the most important participation feature in DFS projection: a player confirmed to start is qualitatively different from a player whose participation is uncertain. Without this signal, Oracle's projections treat uncertain participants the same as confirmed starters, inflating projected scores for players who may sit.

The "menu-scrape gap" identified in the corpus (some winning players never appearing in Oracle's pool) is related: if Oracle is not scraping the Real Sports player pool comprehensively and updating it close to freeze, it will miss late-confirmed starters who are often the best contrarian plays (players confirmed late have lower ownership because casual players miss the news).

---

## 10. Synthesis: The Hierarchy of Improvable Gaps

Based on the corpus data and the theoretical framework above, the improvable gaps rank as follows in expected impact on lineup quality:

1. **Projection accuracy** (94.8% of the score gap per loss decomposition): activating D63 heads in live serving, adding DvP/pace features, fixing participation prior. This is the dominant lever.

2. **Game stack logic** (87-88% of top-20 lineups use 2+ picks from one game; Oracle uses zero game-correlation logic): adding game-correlation constraints to the optimizer would immediately shift lineup distribution toward the winning archetype.

3. **Boost calibration** (winners run sum boost 7.5, Oracle runs 12-15): capping max sum boost at 8-9 would mechanically shift player selection toward the moderate-confidence tier where real EV lives.

4. **Field simulation scale** (120 lineups vs. 8,989 real): increasing to 1,000+ simulated field lineups for ownership estimation and 10,000+ for win probability estimation.

5. **Participation signal repair** (RotoWire 404, 0 matches): sourcing confirmed-starter data from WNBA official reports and beat reporters to restore the single most important pre-freeze feature.

6. **Menu-scrape completeness**: auditing the player pool scrape to ensure 100% coverage of the Real Sports contestant pool at each slate.

7. **Ownership model upgrade**: replacing boost-derived proxy with a direct logistic regression on historical Real Sports field ownership data to produce calibrated slate-level ownership estimates.

---

## Actionable Conclusions for WNBA Oracle

**1. Wire D63 heads into live job2 serving immediately (Phase 2b).** This is the highest-leverage single action in the codebase. Walk-forward correlation of 0.554 vs. 0.246 translates to roughly halving the projection gap. The loss decomposition attributes 94.8% of the score gap to projection error. All other improvements are second-order until the heads are live.

**2. Cap sum boost at 8 and add a minimum real_score projection threshold.** Winners run median sum boost 7.5. Oracle's 12-15 is a systematic error. Implement a hard constraint: sum_boost <= 8.0 for any submitted lineup, with per-pick boost <= 2.0. Additionally, exclude any player with projected real_score < 1.5 regardless of boost. These are parameter changes, not architecture changes.

**3. Implement game-stack logic in the optimizer with a minimum 2-player-from-one-game constraint.** 88% of top-20 lineups stack 2+ picks from one game; 44% stack 3+. The optimizer should require at minimum one 2-player game stack, selected from the highest-total projected game on the slate. Use game pace and game total from sportsbook lines as the stack-target selector. This is the single structural change most likely to shift lineup distribution toward the winning archetype.

**4. Scale field simulation from 120 to at minimum 5,000 lineups per slate.** Use a simple logistic regression or prior-season frequency model to generate a realistic field distribution. At 5,000 simulated entries, ownership estimates become stable enough to drive the contrarian-vs-chalk trade-off calibration. At 10,000+ simulations, win probability estimates become a meaningful lineup selection input via a SimLeverage-equivalent metric.

**5. Repair the participation prior and confirmed-starter signal.** The RotoWire 404 represents a single-source failure. Add WNBA official injury reports (rotowire.com/wnba/roto/injuries.htm uses a different URL pattern from the broken one) and X/Twitter beat-reporter scraping as fallback sources. Implement a binary participation-confirmed flag for every player in the pool, defaulting to 0 (unconfirmed) and requiring an explicit confirmation event to set to 1. Exclude unconfirmed players with projected minutes below 20 from the optimization pool.

**6. Adopt the one-anchor-four-punts ownership template explicitly.** From the corpus: winners run one chalk anchor at 15-25% field ownership (slot 0) plus four leverage punts below 5% ownership (slots 1-4). Implement this as an optimizer constraint: exactly one player with projected ownership > 12% (the anchor), and at least three players with projected ownership < 6% (the punts). This directly encodes the empirically dominant winning archetype.

**7. Populate DvP, pace, and days_rest features in live training and serving.** These features exist in the training spec but were never populated live. DvP and pace features contribute 8-15% additional variance explained in published DFS research. Adding them requires a data pipeline from basketball-reference.com or similar source, but no model architecture changes. Once populated, retrain the D63 heads with these features to capture matchup-dependent performance.

**8. Implement overlay and field-fill monitoring at contest freeze.** Track whether Real Sports contest fills below its guaranteed prize pool. Overlay creates negative-rake (positive EV) conditions where expected value per entry is above the entry fee. This requires monitoring the contest lobby entry count in the 15-30 minutes before freeze. Even if the EV improvement is modest, overlay detection is free positive EV that requires only a scraper addition to the existing job1/job2 pipeline.

---

## Sources

- [NFL DFS Tournament Strategy: GPPs Explained and How to Attack Them](https://rotogrinders.com/articles/nfl-dfs-tournament-strategy-basics-4051877)
- [Learn about Guaranteed Prize Pool (GPP) Fantasy Football Strategy](https://fantasyfootballers.org/strategy/guaranteed-prize-gpp-tournament-strategy/)
- [NFL DFS Leverage Plays & Game Theory: Large Field GPP Strategy](https://www.stokastic.com/news/nfl-dfs-leverage-plays-game-theory-large-field-gpp-strategy-ac11)
- [GPP Leverage Scores: Balancing Value with Ownership in DFS](https://www.4for4.com/gpp-leverage-scores-balancing-value-ownership-dfs)
- [What it Really Takes to Win an NBA GPP](https://rotogrinders.com/articles/what-it-really-takes-to-win-an-nba-gpp-1210935)
- [Daily Fantasy's Big Events: Rake Analysis](https://rotogrinders.com/articles/daily-fantasy-s-big-events-rake-analysis-139492)
- [Levitan's DFS Game Selection: Which Contests To Play](https://establishtherun.com/levitans-dfs-game-selection-which-contests-to-play/)
- [How and When to Game Stack in NBA DFS](https://establishtherun.com/game-stacking-in-nba-dfs/)
- [Advanced Bankroll Metrics - Daily Fantasy Sports 101](https://www.dailyfantasysports101.com/advanced-bankroll-metrics/)
- [Daily Fantasy Bankroll Management: An Overview](https://rotogrinders.com/articles/daily-fantasy-bankroll-management-an-overview-138544)
- [The Most Important DFS Lessons to Learn Playing Best Ball](https://www.playerprofiler.com/article/lessons-from-dfs-to-learn-playing-best-ball/)
- [DFS GPP Strategy: How to Build Winning Tournament Lineups](https://dfsbuild.com/dfs-gpp-strategy/)
- [DFS Strategy: Optimizing Your Lineup Through Stacking & Diversification](https://www.rotowire.com/football/article/dfs-strategy-lineup-value-stacking-diversification-96335)
- [PGA Models: FantasyLabs PGA Perfect% and SimLeverage](https://www.fantasylabs.com/articles/new-product-update-fantasylabs-pga-perfect-sim-leverage/)
- [Bankroll Building, DFS Triangulation, and Mitigating Variance](https://www.fantasylabs.com/articles/bankroll-building-dfs-triangulation-and-mitigating-variance/)
- [Introducing the Minimalist Tournament Model for NFL DFS](https://www.fantasylabs.com/articles/draftkings-fanduel-picks-fanatasy-football-nfl-dfs-introducing-minimalist-tournament-model/)
- [DFS Contest Selection: Small & Large Field Tournaments to Attack](https://www.thefantasyfootballers.com/dfs/dfs-content-selection-small-large-field-tournaments-to-attack/)
- [THE BLITZ: Highly Accurate Projections...and Here's Proof](https://rotogrinders.com/articles/the-blitz-highly-accurate-projections-and-here-s-proof-3423970)
- [The Importance of Game Selection to Maximize ROI in MLB DFS](https://rotogrinders.com/fantasy/lessons/game-selection-mlb-dfs)
- [Variance of DFS Tournaments at Wizard of Vegas](https://wizardofvegas.com/forum/gambling/sports/35135-variance-of-dfs-tournaments-such-as-draft-king-s-millionaire-maker/)
- [On Kelly Betting: Some Limitations](https://arxiv.org/pdf/1710.01787)
- [NFL DFS Strategy: My Bible for Consistent ROI](https://windailysports.com/nfl-dfs-strategy-my-bible-for-consistent-roi/)
- [QuantDFS: Free NBA DFS Lineup Optimizer with Monte Carlo + Kelly Criterion](https://quantdfs.com/)
- [DFS Lineup Optimizers, Sims, Projections, and More - DraftDime](https://draftdime.com/)
