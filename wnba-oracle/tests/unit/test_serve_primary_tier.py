"""#523 Option A: serve_primary selects EB vs LightGBM heads as Tier-0."""

from __future__ import annotations

import json
from typing import Any

import numpy as np

from wnba_oracle.modeling.policy import ModelPolicy
from wnba_oracle.modeling.prediction import predict_players
from wnba_oracle.picker.optimize import OptimizeConfig
from wnba_oracle.train.eb_baseline import EBHierarchicalBaseline
from wnba_oracle.train.pipeline import PickerArtifact


def _policy(*, serve_primary: str, minutes_model_enabled: bool = True) -> ModelPolicy:
    return ModelPolicy(
        optimizer=OptimizeConfig(),
        serve_primary=serve_primary,  # type: ignore[arg-type]
        minutes_model_enabled=minutes_model_enabled,
        starter_signal_enabled=False,
    )


def _artifact() -> PickerArtifact:
    eb = EBHierarchicalBaseline(
        cohort_means={"F": 2.5, "G": 2.8, "C": 2.2},
        player_alpha={101: 1.5},
        pace_beta=0.1,
        league_pace=90.0,
    )
    return PickerArtifact(
        feature_module_sha="test",
        config={},
        eb_baseline=eb,
        training_rows=10,
        low_data_mode=False,
        heads={
            ("minutes", "F"): type("H", (), {"feature_columns": ("mins_l10",)})(),
            ("real_score_per_min", "F"): type("H", (), {"feature_columns": ("mins_l10",)})(),
        },
    )


def _row(
    pid: int,
    *,
    with_head_features: bool = True,
    with_minutes: bool = False,
    team_pace: float | None = 100.0,
) -> dict[str, Any]:
    features: dict[str, Any] = {}
    if with_head_features:
        hf: dict[str, float] = {"mins_l10": 28.0}
        if team_pace is not None:
            hf["team_pace"] = team_pace
        features["head_features"] = hf
    if with_minutes:
        features.update(
            {
                "recent_minutes": 28.0,
                "per_min_rate": 0.4,
                "minutes_vol": 2.0,
                "n_min_games": 10,
            }
        )
    return {
        "real_sports_player_id": pid,
        "name": f"Player {pid}",
        "team": "LV",
        "opponent": "NYL",
        "position": "F",
        "card_boost": 1.0,
        "features_json": json.dumps(features),
    }


def test_default_eb_primary_skips_heads_even_when_predictions_present() -> None:
    art = _artifact()
    head_predictions = {101: {"p10": 3.0, "p50": 7.5, "p90": 14.0}}
    preds = predict_players(
        [_row(101)],
        policy=_policy(serve_primary="eb"),
        art=art,
        head_predictions=head_predictions,
        player_history=None,
        bonus={},
    )
    audit = preds.prediction_audit_by_pid[101]
    assert audit["tier"] == "eb_baseline"
    # 2.5 + 1.5 + 0.1*(100-90) = 5.0; starter_signal disabled -> 1.0x
    assert preds.pred_real_scores[101] == 5.0
    assert 101 not in preds.head_quantiles_by_pid


def test_heads_primary_uses_lgbm_when_predictions_present() -> None:
    art = _artifact()
    head_predictions = {101: {"p10": 3.0, "p50": 7.5, "p90": 14.0}}
    preds = predict_players(
        [_row(101)],
        policy=_policy(serve_primary="heads"),
        art=art,
        head_predictions=head_predictions,
        player_history=None,
        bonus={},
    )
    assert preds.prediction_audit_by_pid[101]["tier"] == "trained_heads"
    assert preds.pred_real_scores[101] == 7.5
    assert preds.head_quantiles_by_pid[101]["p50"] == 7.5


def test_eb_primary_cold_start_uses_minutes_not_heads() -> None:
    """Player absent from EB alpha falls through to minutes blend, not heads."""
    art = _artifact()
    head_predictions = {202: {"p10": 3.0, "p50": 9.0, "p90": 14.0}}
    preds = predict_players(
        [_row(202, with_minutes=True)],
        policy=_policy(serve_primary="eb"),
        art=art,
        head_predictions=head_predictions,
        player_history=None,
        bonus={},
    )
    assert preds.prediction_audit_by_pid[202]["tier"] == "minutes_blend"
    assert 202 not in preds.head_quantiles_by_pid


def test_eb_primary_prefers_eb_over_minutes_when_both_available() -> None:
    art = _artifact()
    preds = predict_players(
        [_row(101, with_minutes=True)],
        policy=_policy(serve_primary="eb"),
        art=art,
        head_predictions={},
        player_history=None,
        bonus={},
    )
    assert preds.prediction_audit_by_pid[101]["tier"] == "eb_baseline"
    assert preds.pred_real_scores[101] == 5.0


def test_build_specs_default_skips_head_predict(monkeypatch) -> None:
    """Default serve_primary=eb must not call LightGBM predict_real_score."""
    from wnba_oracle.common.settings import Settings
    from wnba_oracle.picker.popularity import ContrarianConfig
    from wnba_oracle.scheduler import job2

    art = _artifact()
    calls: list[int] = []

    class _TrackingArtifact:
        eb_baseline = art.eb_baseline
        heads = art.heads

        def predict_real_score(self, frame: Any) -> Any:
            calls.append(len(frame))
            n = len(frame)
            return {
                "p10": np.array([3.0] * n),
                "p50": np.array([7.5] * n),
                "p90": np.array([14.0] * n),
            }

    tracking = _TrackingArtifact()
    monkeypatch.setattr(job2, "_load_model_artifact", lambda *_a, **_k: tracking)
    monkeypatch.setattr(job2, "_load_measured_drafts", lambda *_a, **_k: {})
    monkeypatch.setattr(job2, "_load_slate_label_names", lambda *_a, **_k: {})
    monkeypatch.setattr(job2, "get_settings", lambda: Settings.model_construct())

    _samps, _fields, proj = job2._build_specs(
        [_row(101)],
        slate_date="2026-06-06",
        contrarian_cfg=ContrarianConfig(enabled=False, strength=0.0),
    )
    assert not calls, "default EB primary must not invoke LGBM predict_real_score"
    # 5.0 EB base * 0.75 starter_unknown_fade (default Settings)
    assert proj[101]["pred_real_score_p50"] == 3.75
    assert "pred_real_score_p10" not in proj[101]
