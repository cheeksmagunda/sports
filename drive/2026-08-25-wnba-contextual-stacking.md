# Contextual Stacking and Lineup Balance

Status: done

Created: 2026-08-25

Owner: Codex contextual-stacking implementation session

Policy version: `contextual-stacking-v1`

## Decision

Replace the unconditional preference for same-game stacks with a deterministic,
projections-first balance policy. The optimizer evaluates all feasible lineups
once and retains three winners from the same simulated objective:

1. The best unrestricted candidate.
2. The best candidate that meets the game-balance preference.
3. The best candidate that meets both the game and team preferences.

When game metadata is complete, the policy selects the fully balanced candidate
if it is within `0.01` objective units of the unrestricted winner. If it is not,
the policy applies the same test to the game-balanced candidate. The
unrestricted winner remains selected when its advantage is greater than the
margin. This is the contextual EV override. Balance is therefore preferred at
near-equal value, but stacking is not prohibited when the current projections
and payout simulation show a clear advantage.

The contextual objective excludes the legacy additive game-stack bonus. The
stack-aware field simulation remains active because it models opponent behavior
rather than prescribing the shape of our lineup.

Contextual filtering retains two deterministic top-N universes: the legacy
value-ranked pool and a coverage-aware pool. Their union is sampled once, and
the scan evaluates lineups contained wholly in either pool. This preserves the
best concentrated candidate from the legacy universe, makes the EV override
reachable, and avoids an accidental combinatorial search across mixed pools.

Two environment variables control the policy:

- `OPTIMIZER_CONTEXTUAL_STACKING_ENABLED`, expected production value `true`.
- `OPTIMIZER_CONTEXTUAL_STACK_EV_MARGIN`, default and expected production value
  `0.01`.

Setting `OPTIMIZER_CONTEXTUAL_STACKING_ENABLED=false` is the full rollback. The
false path restores the legacy objective, including
`OPTIMIZER_GAME_STACK_BONUS`, currently expected to be `0.010` in production.
It also restores legacy value filtering, field matchup keys, and the uncapped
team-cap feasibility fallback.

## Current behavior and history

Git history contains the stacking implementation decisions, but no deleted
stacking design brief that should be recovered. This document records the new
decision in the repository-root `drive/` directory.

The behavior being replaced was assembled incrementally:

- D50, commit `b1b304b`, introduced slate-size-aware team caps. One-game slates
  can use up to five players from a team, two-game slates can use up to three,
  and larger slates retain the configured cap, currently two.
- D70, commit `bc43ce4`, added a fixed same-game objective bonus.
- D88, commit `e281d42`, added same-game and same-team concentration to the
  simulated contest field.
- D98, commit `79cae8f`, raised the production game-stack bonus to `0.010` after
  observing frequent stacks in historical winning fields and in the app's own
  recommendations.

Those decisions address feasibility, correlation, and field behavior. They do
not compare the opportunity cost of a concentrated recommendation with the best
balanced alternative on the same slate. They also do not leave a durable reason
for why concentration was selected.

## Production baseline and its limits

The production audit found 67 historical slates with complete legacy
team/opponent structure. Twenty-one complete multi-game slates selected more
than two players from one game. The audit used the latest `frozen_lineups` row
per slate and formed a canonical game key from the unordered team pair.

This 21 of 67 result is a composition baseline, not a performance result. The
historical rows do not provide trustworthy exact contest placements linked to
the submitted frozen lineup. A captured top-20 board cannot assign an exact
rank to an absent lineup, and the latest freeze cannot be assumed to be the
submitted entry when a slate has multiple freeze sequences. The baseline cannot
show that stacking caused better or worse rank, payout, or ROI, and it must not
be used to tune the `0.01` margin.

## Preferred shapes

The preferences are soft. Existing team caps, eligibility checks, anchor rules,
and boost constraints remain hard constraints. The target team count is clamped
to the active slate's represented teams, and the coverage-aware filter retains
representatives when its configured capacity permits.

| Slate size | Game preference | Team preference | Contextual behavior |
| --- | --- | --- | --- |
| 1 game | At least 1 game, maximum 5 from the game | Both teams when both are represented | `3-2` and `4-1` both satisfy team balance; `5-0` can win through the EV override or infeasibility |
| 2 games | Both games, maximum 3 from either game | All 4 teams when represented | A fully balanced lineup has a `3-2` game split and `2-1-1-1` team shape; a 3-team, 2-game candidate is the game-balanced fallback |
| 3+ games | At least 2 games, maximum 2 from a game | At least 4 teams when represented | Five picks and a maximum of 2 per game imply at least 3 selected games for a game-balanced candidate |

The optimizer checks the fully balanced candidate first because it satisfies
both dimensions. It then checks the game-balanced candidate. If neither exists,
the unrestricted winner is returned with `balance_infeasible`. If either exists
but trails the unrestricted winner by more than the margin, the unrestricted
winner is returned with `contextual_ev_override`.

