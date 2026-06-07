"""D78: sportsbook prop-signal multiplier in job2._prop_signal_multiplier."""

from __future__ import annotations

import json

from wnba_oracle.scheduler import job2


def _fj(line: float, over_prob: float) -> str:
    return json.dumps({"prop_points_line": line, "prop_points_over_prob": over_prob})


def test_scale_zero_returns_one() -> None:
    """scale=0 (default off) is a no-op regardless of prop data."""
    assert job2._prop_signal_multiplier(_fj(20.0, 0.80), scale=0.0) == 1.0


def test_no_prop_line_returns_one() -> None:
    """Missing or zero prop line -> 1.0 (no adjustment)."""
    assert job2._prop_signal_multiplier("{}", scale=0.3) == 1.0
    assert job2._prop_signal_multiplier(_fj(0.0, 0.70), scale=0.3) == 1.0


def test_over_probability_60_gives_three_percent_boost() -> None:
    result = job2._prop_signal_multiplier(_fj(18.5, 0.60), scale=0.3)
    assert abs(result - 1.03) < 1e-9


def test_under_probability_40_gives_three_percent_cut() -> None:
    result = job2._prop_signal_multiplier(_fj(18.5, 0.40), scale=0.3)
    assert abs(result - 0.97) < 1e-9


def test_neutral_probability_is_no_op() -> None:
    result = job2._prop_signal_multiplier(_fj(18.5, 0.50), scale=0.3)
    assert abs(result - 1.0) < 1e-9


def test_clip_floor_at_085() -> None:
    """Very low over_prob can't crater prediction below 0.85 multiplier."""
    result = job2._prop_signal_multiplier(_fj(18.5, 0.0), scale=2.0)
    assert result == 0.85


def test_clip_ceiling_at_115() -> None:
    """Extreme over_prob can't inflate prediction above 1.15 multiplier."""
    result = job2._prop_signal_multiplier(_fj(18.5, 1.0), scale=2.0)
    assert result == 1.15
