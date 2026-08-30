# Issue 38: Field Intelligence Verification
Status: done
Created: 2026-08-29
Owner: Codex, with Claude Code audit artifacts and local benchmark recovery

## Executive Decision

The proposed decision architecture is directionally correct, but `choose five`
must remain a WNBA application rule, not a shared-core invariant. The future-
proof object is a structured action with selected items, ordered assignments,
constraints, contest rules, and provenance. The shared layer may provide typed
technical primitives for this object, but the sport application must own the
candidate schema, outcome model, feasible set, slot multipliers, payout curve,
provider identity, and field behavior.

The Real Sports field hypothesis is **PARTIALLY SUPPORTED as a research
direction and UNKNOWN as an incremental production signal**. The corpus shows
that draft counts and realized value are related, but the available relationship
is confounded by `card_boost`, lacks point-in-time ownership snapshots, and is
not a conditional out-of-time estimate of `I(Y; Field | K)`. The claim that
winning drafts often identify the day's highest-value performers is plausible
and testable, but it is not yet verified by the current production corpus.

The current production path does not generally consume measured same-slate
pre-lock drafts. `slate_labels` is written at day-close, while Job 2 normally
runs before that data exists and falls back to a popularity estimator. The
`player_slate_ownership` table is empty. This is the highest-value finding in
the audit because it separates the product's intended field edge from the edge
it currently has.

No production behavior, schedule, credential, frontend, or database state was
changed. The parallel calibration work added only a dormant configuration seam
and local benchmark support; the new switch defaults to `false`.

## Evidence Labels

| Finding | Label | Basis |
| --- | --- | --- |
| `K=5` is a WNBA Real Sports rule, not a universal sports rule | VERIFIED | Current optimizer slot contract and issue scope |
| A structured ordered action is more general than a set | VERIFIED | Ordered multipliers and possible future assignments |
| Current production uses measured pre-lock field ownership | FALSIFIED | Job 2 reads post-close labels; empty ownership table; estimator fallback |
| Draft popularity contains some information about realized value | PARTIALLY SUPPORTED | Raw and boost-stratified correlations, with major confounding |
| Draft popularity adds information conditional on all pre-slate inputs | UNKNOWN / NEEDS DATA | No point-in-time field snapshot joined to the complete knowledge state |
| Crowd agreement with bookmaker expectations is predictive | UNKNOWN / NEEDS DATA | Odds are stored in enrichment, but no synchronized field and line history |
| Exact production contest placement is a reliable outcome target | FALSIFIED for current corpus | Non-null ranks are all the `21` capture sentinel; no exact percentiles |
| WNBA should be promoted into `oracle-core` as a generic domain model | FALSIFIED | Violates current dependency and ownership boundaries |

## The Learning Spine

The required loop is:

1. **What history taught us.** The label corpus contains player-slate Real
   Sports outcomes and draft counts. The gamelog corpus contains player-game
   box scores. They have different grains and identifiers. Historical top-20
   lineups show what successful entries selected, but not the full field.

2. **What we knew.** At decision time, Job 2 has the current Real Sports pool,
   player features, starter and availability signals, recent history, odds
   inputs when available, and the configured contest rules. It generally does
   not have measured current-slate draft counts.

3. **What we used.** The current path uses WNBA-owned features, a distribution
   sampler with availability gating and dependence structure, a heuristic
   popularity estimator, field simulation, and a payout-aware optimizer. A
   measured-draft path exists in code but normally receives an empty map before
   day-close.

4. **What we predicted.** The model predicts player performance distributions,
   not only point estimates. The optimizer predicts lineup scores, field
   competition, payout, and duplication risk under a simulated field.

5. **Why we picked.** The five-player lineup is enumerated subject to WNBA
   contest constraints. The committed order must be fixed before outcomes are
   known. The current optimizer also supports contextual stacking, field
   correlation, and dormant objective-shaping experiments.

6. **What happened.** Realized player scores and the captured top-20 leaderboard
   are available for historical slates. Exact submitted-entry placement is not
   reliably available below the capture boundary, and current ownership
   snapshots are not persisted.

