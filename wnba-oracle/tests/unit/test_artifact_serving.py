"""Tests for the D45 wiring: job2 loads the trained PickerArtifact and
uses EB baseline predictions for seen players (heuristic fallback for
the rest)."""

from __future__ import annotations

import hashlib
import pickle
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from wnba_oracle.scheduler.job2 import (
    _eb_predict_one,
    _heuristic_real_score,
    _load_model_artifact,
)
from wnba_oracle.train.eb_baseline import EBHierarchicalBaseline
from wnba_oracle.train.pipeline import PickerArtifact


def _make_artifact() -> PickerArtifact:
    eb = EBHierarchicalBaseline(
        cohort_means={"F": 2.5, "G": 2.8, "C": 2.2},
        player_alpha={42: 1.5, 43: -1.0, 100: 0.3},
        pace_beta=0.0,
        league_pace=0.0,
    )
    return PickerArtifact(
        feature_module_sha="test",
        config={},
        eb_baseline=eb,
        training_rows=100,
        low_data_mode=False,
    )


def test_eb_predict_one_known_player() -> None:
    art = _make_artifact()
    # cohort F mean 2.5, alpha 1.5 -> 4.0
    assert _eb_predict_one(art, 42, "F") == pytest.approx(4.0)
    # cohort G mean 2.8, alpha -1.0 -> 1.8
    assert _eb_predict_one(art, 43, "G") == pytest.approx(1.8)
    # cohort C mean 2.2, alpha 0.3 -> 2.5
    assert _eb_predict_one(art, 100, "C") == pytest.approx(2.5)


def test_eb_predict_one_unknown_player_returns_none() -> None:
    art = _make_artifact()
    assert _eb_predict_one(art, 999, "F") is None  # not in player_alpha
    assert _eb_predict_one(art, 12345, "C") is None


def test_eb_predict_one_no_artifact() -> None:
    assert _eb_predict_one(None, 42, "F") is None


def test_eb_predict_one_no_eb_baseline() -> None:
    art = PickerArtifact(feature_module_sha="test", config={}, eb_baseline=None, training_rows=0)
    assert _eb_predict_one(art, 42, "F") is None


def test_eb_predict_one_floored_at_half() -> None:
    """A deeply negative alpha shouldn't produce a near-zero prediction
    that would explode the log-scale sampling."""
    eb = EBHierarchicalBaseline(
        cohort_means={"F": 1.0},
        player_alpha={42: -10.0},  # would produce -9.0
        pace_beta=0.0,
        league_pace=0.0,
    )
    art = PickerArtifact(feature_module_sha="t", config={}, eb_baseline=eb, training_rows=1)
    assert _eb_predict_one(art, 42, "F") == pytest.approx(0.5)


def test_load_model_artifact_empty_sha() -> None:
    assert _load_model_artifact("") is None


def test_load_model_artifact_unknown_sha() -> None:
    assert _load_model_artifact("0000000000000000") is None


def test_production_run_fails_closed_without_artifact_sha() -> None:
    from wnba_oracle.scheduler import job2

    settings = SimpleNamespace(
        env="prod",
        model_artifact_sha="",
        pool_exclude_started_games=False,
    )
    with (
        patch.object(job2, "get_settings", return_value=settings),
        patch.object(job2, "_load_enrichment") as load_enrichment,
    ):
        result = job2.run("2026-06-21")

    assert result.reason == "model_artifact_unset"
    assert result.exit_code == 1
    load_enrichment.assert_not_called()


def test_load_model_artifact_roundtrip(tmp_path, monkeypatch) -> None:
    """Drop a fake artifact + sidecar into a temp models/ and confirm
    _load_model_artifact finds it by SHA."""
    art = _make_artifact()
    payload = pickle.dumps(art, protocol=pickle.HIGHEST_PROTOCOL)
    sha = hashlib.sha256(payload).hexdigest()
    fake_models = tmp_path / "models"
    fake_models.mkdir()
    (fake_models / "picker_test_123.pkl").write_bytes(payload)
    (fake_models / "picker_test_123.sha256").write_text(sha)

    # Point REPO_ROOT at our temp dir (_load_model_artifact reads it from
    # its home module, job2_model)
    import wnba_oracle.scheduler.job2_model as job2_model

    monkeypatch.setattr(job2_model, "REPO_ROOT", tmp_path)

    loaded = _load_model_artifact(sha)
    assert loaded is not None
    assert loaded.training_rows == 100
    assert loaded.eb_baseline is not None
    assert loaded.eb_baseline.player_alpha[42] == 1.5


def test_heuristic_real_score_independent_of_artifact_path() -> None:
    """Heuristic must still work when artifact is absent — it's the
    structural fallback. The full _build_specs path uses it for players
    the artifact never saw."""
    assert _heuristic_real_score(0.0) == pytest.approx(3.16)
    assert _heuristic_real_score(3.0) == pytest.approx(1.81)
    assert _heuristic_real_score(10.0) == 0.5  # floored
