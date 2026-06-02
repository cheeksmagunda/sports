"""Game-script (blowout) minutes redistribution."""

from __future__ import annotations

from wnba_oracle.features.game_script_minutes import (
    GameScriptInput,
    GameScriptMinutesConfig,
    blowout_probability,
    redistribute_game_script_minutes,
)


def test_blowout_probability_ramps_monotonically() -> None:
    cfg = GameScriptMinutesConfig(soft_margin=8.0, hard_margin=18.0)
    assert blowout_probability(0.0, cfg) == 0.0
    assert blowout_probability(8.0, cfg) == 0.0
    assert blowout_probability(18.0, cfg) == 1.0
    assert blowout_probability(30.0, cfg) == 1.0
    mid = blowout_probability(13.0, cfg)
    assert 0.0 < mid < 1.0
    # sign of the spread does not matter (favourite or dog, same game)
    assert blowout_probability(-20.0, cfg) == blowout_probability(20.0, cfg)


def test_close_game_means_no_redistribution() -> None:
    rows = [
        GameScriptInput(1, "LVA", 32.0, 3.0),
        GameScriptInput(2, "LVA", 12.0, 3.0),
    ]
    assert redistribute_game_script_minutes(rows) == {}


def test_blowout_trims_starters_and_boosts_bench() -> None:
    rows = [
        GameScriptInput(1, "LVA", 34.0, 20.0),  # starter, trimmed
        GameScriptInput(2, "LVA", 30.0, 20.0),  # starter, trimmed
        GameScriptInput(3, "LVA", 12.0, 20.0),  # bench, boosted
        GameScriptInput(4, "LVA", 8.0, 20.0),  # deep bench, boosted most
    ]
    deltas = redistribute_game_script_minutes(rows)
    assert deltas[1] < 0.0
    assert deltas[2] < 0.0
    assert deltas[3] > 0.0
    assert deltas[4] > 0.0
    # Deepest bench (fewest minutes) inherits the most.
    assert deltas[4] > deltas[3]


def test_no_bench_means_no_trim() -> None:
    # All starters: nobody to absorb the freed minutes, so skip the team
    # entirely rather than trim into a void.
    rows = [
        GameScriptInput(1, "LVA", 34.0, 25.0),
        GameScriptInput(2, "LVA", 28.0, 25.0),
    ]
    assert redistribute_game_script_minutes(rows) == {}


def test_per_player_cap_holds() -> None:
    rows = [
        GameScriptInput(1, "LVA", 38.0, 30.0),  # big starter, lots of freed minutes
        GameScriptInput(2, "LVA", 1.0, 30.0),  # tiny minutes, huge inverse weight
    ]
    cfg = GameScriptMinutesConfig(per_player_cap_minutes=5.0)
    deltas = redistribute_game_script_minutes(rows, cfg=cfg)
    assert deltas[2] <= 5.0


def test_bench_gain_does_not_exceed_freed_pool() -> None:
    rows = [
        GameScriptInput(1, "LVA", 36.0, 22.0),
        GameScriptInput(2, "LVA", 34.0, 22.0),
        GameScriptInput(3, "LVA", 14.0, 22.0),
        GameScriptInput(4, "LVA", 10.0, 22.0),
    ]
    cfg = GameScriptMinutesConfig(per_player_cap_minutes=100.0)  # disable cap
    deltas = redistribute_game_script_minutes(rows, cfg=cfg)
    trimmed = -(deltas[1] + deltas[2])
    gained = deltas[3] + deltas[4]
    # The bench absorbs exactly redistribution_rate of the freed pool.
    assert abs(gained - trimmed * cfg.redistribution_rate) < 1e-9


def test_two_teams_independent() -> None:
    rows = [
        GameScriptInput(1, "LVA", 34.0, 20.0),  # blowout game
        GameScriptInput(2, "LVA", 10.0, 20.0),
        GameScriptInput(3, "NYL", 33.0, 2.0),  # close game, untouched
        GameScriptInput(4, "NYL", 11.0, 2.0),
    ]
    deltas = redistribute_game_script_minutes(rows)
    assert 1 in deltas and 2 in deltas
    assert 3 not in deltas and 4 not in deltas