7. **What we learned.** The highest-value next step is instrumentation, not a
   stronger popularity coefficient. We need synchronized field snapshots,
   bookmaker snapshots, freeze provenance, and complete outcome coverage before
   interpreting crowd behavior as a sensor or tuning it into production.

## General Decision Formulation

Let `H_<t` be historical observations before decision time `t`, and let
`Theta_s = Update_s(H_<t)` be sport-owned learned state. Let `K_t` be the
point-in-time knowledge snapshot, including source timestamps and missingness.
Let `A` be a structured action, `F_s(K_t, R_t)` the sport and contest feasible
action family, `Y` the joint athlete outcome, `Q_s` the field distribution, and
`U_s` the sport-owned contest utility.

```text
A_t* in argmax over A in F_s(K_t, R_t)
  E[ U_s(A, Y, Field, R_t) | K_t, Theta_s ]
```

The action must not be modeled as an unordered set. It should be able to carry:

| Action component | Why it matters |
| --- | --- |
| Selected item IDs | Player, athlete, asset, or other sport-owned candidate identity |
| Ordered assignment | Slot multipliers, batting order, roster roles, or position-specific effects |
| Multiplicity or entry grouping | Multiple entries are a portfolio action, not one larger set |
| Feasibility witness | Cardinality, team, role, salary, eligibility, and contest constraints |
| Contest and rule identity | Payout, lock, scoring, and platform version can change |
| Point-in-time provenance | Reproves what was knowable and what was actually used |

For one current WNBA entry, the action is an ordered five-player tuple and the
slot multipliers are `2.0, 1.8, 1.6, 1.4, 1.2`. For a future sport or contest,
`K`, the number of selected items, the feasible action family, and the utility
can all change without changing the mathematical shape.

## Ownership Boundary

| Layer | Keep here | Do not move here yet |
| --- | --- | --- |
| All-sports technical primitive | Typed action container, deterministic candidate enumeration, constraint protocol, scenario matrix interface, utility interface, timestamps, hashes, and append-only decision provenance | WNBA player semantics, Real Sports API fields, team/game schema, slot multipliers, payout curve, or a generic sport model invented from one implementation |
| Real Sports application family | Platform contest identity, pool and draft observation adapters, lock semantics, field snapshot normalization, provider-specific source quality, and platform scoring rules | Claims that these mechanics are shared by every sport before a second implementation proves them |
| WNBA application | Five-player rule, WNBA player and team identity, card boost, WNBA schedule, starter and injury behavior, WNBA odds interpretation, slot values, payout regime, model features, field heuristics, and domain endpoints | Imports into `oracle-core` or assumptions that a second sport uses the same constraints |

The repository dependency direction remains `sport application -> oracle-core`.
The safe promotion criterion is two or more independent sport implementations
using the same interface with stable semantics and tests. Until then, keep the
domain behavior local and share only provider-neutral mechanics.

## Production Corpus Audit

The following read-only production audit was captured on 2026-08-29. Database
access was forced to transaction read-only mode. Counts are observations, not
claims about an unverified live deployment beyond the queried data.

| Observation | Result |
| --- | ---: |
| `slate_labels` rows | 6,530 |
| Distinct labeled slates | 217 |
| Labeled date range | 2025-05-16 through 2026-08-27 |
| Non-null realized scores | 6,529 |
| Non-null draft counts | 6,351, or 97.3% of labeled rows |
| `contest_leaderboards` rows | 4,340 |
| Distinct leaderboard slates | 217 |
| Distinct users appearing in captured top-20 data | 3,545 |
| Average captured field size | about 8,714.6 |
| Maximum field size | 14,999 |
| `contest_placements` rows | 30 across 29 slates |
| Non-null placement ranks | 11, all equal to the `21` lower-bound sentinel |
| Exact finish percentiles | 0 |
| `player_slate_ownership` rows | 0 |
| `job1_enrichment` rows | 10,501 across 224 slates |
| Latest enrichment date | 2026-08-29 |

