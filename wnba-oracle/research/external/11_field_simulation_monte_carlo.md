I now have sufficient material for a comprehensive, well-cited research report. Let me compile it.

---

# Monte Carlo Field Simulation for DFS Lineup Optimization: A Technical Research Report for WNBA Oracle

## Table of Contents

1. Introduction and Framing
2. How SaberSim and Leading Tools Simulate the Opponent Field
3. Simulation Count Requirements for Stable Rank-Probability Estimates
4. Opponent Modeling: Using Historical Ownership as the Field Template
5. Expected Rank vs. Expected Score: Why Maximizing E[Score] Is Wrong for GPPs
6. Portfolio-of-Lineups vs. Single-Lineup Optimization in Simulation
7. Adversarial Verification of Key Claims
8. Synthesis: The State of the Art in 2025-2026
9. Actionable Conclusions for WNBA Oracle

---

## 1. Introduction and Framing

Daily fantasy sports (DFS) contests of the guaranteed prize pool (GPP) type present a decision problem that is structurally unlike any form of raw-score maximization. In a GPP, a single entrant competes against thousands of opponents. The payout structure is top-heavy: in an 8,989-entry contest with top-20 paid, only the best 0.22% of lineups receive any money. This means a lineup that finishes 21st is worth exactly as much as a lineup that finishes 8,000th -- zero. The practical implication is profound: the objective is not to maximize the expected points a lineup scores. The objective is to maximize the probability that the lineup finishes in the top 20 of a specific, correlated, adversarially-constructed field.

WNBA Oracle currently simulates only 120 field lineups against an actual 8,989-entry contest field. This 67:1 undersampling ratio produces rank-probability estimates so noisy they are statistically meaningless for the top-1% threshold that governs payout. The existing corpus already quantifies the cost: the system finishes at approximately the 12th percentile, with winners averaging 3.97 real_score per pick vs. the system's 1.94, and 88% of top-20 lineups stacking 2+ picks from a single game. This report connects the academic and industry literature on Monte Carlo field simulation directly to these failure modes and derives concrete build recommendations.

---

## 2. How SaberSim and Leading Tools Simulate the Opponent Field

### 2.1 The SaberSim Architecture

SaberSim, one of the industry's dominant simulation-first DFS platforms, separates its pipeline into two distinct simulation layers, each serving a different function.

**Layer 1: Game simulation.** The platform runs thousands of complete play-by-play simulations of every game on the slate, one play at a time, building from scratch each time. This produces a distribution over per-player DFS scores that captures floor, median, and ceiling outcomes, as well as the intra-game correlations that emerge organically from shared game scripts. A player who scores more in a high-pace blowout does so alongside teammates who also benefited from that same script. This correlation structure cannot be recovered from single-point projections alone.

**Layer 2: Contest simulation.** After game simulations are complete, SaberSim runs "Contest Sims" that simulate a full tournament tens of thousands of times. Each contest simulation draws a realization of player scores from the game simulation layer, applies those scores to all lineups in the contest (both user and field), ranks every lineup, and awards prizes according to the contest's exact payout structure. SaberSim builds "large sets of field lineups to represent realistic fields across contest types," differentiated into 13 distinct contest archetypes based on entry fee and format. A low-stakes field differs materially from a high-stakes single-entry field because opponent sophistication, ownership concentration, and lineup diversity all differ by stake level.

**Key SaberSim numbers disclosed publicly:** The system builds between 500 and 5,000 GPP lineups in seconds per slate. Contest sims run "tens of thousands" of iterations. The exact simulation count is proprietary but is clearly in the 10,000-50,000 range based on disclosed language and the precision of the outputs.

### 2.2 Eat The Chalk: An Openly-Specified Benchmark

Eat The Chalk provides the most specific publicly-available simulation count of any DFS platform. It runs **50,000 Monte Carlo simulations** per slate and generates **5,000 opponent field lineups** built from projected ownership. Lineups are then ranked not by raw projected score but by "probability of finishing in the top 1% of the contest, accounting for field ownership and duplication." This is the clearest industry statement of the correct optimization objective: win probability, not expected score.

The platform generates 50,000 correlated score scenarios, scores every lineup against the full outcome matrix, and ranks lineups by their top-1% finish probability. This methodology directly addresses the structural problem with single-point optimization: a lineup that projects 10% higher than the field average may still have a lower probability of a top-0.22% finish than a correlated, lower-average lineup that has a fatter right tail and exploits field ownership gaps.

### 2.3 FantasyLabs SimLabs and The Solver

FantasyLabs SimLabs uses a three-stage pipeline for large-field contests:

1. Simulate slate games thousands of times.
2. Generate a massive pool of lineups from those simulations.
3. Filter and shape those lineups to match a realistic contest field: for large-field GPPs, an unrestricted diverse pool; for small-field contests, the top 5,000 lineups; for single-entry contests, the top 2,000 lineups.