There is no new hard minimum-games rule. This is deliberate: the requested
behavior avoids a blind stacking rule without replacing it with a blind
anti-stacking rule. A concentrated multi-game lineup must earn its selection by
more than the configured objective margin.

## Context and data boundaries

The policy is context-aware through the current, pregame inputs already used by
the optimizer:

- Player score distributions, active probability, starter state, injury and
  availability signals, minutes information, and upstream matchup features.
- Slot multipliers, card boosts, payout curve, field size, measured draft
  counts, and the stack-aware simulated field.
- Slate size, active-team coverage, and authoritative game identity.

Real Sports supplies game identity and the pool data that feeds the projection
pipeline. The preferred key is `realsports:<game_id>`. Legacy rows that lack a
provider ID may use `teams:<TEAM_A>|<TEAM_B>` only when team and opponent pairs
are complete and reciprocal for the whole slate. Mixed or guessed identity is
not allowed.

Railway supplies the service runtime, environment configuration, deployment
state, and logs. It is not itself a predictive input. PostgreSQL remains the
durable source for the enriched optimizer inputs, frozen decision, and later
analytics.

Historical draft counts inform the existing field simulation. Historical
contest results may support future offline calibration only after frozen-entry
identity and outcome completeness are reliable. They do not add a live stacking
bonus in v1.

An unexpected realized performance is not knowable before the contest. V1
represents that uncertainty through each player's sampled distribution and the
latest valid pre-freeze availability inputs. A late injury, starter, minutes, or
projection update can change the decision only through a new finalized Job 2
input and the existing append-only re-freeze path.

The optimizer performs no provider fetch. Job 1 acquires and persists provider
context; Job 2 operates on typed, frozen inputs.

## Deterministic decision procedure

`objective` below is the existing simulated payout objective, including any
configured non-stacking terms, but excluding the legacy fixed game-stack bonus
when contextual mode is enabled. Candidate enumeration, player filtering, field
simulation, and scoring use the same fixed input order and random seed.

```python
def choose_candidate(candidates, context, config):
    unrestricted = None
    game_balanced = None
    fully_balanced = None

    for candidate in candidates_in_stable_order(candidates):
        if violates_existing_hard_constraints(candidate):
            continue

        value = simulated_objective(candidate)
        if not config.contextual_stacking_enabled:
            value += legacy_game_stack_bonus(candidate)

        unrestricted = retain_first_max(unrestricted, candidate, value)

        if config.contextual_stacking_enabled and context.preference is not None:
            if meets_game_preference(candidate, context.preference):
                game_balanced = retain_first_max(
                    game_balanced, candidate, value
                )
                if meets_team_preference(candidate, context.preference):
                    fully_balanced = retain_first_max(
                        fully_balanced, candidate, value
                    )

    if unrestricted is None:
        return None, decision(reason="no_feasible_lineup")

    if not config.contextual_stacking_enabled:
        return unrestricted, decision(reason="policy_disabled")

    # Contextual mode never re-enables the legacy bonus.
    if context.preference is None:
        return unrestricted, decision(reason="metadata_incomplete")

    margin = config.contextual_stack_ev_margin

    if fully_balanced is unrestricted:
        return unrestricted, decision(reason="best_projected_balanced")

    if (
        fully_balanced is not None
        and unrestricted.objective - fully_balanced.objective <= margin + 1e-12
    ):
        return fully_balanced, decision(reason="team_balance_within_margin")

    if game_balanced is unrestricted:
        return unrestricted, decision(reason="best_projected_game_balanced")

    if (
        game_balanced is not None
        and unrestricted.objective - game_balanced.objective <= margin + 1e-12
    ):
        return game_balanced, decision(reason="game_balance_within_margin")

    if game_balanced is not None or fully_balanced is not None:
        return unrestricted, decision(reason="contextual_ev_override")

    return unrestricted, decision(reason="balance_infeasible")
```

Incomplete game metadata is an explicit projections-only fallback. Contextual
mode selects the unrestricted candidate, records `metadata_incomplete`, and
still ignores the legacy stack bonus. Operators who need exact legacy behavior
must disable contextual stacking.

## Data flow

```text
Real Sports game ID, pool, and pregame signals
                    |
                    v
Job 1 typed enrichment and PostgreSQL persistence
                    |
                    v
Job 2 finalized player distributions and optimizer inputs
                    |
                    v
Resolve provider game keys or reciprocal legacy fallback
                    |
                    v
One candidate scan, one sample set, three retained winners
       unrestricted | game-balanced | fully balanced
                    |
                    v
Deterministic 0.01 objective-margin decision
                    |
                    v
Append-only frozen lineup with stack_decision
                    |
                    v
Composition analytics and future paired outcome evaluation
```

The provider game ID must survive the Real Sports home payload, pool parsing,
projection records, sampling specs, optimizer inputs, and freeze provenance.
Odds or enrichment failure must not erase an otherwise authoritative game ID.
Current model-policy payloads use schema v2. Historical schema-v1 payloads are
replayed with contextual selection disabled and retain their original canonical
payload and SHA-256 provenance hash.

