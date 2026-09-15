"""Defense eligibility: pool and optimizer must not silently exclude DL/LB/DB.

Week-1 operator observation (#168): zero defensive players in any lineup.
This test pins the structural claim that defenders remain in the candidate
pool and win optimize when their projected value dominates. It does not
claim week-1 actuals were wrong or right; it closes the "feature/pool bug
excluding defense" branch with a reproducible assert.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nfl_oracle.recommendations.model import HistoricalPerformance, fit_model, predict
from nfl_oracle.recommendations.optimizer import optimize
from nfl_oracle.recommendations.pipeline import ScoringPolicy
from nfl_oracle.recommendations.schema import Candidate, Contest, EvidenceClock, Game, Slate

BASE = datetime(2026, 9, 1, 12, tzinfo=UTC)
POSITIONS = ("QB", "RB", "WR", "TE", "K", "DL", "LB", "DB")
DEFENSE = frozenset({"DL", "LB", "DB"})


def _history(players: int, *, defense_value: float, other_value: float) -> list[HistoricalPerformance]:
    rows: list[HistoricalPerformance] = []
    for week in range(6):
        kickoff = BASE + timedelta(days=week)
        for player in range(1, players + 1):
            position = POSITIONS[player % len(POSITIONS)]
            value = defense_value if position in DEFENSE else other_value
            rows.append(
                HistoricalPerformance(
                    player_id=player,
                    external_id=f"p-{player}",
                    game_id=100_000 + week * 1000 + player,
                    position=position,
                    kickoff_at=kickoff,
                    available_at=kickoff + timedelta(hours=2),
                    captured_at=kickoff + timedelta(hours=3),
                    value=value,
                    did_not_play=False,
                )
            )
    return rows


def _slate(decision: datetime, *, games: int = 4, per_team: int = 8) -> Slate:
    clock = EvidenceClock(source_available_at=decision, captured_at=decision)
    built_games: list[Game] = []
    candidates: list[Candidate] = []
    player_id = 0
    for index in range(games):
        game = Game(
            game_id=19_000 + index,
            season=2026,
            kickoff_at=decision + timedelta(hours=4 + index),
            home_team_id=index * 2 + 1,
            away_team_id=index * 2 + 2,
            home_team=f"H{index}",
            away_team=f"A{index}",
            status="scheduled",
        )
        built_games.append(game)
        for side in range(2):
            for _ in range(per_team):
                player_id += 1
                candidates.append(
                    Candidate(
                        player_id=player_id,
                        game_id=game.game_id,
                        team_id=game.home_team_id if side == 0 else game.away_team_id,
                        name=f"P{player_id}",
                        position=POSITIONS[player_id % len(POSITIONS)],
                        team=game.home_team if side == 0 else game.away_team,
                        opponent=game.away_team if side == 0 else game.home_team,
                        injury_status="Active",
                        card_boost=0,
                        clock=clock,
                    )
                )
    return Slate(
        contest=Contest(
            contest_id=2154,
            day=decision.date(),
            end_day=decision.date(),
            slot_multipliers=(2, 1.8, 1.6, 1.4, 1.2),
            is_locked=False,
            is_finalized=False,
            clock=clock,
            evidence_sha256="a" * 64,
        ),
        games=tuple(built_games),
        candidates=tuple(candidates),
        captured_at=decision,
        source_hashes=("b" * 64,),
        pool_roster_count=len(candidates),
        pool_search_matched_count=len(candidates),
    )


def test_defense_candidates_remain_in_projection_pool() -> None:
    decision = BASE + timedelta(days=8)
    slate = _slate(decision)
    history = _history(len(slate.candidates), defense_value=2.0, other_value=2.0)
    model = fit_model(history, trained_at=decision)
    projections = predict(slate, model, history, decision_at=decision)
    by_id = {c.player_id: c for c in slate.candidates}

    assert len(projections) == len(slate.candidates)
    defense_ids = {c.player_id for c in slate.candidates if c.position in DEFENSE}
    assert defense_ids
    projected_ids = {p.player_id for p in projections}
    assert defense_ids <= projected_ids
    assert all(by_id[p.player_id].position for p in projections)


def test_defense_selected_when_projected_value_dominates() -> None:
    """If defense EV dominates, optimize must be willing to pick defenders.

    Under total_value with no position quota, an all-defense five-card lineup
    is a legal outcome when those players clear the value bar. A regression
    that silently drops DL/LB/DB from eligibility would fail this assert.
    """

    decision = BASE + timedelta(days=8)
    slate = _slate(decision)
    history = _history(len(slate.candidates), defense_value=9.0, other_value=1.5)
    model = fit_model(history, trained_at=decision)
    projections = predict(slate, model, history, decision_at=decision)
    recommendation = optimize(
        slate,
        projections,
        decision_at=decision,
        scoring_policy=ScoringPolicy(),
    )

    assert len(recommendation.picks) == 5
    defense_picks = [p for p in recommendation.picks if p.position in DEFENSE]
    assert len(defense_picks) == 5, (
        "expected all five picks to be defense when defense history dominates; "
        f"got {[p.position for p in recommendation.picks]}"
    )
