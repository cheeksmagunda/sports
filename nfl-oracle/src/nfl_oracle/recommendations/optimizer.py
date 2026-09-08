"""Five-card selection with committed ordering and feasible slate diversity."""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Sequence
from datetime import datetime
from importlib import import_module
from statistics import mean
from typing import Any, Literal

from pydantic import Field

from nfl_oracle.recommendations.model import Projection
from nfl_oracle.recommendations.schema import Candidate, EvidenceClock, Finite, Record, Slate

try:  # scipy is optional for local scaffold environments
    _numpy: Any = import_module("numpy")
    _optimize: Any = import_module("scipy.optimize")
    _sparse: Any = import_module("scipy.sparse")
    np: Any = _numpy
    Bounds: Any = _optimize.Bounds
    LinearConstraint: Any = _optimize.LinearConstraint
    milp: Any = _optimize.milp
    coo_matrix: Any = _sparse.coo_matrix
except ImportError:  # pragma: no cover - exercised only in minimal installs
    np = Bounds = LinearConstraint = milp = coo_matrix = None


class ScoringPolicy(Record):
    # Retained for old serialized scaffold records. The NFL objective now
    # specifies one law for every Real value, including negative values.
    negative_branch: Literal["unverified", "multiply", "unmultiplied"] = "multiply"
    evidence: tuple[str, ...] = ()

    def score(self, value: float, slot: float, boost: float) -> float:
        """Apply the observed additive Real scoring law.

        ``slot`` is the committed card multiplier and ``boost`` is the player
        multiplier bonus. Their sum is the effective multiplier. The negative
        The same formula applies to negative Real values. This is a scoring
        contract, not an instruction to clamp or drop a negative label.
        """
        return value * (slot + boost)


class OptimizerConfig(Record):
    objective: Literal["total_value"] = "total_value"
    beam_width: int = Field(default=150, ge=10, le=2000)
    min_distinct_teams: int = Field(default=3, ge=1, le=5)
    min_distinct_games: int = Field(default=2, ge=1, le=5)
    simulations: int = Field(default=500, ge=100, le=10000)
    upside_weight: Finite = Field(default=0.15, ge=0, le=2)
    field_weight: Finite = Field(default=0.1, ge=0, le=2)
    game_correlation: Finite = Field(default=0.15, ge=0, le=0.8)
    seed: int = 115


class FieldObservation(Record):
    clock: EvidenceClock
    entry_count: int = Field(gt=0)
    player_counts: dict[int, int]
    provenance: str
    # Provider summaries can expose only a known subset of players.  The
    # denominator remains authoritative, while unknown players stay estimated.
    coverage: Literal["complete", "partial"] = "complete"


class Pick(Record):
    player_id: int
    game_id: int
    team_id: int
    name: str
    position: str
    team: str
    opponent: str
    slot: int
    slot_multiplier: Finite
    card_boost: Finite
    projected_value: Finite
    projected_score: Finite
    uncertainty: Finite
    ownership: Finite
    ownership_source: Literal["measured_prelock", "estimated_projection_softmax"]


class Recommendation(Record):
    picks: tuple[Pick, ...]
    objective: Literal["total_value"]
    objective_value: Finite
    total_value: Finite
    total_value_baseline: Finite
    # Kept as an ergonomic alias for clients that consumed the scaffold.
    expected_score: Finite
    expected_score_baseline: Finite
    simulated_p90: Finite
    simulated_field_win_rate: Finite
    requested_distinct_teams: int
    required_distinct_teams: int
    requested_distinct_games: int
    required_distinct_games: int
    diversity_relaxed: bool
    candidate_count: int
    scoring_policy: ScoringPolicy
    assumptions: tuple[str, ...]
    contest_entry: Literal[False] = False


