"""Observational source assurance must never influence recommendation math."""

from __future__ import annotations

import copy
import datetime as dt
import json
from unittest.mock import MagicMock, patch

from wnba_oracle.assurance import source_quality
from wnba_oracle.assurance.connectors import (
    DECISION_INPUT_CONNECTOR_CATALOG_SHA256,
    DECISION_INPUT_CONNECTOR_IDS,
)
from wnba_oracle.assurance.source_quality import build_source_assurance
from wnba_oracle.scheduler import job2, job2_io

NOW = dt.datetime(2026, 8, 22, 22, 20, tzinfo=dt.UTC)
DIGEST = "a" * 64
CANONICAL_DIGEST = "b" * 64


def _row(
    pid: int,
    *,
    captured_at: dt.datetime | str = "2026-08-22T20:00:00+00:00",
    features_json: object | None = None,
) -> dict:
    features = features_json or {
        "game_start_utc": "2026-08-22T23:00:00Z",
        "is_starter": 1,
        "rotowire_confirmed": 1,
        "vegas_total": 164.5,
        "prop_points_line": 18.5,
        "recent_minutes": 29.0,
        "per_min_rate": 0.11,
        "head_features": {"minutes_l10": 29.0},
    }
    return {
        "real_sports_player_id": str(pid),
        "name": f"Player {pid}",
        "team": "IND" if pid % 2 else "NYL",
        "opponent": "NYL" if pid % 2 else "IND",
        "position": "G" if pid % 2 else "F",
        "card_boost": 1.0,
        "features_json": features,
        "captured_at": captured_at,
    }


def test_manifest_reports_aggregate_evidence_and_input_binding() -> None:
    rows = [_row(1), _row(2, captured_at=dt.datetime(2026, 8, 22, 20, 5))]
    payload = build_source_assurance(
        rows,
        assessed_at=NOW,
        decision_input_sha256=DIGEST,
        decision_input_canonical_sha256=CANONICAL_DIGEST,
    )

    assert payload["assessment_status"] == "observed"
    assert payload["decision_input_sha256"] == DIGEST
    assert payload["decision_input_canonical_sha256"] == CANONICAL_DIGEST
    assert (
        payload["decision_input_connector_catalog_sha256"]
        == DECISION_INPUT_CONNECTOR_CATALOG_SHA256
    )
    assert payload["decision_input_connector_ids"] == list(DECISION_INPUT_CONNECTOR_IDS)
    assert "connector_map_sha256" not in payload
    assert payload["assessed_at_utc"] == NOW.isoformat()
    assert payload["capture"] == {
        "rows": 2,
        "teams": 2,
        "captured_at_rows": 2,
        "first_captured_at_utc": "2026-08-22T20:00:00+00:00",
        "last_captured_at_utc": "2026-08-22T20:05:00+00:00",
        "invalid_features_json_rows": 0,
    }
    assert payload["observations"]["realsports"] == {
        "core_rows": 2,
        "game_time_rows": 2,
    }
    assert payload["observations"]["rotowire"]["confirmed_rows"] == 2
    assert payload["observations"]["the_odds_api"] == {
        "vegas_rows": 2,
        "prop_rows": 2,
    }
    assert payload["observations"]["wnba_stats"] == {
        "minutes_rows": 2,
        "head_feature_rows": 2,
    }
    assert "Player 1" not in json.dumps(payload)


def test_manifest_is_degraded_for_findings_or_invalid_features_without_raising() -> None:
    rows = [_row(1, features_json="{not-json")]
    payload = build_source_assurance(
        rows,
        assessed_at=NOW,
        decision_input_sha256=DIGEST,
        decision_input_canonical_sha256=CANONICAL_DIGEST,
        finding_triggers=("schema_minutes_feed_sparse", "schema_minutes_feed_sparse"),
    )

    assert payload["assessment_status"] == "degraded"
    assert payload["capture"]["invalid_features_json_rows"] == 1
    assert payload["finding_triggers"] == ["schema_minutes_feed_sparse"]


