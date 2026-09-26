"""Issue #418: canonical injury/weather context slots always in fit and predict."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nfl_oracle.features.live import (
    canonical_live_context_feature_names,
    injury_indicator_features,
)
from nfl_oracle.recommendations.model import (
    ContextAdjustment,
    FitConfig,
    HistoricalPerformance,
    RatingModel,
    fit_model,
    predict,
)
from nfl_oracle.recommendations.schema import Candidate, Contest, EvidenceClock, Game, Slate

BASE = datetime(2025, 9, 1, 12, tzinfo=UTC)


def _minimal_history(*, context: dict[str, float] | None = None) -> list[HistoricalPerformance]:
    rows: list[HistoricalPerformance] = []
    ctx = context or {"weather_index": 0.5}
    clock = EvidenceClock(
        source_available_at=BASE - timedelta(hours=2),
        captured_at=BASE - timedelta(hours=1),
    )
    for game in range(6):
        kickoff = BASE + timedelta(days=game)
        for player in range(1, 7):
            rows.append(
                HistoricalPerformance(
                    player_id=player,
                    game_id=100 + game,
                    position="WR",
                    role="receiving",
                    kickoff_at=kickoff,
                    available_at=kickoff + timedelta(hours=2),
                    captured_at=kickoff + timedelta(hours=3),
                    value=float(player + game),
                    opportunity=float(player + game),
                    context_features=dict(ctx),
                    context_clock=clock,
                )
            )
    return rows


def test_fit_always_reserves_canonical_injury_weather_context_names() -> None:
    model = fit_model(_minimal_history(), trained_at=BASE + timedelta(days=10))
    canonical = set(canonical_live_context_feature_names())
    assert canonical <= set(model.context_feature_names)
    assert "injury_questionable" in model.context_feature_names
    assert "weather_temp_f" in model.context_feature_names
    assert len(model.coefficients) == len(model.feature_names) + 2 * len(
        model.context_feature_names
    )


def _synthetic_model(*, context_coef_overrides: dict[str, float]) -> RatingModel:
    names = canonical_live_context_feature_names()
    coef: list[float] = [10.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    for name in names:
        coef.append(context_coef_overrides.get(name, 0.0))
        coef.append(0.0)
    return RatingModel(
        trained_at=BASE + timedelta(days=7),
        fit_config=FitConfig(),
        training_fingerprint="418-test",
        training_rows=36,
        coefficients=tuple(coef),
        residuals=(0.0, 0.0),
        evaluation={"kind": "test"},
        context_feature_names=names,
        selected_estimator="ridge",
    )


def _slate_for_player(*, injury_status: str, decision: datetime) -> Slate:
    clock = EvidenceClock(source_available_at=decision, captured_at=decision)
    game = Game(
        game_id=200,
        season=2025,
        kickoff_at=decision + timedelta(hours=4),
        home_team_id=10,
        away_team_id=11,
        home_team="A",
        away_team="B",
        status="scheduled",
    )
    return Slate(
        contest=Contest(
            contest_id=900,
            day=decision.date(),
            end_day=decision.date(),
            slot_multipliers=(2, 1.8, 1.6, 1.4, 1.2),
            is_locked=False,
            is_finalized=False,
            clock=clock,
            evidence_sha256="a" * 64,
        ),
        games=(game,),
        candidates=tuple(
            Candidate(
                player_id=player,
                game_id=game.game_id,
                team_id=10,
                name=f"P{player}",
                position="WR",
                team="A",
                opponent="B",
                injury_status=injury_status if player == 1 else "Active",
                card_boost=0,
                clock=clock,
            )
            for player in range(1, 6)
        ),
        captured_at=decision,
        source_hashes=("b" * 64,),
        pool_roster_count=5,
        pool_search_matched_count=5,
    )


def test_injury_designation_moves_conditional_mean_when_coef_nonzero() -> None:
    model = _synthetic_model(context_coef_overrides={"injury_questionable": 4.0})
    history = _minimal_history()
    decision = BASE + timedelta(days=8)
    clock = EvidenceClock(source_available_at=decision, captured_at=decision)
    active_ctx = {
        1: ContextAdjustment(
            clock=clock,
            features=injury_indicator_features("Active"),
        )
    }
    questionable_ctx = {
        1: ContextAdjustment(
            clock=clock,
            features=injury_indicator_features("Questionable"),
        )
    }
    slate = _slate_for_player(injury_status="Active", decision=decision)
    active_proj = predict(slate, model, history, decision_at=decision, context=active_ctx)[0]
    questionable_proj = predict(
        slate, model, history, decision_at=decision, context=questionable_ctx
    )[0]
    assert questionable_proj.conditional_mean > active_proj.conditional_mean


def test_weather_magnitude_moves_conditional_mean_when_coef_nonzero() -> None:
    model = _synthetic_model(context_coef_overrides={"weather_temp_f": 0.5})
    history = _minimal_history()
    decision = BASE + timedelta(days=8)
    clock = EvidenceClock(source_available_at=decision, captured_at=decision)
    cold = {1: ContextAdjustment(clock=clock, features={"weather_temp_f": 32.0})}
    warm = {1: ContextAdjustment(clock=clock, features={"weather_temp_f": 85.0})}
    slate = _slate_for_player(injury_status="Active", decision=decision)
    cold_proj = predict(slate, model, history, decision_at=decision, context=cold)[0]
    warm_proj = predict(slate, model, history, decision_at=decision, context=warm)[0]
    cold_mean = cold_proj.conditional_mean
    warm_mean = warm_proj.conditional_mean
    assert warm_mean > cold_mean


def test_out_injury_status_still_hard_zeros_availability() -> None:
    model = _synthetic_model(context_coef_overrides={"injury_out": 99.0})
    history = _minimal_history()
    decision = BASE + timedelta(days=8)
    clock = EvidenceClock(source_available_at=decision, captured_at=decision)
    ctx = {
        1: ContextAdjustment(
            clock=clock,
            features=injury_indicator_features("Out"),
        )
    }
    slate = _slate_for_player(injury_status="Out", decision=decision)
    proj = predict(slate, model, history, decision_at=decision, context=ctx)[0]
    assert proj.availability_probability == 0.0
    assert proj.mean == 0.0