The date mismatch is operationally important: measured labels stop at
2026-08-27 while enrichment reaches 2026-08-29. A current Job 2 run therefore
cannot obtain current-slate measured drafts from `slate_labels` merely because
historical draft counts exist.

The top-20 repeat-user counts are 2,969 users appearing once, 435 twice, 93
three times, 30 four times, 11 five times, 3 six times, 3 seven times, and 1
eight times. These are captured-top-20 appearances, not a random sample of all
entries, so they cannot yet establish user skill.

## Field and Bookmaker Findings

The simple full-corpus relationships were:

| Relationship | Result |
| --- | ---: |
| Correlation of drafts with realized score | `+0.01736` |
| Correlation of drafts with card boost | `-0.48624` |
| Correlation of card boost with realized score | `-0.49480` |

Within card-boost tiers, the draft versus realized-score correlations ranged
from `-0.1900` to `-0.5664`. This does not mean the field is anti-informative.
It shows that raw popularity is entangled with the platform's boost mechanism:
players offered larger boosts tend to be less valuable, and both drafts and
outcomes move with that latent valuation. A proper test needs slate fixed
effects, point-in-time features, an out-of-time split, and a pre-registered
outcome metric.

The current code path confirms the data limitation. `job2_io._load_measured_drafts`
explicitly treats an empty same-slate result as normal before contests finalize.
`job2._build_specs` then uses a popularity estimator. `picker/field.py` contains
comments describing measured live counts, but the actual table populated by the
day-close label path is post-contest. No insert or upsert path for
`player_slate_ownership` was found.

Bookmaker context is present in the recent WNBA enrichment path as
`vegas_total`, `vegas_spread`, and related fields. The Odds API adapter reduces
selected books to game-level summaries. Historical backfill cannot reconstruct
the full odds history because the provider does not expose the required
historical endpoint, and the label corpus does not carry a synchronized field
snapshot. Therefore:

- **UNKNOWN:** whether crowd agreement with bookmakers identifies high-value performers.
- **UNKNOWN:** whether crowd-book disagreement is a profitable contrarian signal.
- **UNKNOWN:** whether agreement is useful only in specific injury, starter, total, or slate-size regimes.
- **NEEDS DATA:** the timestamped bookmaker line, field snapshot, and exact knowledge state must be joined before any of these can be estimated.

## What the Current Model Does Well and Where It Is Constrained

The current WNBA model already separates several important uncertainty sources:

| Component | Current treatment | Audit judgment |
| --- | --- | --- |
| Recent player and game structure | Rolling features and separate gamelog corpus | Appropriate WNBA-owned structure |
| Availability and starter uncertainty | Availability gating, starter signals, and unknown fade | Useful, but calibration must remain time-split |
| Joint player outcomes | Copula and mixture variance sampling | Better than independent point estimates; dependence needs regime checks |
| Field ownership | Estimator plus same-game and same-team heuristic boosts | Too heuristic to call a measured field model |
| Contest utility | Monte Carlo payout and duplication-aware experimental paths | Correct target, but placement feedback is censored |
| Slot order | Committed-order implementation exists as a dormant objective | Correct structural correction; production enablement needs paired evidence |
| Regime change | Mostly threshold-based game-script and contest heuristics | Candidate for a small regime layer, not evidence for a broad rewrite |

The model is therefore **PARTIALLY SUPPORTED as a sound baseline** and
**PARTIALLY SUPPORTED as structurally constrained**. It is not justified to
replace it with a large nonlinear or deep architecture from the current data.
The immediate constraint is not model capacity. It is missing provenance and
outcome measurement. The next model improvement should be a calibrated,
point-in-time field observation and regime layer evaluated at the decision
level.

## Research Findings by Method Family

