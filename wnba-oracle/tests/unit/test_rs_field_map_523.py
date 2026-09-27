"""WNBA RS field matrix (#523 / #526 / #583)."""

from __future__ import annotations

from wnba_oracle.features.rs_field_map import mapped_rs_field_count, rs_field_matrix
from wnba_oracle.features.serving_features import fuse_slate_enrichment_into_head_features


def test_wnba_rs_field_matrix() -> None:
    rows = rs_field_matrix()
    assert mapped_rs_field_count() >= 5
    statuses = {r["status"] for r in rows}
    assert "mapped" in statuses
    assert "label" in statuses
    assert "leakage-blocked" in statuses
    vegas = next(r for r in rows if "vegas_total" in r["rs_field"])
    assert vegas["status"] == "mapped"
    season = next(r for r in rows if "seasonAverages" in r["rs_field"])
    assert season["status"] == "unused"


def test_fuse_accepts_rank_and_moneyline_for_eb() -> None:
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
        overall_rank=12.0,
        injury_body_part="knee",
        team_moneyline=-140.0,
        opponent_moneyline=120.0,
    )
    assert head["overall_rank"] == 12.0
    assert head["team_moneyline"] == -140.0
    assert head["opponent_moneyline"] == 120.0
    assert head["moneyline_available"] == 1.0
    assert head["injury_body_part_available"] == 1.0
    assert head["is_confirmed_starter"] == 1.0
