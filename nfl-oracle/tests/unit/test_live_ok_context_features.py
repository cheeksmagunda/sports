"""Canonical live_ok injury/weather context features stay wired (#418)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nfl_oracle.features.live import INJURY_CATEGORIES, WEATHER_FEATURE_NAMES
from nfl_oracle.recommendations.model import (
    REQUIRED_LIVE_OK_CONTEXT_FEATURES,
    HistoricalPerformance,
    _context_feature_names,
    _context_vector,
    fit_model,
)
from nfl_oracle.recommendations.schema import EvidenceClock

BASE = datetime(2025, 9, 1, 12, tzinfo=UTC)


def test_required_live_ok_keys_are_canonical() -> None:
    assert "injury_questionable" in REQUIRED_LIVE_OK_CONTEXT_FEATURES
    assert "injury_status_available" in REQUIRED_LIVE_OK_CONTEXT_FEATURES
    assert "weather_temp_f" in REQUIRED_LIVE_OK_CONTEXT_FEATURES
    assert "weather_available" in REQUIRED_LIVE_OK_CONTEXT_FEATURES
    assert set(WEATHER_FEATURE_NAMES) <= set(REQUIRED_LIVE_OK_CONTEXT_FEATURES)
    for name in INJURY_CATEGORIES:
        assert f"injury_{name}" in REQUIRED_LIVE_OK_CONTEXT_FEATURES


def test_context_feature_names_force_include_when_sparse() -> None:
    rows = []
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
                    did_not_play=False,
                    context_features={"depth_rank": 1.0},
                    context_clock=EvidenceClock(
                        source_available_at=kickoff - timedelta(hours=2),
                        captured_at=kickoff - timedelta(hours=1),
                    ),
                )
            )
    train = [r for r in rows if r.available_at < BASE + timedelta(days=4)]
    names = _context_feature_names(train)
    assert "depth_rank" in names
    for key in REQUIRED_LIVE_OK_CONTEXT_FEATURES:
        assert key in names


def test_fit_model_keeps_live_ok_names_without_dense_history() -> None:
    rows = []
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
                    did_not_play=False,
                    context_features={},
                    context_clock=None,
                )
            )
    model = fit_model(rows, trained_at=BASE + timedelta(days=10))
    for key in REQUIRED_LIVE_OK_CONTEXT_FEATURES:
        assert key in model.context_feature_names


def test_questionable_and_weather_move_linear_score_when_coefs_nonzero() -> None:
    model = fit_model(
        [
            HistoricalPerformance(
                player_id=player,
                game_id=100 + game,
                position="WR",
                role="receiving",
                kickoff_at=BASE + timedelta(days=game),
                available_at=BASE + timedelta(days=game, hours=2),
                captured_at=BASE + timedelta(days=game, hours=3),
                value=float(player + game),
                opportunity=float(player + game),
                did_not_play=False,
                context_features={},
                context_clock=None,
            )
            for game in range(6)
            for player in range(1, 7)
        ],
        trained_at=BASE + timedelta(days=10),
    )
    names = list(model.context_feature_names)
    coefs = list(model.coefficients)
    core = 7
    q_idx = names.index("injury_questionable")
    temp_idx = names.index("weather_temp_f")
    coefs[core + 2 * q_idx] = -3.0
    coefs[core + 2 * temp_idx] = 0.05
    hot = model.model_copy(update={"coefficients": tuple(coefs)})
    ctx_coefs = hot.coefficients[7:]

    def score(features: dict[str, float]) -> float:
        vec = _context_vector(features, hot.context_feature_names)
        return sum(c * x for c, x in zip(ctx_coefs, vec, strict=True))

    active = score(
        {
            "injury_active": 1.0,
            "injury_status_available": 1.0,
            "weather_temp_f": 50.0,
            "weather_available": 1.0,
        }
    )
    questionable = score(
        {
            "injury_questionable": 1.0,
            "injury_status_available": 1.0,
            "weather_temp_f": 50.0,
            "weather_available": 1.0,
        }
    )
    warm = score(
        {
            "injury_active": 1.0,
            "injury_status_available": 1.0,
            "weather_temp_f": 90.0,
            "weather_available": 1.0,
        }
    )
    assert questionable < active
    assert warm > active


def test_missing_live_ok_keys_set_missing_flags() -> None:
    names = REQUIRED_LIVE_OK_CONTEXT_FEATURES
    vec = _context_vector({}, names)
    # Each name contributes (value, missing) => 2 floats; all missing => 1.0 flags
    assert len(vec) == 2 * len(names)
    assert all(vec[i] == 0.0 for i in range(0, len(vec), 2))
    assert all(vec[i] == 1.0 for i in range(1, len(vec), 2))