def _exact_search(
    eligible: Sequence[Projection],
    candidates: dict[int, Candidate],
    scores: dict[int, tuple[float, ...]],
    *,
    teams_required: int,
    games_required: int,
) -> list[tuple[float, tuple[int, ...]]]:
    """Solve the five-slot assignment exactly when scipy is available."""
    if (
        milp is None
        or np is None
        or Bounds is None
        or LinearConstraint is None
        or coo_matrix is None
    ):
        return []
    player_ids = [p.player_id for p in eligible]
    team_ids = sorted({candidates[pid].team_id for pid in player_ids})
    game_ids = sorted({candidates[pid].game_id for pid in player_ids})
    team_index = {value: i for i, value in enumerate(team_ids)}
    game_index = {value: i for i, value in enumerate(game_ids)}
    n_players = len(player_ids)
    x_count = n_players * 5
    team_offset = x_count
    game_offset = team_offset + len(team_ids)
    variable_count = game_offset + len(game_ids)
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    lower: list[float] = []
    upper: list[float] = []

    def add_constraint(entries: Sequence[tuple[int, float]], lo: float, hi: float) -> None:
        row = len(lower)
        for col, value in entries:
            rows.append(row)
            cols.append(col)
            data.append(value)
        lower.append(lo)
        upper.append(hi)

    def x_index(player: int, slot: int) -> int:
        return player * 5 + slot

    for slot in range(5):
        add_constraint([(x_index(player, slot), 1.0) for player in range(n_players)], 1, 1)
    for player in range(n_players):
        add_constraint([(x_index(player, slot), 1.0) for slot in range(5)], 0, 1)
    for player, pid in enumerate(player_ids):
        team_col = team_offset + team_index[candidates[pid].team_id]
        game_col = game_offset + game_index[candidates[pid].game_id]
        for slot in range(5):
            add_constraint([(x_index(player, slot), 1.0), (team_col, -1.0)], -np.inf, 0)
            add_constraint([(x_index(player, slot), 1.0), (game_col, -1.0)], -np.inf, 0)
    for team, team_number in team_index.items():
        add_constraint(
            [
                (team_offset + team_number, 1.0),
                *[
                    (x_index(player, slot), -1.0)
                    for player, pid in enumerate(player_ids)
                    if candidates[pid].team_id == team
                    for slot in range(5)
                ],
            ],
            -np.inf,
            0,
        )
    for game, game_number in game_index.items():
        add_constraint(
            [
                (game_offset + game_number, 1.0),
                *[
                    (x_index(player, slot), -1.0)
                    for player, pid in enumerate(player_ids)
                    if candidates[pid].game_id == game
                    for slot in range(5)
                ],
            ],
            -np.inf,
            0,
        )
    add_constraint(
        [(team_offset + number, 1.0) for number in range(len(team_ids))], teams_required, np.inf
    )
    add_constraint(
        [(game_offset + number, 1.0) for number in range(len(game_ids))], games_required, np.inf
    )
    matrix = coo_matrix((data, (rows, cols)), shape=(len(lower), variable_count)).tocsr()
    objective = np.zeros(variable_count)
    for player, pid in enumerate(player_ids):
        for slot in range(5):
            objective[x_index(player, slot)] = -scores[pid][slot]
    result = milp(
        c=objective,
        integrality=np.ones(variable_count),
        bounds=Bounds(np.zeros(variable_count), np.ones(variable_count)),
        constraints=LinearConstraint(matrix, np.asarray(lower), np.asarray(upper)),
    )
    if not result.success or result.x is None:
        return []
    picks = [
        (slot, player_ids[player])
        for player in range(n_players)
        for slot in range(5)
        if result.x[x_index(player, slot)] > 0.5
    ]
    if len(picks) != 5:
        return []
    picks.sort()
    ids = tuple(pid for _, pid in picks)
    score = sum(scores[pid][slot] for slot, pid in enumerate(ids))
    return [(score, ids)]


def _ownership(
    projections: Sequence[Projection],
    observation: FieldObservation | None,
    decision_at: datetime,
) -> tuple[
    dict[int, float], dict[int, Literal["measured_prelock", "estimated_projection_softmax"]]
]:
    estimated: dict[int, float]
    if observation:
        observation.clock.assert_available(decision_at)
        if any(n < 0 or n > observation.entry_count for n in observation.player_counts.values()):
            raise ValueError("invalid_field_counts")
        observed_total = sum(observation.player_counts.values())
        if observation.coverage == "complete" and observed_total != 5 * observation.entry_count:
            raise ValueError("incomplete_field_observation")
        if observation.coverage == "partial" and observed_total > 5 * observation.entry_count:
            raise ValueError("invalid_partial_field_counts")
        if set(observation.player_counts) - {p.player_id for p in projections}:
            raise ValueError("field_identity_mismatch")
        measured = {
            p.player_id: observation.player_counts[p.player_id] / observation.entry_count
            for p in projections
            if p.player_id in observation.player_counts
        }
        if observation.coverage == "complete":
            return measured, {pid: "measured_prelock" for pid in measured}
        estimated, _ = _ownership(projections, None, decision_at)
        merged = {p.player_id: estimated[p.player_id] for p in projections}
        merged.update(measured)
        return merged, {
            p.player_id: (
                "measured_prelock" if p.player_id in measured else "estimated_projection_softmax"
            )
            for p in projections
        }
    # Inclusion frequencies from weighted samples without replacement, not a
    # false claim that softmax probabilities are measured five-card ownership.
    rng = random.Random(115)
    center = mean(p.mean for p in projections)
    scale = max(1, math.sqrt(mean((p.mean - center) ** 2 for p in projections)))
    counts: Counter[int] = Counter()
    for _ in range(1000):
        ranked = sorted(
            projections,
            key=lambda p: (
                math.log(max(rng.random(), 1e-12))
                / math.exp(max(-10, min(10, (p.mean - center) / scale)))
            ),
            reverse=True,
        )
        counts.update(p.player_id for p in ranked[:5])
    estimated = {p.player_id: counts[p.player_id] / 1000 for p in projections}
    return estimated, {pid: "estimated_projection_softmax" for pid in estimated}