## Observability and analytics

Every recommendation carries a versioned `StackingDecision`. Job 2 persists it
as the top-level `lineup.stack_decision` object in the append-only frozen-lineup
JSON. The record contains:

- Policy version, enabled state, reason, and metadata quality.
- Slate game and team counts.
- Preferred minimum games, maximum players per game, and team count.
- Effective team cap and whether it came from configuration, small-slate
  dynamics, or the smallest feasible relaxation.
- Selected game and team counts, including per-game and per-team composition.
- Selected, unrestricted, game-balanced, and fully balanced objective values.
- Objective sacrificed for balance and the configured override margin.
- Whether a configured legacy stack bonus was ignored.

The frozen row also stores the contextual switch and margin in
`serving_knobs`. Emit `optimizer_stacking_decision` as a structured log with the
decision summary for operational diagnosis. Railway logs are supplementary;
the frozen PostgreSQL record is the analytics source of truth.

Report these aggregates separately for one-game, two-game, and larger slates:

- Selected games, selected teams, maximum players per game, and maximum players
  per team.
- Fully balanced, game-balanced, EV-override, metadata-incomplete, and
  balance-infeasible rates.
- Mean and distribution of `objective_sacrifice`.
- Concentration rate against the 21 of 67 historical composition baseline,
  while keeping the historical classifier explicit.
- Provider-ID, reciprocal-fallback, and incomplete-metadata rates.

Future performance reporting must pair policies on identical frozen inputs,
seeds, samples, slot order, and outcome coverage. Track committed-order score,
captured top-20 status, and margin to the twentieth-place score. Report exact
placement only when an exact board or submitted-entry link supports it.

## Validation

Required automated coverage:

- One-game preferences target both represented teams without imposing a hard
  `3-2` rule.
- Two-game flat slates prefer both games, no more than three from a game, and
  all four represented teams.
- Three-game and larger flat slates prefer no more than two from a game and at
  least four represented teams.
- A fully balanced candidate within `0.01` objective units wins over the
  unrestricted candidate.
- A game-balanced candidate within the margin wins when full team balance is
  too costly or infeasible.
- A concentrated candidate with an advantage greater than `0.01` wins and
  records `contextual_ev_override`.
- Incomplete game metadata selects the unrestricted candidate, records
  `metadata_incomplete`, and does not apply the legacy bonus.
- Provider game IDs work when opponent text is absent; legacy fallback requires
  reciprocal team and opponent pairs.
- Contextual mode ignores `OPTIMIZER_GAME_STACK_BONUS`; disabled mode preserves
  the legacy objective.
- Freeze serialization preserves the complete `stack_decision` object.
- Shuffling equivalent input rows or replaying the same fixed seed does not
  change the selected lineup or reason.

Run the focused contextual-stacking, picker, settings, model-boundary,
Real Sports contract, Job 1, Job 2, and freeze tests. Then run the WNBA test,
lint, and type gates required by `AGENTS.md`.

Historical replay can validate composition classification, metadata fallback,
and determinism on the 67 complete slates. It cannot validate exact placement,
ROI, or the optimal margin. Do not treat a lineup absent from a captured top-20
board as rank 21, replace missing outcomes with zero, reorder committed slots by
realized score, or tune and report on the same sample.

## Rollout

1. Merge the provider game-ID pipeline, contextual policy, decision provenance,
   tests, and this brief directly to `main` after the required local gates pass.
2. Deploy Job 1 and Job 2 with
   `OPTIMIZER_CONTEXTUAL_STACKING_ENABLED=true` and
   `OPTIMIZER_CONTEXTUAL_STACK_EV_MARGIN=0.01`. Keep
   `OPTIMIZER_GAME_STACK_BONUS=0.010` configured for rollback; contextual mode
   records that it ignored the value.
3. Verify the first eligible frozen lineup against the durable row: provider
   game count, selected shape, reason, candidate objectives, sacrificed
   objective, serving knobs, input provenance, and committed slot order.
4. Monitor metadata quality and decision-reason rates by slate size. Investigate
   any rise in `metadata_incomplete` before interpreting composition changes.
5. Build prospective paired-policy evidence before changing the `0.01` margin or
   claiming performance improvement. Keep exact, censored, and incomplete
   outcomes separate.

Direct-to-main publishing does not remove the runtime safety switch. No schema
migration is required because the decision is stored in the existing lineup
JSON.

## Rollback

Set `OPTIMIZER_CONTEXTUAL_STACKING_ENABLED=false` on Job 2 and redeploy that
service. The disabled path restores the previous optimizer objective, including
the dynamic team cap, `OPTIMIZER_GAME_STACK_BONUS=0.010`, and current field
simulation settings.

Verify the next recommendation with a fixed-seed replay and confirm a
`policy_disabled` decision. Retain all append-only frozen lineups, decision
records, and prospective shadow evidence. Rollback does not authorize deleting
policy evidence, rewriting historical lineups, changing schedules, or mutating
placement data.