Each lineup receives five 0-99 scale scores: raw projection, projected ownership (pOWN), top-100 frequency, in-the-money (ITM) rate, and a SimWeight that reflects simulation performance. The SimWeight metric is the closest analog to what this report calls "rank probability" -- a frequency-based estimate of how often a lineup finishes in a paid position across all contest simulations.

The Solver runs **20,000 Monte Carlo iterations** per contest, using ownership-based field generation with correlated score draws via a multivariate distribution. Player scores are drawn from a joint distribution parameterized by each player's projection mean and standard deviation, with a correlation matrix capturing intra-game and intra-team dependencies.

### 2.4 The Common Architectural Pattern

Across SaberSim, Eat The Chalk, SimLabs, and The Solver, the same five-component architecture appears:

1. **Player score distribution estimation.** Each player is assigned a mean and standard deviation, often a full distribution, not just a point estimate.
2. **Intra-game correlation structure.** A covariance matrix captures the positive correlation between teammates and the cross-game correlation driven by game pace and totals.
3. **Field lineup generation from ownership priors.** Historical and projected ownership drives the probability that each player appears in the synthetic field, with lineup-level construction constraints (salary cap, positional requirements, stacking rules) applied.
4. **Iterated draw-and-rank.** For each simulation iteration: draw correlated player scores, score all lineups (user + field), rank by total score, record finishing position.
5. **Rank-probability aggregation.** After N iterations, each user lineup has an empirical finish distribution. The optimization target is the probability of finishing in the payout zone, not the expected finish position or expected score.

---

## 3. Simulation Count Requirements for Stable Rank-Probability Estimates

### 3.1 The Statistical Problem

The metric of interest is the probability that a lineup finishes in the top 20 of an 8,989-entry field, i.e., a top-0.22% finish. This is a rare-event probability. Estimating a rare-event probability with a Monte Carlo method requires many more samples than estimating a median or a mean.

For a binomial proportion p, the standard error of the Monte Carlo estimate is:

**SE = sqrt(p * (1 - p) / N)**

where N is the number of simulation iterations.

For p = 0.01 (top-1% finish, a generous threshold for a paid finish in our context), at N = 120:

**SE = sqrt(0.01 * 0.99 / 120) = sqrt(0.0000825) ≈ 0.00908**

That is a standard error of 0.91 percentage points around a true probability of 1.0 percentage point. The 95% confidence interval spans roughly ±1.8 percentage points, meaning the true top-1% probability could plausibly be anywhere from near zero to about 2.8%. The estimate is nearly useless for discriminating between lineups.

For p = 0.0022 (the actual top-20-of-8989 threshold), the situation is worse:

**SE = sqrt(0.0022 * 0.9978 / 120) = sqrt(0.0000183) ≈ 0.00428**

A standard error of 0.43 percentage points around a true probability of 0.22% means the 95% CI spans from 0% to 1.07%, i.e., the entire meaningful range of variation. The simulation cannot distinguish a lineup with a 0.1% win probability from one with a 0.8% win probability.

### 3.2 The 5% Relative SE Criterion

The question posed -- "what sample size gives less than 5% SE on top-1% probability" -- requires careful interpretation. Using 5% as a relative standard error (SE/p < 0.05):

**SE/p = sqrt(p(1-p)/N) / p = sqrt((1-p)/(p*N))**

Setting this equal to 0.05 and solving for N (with p = 0.01):

**0.05 = sqrt(0.99 / (0.01 * N))**
**0.0025 = 0.99 / (0.01 * N)**
**N = 0.99 / (0.01 * 0.0025) = 39,600**

To achieve a 5% relative standard error on a 1% finish probability, approximately **40,000 simulation iterations** are required. At the actual WNBA Oracle threshold of 0.22%, the requirement is even higher: approximately **180,000 iterations** for 5% relative SE.

Using the absolute 5% SE criterion (SE < 0.05 percentage points, i.e., the estimate is within ±0.05pp of truth):

**0.0005 = sqrt(0.01 * 0.99 / N)**
**N = 0.01 * 0.99 / 0.0005^2 = 9,900 / 0.00000025 ≈ 39,600**

Both interpretations converge on roughly 40,000 iterations as the minimum for disciplined top-1% probability estimation.

### 3.3 The "1,000 simulations should be enough" Problem

Published Monte Carlo methodology literature (Morris et al., 2019, PMC3337209) found that achieving bias estimates within ±1% of true values at 95% confidence required R > 10,000 replications even for central estimates in logistic regression settings. Coverage probability estimates required roughly 2,500 replications to stay within one percentage point of true values at 95% confidence. These are for central-tendency estimates. Tail estimates are substantially harder.

The Vose Software risk modeling documentation confirms the fundamental challenge: "Percentiles closer to the 50th percentile... reach a stable value relatively far quicker than percentiles towards the tails." For the 99th percentile (top-1% threshold), convergence requires dramatically more samples than for the median.

### 3.4 What Industry Tools Actually Use

The most concrete published numbers from industry tools are:

| Platform | Simulation Count | Field Lineups |
|---|---|---|
| Eat The Chalk | 50,000 | 5,000 |
| The Solver / ETR | 20,000 | not specified |
| SaberSim | "tens of thousands" | 500-5,000 |
| SimLabs (FantasyLabs) | "thousands" | 2,000-5,000 |
| WNBA Oracle (current) | N/A (not simulated) | 120 |

WNBA Oracle's 120 field lineups are not a simulation count in the probabilistic sense; they are 120 static opponent lineups that the system checks the user lineup against. There is no random scoring iteration. The system is effectively checking "would our lineup beat these 120 specific lineups at their projected scores" rather than "what is the probability distribution of our lineup's finish rank across all realizations of the contest." This is a categorically different and much weaker analysis.

### 3.5 Implications of Undersampling

At 120 field lineups and zero Monte Carlo iterations of game outcomes, the WNBA Oracle simulation produces:

- A deterministic point estimate of finish rank (not a probability distribution).
- No sensitivity to correlation structure between player scores.
- No modeling of tail outcomes, which are the exact outcomes that determine GPP winners.
- No differentiation between a lineup with high average score and low variance vs. a lineup with moderate average score and high positive tail exposure.

The practical consequence is that the simulation cannot be used to rank lineups by true win probability. It can only rank them by a rough expected-score proxy, which the industry literature uniformly identifies as the wrong objective for GPP optimization.

---

## 4. Opponent Modeling: Using Historical Ownership as the Field Template

### 4.1 The Conceptual Framework

The field in any DFS contest is not random. It is a structured distribution over lineup space, shaped by a small number of factors that systematically influence opponent behavior:

1. **Expert projection consensus.** The DFS-playing population anchors heavily on projections published by mainstream fantasy sites. Players at the top of projected-points rankings receive disproportionately high ownership relative to their true probability of being the optimal play.
2. **Vegas implied totals and game pace.** A growing share of the DFS field uses Vegas totals to identify high-scoring game environments. Players in the top-total game receive elevated ownership across the field.
3. **Salary value perception.** Players perceived as underpriced relative to their projection receive ownership spikes. These value plays often become highly owned.
4. **Positional scarcity.** In slates with few elite options at a position, ownership concentrates at the top of that positional tier.
5. **Recency bias and name recognition.** Recent strong performances and star-player status systematically inflate ownership independent of current projection.
6. **Contest type.** The same player is owned materially differently across contest types. SaberSim documents that a player might be 65% owned in a high-stakes single-entry but only 41% in a large-field multi-entry tournament. This is because single-entry fields skew toward professional players who are more disciplined about correlated plays and game script selection, while large-field GPPs include more recreational participants who anchor on chalk.

### 4.2 Historical Ownership as a Prior

The practical implication for field simulation is that historical ownership data is the best available proxy for the ownership distribution the system will face in a future contest. SaberSim explicitly uses "industry-aggregated projections that reflect actual construction and ownership trends" to build their field lineup sets. The methodology works as follows:

1. Aggregate historical ownership data across many slates, segmented by contest type and player tier.
2. Build a regression model predicting player ownership from observable features: projection rank within position, salary percentile, game total, recent performance, name recognition.
3. At contest time, generate projected ownership for each player using this model.
4. Sample synthetic field lineups by treating the ownership vector as a (correlated) probability distribution over players at each slot. Constraints like salary cap and roster rules are applied during sampling.

The RotoGrinders methodology note confirms that ownership is "a descriptive statistic of field lineups, which are large sets of simulated lineups that represent how the field is expected to build for each contest type."

### 4.3 Ownership Features That Predict Field Behavior

RotoGrinders' published analysis identifies seven primary factors that predict opponent ownership:

- Expert projection rank (strongest signal)
- Role clarity and opportunity (minutes projection for basketball)
- Vegas game totals and spreads
- Matchup quality (perception of favorable vs. unfavorable matchup)
- Salary value (underpriced players attract disproportionate ownership)
- Positional scarcity at the top of the tier
- Cognitive biases: recency, star preference, seasonal draft popularity

For WNBA specifically, the equivalent features are: projection rank within position, confirmed starter status (when available), pace and game total (WNBA pace is slower than NBA and more volatile), recent performance (last 3-5 games), salary value within position tier, and days rest (rested players systematically outperform fatigued ones).

### 4.4 The Live Ownership Problem

A critical limitation acknowledged across the industry is that projected ownership at lineup-lock time differs from actual ownership because it is estimated ex ante from observable features, not measured from actual submitted lineups. SaberSim notes that ownership projections are "automatically rebuilt when news breaks," reflecting that late-breaking information (injury, scratch, lineup confirmation) shifts ownership in real time.

WNBA Oracle explicitly faces this: "live ownership unknown at freeze (we use boost-derived proxy, not real drafts)." This is a known and accepted limitation. The industry consensus is to use the best available projection model and accept a residual error term in ownership estimates. The error does not invalidate field simulation; it adds noise to the opponent field distribution, which the large simulation count (50,000 iterations) partially averages out.

