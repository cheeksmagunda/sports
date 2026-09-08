# NFL Oracle build handoff

This is the continuation brief for Claude Code and a parallel team. Issue [#115](https://github.com/cheeksmagunda/sports/issues/115) is the source of truth for acceptance evidence. Draft PR [#116](https://github.com/cheeksmagunda/sports/pull/116) contains checkpoint `0ef5396a679ccf921197c59cb19215f01863879d`; it is unfinished and not deployed.

## Product contract

Before kickoff, choose five of the verified eligible NFL players and commit their order to slots `[2.0, 1.8, 1.6, 1.4, 1.2]`. Maximize:

`sum(finalized Real value_i * (player_boost_i + slot_multiplier_i))`

Player boosts are `0..3`. The app recommends picks for the operator to enter manually. Contest submission stays hard-denied. Every slate size, including one game, must produce a legal answer when five eligible players exist. Slate diversity heuristics must never leak into labels or grading.

The model must use the full historical contest corpus to learn stable player value, role, boosts, slot behavior, field patterns, and prelock information. At the decision clock it must refresh eligibility, availability, depth, matchup, weather, team context, and attributed media evidence. A coach or team source can change a projection when the statement is specific, time-valid, attributable, and calibrated. Do not require a new numeric stat before language can update role or availability. Do not turn generic hype or repeated copies into independent evidence.

## Twenty-agent execution plan

Claude should spawn these bounded agents, assign non-overlapping files, and merge through typed interfaces. Each agent reports tests, evidence, and unresolved uncertainty. No agent deploys or changes contest-entry gates.

1. **Contract owner:** verify root and NFL instructions, issue/branch rules, exact score law, and acceptance checklist.
2. **Real contest discovery:** map authenticated NFL contest/day routes and validate sport, date, teams, game, and finalized state.
3. **Historical collector:** build resumable last-18-month contest retrieval with redacted, content-addressed payloads.
4. **Contest schema auditor:** normalize rules, slots, boosts, pool, entries, ranks, payouts, and rule-era changes.
5. **Pool completeness:** reconcile provider roster, eligibility, inactive state, and missing-player denominators at lock.
6. **Identity bridge:** replace unsafe name fallbacks with dated evidence-backed Real/nflverse/GSIS aliases and explicit ambiguity states.
7. **Historical schedule:** derive effective week from verified schedule identity, including postseason, and test time alignment.
8. **Human-winner study:** compare saved winners, ordinary entries, alternatives, boosts, order, and observable prelock signals without survivor bias.
9. **Contest censoring:** model top-N-only boards, missing payouts, field counts, ties, duplication, and what cannot be inferred.
10. **Real-value labels:** audit finalized `playerBoxScores[].value`, DNP handling, negative values, and duplicate game labels.
11. **Role model:** estimate opportunity, snap/route/touch role, depth, and workload changes using walk-forward splits.
12. **Availability model:** combine official status, inactives, beat reporting, and coach statements with calibrated participation probabilities.
13. **Media ingestion:** implement podcast/RSS/transcript claim records with speaker, segment, timestamps, rights, source independence, conflicts, and corrections.
14. **Media calibration:** measure incremental role/availability value from claims with held-out Brier/log loss, reliability, coverage, and missingness.
15. **Football context:** build matchup, weather, pace, opponent, game-script, and team dependence features with point-in-time clocks.
16. **Joint scenario sampler:** model player, teammate, opponent, game, role, weather, and availability dependence; preserve uncertainty and tail behavior.
17. **Expected-value optimizer:** jointly select five and assign slots under the exact additive law, relaxing only unsupported structural rules.
18. **Decision evaluation:** replay historical contests at their information clocks and compare named baselines, regret, calibration, and exact Total Value.
19. **Freeze worker:** prepare expensive work early, perform complete T-40 refresh, validate hashes/clocks/identity/pool, then atomically freeze.
20. **API/frontend/ops:** expose five picks, readiness, timing, evidence provenance, pool coverage, model fingerprint, and no-submission status; verify container, Railway, rollback, and smoke checks.

Agents 2-9 must provide data and censoring contracts before agents 10-18 train models. Agents 11-16 must publish feature clocks and leakage tests before agent 17 promotes an optimizer. Agent 19 cannot freeze partial pools or stale context. Agent 20 cannot call a recommendation authoritative without readiness evidence.

## Current verified baseline

The checkpoint has a numerical model, structured context, exact scoring schema, optimizer, append-only store, freeze scaffolding, API, frontend, Docker/Railway source, and focused tests. Corpus G currently has 37,710 usable finalized player-games from 570 validated games. The saved NFL contest corpus is only one finalized contest, contest 870, with ranks 1-20 of a reported 20,841 entrants. It is useful for schema and descriptive checks, not general strategy claims. The September 9 target capture is contest 2141, one game NE at SEA, with 161 observed candidates and all observed boosts zero. Revalidate live before using it.

Known blockers are incomplete Corpus C, unsafe context identity fallbacks, no calibrated media claim feed, incomplete T-40 source refresh, overly permissive active-model validation, partial-pool publication risk, and a synthetic opponent metric that is not whole-field win probability. Do not claim a winning edge until later held-out contest replay supports it.

## Required continuation checks

Read root `AGENTS.md`, `CONTRIBUTING.md`, NFL `AGENTS.md`, `README.md`, `STATUS.md`, and `drive/NFL-ORACLE Data Science Resources, Strategy, Research, and more.txt`. Run `make write-path-check`, inspect current `main`, preserve `.codex-current-screen.png`, and keep all work linked to #115. Run the documented NFL tests, lint, mypy, boundaries, application contracts, package/container checks, and redacted secret scan. Use the authenticated local Railway CLI only. Do not create credentials, submit contests, mutate production, or merge until all acceptance blockers have evidence.
