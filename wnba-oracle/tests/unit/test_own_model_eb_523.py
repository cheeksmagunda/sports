"""WNBA own-model EB pace terms + feature map (#523 Option A companion)."""

from __future__ import annotations

import polars as pl
import pytest

from wnba_oracle.features.own_model_map import (
    EB_PACE_FEATURES,
    classify_serving_feature,
    wnba_own_model_gap_matrix,
)
from wnba_oracle.modeling.artifact import eb_predict_one
from wnba_oracle.train.eb_baseline import EBHierarchicalBaseline
from wnba_oracle.train.pipeline import PickerArtifact


def test_gap_matrix_marks_pace_vegas_boost() -> None:
    rows = {r["feature"]: r for r in wnba_own_model_gap_matrix()}
    for name in EB_PACE_FEATURES:
        assert name in rows
        assert classify_serving_feature(name) == "eb_pace"
    assert classify_serving_feature("vegas_total") == "eb_vegas"
    assert classify_serving_feature("card_boost") == "eb_boost"
    assert classify_serving_feature("is_confirmed_starter") == "serve_starter_multiplier"


def test_eb_fit_learns_opp_pace_vegas_boost() -> None:
    rows = []
    for i in range(40):
        rows.append(
            {
                "player_id": i % 5,
                "cohort": "F",
                "real_score": 10.0 + 0.05 * i + 0.2 * (i % 3),
                "team_pace": 95.0 + (i % 4),
                "opp_pace": 90.0 + (i % 5),
                "vegas_total": 160.0 + (i % 6),
                "card_boost": float(i % 4) * 0.5,
            }
        )
    eb = EBHierarchicalBaseline()
    eb.fit(pl.from_dicts(rows))
    assert isinstance(eb.opp_pace_beta, float)
    assert isinstance(eb.league_opp_pace, float)
    assert isinstance(eb.vegas_beta, float)
    assert isinstance(eb.boost_beta, float)


def test_eb_predict_one_applies_pace_vegas_boost_terms() -> None:
    eb = EBHierarchicalBaseline(
        cohort_means={"F": 2.0},
        player_alpha={7: 1.0},
        pace_beta=0.1,
        opp_pace_beta=0.05,
        vegas_beta=0.02,
        boost_beta=0.5,
        league_pace=100.0,
        league_opp_pace=100.0,
        league_vegas=160.0,
        league_boost=1.0,
    )
    art = PickerArtifact(
        feature_module_sha="t",
        config={},
        eb_baseline=eb,
        training_rows=1,
    )
    base = eb_predict_one(art, 7, "F")
    hot = eb_predict_one(
        art,
        7,
        "F",
        team_pace=110.0,
        opp_pace=100.0,
        vegas_total=170.0,
        card_boost=2.0,
    )
    assert base == pytest.approx(3.0)
    # 3.0 + 0.1*10 + 0.05*0 + 0.02*10 + 0.5*1 = 4.7
    assert hot == pytest.approx(4.7)


def test_ensemble_yaml_documents_eb_primary() -> None:
    from pathlib import Path

    import yaml

    cfg = yaml.safe_load(
        (Path(__file__).resolve().parents[2] / "src/wnba_oracle/train/models.yaml").read_text()
    )
    # Serve never applied these weights; yaml now documents EB as own-model
    # primary while LightGBM heads remain optional research/shadow.
    assert cfg["ensemble"]["eb_baseline"] >= cfg["ensemble"]["lightgbm"]
    assert cfg["ensemble"]["lightgbm"] == 0.0