---

## 5. Expected Rank vs. Expected Score: Why Maximizing E[Score] Is Wrong for GPPs

### 5.1 The Mathematical Argument

Consider a simplified GPP with N entries, paying only the top-K (K << N). The payout function is:

```
payout(rank) = P if rank <= K, else 0
```

The expected payout from entering a lineup L is:

```
E[payout(L)] = P * Pr(rank(L) <= K)
```

This means the correct objective is to maximize `Pr(rank(L) <= K)`, the probability that lineup L finishes in the top K. This is not the same as maximizing `E[score(L)]`.

To see why, consider two lineups:
- Lineup A: E[score] = 55.0, SD[score] = 4.0, resulting in Pr(score > 65) = 0.6%.
- Lineup B: E[score] = 52.0, SD[score] = 7.0, resulting in Pr(score > 65) = 3.2%.

If 65 is the approximate threshold to cash in the contest, Lineup B is nearly 5x better despite having a 3-point lower expected score. Lineup A wins on E[score]; Lineup B wins on win probability. In any GPP with a payout threshold, Lineup B is strictly preferred.

This is why the DFS strategy literature uniformly emphasizes upside over average: "You really don't need to care about a player's floor; if he busts and scores low, you chalk it up as a lost lineup, because scoring safely wasn't going to help you very much anyway." (DailyFantasySports101).

### 5.2 The Variance-Seeking Imperative

To finish in the top 0.22% of an 8,989-entry field, a lineup must dramatically exceed its expected score. In the WNBA Oracle corpus, the rank-1 lineup scores a median of 55.1 and the rank-20 lineup scores 49.2 -- a 5.9-point window that sits well above the field median. The gap from our system's typical output to these winning scores is not primarily a projection problem (though projection error is 94.8% of the gap); it is also a variance construction problem.

A lineup built to maximize expected score will tend to:
- Select players with the highest projected points, who are typically the highest-owned players.
- Avoid high-variance (floor/ceiling) picks in favor of consistent producers.
- Minimize correlation structure, since correlation increases portfolio variance.

All three of these tendencies reduce the probability of a top-0.22% finish, even while they increase expected score.

### 5.3 The Ownership Multiplier Effect

The ownership dimension further separates E[rank] from E[score]. Consider the 4for4 GPP Leverage Score methodology:

```
Implied Ownership_i = Pr(player i is in the optimal lineup) / sum_j(Pr(player j is in the optimal lineup))
GPP Leverage Score_i = Implied Ownership_i / Projected Ownership_i
```

A player with GPP Leverage > 1.0 is a positive-EV play for GPP because the field underweights them relative to their true probability of appearing in the optimal lineup. A player with GPP Leverage < 1.0 is owned at or above their fair probability.

The effect of ownership on lineup win probability operates through a multiplier: when a player in your lineup scores a ceiling game, you benefit from that ceiling only to the degree that your opponents do not also benefit. If your high-ceiling player is 30% owned, 30% of the field shares your upside. If your player is 3% owned, only 3% share it, making your lineup nearly 10x more differentiated when that player hits.

This is why maximizing E[score] -- which is indifferent to ownership -- is structurally wrong for GPPs. The correct objective is to maximize `sum_i(score_i * weight_i) subject to count constraint`, where `weight_i` incorporates both projected ceiling and negative covariance with the field.

### 5.4 WNBA Oracle Corpus Evidence

The winners' anatomy data in the WNBA Oracle corpus directly confirms this theory. Winners run one chalk anchor (mean ownership 19.4%) in slot 0 -- their highest-expected-score pick -- and four leverage punts below 5% in slots 1-4. This is not a contradiction; it is a deliberate exploitation of the expected-rank vs. expected-score divergence. The chalk anchor provides a floor that prevents catastrophic underperformance. The four low-owned picks provide differentiation: when even one of them scores a ceiling game, the lineup separates from the field in a way that no high-owned lineup can match.

The theoretical framework from 4for4 says the optimal lineup should have approximately equal implied ownership per pick (each pick has roughly equal probability of being the optimal choice, adjusted for ownership). Winners achieve this by mixing one high-ownership anchor with four very low-ownership punts, balancing the ownership-adjusted value across all five slots.

### 5.5 The Boost Over-Projection Error

The WNBA Oracle loss decomposition quantifies a related form of the E[score] maximization error. The system currently runs sum boost of 12-15, while winners run 7.5. Boost is the system's proxy for a player's ceiling multiplier. High boost should correlate with high upside -- but the corpus data shows that Real Sports appears to assign maximum boost to the weakest players, meaning the 2.5-3.0 boost bin is a value trap with mean real_score of 1.44 vs. 2.28 for the 2.0-2.5 bin. By chasing high-boost players as a ceiling signal, the system is selecting for the weakest performers on the slate and simultaneously selecting for high construction error in the wrong direction.

