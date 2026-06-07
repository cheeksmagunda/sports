# 04 - Simulation Optimizers and Lineup Builders for DFS

Scope: how the leading commercial Monte Carlo lineup tools work (SaberSim,
Stokastic SIMS, RotoGrinders LineupHQ, Awesemo, FantasyCruncher), what
parameters they expose, and which open source libraries (`pulp`, `ortools`,
`pydfs-lineup-optimizer`, `draftfast`) can rebuild the same machinery for the
Real Sports WNBA contest. The contest format we care about is a 5-player
pick-with-multipliers entry in a large field (8k-13k entries, top-20 paid),
which sits between salary cap DFS (DraftKings, FanDuel) and pure pick-em
(PrizePicks, Underdog). Most published tooling is written for salary cap, so
each section calls out which ideas transfer cleanly to multiplier-card pick-em
and which do not.

Sources are dated where possible. Anything older than 2023 is flagged as
potentially stale. No verified equity numbers are given for Real Sports
specifically; the platform is not covered by mainstream DFS analytics media as
of mid-2026.

---

## 1. Why simulation, not pure optimization

The classic salary cap optimizer is a mixed integer program: maximize
sum(projection) subject to salary and roster constraints. The fastest open
solver path is PuLP modeling the binary x_i in {0,1} per player and feeding
CBC or OR-Tools CP-SAT. A reference DraftKings NFL build with PuLP is walked
through step by step at Levonian (2020), with the binary variables, position
slot constraints, and a 50,000 salary cap shown in code form
([Levonian, Medium](https://zwlevonian.medium.com/integer-linear-programming-with-pulp-optimizing-a-draftkings-nfl-lineup-5e7524dd42d3)).
A peer-reviewed extension for MLB salary cap that uses standard deviation aware
LP is at arXiv:2411.11012
([Optimizing Daily Fantasy Baseball Lineups, 2024](https://arxiv.org/pdf/2411.11012)).

Pure projection-maximization has three failure modes in large-field GPPs:

1. The objective is the wrong thing. Cash and head-to-head want median.
   GPPs want the high tail because payouts are top-heavy. SaberSim states
   the case explicitly: "The Sim Optimizer is designed to optimize for upside
   because the top-heavy nature of DFS payouts rewards ceiling outcomes,
   not averages"
   ([SaberSim, How it Works](https://www.sabersim.com/how-it-works)).
2. The objective ignores duplication. RotoGrinders 2024 GPP guide notes that
   in a 50,000-entry field "a 40% player is not the same as a 40% player
   in a 1,000-entry field" and that splitting first place 500 ways destroys
   EV ([RotoGrinders, NFL GPP Strategy](https://rotogrinders.com/articles/nfl-dfs-tournament-strategy-basics-4051877)).
3. The objective ignores correlation. Two players in the same game share
   pace, blowout risk, and (for hitter or QB-pass-catcher) direct shot
   sharing. A linear sum of independent means understates joint variance.
   Sharpstack (MIT Sloan 2021 paper) quantifies this at 48% QB to WR2 and
   40% QB to TE1 in NFL
   ([Sloan, Sharpstack](https://www.sloansportsconference.com/research-papers/sharpstack-cholesky-correlations-for-building-better-lineups)).

Monte Carlo optimizers solve all three by drawing N joint samples of player
fantasy points from a correlated distribution, scoring each candidate
lineup's full payout curve under those samples, and ranking by simulated
ROI rather than mean projection.

---

## 2. SaberSim

### 2.1 Architecture

SaberSim is the most fully sim-native of the commercial tools. Its public
explainer says it runs "thousands of complete play-by-play simulations for
each slate" and that "each simulation creates a full game script that shows
who scores, who busts, and how players correlate"
([SaberSim, How it Works](https://www.sabersim.com/how-it-works)). The
lineup builder then samples lineups from those simulations rather than
constraining a single MIP. From the help center: "each lineup in that pool
is still the best possible GPP lineup for a given sim of the way that the
slate may go"
([SaberSim, Min Uniques](https://support.sabersim.com/en/articles/12079514-using-the-portfolio-diversifier)).

This is the structural difference from a classical optimizer. A classical
optimizer solves one MIP against mean projections and then re-solves with
exposure or min-unique constraints to get N variations. SaberSim solves
one MIP per simulation draw and returns the union, so correlation is
built into the candidate pool by construction rather than bolted on.

### 2.2 SaberScore, cROI, Adjusted Ownership

The default ranking metric is SaberScore: "the return on investment (ROI)
from a simple, generalized contest simulation". On the Ultimate plan you
get cROI (contest specific ROI) computed against the actual payout curve
of the contest you target
([SaberSim, SaberScore](https://support.sabersim.com/en/articles/12558411-how-saberscore-works)).

The leverage primitive is Adjusted Ownership. "Adjusted Ownership feeds
directly into SaberScore as a negative factor, penalizing lineups
overloaded with over-owned players and boosting lineups with the right
balance of projection, upside, and leverage"
([SaberSim, SaberScore](https://support.sabersim.com/en/articles/12558411-how-saberscore-works)).
Under-owned is defined by Adjusted Ownership less than Projected Ownership.

### 2.3 Diversification: Min Uniques vs Portfolio Diversifier

Two settings control how the top-N is pulled from the candidate pool.

- Min Uniques. A sorting constraint: when filling your 20 entries, force
  each to differ by K players from each other already selected. SaberSim
  recommends "first figure out what the maximum number of min uniques is
  that still gives you the number of lineups that you need, then experiment
  with a min unique setting that is one or two lower than that as a
  starting point"
  ([SaberSim, Master Min Uniques](https://www.sabersim.com/video/master-min-uniques-the-secret-to-dfs-diversification)).
- Portfolio Diversifier. The newer default. SaberSim characterizes the
  limit of Min Uniques as "Min Uniques only enforced numerical
  differentiation, lineups looked different, but they often depended on
  the same game scripts". The Diversifier "solves your portfolio
  holistically, looking across your entire set of entries and assembling
  the group of lineups that work best together, not just individually"
  ([SaberSim, Portfolio Diversifier](https://support.sabersim.com/en/articles/12079514-using-the-portfolio-diversifier)).

Pick-em transfer: both ideas port directly. In our 5-player Real Sports
build the natural Min Uniques would be 1-2 (one or two of the five players
differ across entries). The Diversifier idea (cover different game scripts,
not just different rosters) is the load-bearing one for a small roster.

### 2.4 Verified vs claimed

The "thousands of play-by-play sims" claim is marketing copy and not
externally audited. What is verifiable is the user-facing parameter set
(SaberScore, cROI, Adjusted Ownership, Min Uniques, Portfolio Diversifier)
and the help-center documentation linked above.

---

## 3. Stokastic SIMS

### 3.1 Methodology

Stokastic positions SIMS as a replacement for static optimizers: "rather
than using traditional static optimizers, Stokastic's NBA DFS Sims run
thousands of simulations, allowing for a variety in-game events in player
projections, modeling what could happen across hundreds, up to thousands
of scenarios"
([Stokastic, NBA Sims vs Optimizers](https://www.stokastic.com/nba/how-stokastics-nba-dfs-sims-are-better-than-optimizers-in-every-way-ac11/)).

Stokastic explicitly enumerates the variance sources their NBA model
captures: "foul trouble, rotations and game tempo can wildly affect
outcomes" and "teams altering rotations based on matchup, players getting
into foul trouble or games turning into blowouts"
([Stokastic, NBA Sims](https://www.stokastic.com/nba/how-stokastics-nba-dfs-sims-are-better-than-optimizers-in-every-way-ac11/)).
These are the same variance levers a WNBA model needs.

### 3.2 Boom Bust tool

Stokastic exposes per-player percentiles. Ceiling is defined as the
75th percentile sim outcome, floor as the 25th. Boom probability and bust
probability are framed against the field consensus salary expectation:
"Boom Probability is the percentage chance that a player exceeds their
salary expectations" and "Bust Probability highlights the risk involved,
showing how likely a player is to fail to meet value"
([Stokastic, Boom Bust](https://www.stokastic.com/nba/boom-bust-probability)).

The percentiles are a concrete, copyable interface for a Real Sports
pick-em recommender: instead of "value vs salary" the boom/bust threshold
becomes "exceeds breakeven given assigned multiplier".

### 3.3 Capacity numbers

Documented limits (Core vs Max): "The Core package allows running up to
1,000 lineup simulations, while the Max package can simulate up to 5,000
lineups for maximum ROI in high-stakes contests"
([Stokastic, NBA DFS Tools 2025-26](https://www.stokastic.com/nba/nba-dfs-tools-2025-26-get-stokastic-sims-data-ac14/)).
These are lineup counts (entries built), not slate sim counts.

### 3.4 Pick-em coverage

Stokastic publishes a dedicated correlation guide for PrizePicks and
Underdog NBA: "if you take the more on a point guard's assists, you should
consider pairing it with the more on points for one or multiple scorers on
the same team". They also flag a payout subtlety we should mirror: "in
PrizePicks, if you built a six-man golf entry that used three players to
have less total strokes and all those same players to have more total
birdies, the payout on six correct is 15x, not 25"
([Stokastic, Pick-em Correlation](https://www.stokastic.com/nba/nba-dfs-correlation-for-pickem-entries-strategy-for-prizepicks-underdog-more-ac11/)).
Real Sports does not have a documented same-bet-from-different-angle
penalty, but the lesson stands: read the payout schedule before assuming
correlation is free.

---

## 4. RotoGrinders LineupHQ

### 4.1 Coverage and feature set

LineupHQ is breadth-first. Per RotoGrinders, it includes "29 lineup
optimizers across 15 sports and four different operators" and exposes
"player projections updated for usage and injury news all the way to
kickoff, ownership projections to identify chalk and leverage
opportunities, and fully customizable stack settings for various
correlation types (QB-WR-WR, QB-RB-WR, QB-WR-TE, etc.)"
([RotoGrinders, LineupHQ](https://rotogrinders.com/lineuphq) and
[RotoGrinders, MLB Optimizer](https://rotogrinders.com/articles/mlb-dfs-optimizer-lineuphq-3875742)).
It supports min and max exposure, multi-source projection blending with
weights, and "RG Value" plus "Points per Dollar" derived metrics.

### 4.2 Where it sits methodologically

LineupHQ is closer to a traditional MIP plus stack rules and exposure caps
than a Monte Carlo lineup sampler. It is the closest commercial analog to
a configured `pydfs-lineup-optimizer`. It does not advertise per-lineup
contest-simulated ROI the way SaberSim does. For our build, LineupHQ-style
behavior is what you get out of the open source path with no extra work;
the SaberSim and Stokastic behavior requires adding a sim layer in front of
the optimizer.

### 4.3 MMA tool exception

RotoGrinders does ship a Monte Carlo product for MMA specifically
([RotoGrinders, MMA Sim Tool](https://rotogrinders.com/articles/mma-dfs-optimal-lineup-simulation-tool-draftkings-3915353)),
so they understand the sim-first idea, just have not made it the default
for the bigger sports.

---

## 5. Awesemo and FantasyCruncher

### 5.1 Awesemo

Awesemo publishes projections plus an optimizer rather than a
simulation-first product. Their public stance on the correlation question:
"In GPPs, optimizing solely for projection can lead to over-exposure to
high value plays, when ownership and correlation are equally important"
([Awesemo, Diversification Primer](https://awesemo.com/gameplan/diversification-primer)).

The OWS ("One Week Season" or "Optimal Win Share" in some referrals) brand
is associated with NFL workflow training rather than a published
simulation engine. Public material does not document a Monte Carlo joint
distribution model. Treat Awesemo as a projection plus exposure layer on
top of standard MIP optimization, not as a peer of SaberSim or Stokastic
on the sim axis.

The concrete diversification primitive they teach is the unique-players
function: "if you specify three unique players, then every lineup you
generate will have a minimum of three players who are different from
every other previously produced lineup"
([Awesemo, Diversification Primer](https://awesemo.com/gameplan/diversification-primer)).
This is the same Min Uniques concept SaberSim exposes.

### 5.2 FantasyCruncher

FantasyCruncher is one of the oldest tools in the space. Per WIN DAILY's
2024 review, "long before many DFS platforms incorporated advanced
simulation models and ownership projections, FantasyCruncher was helping
DFS players build high-quality, data-driven lineups with its intuitive
optimizer and extensive customization features"
([WIN DAILY, FantasyCruncher Review](https://windailysports.com/reviews/fantasycruncher/)).

The one piece worth lifting is their variance treatment. Per the same
review, "FantasyCruncher developed new ways to handle variations in
player performance using the players standard deviations and normal or
log normal distribution to adjust projections. These projections have
proven to be more consistent with actual results while still producing
diverse lineups". This is a marginal-only variance model (per-player
sigma, no off-diagonal terms), which is a strict subset of what Sharpstack
or SaberSim claim. It is also the easiest variance model to ship: per
player, draw from N(mu, sigma) or LogN(mu, sigma) per sim, no
correlation matrix to estimate.

---

## 6. The correlation question and Sharpstack

The MIT Sloan 2021 paper "Sharpstack: Cholesky Correlations for Building
Better Lineups" (Andy Ash) is the cleanest public writeup of how to do
correlated lineup simulation
([Sloan, Sharpstack](https://www.sloansportsconference.com/research-papers/sharpstack-cholesky-correlations-for-building-better-lineups),
[PDF](https://global-uploads.webflow.com/5f1af76ed86d6771ad48324b/607a4434a565aa7763bd1312_AndyAsh-Sharpstack-RPpaper.pdf)).
The recipe:

1. Estimate a per-slate correlation matrix C from historical joint
   outcomes at the same lineup roles (NFL: QB and WR1, QB and WR2, QB and
   TE1, opposing QB and your WR, etc.).
2. Cholesky-factor C = L L^T.
3. For each sim, draw independent standard normals z and form
   x = mu + L diag(sigma) z. The resulting x respects the correlation
   structure of C.
4. Run an optimizer per sim on the realized x; collect the per-sim winners;
   rank lineups by frequency-of-being-top weighted by simulated payout.

Published WNBA correlation numbers are scarce. The NBA-adjacent intuition
(usage shares within a lineup roughly sum to 100, so two stars from one
team are negatively correlated within game, positively correlated across
games via pace and blowout) ports cleanly. For our build the practical
question is whether to estimate a true covariance matrix from game logs or
to start with a Gaussian copula over per-player marginals derived from the
existing decomposed projection heads. Either is defensible; the
correlation matrix is the lower-bandwidth representation.

Note: 2021 paper, so on the older edge of "non-stale", but the math is
not time-sensitive.

---

## 7. Open source equivalents

### 7.1 pydfs-lineup-optimizer

Maintainer: Dima Kudosh. License: MIT. Repo:
[github.com/DimaKudosh/pydfs-lineup-optimizer](https://github.com/DimaKudosh/pydfs-lineup-optimizer).
Docs: [readthedocs](https://pydfs-lineup-optimizer.readthedocs.io/en/latest/index.html).

Site and sport coverage as of 2.x docs: DraftKings, FanDuel, Yahoo, FantasyDraft,
DraftCast, FanBall for NFL, NBA, MLB, NHL, soccer, golf, LoL, and others
([readthedocs index](https://pydfs-lineup-optimizer.readthedocs.io/en/latest/index.html)).
WNBA is not listed natively but a custom RuleSet handles it.

Relevant features (from the
[rules doc](https://pydfs-lineup-optimizer.readthedocs.io/en/latest/rules.html)):

- TeamStack, GameStack, PositionsStack, and PlayersGroup primitives for
  correlation rules.
- `set_teams_max_exposures` and per-player max-exposure.
- Two exposure strategies: total-count (high-projected players occupy the
  first N lineups) and after-each-lineup (rebalance per draw).
- `RandomFantasyPointsStrategy` injects noise into projections per sim,
  default range 0 to 12 percent deviation. This is the library's built-in
  knob for "simulate variance without a full joint model".

Caveat (current): per Libraries.io the package "has not seen any new
versions released to PyPI in the past 12 months and could be considered
as a discontinued project"
([Libraries.io](https://libraries.io/pypi/pydfs-lineup-optimizer)).
It still works, but bug-fix latency is a real risk for production.

### 7.2 draftfast

Maintainer: Ben Brostoff. License: Apache-2.0. Repo:
[github.com/BenBrostoff/draftfast](https://github.com/BenBrostoff/draftfast).

Supports NFL, NBA, MLB, and WNBA on DraftKings and FanDuel out of the box,
which is the only open optimizer in this list that ships WNBA support
explicitly. Uses a `RuleSet` for salary, slot counts, and other constraints.
Requires Python 3.12+.

Exposure handling is a documented first-class concept: "Long-term DFS
winners have the best player projections, bankroll management,
diversification in contests played, and diversification across lineups
(see draftfast.exposure)" (per project README). The package surfaces
`draftfast.exposure` directly.

### 7.3 PuLP and OR-Tools

PuLP is the de facto LP / MIP modeling layer for DFS in Python
([coin-or/pulp](https://github.com/coin-or/pulp),
[docs](https://coin-or.github.io/pulp/)). CBC is the default solver; OR-Tools
CP-SAT is available with `pip install pulp[ortools]`. Performance reference
point from Brondum: "16.2k lineups in around 90 minutes" on a single
machine for an NFL workload
([Brondum, Fantasy-Football-Optimization](https://github.com/mattbrondum/Fantasy-Football-Optimization)).

Direct OR-Tools (no PuLP wrapper) is faster for tight MIPs and supports
constraint programming primitives PuLP does not expose. For a 5-roster
WNBA pick-em the MIP is small (a few hundred binaries at most). CBC via
PuLP is more than sufficient and easier to debug.

### 7.4 dfs_optimizers and contest sim

Jarvis Nederlof's `dfs_optimizers` repo
([github.com/jnederlo/dfs_optimizers](https://github.com/jnederlo/dfs_optimizers))
is a thin Python implementation of the Becker and Sun "Picking Winners"
paper and is a useful reference for the MIP formulation tied to a
specific contest payout curve, not just average projection.

For the contest-side sim (model where your lineup lands in a field of N
entries with given ownership), `tburger101/dfs_simulator`
([github](https://github.com/tburger101/dfs_simulator)) is the public
reference, though it has not been updated recently and would need to be
ported. SaberSim's cROI and Stokastic's leverage charts are essentially
this calculation done at scale.

---

## 8. A buildable stack for Real Sports WNBA

Mapping the above into our repo's shape:

1. Marginal projections per player: we already have decomposed projection
   heads (per CLAUDE.md D63). Use these directly as `mu`. Use per-head
   residual variance as `sigma`.
2. Correlation: start with a sparse correlation model. Same-team scoring
   shares are negatively correlated (one player's usage displaces a
   teammate's). Same-game pace is positively correlated across both
   teams. A 2x2 block per game plus a per-team negative off-diagonal is
   enough to start. Estimate from game logs via shrinkage (Ledoit Wolf).
3. Multiplier card layer. Real Sports assigns a multiplier per player per
   slate. The lineup score per sim is sum over players of mult_i * x_i.
   This is still linear in x given a sim draw, so the per-sim winner
   problem is still a MIP that PuLP solves in milliseconds. The choice of
   which 5 players times which multipliers (0.5x to 5x) is itself a
   combinatorial layer on top.
4. Pick the top lineup per sim. Across N sims (start with N = 2000), each
   sim yields a single winner. The candidate pool is the union.
5. Score each candidate by expected payout in the field. Approximate the
   field with an ownership-weighted random draw of 5-player entries from
   the population of plausible plays. The 8k-13k entry field is small
   enough to enumerate by sampling 50k synthetic opponents per sim.
6. Diversification at portfolio time. Apply Min Uniques first
   (start K = 1 for 5-roster), then if time permits port the SaberSim
   Portfolio Diversifier idea (cover different game scripts), which in
   our case maps to "different multiplier-card assignments to different
   game outcomes".

Operationally:

- `pydfs-lineup-optimizer` gives the cleanest API for stacks, exposures,
  and the `RandomFantasyPointsStrategy` projection-noise hack, but is on
  life support upstream and has no first-class multiplier-card concept.
- `draftfast` is actively maintained and has WNBA built in, but its
  exposure tooling is thinner.
- A direct PuLP build is what most production DFS shops actually run
  because the MIP is small and the value is all in the simulation layer
  in front of the MIP, not in the MIP itself. This is the path that
  matches SaberSim's architecture most closely.

Recommended: thin PuLP layer for the per-sim MIP, our own Python wrapper
for the Monte Carlo and the field model. Use `pydfs-lineup-optimizer` only
as a reference implementation for stacking and exposure semantics.

---

## 9. Pick-em vs salary-cap deltas to keep in mind

- No salary, so the dominant constraint becomes the multiplier card
  assignment, not the budget. Most published optimizer math assumes a
  salary cap; the cap becomes a no-op for us.
- Roster size 5, much smaller than NFL (9) or NBA (8). Min Uniques in the
  K = 1 to 2 range is the only realistic differentiation.
- Top-20 paid in 8-13k entries puts the equity heavily on the very top of
  the lineup score distribution. SaberSim's "optimize for upside" framing
  applies even more strongly here than in mass-multi-entry DraftKings.
- Multiplier assignment introduces a per-player scaling factor that
  changes the variance contribution. A 5x card on a 25-point sigma player
  produces 125-point sigma. The portfolio variance is non-trivially
  altered by card placement; the standard optimizer literature does not
  cover this directly.
- Correlation matters for which players you pick but does not interact
  with payout structure the same way it does on PrizePicks (where the
  payout schedule changes per number-of-picks). Verify the Real Sports
  payout rules for same-game stack treatment before assuming linearity.

---

## 10. Source ratings

Verified, primary documentation:

- SaberSim help center and product pages, accessed 2026
  ([How it Works](https://www.sabersim.com/how-it-works),
  [SaberScore](https://support.sabersim.com/en/articles/12558411-how-saberscore-works),
  [Portfolio Diversifier](https://support.sabersim.com/en/articles/12079514-using-the-portfolio-diversifier),
  [Building Lineups](https://support.sabersim.com/en/articles/12079141-building-lineups-in-sabersim)).
- Stokastic product pages and how-it-works writeups, 2024-2026
  ([NBA Sims vs Optimizers](https://www.stokastic.com/nba/how-stokastics-nba-dfs-sims-are-better-than-optimizers-in-every-way-ac11/),
  [Boom Bust](https://www.stokastic.com/nba/boom-bust-probability),
  [Pick-em Correlation](https://www.stokastic.com/nba/nba-dfs-correlation-for-pickem-entries-strategy-for-prizepicks-underdog-more-ac11/)).
- RotoGrinders LineupHQ pages, 2024-2025
  ([LineupHQ](https://rotogrinders.com/lineuphq),
  [GPP Strategy](https://rotogrinders.com/articles/nfl-dfs-tournament-strategy-basics-4051877)).
- Awesemo Diversification Primer
  ([Awesemo](https://awesemo.com/gameplan/diversification-primer)).
- WIN DAILY 2024 FantasyCruncher review
  ([WIN DAILY](https://windailysports.com/reviews/fantasycruncher/)).
- Open source: pydfs-lineup-optimizer docs and repo
  ([readthedocs rules](https://pydfs-lineup-optimizer.readthedocs.io/en/latest/rules.html),
  [GitHub](https://github.com/DimaKudosh/pydfs-lineup-optimizer)),
  draftfast repo ([GitHub](https://github.com/BenBrostoff/draftfast)),
  PuLP ([GitHub](https://github.com/coin-or/pulp)).

Academic and longer-form:

- Sharpstack, MIT Sloan 2021 (older but math is fine,
  [Sloan link](https://www.sloansportsconference.com/research-papers/sharpstack-cholesky-correlations-for-building-better-lineups)).
- arXiv:2411.11012, MLB salary-cap LP, 2024
  ([PDF](https://arxiv.org/pdf/2411.11012)).
- Levonian, PuLP DraftKings walkthrough, 2020 (stale on rules but the LP
  formulation is canonical,
  [Medium](https://zwlevonian.medium.com/integer-linear-programming-with-pulp-optimizing-a-draftkings-nfl-lineup-5e7524dd42d3)).
- DFS Hub GPP 2024 guide
  ([DFS Hub](https://dfshub.com/nfl-dfs-tips/guaranteed-prize-pool-gpp-tips/)).

Flagged as potentially stale or marketing rather than verified:

- All "thousands of play-by-play sims" claims (SaberSim, Stokastic) are
  not externally audited. Treat as architectural intent, not benchmark.
- Pre-2023 RotoGrinders strategy posts (some are pre-2020 and reference
  removed contest types).
- Any "Awesemo OWS" reference to a specific simulation engine. The OWS
  brand in their materials is content packaging, not a documented
  Monte Carlo model.

Not found in public sources:

- Real Sports specific optimizer coverage in mainstream DFS analytics
  media. The platform is not analyzed by SaberSim, Stokastic,
  RotoGrinders, Awesemo, FantasyCruncher, or Unabated as of mid-2026
  (verified by negative search across each site).