| Research family | What it solves for Oracle | What it does not solve |
| --- | --- | --- |
| Contextual combinatorial bandits and semi-bandits | Changing candidate universes, structured actions, partial component feedback, and sequential adaptation | Does not create unbiased field observations or solve contest censoring |
| Decision-focused learning and Smart Predict-then-Optimize | Trains predictions to rank feasible actions by downstream decision quality instead of only player loss | Does not fix leakage, missing action outcomes, or an incorrect field simulator |
| Bayesian decision theory and hierarchical partial pooling | Shrinks sparse player, user, sport, and regime estimates while propagating posterior uncertainty | Does not make selected top-20 users representative of the field |
| Heteroscedastic, mixture, and copula models | Separates conditional variance, availability mixtures, and cross-player dependence | Does not identify causal information in popularity |
| Conformal and distributional calibration | Checks predictive coverage and adapts intervals under stated exchangeability or shift assumptions | Coverage is not decision utility, and distribution shift can break guarantees |
| Markov or state-space regime models | Represents latent phases such as injury-heavy, starter-uncertain, or high-total slates | A regime label is not automatically stable or identifiable with 217 slates |
| Doubly robust and off-policy evaluation | Reduces bias when evaluating policies from logged actions and propensities | Requires action propensities, overlap, and credible logging; top-20 capture is insufficient |
| Distributionally robust optimization | Prices ambiguity around the outcome or field distribution and limits worst-case degradation | Can become conservative or arbitrary without a defensible ambiguity set |
| Conditional independence and knockoff-style tests | Tests incremental signal while controlling observed confounders | Cannot control unrecorded point-in-time information or repair bad timestamps |
| Provenance and temporal database design | Reconstructs what was knowable, observed, used, and changed at freeze time | Does not itself produce a better model or field estimate |