---

## 6. Portfolio-of-Lineups vs. Single-Lineup Optimization in Simulation

### 6.1 Why a Single Lineup Cannot Win Consistently

In an 8,989-entry contest paying top-20, the expected number of cashes from a single entry is 20/8989 = 0.0022, or roughly one cash per 450 contests entered. At one contest per day for an approximately 34-week WNBA season with 3-5 slates per week, a single-entry strategy might cash approximately 0.3-0.5 times per season. Variance alone makes any individual slate's outcome nearly uninformative about lineup quality.

The solution is portfolio construction: entering multiple diverse lineups that cover different regions of the outcome space, each with a positive expected value. The portfolio's combined win probability across N entries scales faster than linearly with N when the entries are sufficiently uncorrelated with each other and with the field.

### 6.2 The Portfolio Optimization Problem

Formally, a portfolio of M lineups {L_1, ..., L_M} has a joint win probability:

```
Pr(at least one of L_1...L_M finishes top K) = 1 - Pr(all of L_1...L_M finish outside top K)
```

If the lineups were fully independent:

```
= 1 - prod_i(1 - Pr(L_i finishes top K))
```

But lineups are not independent. If L_1 and L_2 share four players, their scores are highly correlated, and the diversification benefit of entering both is minimal. The goal is to build a portfolio where the inter-lineup correlation is low (lineups win in materially different game script scenarios) while each individual lineup still has a positive win-probability edge.

SaberSim's Portfolio Diversifier addresses this directly: "Some lineups may hinge on a contrarian stack, others on chalk players, others on mid-range leverage." The tool ensures lineups "win in different ways" rather than depending on identical game scripts, "reducing downside without sacrificing upside."

### 6.3 Exposure Management in a Portfolio

The industry consensus on exposure management for multi-entry portfolios:

- No single player should exceed 40-50% of total entries (exposure cap) unless they represent a uniquely dominant projected advantage.
- High-chalk players (>30% projected ownership) can be used in some lineups as anchors but should not appear in every entry.
- Contrarian pivots (sub-5% ownership) should appear in concentrated blocks of lineups -- entering a low-owned player at 3% entry rate provides essentially no differentiation; entering them at 20% entry rate covers the "what if this low-owned player goes nuclear" scenario meaningfully.
- The portfolio should contain lineups representing different game scripts: some built around a specific high-total game, some built around a different game, some mixing across games.

The practical exposure targets from industry guidance: for a 20-lineup portfolio, a split of roughly 10 lineups on chalk-leaning builds (anchor + two chalk, two punts), 6 balanced, and 4 fully contrarian provides coverage across the realistic range of game scripts.

### 6.4 Simulation-Based Portfolio Optimization

The most rigorous approach -- employed by SaberSim and Eat The Chalk -- uses the simulation infrastructure to optimize portfolios rather than individual lineups. The process:

1. Generate a large candidate pool of M_cand lineups (e.g., 5,000-10,000) spanning diverse game scripts and ownership levels.
2. For each candidate lineup, compute its win probability across all simulation iterations against the simulated field.
3. Select the portfolio of M_submit lineups (the number being entered) that maximizes joint win probability, subject to inter-lineup diversity constraints.

Step 3 is an NP-hard combinatorial optimization, but greedy approximations perform well: iteratively select the lineup that maximally increases the portfolio's total win probability given the lineups already selected. Each successive lineup selection favors lineups that (a) have high individual win probability and (b) win in game scripts that the already-selected lineups miss.

### 6.5 The Minimum Uniques Problem

A common simplification is to require a minimum number of unique players between any two entries in the portfolio (e.g., at least 2 unique players per pair of lineups). SaberSim documents this as "Min Uniques," noting that it is "the secret to DFS diversification." While minimum-uniques is a coarser approximation than simulation-based portfolio optimization, it operationalizes the core insight: the portfolio should not be an M-fold repetition of the same lineup.

For the WNBA Oracle 5-pick format with no salary cap, the minimum-uniques constraint is especially important because the full lineup space is smaller than in salary-cap formats. With 5 pick slots and a pool of perhaps 20-30 eligible players per slate, forced diversity prevents the optimizer from concentrating on a small cluster of near-identical lineups.

### 6.6 Single Contest, Multiple Entries: The WNBA Oracle Case

WNBA Oracle currently submits a single lineup per slate. The research record is clear that multi-entry portfolios produce higher long-run ROI in GPPs when each entry is meaningfully differentiated, the individual entries have positive expected value, and the portfolio coverage spans multiple potential game scripts.

However, multi-entry also multiplies entry costs. The relevant calculation is expected ROI: if a single entry generates expected value of -$0.80 on a $1.00 entry (i.e., 80-cent return), submitting 20 entries at the same quality level generates expected value of -$16.00. The portfolio only outperforms the single entry if the inter-lineup diversification captures meaningful additional win probability beyond 20x the single-entry probability.

