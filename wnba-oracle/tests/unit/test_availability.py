"""Two-part availability model (D57, Tier 2)."""

from __future__ import annotations

from wnba_oracle.predict.availability import (
    AvailabilityConfig,
    availability_probability,
)


def test_no_history_player_gets_low_base_rate() -> None:
    # The 2026-06-01 failure mode: a cold-start dart with no nba_api history and
    # no confirmed role. Must be low so its boost-inflated value collapses.
    p = availability_probability(
        recent_minutes=0.0, minutes_vol=0.0, n_min_games=0, rotowire_confirmed=False
    )
    assert p == AvailabilityConfig().prior_active
    assert p < 0.35


def test_established_starter_is_highly_available() -> None:
    p = availability_probability(
        recent_minutes=32.0, minutes_vol=4.0, n_min_games=15, rotowire_confirmed=False
    )
    assert p > 0.85


def test_deep_bench_is_only_moderately_available() -> None:
    # Plays ~8 min when active: a real but low-floor rotation piece.
    p = availability_probability(
        recent_minutes=8.0, minutes_vol=5.0, n_min_games=10, rotowire_confirmed=False
    )
    assert 0.25 < p < 0.6


def test_confirmed_starter_overrides_thin_history() -> None:
    # No history but RotoWire confirms a start tonight: must be high.
    p = availability_probability(
        recent_minutes=0.0,
        minutes_vol=0.0,
        n_min_games=0,
        rotowire_confirmed=True,
        is_starter=True,
    )
    assert p >= AvailabilityConfig().confirmed_starter_active


def test_confirmed_bench_is_active_but_limited() -> None:
    p = availability_probability(
        recent_minutes=0.0,
        minutes_vol=0.0,
        n_min_games=0,
        rotowire_confirmed=True,
        is_starter=False,
    )
    assert p == AvailabilityConfig().confirmed_bench_active


def test_monotonic_in_recent_minutes() -> None:
    lo = availability_probability(recent_minutes=12.0, minutes_vol=5.0, n_min_games=10)
    hi = availability_probability(recent_minutes=28.0, minutes_vol=5.0, n_min_games=10)
    assert hi > lo


def test_more_games_pulls_toward_the_player_signal() -> None:
    # A clear starter: more history should INCREASE confidence in the high
    # within-game floor probability (pull away from the neutral prior).
    few = availability_probability(recent_minutes=30.0, minutes_vol=4.0, n_min_games=2)
    many = availability_probability(recent_minutes=30.0, minutes_vol=4.0, n_min_games=20)
    assert many > few


def test_result_is_clamped() -> None:
    p = availability_probability(
        recent_minutes=40.0,
        minutes_vol=1.0,
        n_min_games=40,
        rotowire_confirmed=True,
        is_starter=True,
    )
    assert p <= 1.0
