"""job2 starter-signal multiplier from the RotoWire starter flag (D52, D104)."""

from __future__ import annotations

import json

from wnba_oracle.scheduler.job2 import _effective_confirmed, _starter_multiplier


def test_confirmed_starter_boosts() -> None:
    fj = json.dumps({"rotowire_confirmed": 1, "is_starter": 1})
    assert _starter_multiplier(fj, enabled=True) == 1.10


def test_confirmed_bench_fades() -> None:
    fj = json.dumps({"rotowire_confirmed": 1, "is_starter": 0})
    assert _starter_multiplier(fj, enabled=True) == 0.82


def test_unlisted_is_neutral() -> None:
    # RotoWire did not list this player -> no info, do not punish.
    fj = json.dumps({"rotowire_confirmed": 0, "is_starter": 0})
    assert _starter_multiplier(fj, enabled=True) == 1.0


def test_expected_starter_boosts_by_default() -> None:
    # D104: a RotoWire EXPECTED starter (listed in the top five but not yet
    # flipped to "Confirmed") gets the starter boost -- confirmed lineups for
    # every game on a slate are not all out by the T-40 freeze.
    fj = json.dumps({"rotowire_confirmed": 0, "is_starter": 1, "starter_slot": 2})
    assert _starter_multiplier(fj, enabled=True) == 1.10


def test_expected_starter_neutral_when_use_expected_off() -> None:
    # Reversible: STARTER_SIGNAL_USE_EXPECTED=false restores confirmed-only.
    fj = json.dumps({"rotowire_confirmed": 0, "is_starter": 1, "starter_slot": 2})
    assert _starter_multiplier(fj, enabled=True, use_expected=False) == 1.0


def test_expected_bench_stays_neutral() -> None:
    # An expected NON-starter is left neutral: RotoWire's expected bench order
    # is noisy, so only a CONFIRMED bench is faded.
    fj = json.dumps({"rotowire_confirmed": 0, "is_starter": 0, "starter_slot": 7})
    assert _starter_multiplier(fj, enabled=True) == 1.0


def test_disabled_is_neutral() -> None:
    fj = json.dumps({"rotowire_confirmed": 1, "is_starter": 0})
    assert _starter_multiplier(fj, enabled=False) == 1.0


def test_missing_features_is_neutral() -> None:
    assert _starter_multiplier(None, enabled=True) == 1.0
    assert _starter_multiplier("{}", enabled=True) == 1.0


def test_effective_confirmed_table() -> None:
    def f(c: int, s: int) -> dict[str, int]:
        return {"rotowire_confirmed": c, "is_starter": s}

    # Confirmed always counts, regardless of starter/bench.
    assert _effective_confirmed(f(1, 1), use_expected=True) is True
    assert _effective_confirmed(f(1, 0), use_expected=True) is True
    # Expected start counts only when use_expected; expected bench never does.
    assert _effective_confirmed(f(0, 1), use_expected=True) is True
    assert _effective_confirmed(f(0, 1), use_expected=False) is False
    assert _effective_confirmed(f(0, 0), use_expected=True) is False