def optimize(
    slate: Slate,
    projections: Sequence[Projection],
    *,
    decision_at: datetime,
    scoring_policy: ScoringPolicy,
    config: OptimizerConfig | None = None,
    field: FieldObservation | None = None,
) -> Recommendation:
    slate.assert_prelock(decision_at)
    cfg = config or OptimizerConfig()
    candidates = {p.player_id: p for p in slate.candidates}
    if any(candidate.card_boost > 3 for candidate in slate.candidates):
        raise ValueError("player_boost_out_of_range")
    if len({p.player_id for p in projections}) != len(projections):
        raise ValueError("duplicate_projection")
    if {p.player_id for p in projections} != set(candidates):
        raise ValueError("projection_pool_mismatch")
    eligible = [p for p in projections if p.availability_probability > 0]
    if len(eligible) < 5:
        raise ValueError("fewer_than_five_available_candidates")
    if any(not p.samples for p in eligible):
        raise ValueError("missing_distribution")
    by_id = {p.player_id: p for p in eligible}
    ownership, ownership_source = _ownership(eligible, field, decision_at)
    slots = slate.contest.slot_multipliers
    scores = {
        p.player_id: tuple(
            mean(
                scoring_policy.score(v, slot, candidates[p.player_id].card_boost) for v in p.samples
            )
            * p.availability_probability
            for slot in slots
        )
        for p in eligible
    }
    # Preserve the configured request in the report.  Feasibility is resolved
    # below against the actual slate cardinalities, so a one-team slate is
    # visibly a relaxed request rather than an apparently satisfied request.
    requested_teams = cfg.min_distinct_teams
    requested_games = cfg.min_distinct_games

    def search(teams: int, games: int) -> list[tuple[float, tuple[int, ...]]]:
        exact = _exact_search(
            eligible,
            candidates,
            scores,
            teams_required=teams,
            games_required=games,
        )
        if exact:
            return exact
        beam: list[tuple[float, tuple[int, ...]]] = [(0, ())]
        for slot in range(5):
            expanded = []
            for value, ids in beam:
                for p in eligible:
                    if p.player_id in ids:
                        continue
                    new = (*ids, p.player_id)
                    remaining = 4 - slot
                    if len({candidates[i].team_id for i in new}) + remaining < teams:
                        continue
                    if len({candidates[i].game_id for i in new}) + remaining < games:
                        continue
                    expanded.append((value + scores[p.player_id][slot], new))
            # Preserve a beam for each diversity signature so a strong single
            # team cannot evict every feasible multi-team completion.
            expanded.sort(key=lambda item: (-item[0], item[1]))
            groups: dict[tuple[int, int], list[tuple[float, tuple[int, ...]]]] = {}
            for item in expanded:
                signature = (
                    len({candidates[i].team_id for i in item[1]}),
                    len({candidates[i].game_id for i in item[1]}),
                )
                group = groups.setdefault(signature, [])
                if len(group) < cfg.beam_width:
                    group.append(item)
            beam = [item for group in groups.values() for item in group]
        return sorted(beam, key=lambda item: (-item[0], item[1]))

    # Team and game diversity are independent constraints. Search all relaxed
    # pairs in order of total shortfall so one infeasible dimension does not
    # silently force the other dimension down as well.
    pairs = [
        (teams, games)
        for teams in range(requested_teams, 0, -1)
        for games in range(requested_games, 0, -1)
    ]
    pairs.sort(
        key=lambda pair: (
            (requested_teams - pair[0]) + (requested_games - pair[1]),
            requested_teams - pair[0],
            requested_games - pair[1],
        )
    )
    target_teams, target_games, beam = requested_teams, requested_games, []
    for teams, games in pairs:
        candidate_beam = search(teams, games)
        if candidate_beam:
            target_teams, target_games, beam = teams, games, candidate_beam
            break
    if not beam:
        raise ValueError("optimizer_no_feasible_lineup")
    baseline_ids = tuple(
        p.player_id for p in sorted(eligible, key=lambda p: (-p.mean, p.player_id))[:5]
    )
    baseline_score = sum(scores[pid][slot] for slot, pid in enumerate(baseline_ids))
    rng = random.Random(cfg.seed)
    trials: list[dict[int, float]] = []
    field_scores = []
    for _ in range(cfg.simulations):
        shocks = {g.game_id: rng.gauss(0, 1) for g in slate.games}
        values = {}
        for p in eligible:
            z = math.sqrt(cfg.game_correlation) * shocks[candidates[p.player_id].game_id]
            z += math.sqrt(1 - cfg.game_correlation) * rng.gauss(0, 1)
            percentile = 0.5 * (1 + math.erf(z / math.sqrt(2)))
            samples = sorted(p.samples)
            values[p.player_id] = (
                samples[min(len(samples) - 1, int(percentile * len(samples)))]
                if rng.random() < p.availability_probability
                else 0.0
            )
        trials.append(values)
        field_selected = sorted(
            eligible,
            key=lambda p: math.log(max(rng.random(), 1e-12)) / max(0.001, ownership[p.player_id]),
            reverse=True,
        )[:5]
        field_selected.sort(key=lambda p: -p.mean)
        field_scores.append(
            sum(
                scoring_policy.score(
                    values[p.player_id], slots[i], candidates[p.player_id].card_boost
                )
                for i, p in enumerate(field_selected)
            )
        )

    def evaluate(ids: tuple[int, ...]) -> tuple[float, float]:
        simulations = [
            sum(
                scoring_policy.score(values[pid], slots[i], candidates[pid].card_boost)
                for i, pid in enumerate(ids)
            )
            for values in trials
        ]
        p90 = sorted(simulations)[int(0.9 * (len(simulations) - 1))]
        wins = mean(
            float(a > b) + 0.5 * float(a == b)
            for a, b in zip(simulations, field_scores, strict=True)
        )
        return p90, wins

    # Total Value is the sole production objective. Simulations remain
    # descriptive diagnostics and never select a different lineup.
    chosen = (beam[0][0], beam[0][1], *evaluate(beam[0][1]))
    expected, ids, p90, wins = chosen
    return Recommendation(
        picks=tuple(
            Pick(
                player_id=pid,
                game_id=candidates[pid].game_id,
                team_id=candidates[pid].team_id,
                name=candidates[pid].name,
                position=candidates[pid].position,
                team=candidates[pid].team,
                opponent=candidates[pid].opponent,
                slot=i + 1,
                slot_multiplier=slots[i],
                card_boost=candidates[pid].card_boost,
                projected_value=by_id[pid].mean,
                projected_score=scores[pid][i],
                uncertainty=by_id[pid].stddev,
                ownership=ownership[pid],
                ownership_source=ownership_source[pid],
            )
            for i, pid in enumerate(ids)
        ),
        objective=cfg.objective,
        objective_value=expected,
        total_value=expected,
        total_value_baseline=baseline_score,
        expected_score=expected,
        expected_score_baseline=baseline_score,
        simulated_p90=p90,
        simulated_field_win_rate=wins,
        requested_distinct_teams=requested_teams,
        required_distinct_teams=target_teams,
        requested_distinct_games=requested_games,
        required_distinct_games=target_games,
        diversity_relaxed=(target_teams < requested_teams or target_games < requested_games),
        candidate_count=len(eligible),
        scoring_policy=scoring_policy,
        assumptions=(
            "exact_binary_assignment_when_scipy_is_available_else_bounded_beam_fallback",
            "game_correlation_is_configured_sensitivity_not_fitted",
            "field_win_rate_against_simulated_opponent_not_payout_probability",
            "total_value_is_expected_sum_of_committed_slot_and_player_multipliers",
            "simulation_metrics_are_diagnostics_and_do_not_reassign_the_frozen_lineup",
        ),
    )
