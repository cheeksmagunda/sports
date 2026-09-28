"""WNBA h2h moneyline fuse stays off unless WNBA_FUSE_MONEYLINE is set (#583)."""

from __future__ import annotations

from wnba_oracle.features.serving_features import (
    fuse_slate_enrichment_into_head_features,
    moneyline_fuse_enabled,
    moneyline_pair,
)


def test_moneyline_flag_defaults_off(monkeypatch) -> None:
    monkeypatch.delenv("WNBA_FUSE_MONEYLINE", raising=False)
    assert moneyline_fuse_enabled() is False
    assert moneyline_fuse_enabled("0") is False
    assert moneyline_fuse_enabled("off") is False


def test_moneyline_flag_accepts_explicit_on() -> None:
    assert moneyline_fuse_enabled("1") is True
    assert moneyline_fuse_enabled("true") is True
    assert moneyline_fuse_enabled(" YES ") is True


def test_moneyline_pair_is_empty_when_disabled() -> None:
    assert moneyline_pair(team=-140.0, opponent=120.0, enabled=False) == {}


def test_moneyline_pair_writes_both_sides_when_enabled() -> None:
    assert moneyline_pair(team=-140.0, opponent=120.0, enabled=True) == {
        "team_moneyline": -140.0,
        "opponent_moneyline": 120.0,
    }


def test_fuse_omits_moneyline_when_job1_did_not_pass_it() -> None:
    head = fuse_slate_enrichment_into_head_features(
        None,
        card_boost=1.5,
        primary_ranking=10.0,
        vegas_total=164.5,
        vegas_spread=-3.5,
        is_home=1.0,
        is_starter=1,
        starter_slot=1,
        rotowire_confirmed=1,
    )
    assert "team_moneyline" not in head
    assert head["moneyline_available"] == 0.0


def test_fuse_accepts_moneyline_when_the_flag_path_passes_it() -> None:
    head = fuse_slate_enrichment_into_head_features(
        None,
        card_boost=1.5,
        primary_ranking=10.0,
        vegas_total=164.5,
        vegas_spread=-3.5,
        is_home=1.0,
        is_starter=1,
        starter_slot=1,
        rotowire_confirmed=1,
        team_moneyline=-140.0,
        opponent_moneyline=120.0,
    )
    assert head["team_moneyline"] == -140.0
    assert head["opponent_moneyline"] == 120.0
    assert head["moneyline_available"] == 1.0
