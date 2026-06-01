"""job2 starter-signal multiplier from the RotoWire confirmed-starter flag."""

from __future__ import annotations

import json

from wnba_oracle.scheduler.job2 import _starter_multiplier


def test_confirmed_starter_boosts() -> None:
    fj = json.dumps({"rotowire_confirmed": 1, "is_starter": 1})
    assert _starter_multiplier(fj, enabled=True) == 1.10


def test_confirmed_bench_fades() -> None:
    fj = json.dumps({"rotowire_confirmed": 1, "is_starter": 0})
    assert _starter_multiplier(fj, enabled=True) == 0.82


def test_unconfirmed_is_neutral() -> None:
    # RotoWire did not list/confirm this player -> no info, do not punish.
    fj = json.dumps({"rotowire_confirmed": 0, "is_starter": 0})
    assert _starter_multiplier(fj, enabled=True) == 1.0


def test_disabled_is_neutral() -> None:
    fj = json.dumps({"rotowire_confirmed": 1, "is_starter": 0})
    assert _starter_multiplier(fj, enabled=False) == 1.0


def test_missing_features_is_neutral() -> None:
    assert _starter_multiplier(None, enabled=True) == 1.0
    assert _starter_multiplier("{}", enabled=True) == 1.0