def test_manifest_does_not_mutate_enrichment_rows() -> None:
    rows = [_row(1), _row(2, features_json=json.dumps(_row(2)["features_json"]))]
    before = copy.deepcopy(rows)

    build_source_assurance(
        rows,
        assessed_at=NOW,
        decision_input_sha256=DIGEST,
        decision_input_canonical_sha256=CANONICAL_DIGEST,
    )

    assert rows == before


def test_internal_failure_returns_unknown_with_error_type_only() -> None:
    secret_message = "postgresql://user:password@example/token-value"
    with patch.object(
        source_quality,
        "_build_source_assurance",
        side_effect=RuntimeError(secret_message),
    ):
        payload = build_source_assurance(
            [_row(1)],
            assessed_at=NOW,
            decision_input_sha256=DIGEST,
            decision_input_canonical_sha256=CANONICAL_DIGEST,
        )

    serialized = json.dumps(payload, sort_keys=True)
    assert payload["assessment_status"] == "unknown"
    assert payload["error"] == {"type": "RuntimeError"}
    assert "password" not in serialized
    assert "token-value" not in serialized
    assert secret_message not in serialized


def test_schema_assessment_failure_returns_unknown_with_error_type_only() -> None:
    payload = build_source_assurance(
        [_row(1)],
        assessed_at=NOW,
        decision_input_sha256=DIGEST,
        decision_input_canonical_sha256=CANONICAL_DIGEST,
        assessment_error_type="SchemaAssessmentError",
    )

    assert payload["assessment_status"] == "unknown"
    assert payload["error"] == {"type": "SchemaAssessmentError"}
    assert "observations" not in payload


def test_manifest_observation_ids_are_declared_connectors() -> None:
    payload = build_source_assurance(
        [_row(1)],
        assessed_at=NOW,
        decision_input_sha256=DIGEST,
        decision_input_canonical_sha256=CANONICAL_DIGEST,
    )
    assert set(payload["observations"]) <= set(DECISION_INPUT_CONNECTOR_IDS)


def test_model_enrichment_loader_retains_exact_scoring_projection() -> None:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    connection.execute.return_value = []
    with patch.object(job2_io, "get_engine", return_value=engine):
        assert job2_io._load_enrichment("2026-08-22") == []

    statement = str(connection.execute.call_args.args[0])
    assert statement == (
        "SELECT real_sports_player_id, name, team, opponent, position, "
        "card_boost, features_json FROM job1_enrichment WHERE slate_date = :sd"
    )
    assert "captured_at" not in statement


def test_assurance_capture_loader_is_separate_and_value_free() -> None:
    engine = MagicMock()
    connection = engine.connect.return_value.__enter__.return_value
    row = MagicMock()
    row._mapping = {"real_sports_player_id": "7", "captured_at": NOW}
    connection.execute.return_value = [row]
    with patch.object(job2_io, "get_engine", return_value=engine):
        captured, error_type = job2_io._load_assurance_capture_times("2026-08-22")

    assert captured == {7: NOW}
    assert error_type is None
    assert "captured_at" in str(connection.execute.call_args.args[0])

    secret_message = "postgresql://user:password@example/token-value"
    with (
        patch.object(job2_io, "get_engine", side_effect=RuntimeError(secret_message)),
        patch.object(job2_io.log, "warning") as warning,
    ):
        captured, error_type = job2_io._load_assurance_capture_times("2026-08-22")

    assert captured == {}
    assert error_type == "RuntimeError"
    assert warning.call_args.kwargs == {"error_type": "RuntimeError"}
    assert secret_message not in str(warning.call_args)


def test_assurance_timestamp_join_preserves_model_rows_and_order() -> None:
    model_rows = [_row(2), _row(1)]
    for row in model_rows:
        row.pop("captured_at")
    before = copy.deepcopy(model_rows)

    assurance_rows = job2._assurance_rows_with_capture_times(
        model_rows,
        {1: NOW, 2: NOW - dt.timedelta(minutes=5)},
    )

    assert model_rows == before
    assert [row["real_sports_player_id"] for row in assurance_rows] == ["2", "1"]
    assert [row["captured_at"] for row in assurance_rows] == [
        NOW - dt.timedelta(minutes=5),
        NOW,
    ]
