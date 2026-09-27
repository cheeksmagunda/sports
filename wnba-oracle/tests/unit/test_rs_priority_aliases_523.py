"""Priority RS leaf aliases → WNBA EB / head_features (#523)."""

from __future__ import annotations

import polars as pl
import pytest

from wnba_oracle.features.own_model_map import classify_serving_feature
from wnba_oracle.features.rs_aliases import (
    LEAKAGE_BLOCKED_SAME_SLATE,
    RS_FEATURE_ALIASES,
    extract_draft_stats_row,
)
from wnba_oracle.features.serving_features import fuse_slate_enrichment_into_head_features
from wnba_oracle.modeling.artifact import eb_predict_one
from wnba_oracle.train.eb_baseline import EBHierarchicalBaseline
from wnba_oracle.train.pipeline import PickerArtifact


def test_priority_aliases_table() -> None:
    assert RS_FEATURE_ALIASES["overallRank"] == "overall_rank"
    assert RS_FEATURE_ALIASES["homeMoneyline"] == "home_moneyline"
    assert RS_FEATURE_ALIASES["lastTenWins"] == "last_ten_wins"
    assert "base_boosted_value" in LEAKAGE_BLOCKED_SAME_SLATE
    assert extract_draft_stats_row({"score": 12, "rank": 1}, mode="live_ok") == {}


def test_fuse_includes_priority_rs_fields() -> None:
    head = fuse_slate_enrichment_into_head_features(
        {"mins_l5": 28.0},
        card_boost=1.5,
        primary_ranking=3.0,
        vegas_total=160.0,
        vegas_spread=-2.5,
        is_home=1.0,
        is_starter=1,
        starter_slot=2,
        rotowire_confirmed=1,
        overall_rank=7.0,
        injury_body_part="Knee",
        team_moneyline=-140.0,
        opponent_moneyline=120.0,
        last_ten_wins=6.0,
        season_averages={"pts": 15.2, "reb": 5.0},
    )
    assert head["overall_rank"] == 7.0
    assert head["injury_body_part_available"] == 1.0
    assert head["team_moneyline"] == -140.0
    assert head["last_ten_wins"] == 6.0
    assert head["team_l10_wins"] == 6.0
    assert head["season_avg_pts"] == 15.2
    assert classify_serving_feature("overall_rank") == "eb_rank"
    assert classify_serving_feature("team_moneyline") == "eb_moneyline"


def test_eb_fit_learns_rank_and_moneyline() -> None:
    rows = [
        {
            "player_id": i % 5,
            "cohort": "F",
            "real_score": 10.0 + 0.05 * i,
            "team_pace": 95.0,
            "opp_pace": 95.0,
            "vegas_total": 160.0,
            "card_boost": 1.0,
            "overall_rank": float(i % 20),
            "team_moneyline": -100.0 - float(i % 10),
        }
        for i in range(40)
    ]
    eb = EBHierarchicalBaseline()
    eb.fit(pl.from_dicts(rows))
    assert isinstance(eb.overall_rank_beta, float)
    assert isinstance(eb.moneyline_beta, float)


def test_eb_predict_one_applies_rank_and_moneyline() -> None:
    eb = EBHierarchicalBaseline(
        cohort_means={"F": 2.0},
        player_alpha={7: 1.0},
        overall_rank_beta=-0.1,
        moneyline_beta=0.01,
        league_overall_rank=10.0,
        league_moneyline=-110.0,
    )
    art = PickerArtifact(feature_module_sha="t", config={}, eb_baseline=eb, training_rows=1)
    base = eb_predict_one(art, 7, "F")
    hot = eb_predict_one(art, 7, "F", overall_rank=5.0, team_moneyline=-150.0)
    assert base == pytest.approx(3.0)
    assert hot == pytest.approx(3.1)
