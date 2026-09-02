"""Artifact persistence and integrity compatibility tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from wnba_oracle.train import pipeline
from wnba_oracle.train.pipeline import PickerArtifact


def _artifact() -> PickerArtifact:
    return PickerArtifact(
        feature_module_sha="feature-sha",
        config={"seed": 1729},
        training_rows=12,
    )


def test_write_and_load_artifact_atomically(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "MODELS_DIR", tmp_path)
    monkeypatch.setattr("time.time", lambda: 1_700_000_000)

    path = pipeline.write_artifact(_artifact(), commit="abcdef012345")

    assert path.name == "picker_abcdef01_1700000000.pkl"
    assert len(path.with_suffix(".sha256").read_text()) == 64
    manifest = json.loads(path.with_suffix(".manifest.json").read_text())
    assert manifest["artifact"] == path.name
    assert manifest["artifact_sha256"] == path.with_suffix(".sha256").read_text()
    assert manifest["refit_full"] is False
    assert manifest["calibrators_consumed_at_serving"] is False
    assert "cohort_feature_contract" in manifest
    assert pipeline.load_artifact(path).training_rows == 12
    assert list(tmp_path.glob(".*.tmp")) == []


def test_load_artifact_rejects_checksum_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "picker_test.pkl"
    path.write_bytes(b"not the persisted artifact")
    path.with_suffix(".sha256").write_text("0" * 64)

    with pytest.raises(RuntimeError, match="SHA mismatch"):
        pipeline.load_artifact(path)


def test_load_artifact_rejects_unexpected_pickle_type(tmp_path: Path) -> None:
    import pickle

    path = tmp_path / "picker_test.pkl"
    path.write_bytes(pickle.dumps({"unexpected": True}))

    with pytest.raises(TypeError, match="unexpected type"):
        pipeline.load_artifact(path)


def test_manifest_contract_metadata_and_refit_flag(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(pipeline, "MODELS_DIR", tmp_path)
    monkeypatch.setattr("time.time", lambda: 1_700_000_000)

    art = PickerArtifact(
        feature_module_sha="feat-sha-123",
        config={},
        training_rows=100,
        refit_full=True,
        calibrators_consumed_at_serving=False,
        cohorts_trained=("F", "G"),
        feature_subset_per_head={
            ("minutes", "F"): ("days_rest", "mins_l5"),
            ("real_score_per_min", "F"): ("ts_pct_l10",),
        },
    )

    path = pipeline.write_artifact(art, commit="1234567890ab")
    manifest = json.loads(path.with_suffix(".manifest.json").read_text())

    assert manifest["refit_full"] is True
    assert manifest["calibrators_consumed_at_serving"] is False
    assert manifest["cohorts_trained"] == ["F", "G"]
    assert manifest["cohort_feature_contract"]["minutes:F"] == ["days_rest", "mins_l5"]
    assert manifest["cohort_feature_contract"]["real_score_per_min:F"] == ["ts_pct_l10"]
    loaded = pipeline.load_artifact(path)
    assert loaded.refit_full is True
    assert loaded.calibrators_consumed_at_serving is False