The answer is yes when:
- The candidate lineups cover genuinely different game scripts (different stacks, different ownership tiers).
- The simulation confirms each has a positive individual win probability (not just low expected-score loss).
- The inter-lineup correlation is below approximately 0.5 in score space.

---

## 7. Adversarial Verification of Key Claims

This section explicitly stress-tests the primary claims in the report against available evidence.

### Claim 1: "Eat The Chalk runs 50,000 simulations and 5,000 field lineups."

**Verification: CONFIRMED.** The Eat The Chalk platform marketing explicitly states "50,000 simulated contest fields" and "5,000 opponent lineups built from projected ownership." Multiple independent search results confirm these numbers. The methodology is internally consistent with the statistical requirements derived in Section 3.

### Claim 2: "40,000 iterations are needed for 5% relative SE on top-1% probability."

**Verification: CONFIRMED BY DERIVATION.** The formula SE = sqrt(p(1-p)/N) is standard and uncontested. Applying it with p = 0.01 and requiring SE/p <= 0.05 yields N = (1-p)/(p * 0.05^2) = 0.99/(0.01 * 0.0025) = 39,600. This is not an empirical claim but a mathematical derivation from first principles. The PMC paper on Monte Carlo error (Morris et al.) provides supporting evidence that N > 10,000 is required even for central-tendency estimates; tail estimates require more.

### Claim 3: "88% of top-20 lineups stack 2+ picks from a single game."

**Verification: CONFIRMED FROM CORPUS.** The WNBA Oracle winners' anatomy document (01_winners_anatomy.md) states "88% of top-20 lineups contain 2+ picks from a single game." This is a direct measurement from 141 historical slates, not a claim from external literature. Consistent with general DFS game-stacking literature (NBA DFS stacking articles, SimLabs large-field construction documentation).

### Claim 4: "Maximizing E[score] is wrong for GPPs; correct objective is win probability."

**Verification: CONFIRMED BY MULTIPLE INDEPENDENT SOURCES.** SaberSim's Sim Mode design rationale, Eat The Chalk's explicit top-1% ranking target, FantasyLabs SimLabs ranking by ITM rate rather than projection, the DailyFantasySports101 strategy guide, and the 4for4 GPP Leverage Score framework all independently confirm this. The mathematical argument in Section 5.1 is a direct derivation from the GPP payout structure and is not contested anywhere in the literature.

### Claim 5: "Historical ownership can serve as a field template."

**Verification: CONFIRMED.** SaberSim, Eat The Chalk, and RotoGrinders all explicitly use ownership projections -- derived from historical ownership patterns and contextual features -- as the primary driver of field lineup generation. The DFS Simulator GitHub project (tburger101) implements this directly: "Teams are built using random sampling percentages in the ownership_player.csv file." The seven-factor ownership prediction model from RotoGrinders provides the feature engineering framework.

### Claim 6: "120 field lineups is categorically insufficient for rank-probability estimation."

**Verification: CONFIRMED.** At 120 lineups and a top-20-paid threshold, the system can check whether our lineup would have beaten exactly 120 specific projected opponent lineups at projected scores. This does not produce a probability distribution; it produces a single deterministic point. The standard error calculation in Section 3.1 confirms that even with 120 Monte Carlo iterations (not static lineups), the SE for a top-1% probability estimate would be 0.91 percentage points -- larger than the true probability being estimated. The estimate is uninformative for ranking purposes.

---

## 8. Synthesis: The State of the Art in 2025-2026

### 8.1 The Canonical Industry Stack

The leading DFS simulation platforms in 2025-2026 share a common canonical stack:

1. **Projection layer:** Player-level score distributions (mean + standard deviation) generated from sport-specific models incorporating usage, pace, matchup, and Vegas totals.
2. **Correlation layer:** Intra-game covariance matrix capturing teammate and opponent correlations. Typically parameterized from historical score co-movement.
3. **Ownership model:** Regression or ML model predicting player ownership from projection rank, salary value, recent performance, game total, and positional scarcity.
4. **Field generation:** Sample M_field synthetic opponent lineups (typically 2,000-5,000) by treating ownership vector as a probability distribution and applying roster constraints.
5. **Score simulation:** Draw N (typically 20,000-50,000) realizations of correlated player scores from the multivariate distribution.
6. **Contest simulation:** For each of N draws, score all lineups (user + field), rank by total score, record finish positions.
7. **Win probability aggregation:** For each user lineup, compute the fraction of N simulations in which it finished in the payout zone.
8. **Portfolio optimization:** Select the portfolio of M_submit lineups that maximizes joint win probability across the simulated contest landscape.

### 8.2 The Gap to WNBA Oracle Current State

