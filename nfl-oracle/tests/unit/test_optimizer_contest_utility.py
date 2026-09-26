"""Contest-utility selection: field_weight / upside_weight wire into picks (#400)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nfl_oracle.recommendations.model import Projection
from nfl_oracle.recommendations.optimizer import (
    FieldObservation,
    OptimizerConfig,
    ScoringPolicy,
    contest_utility,
    optimize,
)
from nfl_oracle.recommendations.schema import (
    Candidate,
    Contest,
    EvidenceClock,
    Game,
    Slate,
)

BASE = datetime(2025, 9, 1, 12, tzinfo=UTC)
DECISION = BASE + timedelta(days=8)
CLOCK = EvidenceClock(source_available_at=DECISION, captured_at=DECISION)
SLOTS = (2.0, 1.8, 1.6, 1.4, 1.2)


def test_contest_utility_formula_is_documented_linear_mix() -> None:
    # U = E + upside_weight * p90 + field_weight * E * (field_beat - mean_own)
    assert contest_utility(
        10.0, 20.0, 0.5, upside_weight=0.15, field_weight=0.1, mean_ownership=0.2
    ) == (10.0 + 0.15 * 20.0 + 0.1 * 10.0 * 0.5 - 0.1 * 10.0 * 0.2)
    assert contest_utility(10.0, 20.0, 0.5, upside_weight=0.0, field_weight=0.0) == 10.0


def _game(game_id: int, home: int, away: int) -> Game:
    return Game(
        game_id=game_id,
        season=2025,
        kickoff_at=DECISION + timedelta(hours=4),
        home_team_id=home,
        away_team_id=away,
        home_team=f"H{home}",
        away_team=f"A{away}",
        status="scheduled",
    )


def _candidate(
    player_id: int,
    *,
    game_id: int,
    team_id: int,
    boost: float = 0.0,
) -> Candidate:
    return Candidate(
        player_id=player_id,
        game_id=game_id,
        team_id=team_id,
        name=f"P{player_id}",
        position="WR",
        team=f"T{team_id}",
        opponent="OPP",
        injury_status="Active",
        card_boost=boost,
        clock=CLOCK,
    )


def _projection(
    player_id: int,
    mean: float,
    samples: tuple[float, ...],
) -> Projection:
    return Projection(
        player_id=player_id,
        mean=mean,
        conditional_mean=mean,
        stddev=max(0.01, (max(samples) - min(samples)) / 2),
        availability_probability=1.0,
        prior_games=5,
        samples=samples,
        provenance=("test",),
    )


def _slate(candidates: tuple[Candidate, ...], games: tuple[Game, ...]) -> Slate:
    return Slate(
        contest=Contest(
            contest_id=900,
            day=DECISION.date(),
            end_day=DECISION.date(),
            slot_multipliers=SLOTS,
            is_locked=False,
            is_finalized=False,
            clock=CLOCK,
            evidence_sha256="a" * 64,
        ),
        games=games,
        candidates=candidates,
        captured_at=DECISION,
        source_hashes=("b" * 64,),
        pool_roster_count=len(candidates),
        pool_search_matched_count=len(candidates),
    )


def _field(player_counts: dict[int, int], entry_count: int) -> FieldObservation:
    return FieldObservation(
        clock=CLOCK,
        entry_count=entry_count,
        player_counts=player_counts,
        provenance="test_measured",
        coverage="complete",
    )


def _pick_ids(result) -> set[int]:
    return {p.player_id for p in result.picks}


def test_raising_field_weight_prefers_lower_owned_portfolio() -> None:
    """Raising field_weight changes the selected set when ownership differs."""
    games = tuple(_game(200 + i, 10 + 2 * i, 11 + 2 * i) for i in range(5))
    chalk = tuple(
        _candidate(i, game_id=200 + (i - 1), team_id=10 + 2 * (i - 1)) for i in range(1, 6)
    )
    contrarian = tuple(
        _candidate(i, game_id=200 + (i - 6), team_id=11 + 2 * (i - 6)) for i in range(6, 11)
    )
    slate = _slate(chalk + contrarian, games)
    chalk_samples = (9.7, 9.8, 9.9, 10.0, 10.0, 10.1, 10.2, 10.3)
    contra_samples = (3.0, 4.0, 5.0, 9.0, 13.0, 14.0, 15.0, 16.0)
    chalk_mean = sum(chalk_samples) / len(chalk_samples)
    contra_mean = sum(contra_samples) / len(contra_samples)
    assert chalk_mean > contra_mean
    projections = tuple(
        [
            *[_projection(i, mean=chalk_mean, samples=chalk_samples) for i in range(1, 6)],
            *[_projection(i, mean=contra_mean, samples=contra_samples) for i in range(6, 11)],
        ]
    )
    field = _field({1: 20, 2: 20, 3: 20, 4: 20, 5: 20, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0}, 20)

    baseline = optimize(
        slate,
        projections,
        decision_at=DECISION,
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(
            field_weight=0.0,
            upside_weight=0.0,
            simulations=200,
            min_distinct_teams=3,
            min_distinct_games=2,
            seed=7,
        ),
        field=field,
    )
    leveraged = optimize(
        slate,
        projections,
        decision_at=DECISION,
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(
            field_weight=2.0,
            upside_weight=0.0,
            simulations=200,
            min_distinct_teams=3,
            min_distinct_games=2,
            seed=7,
        ),
        field=field,
    )
    assert _pick_ids(baseline) == {1, 2, 3, 4, 5}
    assert _pick_ids(leveraged) == {6, 7, 8, 9, 10}
    assert (
        "selection_maximizes_contest_utility_E_upside_p90_field_beat_minus_ownership"
        in baseline.assumptions
    )


def test_raising_upside_weight_prefers_higher_p90_when_means_tied() -> None:
    """Raising upside_weight prefers the higher-p90 portfolio when E is tied."""
    games = tuple(_game(200 + i, 10 + 2 * i, 11 + 2 * i) for i in range(5))
    flat = tuple(
        _candidate(i, game_id=200 + (i - 1), team_id=10 + 2 * (i - 1)) for i in range(1, 6)
    )
    upside = tuple(
        _candidate(i, game_id=200 + (i - 6), team_id=11 + 2 * (i - 6)) for i in range(6, 11)
    )
    slate = _slate(flat + upside, games)
    flat_mean = 8.0
    upside_samples = (0.0, 0.0, 0.0, 0.0, 0.0, 8.0, 8.0, 16.0, 16.0, 32.0)
    assert sum(upside_samples) / len(upside_samples) == flat_mean
    projections = tuple(
        [
            *[_projection(i, mean=flat_mean, samples=(flat_mean,) * 10) for i in range(1, 6)],
            *[_projection(i, mean=flat_mean, samples=upside_samples) for i in range(6, 11)],
        ]
    )
    field = _field({i: 10 for i in range(1, 11)}, entry_count=20)

    no_upside = optimize(
        slate,
        projections,
        decision_at=DECISION,
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(
            field_weight=0.0,
            upside_weight=0.0,
            simulations=300,
            min_distinct_teams=3,
            min_distinct_games=2,
            seed=11,
            game_correlation=0.0,
        ),
        field=field,
    )
    with_upside = optimize(
        slate,
        projections,
        decision_at=DECISION,
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(
            field_weight=0.0,
            upside_weight=2.0,
            simulations=300,
            min_distinct_teams=3,
            min_distinct_games=2,
            seed=11,
            game_correlation=0.0,
        ),
        field=field,
    )
    assert _pick_ids(no_upside) == {1, 2, 3, 4, 5}
    assert _pick_ids(with_upside) == {6, 7, 8, 9, 10}
    assert with_upside.simulated_p90 > no_upside.simulated_p90


def test_chalk_studs_win_when_omitting_them_collapses_expected_score() -> None:
    """Contrarian leverage does not discard studs when E collapses irreparably."""
    games = tuple(_game(200 + i, 10 + 2 * i, 11 + 2 * i) for i in range(5))
    studs = tuple(
        _candidate(i, game_id=200 + (i - 1), team_id=10 + 2 * (i - 1)) for i in range(1, 6)
    )
    fillers = tuple(
        _candidate(i, game_id=200 + (i - 6), team_id=11 + 2 * (i - 6)) for i in range(6, 11)
    )
    slate = _slate(studs + fillers, games)
    projections = tuple(
        [
            *[_projection(i, mean=20.0, samples=(20.0,) * 8) for i in range(1, 6)],
            *[_projection(i, mean=4.0, samples=(4.0,) * 8) for i in range(6, 11)],
        ]
    )
    field = _field({1: 20, 2: 20, 3: 20, 4: 20, 5: 20, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0}, 20)

    result = optimize(
        slate,
        projections,
        decision_at=DECISION,
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(
            field_weight=2.0,
            upside_weight=2.0,
            simulations=200,
            min_distinct_teams=3,
            min_distinct_games=2,
            seed=3,
        ),
        field=field,
    )
    assert _pick_ids(result) == {1, 2, 3, 4, 5}
