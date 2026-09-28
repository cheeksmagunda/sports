"""Position caps and slot-by-mean ordering for research arms (#603).

Serving defaults (one K, one defender, slot-by-mean) landed via #616/#617.
These tests pin the research overrides: 0 disables a cap; slot_by_mean flips
ordering. They do not change live Railway knobs.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nfl_oracle.recommendations.model import Projection
from nfl_oracle.recommendations.optimizer import OptimizerConfig, ScoringPolicy, optimize
from nfl_oracle.recommendations.schema import Candidate, Contest, EvidenceClock, Game, Slate

DECISION = datetime(2026, 9, 20, 16, tzinfo=UTC)
DEFENSE = frozenset({"DL", "LB", "DB"})


def _projection(
    player_id: int, mean: float, samples: tuple[float, ...] | None = None
) -> Projection:
    drawn = samples if samples is not None else (mean - 0.2, mean, mean + 0.2)
    return Projection(
        player_id=player_id,
        mean=mean,
        conditional_mean=mean,
        stddev=0.2,
        availability_probability=1.0,
        prior_games=4,
        samples=drawn,
        provenance=("test",),
    )


def _slate(
    specs: list[tuple[int, str, float, float]],
    samples_by_id: dict[int, tuple[float, ...]] | None = None,
) -> tuple[Slate, tuple[Projection, ...]]:
    clock = EvidenceClock(source_available_at=DECISION, captured_at=DECISION)
    games = []
    candidates = []
    projections = []
    for index, (player_id, position, mean, boost) in enumerate(specs):
        game = Game(
            game_id=5000 + index,
            season=2026,
            kickoff_at=DECISION + timedelta(hours=4),
            home_team_id=100 + index,
            away_team_id=200 + index,
            home_team=f"H{index}",
            away_team=f"A{index}",
            status="scheduled",
        )
        games.append(game)
        candidates.append(
            Candidate(
                player_id=player_id,
                game_id=game.game_id,
                team_id=game.home_team_id,
                name=f"P{player_id}",
                position=position,
                team=game.home_team,
                opponent=game.away_team,
                injury_status="Active",
                card_boost=boost,
                clock=clock,
            )
        )
        projections.append(_projection(player_id, mean, (samples_by_id or {}).get(player_id)))
    slate = Slate(
        contest=Contest(
            contest_id=603,
            day=DECISION.date(),
            end_day=DECISION.date(),
            slot_multipliers=(2.0, 1.8, 1.6, 1.4, 1.2),
            is_locked=False,
            is_finalized=False,
            clock=clock,
            evidence_sha256="c" * 64,
        ),
        games=tuple(games),
        candidates=tuple(candidates),
        captured_at=DECISION,
        source_hashes=("d" * 64,),
        pool_roster_count=len(candidates),
        pool_search_matched_count=len(candidates),
    )
    return slate, tuple(projections)


def _config(**overrides: object) -> OptimizerConfig:
    # Research baseline: uncapped joint slots. Serving defaults differ (#616/#617).
    base: dict[str, object] = {
        "simulations": 100,
        "min_distinct_teams": 1,
        "min_distinct_games": 1,
        "profile": "max_value",
        "upside_weight": 0.0,
        "field_weight": 0.0,
        "max_defenders": 0,
        "max_kickers": 0,
        "slot_by_mean": False,
    }
    base.update(overrides)
    return OptimizerConfig(**base)  # type: ignore[arg-type]


def test_max_one_defender_and_kicker_when_those_positions_dominate() -> None:
    specs = [
        (1, "DL", 30.0, 0.0),
        (2, "LB", 29.0, 0.0),
        (3, "DB", 28.0, 0.0),
        (4, "K", 27.0, 0.0),
        (5, "K", 26.0, 0.0),
        (6, "WR", 10.0, 0.0),
        (7, "RB", 9.0, 0.0),
        (8, "QB", 8.0, 0.0),
    ]
    slate, projections = _slate(specs)
    capped = optimize(
        slate,
        projections,
        decision_at=DECISION,
        scoring_policy=ScoringPolicy(),
        config=_config(max_defenders=1, max_kickers=1),
    )
    positions = [pick.position for pick in capped.picks]
    assert sum(position in DEFENSE for position in positions) <= 1
    assert sum(position == "K" for position in positions) <= 1
    assert "max_defenders=1" in capped.assumptions
    assert "max_kickers=1" in capped.assumptions

    open_lineup = optimize(
        slate,
        projections,
        decision_at=DECISION,
        scoring_policy=ScoringPolicy(),
        config=_config(),
    )
    open_positions = [pick.position for pick in open_lineup.picks]
    assert sum(position in DEFENSE or position == "K" for position in open_positions) == 5


def test_slot_by_mean_orders_descending_projected_mean() -> None:
    # Sample means invert Projection.mean so the joint slot score and the
    # mean sort disagree. Additive boosts alone cannot do that.
    specs = [
        (1, "WR", 10.0, 0.0),
        (2, "RB", 8.0, 0.0),
        (3, "QB", 6.0, 0.0),
        (4, "TE", 4.0, 0.0),
        (5, "WR", 2.0, 0.0),
        (6, "RB", 1.0, 0.0),
    ]
    samples = {
        1: (1.0, 1.0, 1.0),
        2: (2.0, 2.0, 2.0),
        3: (3.0, 3.0, 3.0),
        4: (4.0, 4.0, 4.0),
        5: (9.0, 9.0, 9.0),
        6: (8.0, 8.0, 8.0),
    }
    slate, projections = _slate(specs, samples)
    joint = optimize(
        slate,
        projections,
        decision_at=DECISION,
        scoring_policy=ScoringPolicy(),
        config=_config(slot_by_mean=False),
    )
    ordered = optimize(
        slate,
        projections,
        decision_at=DECISION,
        scoring_policy=ScoringPolicy(),
        config=_config(slot_by_mean=True),
    )
    means = [pick.projected_value for pick in ordered.picks]
    assert means == sorted(means, reverse=True)
    assert ordered.picks[0].projected_value == max(pick.projected_value for pick in ordered.picks)
    assert "committed_slots_follow_descending_projected_mean" in ordered.assumptions
    assert [pick.player_id for pick in joint.picks] != [pick.player_id for pick in ordered.picks]
