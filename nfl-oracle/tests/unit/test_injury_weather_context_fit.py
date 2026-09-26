"""Force-include injury/weather live_ok context slots in fit/predict (#418)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nfl_oracle.features.live import (
    canonical_live_context_feature_names,
    injury_indicator_features,
)
from nfl_oracle.recommendations.model import (
    ContextAdjustment,
    HistoricalPerformance,
    fit_model,
    predict,
)
from nfl_oracle.recommendations.schema import (
    Candidate,
    Contest,
    EvidenceClock,
    Game,
    Slate,
)

BASE = datetime(2025, 9, 1, 12, tzinfo=UTC)


def _history(
    *, injury_signal: bool = False, weather_signal: bool = False
) -> list[HistoricalPerformance]:
    rows: list[HistoricalPerformance] = []
    for game in range(8):
        kickoff = BASE + timedelta(days=game)
        for player in range(1, 7):
            features: dict[str, float] = {}
            value = float(10 + player + game)
            if injury_signal and player == 2 and game % 2 == 0:
                features.update(injury_indicator_features("Questionable"))
                value -= 6.0
            elif injury_signal:
                features.update(injury_indicator_features("Active"))
            if weather_signal:
                wind = 5.0 + float(game * 3)
                features["weather_wind_mph"] = wind
                features["weather_temp_f"] = 70.0
                features["weather_precip_prob"] = 0.1
                features["weather_available"] = 1.0
                value += 0.4 * wind
            rows.append(
                HistoricalPerformance(
                    player_id=player,
                    game_id=100 + game,
                    position="WR",
                    role="receiving",
                    kickoff_at=kickoff,
                    available_at=kickoff + timedelta(hours=2),
                    captured_at=kickoff + timedelta(hours=3),
                    value=value,
                    opportunity=value,
                    did_not_play=False,
                    context_features=features,
                    context_clock=EvidenceClock(
                        source_available_at=kickoff - timedelta(hours=2),
                        captured_at=kickoff - timedelta(hours=1),
                    )
                    if features
                    else None,
                )
            )
    return rows


def _slate(
    decision: datetime,
    *,
    injury_status: str = "Active",
    player_id: int = 2,
) -> Slate:
    clock = EvidenceClock(source_available_at=decision, captured_at=decision)
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
        games=(
            Game(
                game_id=200,
                season=2025,
                kickoff_at=decision + timedelta(hours=4),
                home_team_id=10,
                away_team_id=11,
                home_team="A",
                away_team="B",
                status="scheduled",
            ),
        ),
        candidates=(
            Candidate(
                player_id=player_id,
                game_id=200,
                team_id=10,
                name="P2",
                position="WR",
                team="A",
                opponent="B",
                injury_status=injury_status,
                card_boost=0,
                clock=clock,
            ),
            Candidate(
                player_id=3,
                game_id=200,
                team_id=10,
                name="P3",
                position="WR",
                team="A",
                opponent="B",
                injury_status="Active",
                card_boost=0,
                clock=clock,
            ),
            Candidate(
                player_id=4,
                game_id=200,
                team_id=11,
                name="P4",
                position="RB",
                team="B",
                opponent="A",
                injury_status="Active",
                card_boost=0,
                clock=clock,
            ),
            Candidate(
                player_id=5,
                game_id=200,
                team_id=11,
                name="P5",
                position="TE",
                team="B",
                opponent="A",
                injury_status="Active",
                card_boost=0,
                clock=clock,
            ),
            Candidate(
                player_id=1,
                game_id=200,
                team_id=10,
                name="P1",
                position="QB",
                team="A",
                opponent="B",
                injury_status="Active",
                card_boost=0,
                clock=clock,
            ),
        ),
        captured_at=decision,
        source_hashes=("b" * 64,),
        pool_roster_count=5,
        pool_search_matched_count=5,
    )


def test_fit_always_reserves_canonical_injury_weather_slots() -> None:
    # Only weather_index observed — canonical live_ok slots must still appear.
    rows: list[HistoricalPerformance] = []
    for game in range(8):
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
                    value=float(10 + player + game),
                    opportunity=float(10 + player + game),
                    did_not_play=False,
                    context_features={"weather_index": float(game)},
                    context_clock=EvidenceClock(
                        source_available_at=kickoff - timedelta(hours=2),
                        captured_at=kickoff - timedelta(hours=1),
                    ),
                )
            )
    model = fit_model(rows, trained_at=BASE + timedelta(days=10))
    canonical = set(canonical_live_context_feature_names())
    assert canonical.issubset(model.context_feature_names)
    assert "weather_index" in model.context_feature_names
    assert len(model.coefficients) == len(model.feature_names) + 2 * len(
        model.context_feature_names
    )


def test_questionable_vs_active_changes_conditional_mean() -> None:
    history = _history(injury_signal=True)
    model = fit_model(history, trained_at=BASE + timedelta(days=10))
    assert "injury_questionable" in model.context_feature_names
    decision = BASE + timedelta(days=11)
    slate = _slate(decision, injury_status="Questionable")
    active_ctx = {
        2: ContextAdjustment(
            clock=EvidenceClock(source_available_at=decision, captured_at=decision),
            features=injury_indicator_features("Active"),
        )
    }
    q_ctx = {
        2: ContextAdjustment(
            clock=EvidenceClock(source_available_at=decision, captured_at=decision),
            features=injury_indicator_features("Questionable"),
        )
    }
    active_mean = predict(slate, model, history, decision_at=decision, context=active_ctx)[
        0
    ].conditional_mean
    q_mean = predict(slate, model, history, decision_at=decision, context=q_ctx)[0].conditional_mean
    assert q_mean < active_mean


def test_weather_magnitude_changes_conditional_mean() -> None:
    history = _history(weather_signal=True)
    model = fit_model(history, trained_at=BASE + timedelta(days=10))
    assert "weather_wind_mph" in model.context_feature_names
    decision = BASE + timedelta(days=11)
    slate = _slate(decision)
    calm = {
        2: ContextAdjustment(
            clock=EvidenceClock(source_available_at=decision, captured_at=decision),
            features={
                "weather_wind_mph": 5.0,
                "weather_temp_f": 70.0,
                "weather_precip_prob": 0.1,
                "weather_available": 1.0,
            },
        )
    }
    windy = {
        2: ContextAdjustment(
            clock=EvidenceClock(source_available_at=decision, captured_at=decision),
            features={
                "weather_wind_mph": 30.0,
                "weather_temp_f": 70.0,
                "weather_precip_prob": 0.1,
                "weather_available": 1.0,
            },
        )
    }
    calm_mean = predict(slate, model, history, decision_at=decision, context=calm)[
        0
    ].conditional_mean
    windy_mean = predict(slate, model, history, decision_at=decision, context=windy)[
        0
    ].conditional_mean
    assert windy_mean != calm_mean


def test_out_status_still_hard_zeros_mean() -> None:
    history = _history(injury_signal=True)
    model = fit_model(history, trained_at=BASE + timedelta(days=10))
    decision = BASE + timedelta(days=11)
    slate = _slate(decision, injury_status="Out")
    projections = predict(slate, model, history, decision_at=decision)
    out_proj = next(p for p in projections if p.player_id == 2)
    assert out_proj.availability_probability == 0.0
    assert out_proj.mean == 0.0