Primary references used include [Smart Predict-then-Optimize](https://pubsonline.informs.org/doi/abs/10.1287/mnsc.2020.3922),
[Decision-Focused Learning](https://proceedings.mlr.press/v162/mandi22a.html),
[Nonstochastic Contextual Combinatorial Bandits](https://proceedings.mlr.press/v206/zierahn23a.html),
[Efficient Learning in Large-Scale Combinatorial Semi-Bandits](https://proceedings.mlr.press/v37/wen15.html),
[Nonparametric Predictive Distributions from Conformal Prediction](https://proceedings.mlr.press/v60/vovk17a.html),
[Doubly Robust Policy Evaluation and Learning](https://icml.cc/2011/papers/554_icmlpaper.pdf),
[Hamilton's regime-switching model](https://www.jstor.org/stable/1912559),
[Wasserstein Distributionally Robust Optimization](https://pubsonline.informs.org/doi/10.1287/educ.2019.0198),
and the [conditional permutation test for independence](https://academic.oup.com/jrsssb/article/82/1/175/7056014).

The practical synthesis is conservative: use the academic methods to design
measurement and evaluation contracts first, not as justification for importing
a generic research framework into `oracle-core`.

## Highest-Information Experiments

1. **Instrument the field at decision time.** Persist append-only ownership or
   draft snapshots with `slate_date`, contest ID, player identity, observed-at
   timestamp, source, field size, draft count, capture status, and a hash of
   the raw observation. Persist bookmaker snapshots with the same time basis.
   The freeze record must identify the exact snapshot used or explicitly record
   `field_observation_missing`.

2. **Measure incremental player-level signal out of time.** Build nested models
   with the same candidate and knowledge rows: `K` only, `K + field`, and
   `K + bookmaker`, then `K + field + bookmaker`. Use rolling or blocked
   out-of-time evaluation, slate fixed effects, cross-fitting, log score or
   CRPS for distributions, and rank metrics for top-value identification.
   Report the incremental delta and uncertainty, not only correlation.

3. **Test crowd-bookmaker agreement and divergence.** Normalize field and book
   ranks within each slate, define agreement and signed divergence at a common
   timestamp, and test interactions with card boost, starter certainty, injury
   transitions, game total, spread, and slate size. The preregistered question
   is whether divergence improves downstream decision utility, not whether it
   looks interesting descriptively.

4. **Estimate repeat-user skill with shrinkage.** Once complete entry histories
   and propensities exist, estimate user-level reliability with a hierarchical
   model. Hold out future slates and compare against a population field prior.
   Treat current top-20 repeat counts as selection-biased until full-field data
   is available.

5. **Run paired decision experiments.** On identical frozen inputs, seeds,
   samples, candidate pools, slot order, payout curve, and outcome coverage,
   compare the incumbent field model against a measured-field challenger and a
   bookmaker-only challenger. Require improvements in decision-level metrics,
   with censored outcomes reported separately, before enabling a production
   overlay.

## Parallel Calibration Artifact

The local benchmark recovery used the verified three-file corpus snapshots:

| Input | SHA-256 |
| --- | --- |
| `slate_labels.csv` | `f1ea1e438852cdaa15d5d8aff6dc31489324c334605f896f56c2b8a0d512876b` |
| `contest_leaderboards.csv` | `6da928411d352e33c4299d999947aca1f3c09cb83dd51f9789edbab167619cac` |
| `game_identity.csv` | `d95ea6a8755223e4ad16a643c09e8fce5548435f472ee7f16da2640db59615a9` |

The benchmark covered 101 eligible slates with 400 Monte Carlo samples per
variant, zero optimizer errors, and zero infeasible results. It is a local,
right-censored candidate comparison, not a production field-signal result:

| Variant | Top 20 | Top 5 | Top 1 | Mean payout capture |
| --- | ---: | ---: | ---: | ---: |
| Baseline | 8.9% | 5.0% | 1.0% | 0.0891 |
| Leverage weight 0.28 | 22.8% | 11.9% | 5.9% | 0.2277 |
| Leverage 0.28 plus committed order | 28.7% | 13.9% | 5.0% | 0.2871 |

These results justify further paired measurement and preserve the dormant
`OPTIMIZER_COMMITTED_ORDER_OBJECTIVE=false` default. They do not justify
turning on leverage, committed order, or any new field behavior in production
within this audit.

## Final Answers

1. **Most future-proof equation:** maximize expected sport-owned contest
   utility over a structured feasible action, conditioned on a timestamped
   knowledge state and learned historical state, while modeling athlete
   outcomes, field behavior, and contest rules separately.

2. **Generic versus sport-owned:** genericize action representation,
   constraints, scenario evaluation, and provenance. Keep WNBA and Real Sports
   mechanics, features, scoring, providers, calendars, and payout rules local
   until independent implementations prove a shared contract.

3. **Is the field-information hypothesis testable now?** Conceptually yes;
   empirically not honestly with the current production corpus. We can measure
   descriptive top-20 and player-label relationships now, but not incremental
   conditional information or full-field decision lift.

4. **What can be measured now?** Player-level realized values, draft counts
   after close, captured top-20 selections, repeated captured user IDs, model
   counterfactuals on shared frozen inputs, and the direction of confounding by
   card boost.

5. **What blocks honest measurement?** Missing pre-lock field snapshots,
   empty ownership calibration table, incomplete exact placements, top-20-only
   leaderboard capture, missing synchronized bookmaker history, and weak
   point-in-time provenance for joins.

6. **Strongest current signal/noise method:** instrument the decision-time
   state, fit nested cross-fitted out-of-time models, use hierarchical shrinkage
   for sparse user and regime effects, evaluate predictive distributions and
   decision utility separately, and report censoring and uncertainty.

7. **Where is WNBA too heuristic?** The field estimator, same-game and
   same-team boosts, contrarian adjustment, and game-script thresholds are
   plausible local heuristics. They should be calibrated against timestamped
   field and placement data before being generalized or compounded.

8. **Highest-value next experiments:** field and bookmaker instrumentation,
   conditional out-of-time incremental-signal testing, crowd-book divergence,
   hierarchical repeat-user skill, and paired decision evaluation.

## Cross-References

This report is the independent verification requested by issue #38. It should
be read with issue #35's data and outcome instrumentation work and issue #37's
decision and stacking work. The implementation boundary remains WNBA-owned;
this report does not promote either issue into `oracle-core`.