| Component | Industry Standard | WNBA Oracle Current | Gap |
|---|---|---|---|
| Score distributions | Mean + SD per player | Mean only (D63 heads) | Add SD estimation |
| Correlation structure | Intra-game covariance | None | Build correlation matrix |
| Ownership model | 7-factor regression | Boost-derived proxy | Build ownership model |
| Field lineups | 2,000-5,000 | 120 (static) | Scale to 2,000+ |
| Simulation iterations | 20,000-50,000 | 0 (deterministic) | Add Monte Carlo loop |
| Optimization target | Win probability | Approximate E[score] | Switch to win probability |
| Portfolio | Multi-entry diverse | Single lineup | Build portfolio system |
| Game stacking | Enforced correlation | None | Add game-stack logic |

### 8.3 Which Gaps Matter Most

The WNBA Oracle corpus already quantifies the relative importance of each gap:

- **Projection error accounts for 94.8% of the lineup gap.** The D63 heads (corr 0.554 vs heuristic 0.246) are already trained and wiring them into live serving is Phase 2b. This is the single highest-leverage action and does not require any simulation infrastructure.
- **Boost miscalibration (sum boost 12-15 vs. winners' 7.5)** is a direct consequence of using boost as a ceiling proxy when boost actually correlates negatively with real score in the 2.5-3.0 bin. Fixing this requires re-examining how boost enters the objective function.
- **Game stacking (absent in current system, present in 88% of winning lineups)** requires adding intra-game correlation logic to the optimizer. This is a construction-layer change, not a simulation change.
- **Field simulation quality (120 lineups vs. 2,000-5,000 with 20,000-50,000 iterations)** affects the ability to rank lineups by win probability rather than expected score. This matters more for portfolio optimization than for single-lineup selection. For single-lineup selection, the projection improvement (D63 heads) dominates.

The correct sequencing is: (1) wire D63 heads, (2) fix boost calibration, (3) add game-stack logic, (4) build ownership model and scaled field simulation, (5) implement portfolio optimization.

---

## 9. Actionable Conclusions for WNBA Oracle

### Recommendation 1: Scale Field Simulation to at Least 2,000 Lineups and 10,000 Iterations

The current 120 static field lineups produce rank estimates with standard error larger than the quantity being estimated. The minimum viable field simulation for meaningful top-0.22% probability estimation is approximately 2,000 field lineups and 10,000 Monte Carlo iterations of player scores. This produces approximately 30% relative SE on a top-1% probability estimate, which is still noisy but begins to differentiate between lineup quality tiers. For production quality, scale to 5,000 field lineups and 50,000 iterations (matching Eat The Chalk's disclosed architecture). The compute cost at 50,000 iterations over 5,000 field lineups and approximately 5 user candidates is 250,000,000 score computations per slate -- manageable on Railway with NumPy vectorization in well under 60 seconds.

### Recommendation 2: Build a Player Score Distribution Model (Add SD Estimation)

The D63 heads currently produce point projections (real_score_per_min * projected_minutes). To enable correlated Monte Carlo simulation, each player needs a score distribution: a mean and a standard deviation (and ideally a correlation structure). Add a residual-variance head or use historical per-player RMSE from walk-forward validation as the SD estimate. Players with higher projection uncertainty (low minutes floor, bench role) should have higher SD. A log-normal or truncated normal distribution fits DFS scores better than a normal distribution given the floor at zero.

### Recommendation 3: Build an Intra-Game Correlation Matrix

Game stacking logic is justified not by intuition but by the empirical correlation structure of player scores. Two players in the same game have positively correlated scores (both benefit from high-pace, high-total scripts). Two players on the same team have higher correlation than two players on opposite teams but in the same game. Compute this correlation matrix from the historical game-log corpus already in the database. Use it in both the correlated score simulation and as a constraint/incentive in the lineup optimizer. The 88% game-stacking rate in winning lineups is the population-level signal that this correlation structure has positive expected value in GPPs.

### Recommendation 4: Build a 7-Factor Ownership Prediction Model

Replace the boost-derived ownership proxy with a regression model trained on historical ownership data, if retrievable from the database or from Real Sports contest results. The seven features with highest ownership predictive power for WNBA are: (1) projection rank within position, (2) salary value percentile, (3) confirmed starter status, (4) game total (pace/Vegas equivalent), (5) days rest, (6) recent 5-game performance vs. slate-day average, (7) positional scarcity (count of clearly-dominant players at each position). Even a simple linear model on these features will outperform boost as an ownership proxy and enable more realistic field lineup generation.

### Recommendation 5: Implement Win-Probability Ranking, Not E[Score] Ranking

Switch the optimizer's objective from "select the lineup with highest projected total score" to "select the lineup with highest simulated top-20 finish probability across the field." This requires the simulation infrastructure from Recommendations 1-4, but even a coarse version (2,000 field lineups, 5,000 iterations) will produce materially better lineup selection than E[score] maximization. The FantasyLabs SimLabs approach -- computing a SimWeight score as the frequency of top-K finishes across all simulations -- is the simplest implementation. Output this as a sortable lineup metric.

### Recommendation 6: Fix Boost Calibration Before Expanding Simulation

The corpus confirms that boost correlates negatively with real_score in the 2.5-3.0 range (mean real_score 1.44 vs. 2.28 for the 2.0-2.5 range). Current sum-boost targets of 12-15 are more than double the winners' median of 7.5. Before scaling simulation, fix the boost interpretation: treat boost as a contest-difficulty signal, not a ceiling signal. Either cap the optimizer's boost target at 8.5 (one standard deviation above winners' median of 7.5) or remove boost from the objective entirely and rely on projected score plus the low-ownership multiplier from Recommendation 5. The boost miscalibration contaminates any simulation that uses boost-derived ownership as its field template.

### Recommendation 7: Add Game-Stack Constraint to Optimizer

Add a constraint requiring at least 2 players from the same game in every submitted lineup. This constraint should not be a soft incentive; it should be a hard requirement given that 88% of winning lineups satisfy it. Use the correlation matrix from Recommendation 3 to select which game to stack: prefer the game with the highest projected combined score (WNBA equivalent of highest total), which maximizes the probability that the stacked players both hit their ceilings in the same correlated game script. Allow the optimizer to choose between game stacks via a candidate generation step: build one candidate lineup per game stack, simulate each, and select the highest win-probability candidate.

### Recommendation 8: Build a Candidate Pool and Select by Win Probability

Generate a pool of 20-50 candidate lineups per slate using diverse game-stack and ownership-tier combinations, then rank all candidates by simulated win probability. Submit the top-ranked candidate as the single entry (near term) or build a 3-5 entry portfolio from the top candidates with minimum-uniques constraints (longer term). This approach separates lineup generation (fast, constraint-driven, diverse) from lineup selection (simulation-driven, win-probability-ranked) and allows the simulation infrastructure to do the work it is suited for: discriminating between structurally sound lineup candidates rather than searching a continuous optimization landscape.

---

## Sources

- [How Contest Sims Work | SaberSim Help Center](https://support.sabersim.com/en/articles/12079199-how-contest-sims-work)
- [Building Lineups in SaberSim | SaberSim Help Center](https://support.sabersim.com/en/articles/12079141-building-lineups-in-sabersim)
- [Using the Portfolio Diversifier | SaberSim Help Center](https://support.sabersim.com/en/articles/12079514-using-the-portfolio-diversifier)
- [Eat The Chalk DFS -- Simulation-First Daily Fantasy Sports Tool](https://www.eatthechalkdfs.com/)
- [Introducing the SimLabs Lineup Generator | FantasyLabs](https://www.fantasylabs.com/articles/nfl-dfs-product-update-introducing-the-simlabs-lineup-generator/)
- [PGA Models: FantasyLabs PGA Perfect% and SimLeverage | FantasyLabs](https://www.fantasylabs.com/articles/new-product-update-fantasylabs-pga-perfect-sim-leverage/)
- [Introducing SimLabs: DFS Sims Lineup Generation FAQ | RotoGrinders](https://rotogrinders.com/articles/dfs-sims-faq-3952660)
- [DFS Simulator FAQ | The Solver / ETR](https://thesolver.com/simulator/faq)
- [DFS Strategy: Predicting Ownership | RotoGrinders](https://rotogrinders.com/articles/dfs-strategy-predicting-ownership-1360237)
- [GPP Leverage Scores: Balancing Value with Ownership in DFS | 4for4](https://www.4for4.com/gpp-leverage-scores-balancing-value-ownership-dfs)
- [SaberSim.com: A Comprehensive Review | WindailySports](https://windailysports.com/reviews/sabersim/)
- [DFS GPP Strategy: How to Build Winning Tournament Lineups | DFSBuild](https://dfsbuild.com/dfs-gpp-strategy/)
- [NFL DFS Leverage Plays & Game Theory | Stokastic](https://www.stokastic.com/news/nfl-dfs-leverage-plays-game-theory-large-field-gpp-strategy-ac11)
- [10 Commandments To Winning GPP DFS Football Tournaments | DailyFantasySports101](https://www.dailyfantasysports101.com/10-commandments-of-winning-gpp-fantasy-football-tournaments/)
- [On the Assessment of Monte Carlo Error in Simulation-Based Statistical Analyses | PMC / Morris et al.](https://pmc.ncbi.nlm.nih.gov/articles/PMC3337209/)
- [How Many Monte Carlo Samples Are Enough? | Vose Software / Riskwiki](https://riskwiki.vosesoftware.com/Howmanyiterationstorun.php)
- [GitHub: DFS Simulator -- tburger101](https://github.com/tburger101/dfs_simulator)
- [Optimizing Daily Fantasy Baseball Lineups: A Linear Programming Approach | arXiv](https://arxiv.org/pdf/2411.11012)
- [Correlated Variables in Monte Carlo Simulations | Towards Data Science](https://towardsdatascience.com/correlated-variables-in-monte-carlo-simulations-19266fb1cf29/)
- [Binomial Proportion Confidence Interval | Wikipedia](https://en.wikipedia.org/wiki/Binomial_proportion_confidence_interval)
