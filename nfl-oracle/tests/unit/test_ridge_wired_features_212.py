"""Issue #212: activate ridge when context is wired; offline pick attribution."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nfl_oracle.recommendations.model import (
    HistoricalPerformance,
    feature_contribution_rows,
    fit_model,
    predict,
)
from nfl_oracle.recommendations.schema import Candidate, Contest, EvidenceClock, Game, Slate

BASE = datetime(2024, 9, 1, 17, tzinfo=UTC)


def _row(
    player_id: int,
    game_id: int,
    day: int,
    value: float,
    *,
    position: str = "WR",
    context: dict[str, float] | None = None,
) -> HistoricalPerformance:
    kick = BASE + timedelta(days=day)
    return HistoricalPerformance(
        player_id=player_id,
        external_id=f"gsis-{player_id}",
        game_id=game_id,
        position=position,
        role=position,
        kickoff_at=kick,
        available_at=kick + timedelta(hours=4),
        captured_at=kick + timedelta(hours=5),
        value=value,
        opportunity=4.0 + value / 10.0,
        context_features=context or {},
        context_clock=EvidenceClock(
            source_available_at=kick - timedelta(hours=1),
            captured_at=kick - timedelta(minutes=30),
        )
        if context
        else None,
        context_evidence_mode="retrospective_reconstructed" if context else "prospective",
    )


def _history_with_context() -> list[HistoricalPerformance]:
    rows: list[HistoricalPerformance] = []
    game = 1
    for week in range(1, 12):
        for player, pos, base in (
            (1, "WR", 12.0),
            (2, "RB", 10.0),
            (3, "QB", 14.0),
            (4, "TE", 8.0),
            (5, "WR", 9.0),
            (6, "RB", 7.0),
        ):
            ctx = {
                "team_pace_prior": 0.4 + (player % 3) * 0.05,
                "opponent_pace_prior": 0.35,
                "depth_rank": float(1 + (player % 2)),
                "is_divisional": float(week % 4 == 0),
            }
            rows.append(
                _row(
                    player,
                    game,
                    week,
                    base + week * 0.15 + player * 0.2,
                    position=pos,
                    context=ctx,
                )
            )
            game += 1
    return rows


def _slate(decision: datetime) -> Slate:
    clock = EvidenceClock(source_available_at=decision, captured_at=decision)
    game = Game(
        game_id=9001,
        season=2024,
        kickoff_at=decision + timedelta(hours=6),
        home_team_id=1,
        away_team_id=2,
        home_team="KC",
        away_team="BUF",
        status="scheduled",
    )
    candidates = tuple(
        Candidate(
            player_id=player,
            game_id=game.game_id,
            team_id=1 if player % 2 else 2,
            name=f"P{player}",
            position=pos,
            team="KC" if player % 2 else "BUF",
            opponent="BUF" if player % 2 else "KC",
            injury_status="Active",
            card_boost=0,
            clock=clock,
        )
        for player, pos in ((1, "WR"), (2, "RB"), (3, "QB"), (4, "TE"), (5, "WR"), (6, "RB"))
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


def test_wired_context_forces_ridge_even_if_player_prior_wins_holdout() -> None:
    model = fit_model(_history_with_context(), trained_at=BASE + timedelta(days=20))
    assert model.context_feature_names
    assert model.selected_estimator == "ridge"
    assert model.evaluation["selected_estimator"] == "ridge"
    assert "holdout_winner" in model.evaluation
    assert len(model.coefficients) == len(model.feature_names) + 2 * len(
        model.context_feature_names
    )
    core = dict(
        zip(
            model.feature_names,
            model.coefficients[: len(model.feature_names)],
            strict=True,
        )
    )
    assert not (
        core["intercept"] == 0.0
        and core["player_mean_shrunk"] == 1.0
        and core["recent_mean_shrunk"] == 0.0
        and core["position_mean"] == 0.0
    )


def test_feature_contributions_prefer_signals_not_appearance_count() -> None:
    model = fit_model(_history_with_context(), trained_at=BASE + timedelta(days=20))
    values = [1.0, 10.0, 9.0, 8.0, 0.0, 2.0, 0.1]
    for _name in model.context_feature_names:
        values.extend([0.5, 0.0])
    rows = feature_contribution_rows(model, values, top_n=8)
    assert rows
    assert all(
        row["feature"] != "prior_log_count" or float(row["contribution"]) == 0.0 for row in rows
    )


def test_predict_attaches_offline_why_this_pick_contributions() -> None:
    history = _history_with_context()
    model = fit_model(history, trained_at=BASE + timedelta(days=20))
    decision = BASE + timedelta(days=21)
    projections = predict(_slate(decision), model, history, decision_at=decision)
    assert projections
    assert projections[0].feature_contributions
    assert projections[0].feature_contributions[0]["feature"]
