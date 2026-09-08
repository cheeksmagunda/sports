from __future__ import annotations

from datetime import UTC, datetime, timedelta
from statistics import mean

import pytest

from nfl_oracle.recommendations.model import HistoricalPerformance, fit_model, predict
from nfl_oracle.recommendations.schema import Candidate, Contest, EvidenceClock, Game, Slate

BASE = datetime(2025, 9, 1, 12, tzinfo=UTC)


def rows(*, dnp_player: int | None = None, ambiguous: bool = False) -> list[HistoricalPerformance]:
    result: list[HistoricalPerformance] = []
    for game in range(6):
        kickoff = BASE + timedelta(days=game)
        for player in range(1, 7):
            result.append(
                HistoricalPerformance(
                    player_id=player,
                    external_id=("same" if ambiguous else f"p-{player}"),
                    game_id=1000 + game * 10 + player,
                    position="WR",
                    kickoff_at=kickoff,
                    available_at=kickoff + timedelta(hours=2),
                    captured_at=kickoff + timedelta(hours=3),
                    value=float(player + game),
                    did_not_play=dnp_player == player and game == 0,
                )
            )
    return result


def target_slate() -> Slate:
    decision = BASE + timedelta(days=8)
    clock = EvidenceClock(source_available_at=decision, captured_at=decision)
    game = Game(
        game_id=9000,
        season=2025,
        kickoff_at=decision + timedelta(hours=4),
        home_team_id=10,
        away_team_id=11,
        home_team="A",
        away_team="B",
        status="scheduled",
    )
    candidates = tuple(
        Candidate(
            player_id=player,
            game_id=game.game_id,
            team_id=10 if player % 2 else 11,
            name=f"P{player}",
            position="WR",
            team="A" if player % 2 else "B",
            opponent="B" if player % 2 else "A",
            injury_status="Active",
            card_boost=0,
            clock=clock,
        )
        for player in range(1, 7)
    )
    return Slate(
        contest=Contest(
            contest_id=1,
            day=decision.date(),
            end_day=decision.date(),
            slot_multipliers=(2, 1.8, 1.6, 1.4, 1.2),
            is_locked=False,
            is_finalized=False,
            clock=clock,
            evidence_sha256="a" * 64,
        ),
        games=(game,),
        candidates=candidates,
        captured_at=decision,
        source_hashes=("b" * 64,),
        pool_roster_count=6,
        pool_search_matched_count=6,
    )


def test_residual_draws_are_centered_on_conditional_mean() -> None:
    model = fit_model(rows(), trained_at=BASE + timedelta(days=8))
    projections = predict(target_slate(), model, rows(), decision_at=BASE + timedelta(days=8))
    for projection in projections:
        assert mean(projection.samples) == pytest.approx(projection.conditional_mean)
        assert f"real_value_chronological_{model.selected_estimator}" in projection.provenance


def test_dnp_is_availability_evidence_and_not_a_second_performance_zero() -> None:
    history = rows(dnp_player=1)
    model = fit_model(history, trained_at=BASE + timedelta(days=8))
    projection = predict(target_slate(), model, history, decision_at=BASE + timedelta(days=8))[0]
    assert projection.availability_probability < 1
    assert projection.conditional_mean > 0
    assert "historical_did_not_play_rate" in projection.provenance


def test_stable_identity_aliases_across_disjoint_games_are_allowed() -> None:
    history = rows()
    history = [
        row
        for row in history
        if not (row.player_id == 1 and row.game_id >= 1030)
        and not (row.player_id == 2 and row.game_id < 1030)
    ]
    history = [
        row.model_copy(update={"external_id": "stable-1"}) if row.player_id in {1, 2} else row
        for row in history
    ]
    model = fit_model(history, trained_at=BASE + timedelta(days=10))
    assert model.training_rows == 30


def test_same_stable_identity_game_fails_closed() -> None:
    history = rows()
    history = [
        row.model_copy(update={"external_id": "p-1", "game_id": row.game_id - 1})
        if row.player_id == 2
        else row
        for row in history
    ]
    with pytest.raises(ValueError, match="duplicate_stable_identity_game"):
        fit_model(history, trained_at=BASE + timedelta(days=10))


def test_real_identity_switching_stable_ids_fails_closed() -> None:
    history = rows()
    history[0] = history[0].model_copy(update={"external_id": "other-stable"})
    with pytest.raises(ValueError, match="conflicting_external_identity"):
        fit_model(history, trained_at=BASE + timedelta(days=10))
