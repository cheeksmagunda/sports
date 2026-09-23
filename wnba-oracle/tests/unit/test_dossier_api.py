"""#35 phase 3 / #39: read-only dossier API surface."""

from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from wnba_oracle.api.app import app

_DOSSIER = {
    "slate_date": "2026-06-08",
    "entries": {
        "committed": {
            "kind": "committed",
            "score": 100.0,
            "achievable": True,
            "slot_order_basis": "committed",
            "censor_reason": None,
        },
        "field_best": {
            "kind": "field_best",
            "score": 110.0,
            "achievable": True,
            "slot_order_basis": "as_entered",
            "censor_reason": None,
        },
        "theoretical_ceiling": {
            "kind": "theoretical_ceiling",
            "score": 130.0,
            "achievable": False,
            "slot_order_basis": "optimal_resort",
            "censor_reason": None,
        },
    },
    "gap_to_field": {
        "from_kind": "committed",
        "to_kind": "field_best",
        "value": 10.0,
        "exactness": "exact",
        "from_censor": None,
        "to_censor": None,
    },
    "gap_field_to_ceiling": {
        "from_kind": "field_best",
        "to_kind": "theoretical_ceiling",
        "value": 20.0,
        "exactness": "lower_bound",
        "from_censor": None,
        "to_censor": None,
    },
    "gap_to_ceiling": {
        "from_kind": "committed",
        "to_kind": "theoretical_ceiling",
        "value": 30.0,
        "exactness": "lower_bound",
        "from_censor": None,
        "to_censor": None,
    },
    "sources": {"model_artifact": {"status": "available"}},
    "input_snapshot": {"status": "bound_snapshot_available"},
    "feature_and_signal_lineage": {"status": "available", "matrix": []},
    "prediction_paths": {"status": "captured_in_immutable_snapshot", "rows": []},
    "optimizer": {"status": "available"},
    "frozen_lineup": {"audit_snapshot_sha256": "abc123"},
    "realized_player_results": {"status": "available", "rows": [], "top_value": []},
    "contest_results": {"leaderboard": [], "placement": {"status": "unavailable"}},
    "our_outcome": {"status": "partial"},
    "data_quality_and_censoring": {"provenance": "partial", "missing_sources": []},
    "shared_slate_dossier": {"slate_identity": {"slate_date": "2026-06-08"}},
}


def test_returns_dossier_payload_when_available() -> None:
    with (
        patch("wnba_oracle.api.dossier.get_engine", return_value="fake-engine"),
        patch(
            "wnba_oracle.api.dossier.build_post_slate_dossier",
            return_value=_DOSSIER,
        ) as mock_build,
    ):
        resp = TestClient(app).get("/dossier/2026-06-08")

    assert resp.status_code == 200
    body = resp.json()
    assert body["slate_date"] == "2026-06-08"
    assert body["entries"]["theoretical_ceiling"]["achievable"] is False
    assert body["gap_field_to_ceiling"]["exactness"] == "lower_bound"
    assert body["gap_to_ceiling"]["exactness"] == "lower_bound"
    assert body["prediction_paths"]["status"] == "captured_in_immutable_snapshot"
    assert body["shared_slate_dossier"]["slate_identity"]["slate_date"] == "2026-06-08"
    mock_build.assert_called_once_with("2026-06-08", engine="fake-engine")


def test_404_when_dossier_cannot_be_built() -> None:
    with (
        patch("wnba_oracle.api.dossier.get_engine", return_value="fake-engine"),
        patch("wnba_oracle.api.dossier.build_post_slate_dossier", return_value=None),
    ):
        resp = TestClient(app).get("/dossier/2026-06-08")

    assert resp.status_code == 404


def test_503_when_engine_is_unavailable() -> None:
    with patch(
        "wnba_oracle.api.dossier.get_engine", side_effect=RuntimeError("no database configured")
    ):
        resp = TestClient(app).get("/dossier/2026-06-08")

    assert resp.status_code == 503


def test_censored_ceiling_serializes_censor_reason() -> None:
    censored = {**_DOSSIER}
    censored["gap_field_to_ceiling"] = {
        **_DOSSIER["gap_field_to_ceiling"],
        "to_censor": "incomplete_labels",
    }
    with (
        patch("wnba_oracle.api.dossier.get_engine", return_value="fake-engine"),
        patch("wnba_oracle.api.dossier.build_post_slate_dossier", return_value=censored),
    ):
        resp = TestClient(app).get("/dossier/2026-06-08")

    assert resp.status_code == 200
    assert resp.json()["gap_field_to_ceiling"]["to_censor"] == "incomplete_labels"
