from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

from wnba_oracle.lineage.freeze_snapshot import (
    FREEZE_AUDIT_SNAPSHOT_INSERT,
    build_freeze_audit_snapshot,
    persist_freeze_audit_snapshot,
)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class _Row:
    def __init__(self, **kwargs):
        self._mapping = kwargs


@patch("wnba_oracle.lineage.freeze_snapshot._artifact_contract")
def test_build_freeze_audit_snapshot_captures_prediction_path_and_identity(mock_artifact_contract):
    mock_artifact_contract.return_value = {
        "status": "available",
        "artifact_sha256": "sha-model",
        "feature_subset_per_head": {
            "minutes:F": ["mins_l10", "team_pace"],
            "real_score_per_min:F": ["mins_l10", "team_pace"],
        },
    }
    conn = MagicMock()
    conn.execute.return_value = _Result(
        [
            _Row(
                real_sports_player_id="101",
                wnba_player_id=9001,
                provenance="provider_nba_id",
                provider_nba_id=9001,
                real_sports_display_name="A Player",
                real_sports_team="NYL",
                wnba_full_name="A Player",
                first_seen_at=dt.datetime(2026, 9, 20, 12, tzinfo=dt.UTC),
                last_seen_at=dt.datetime(2026, 9, 20, 12, tzinfo=dt.UTC),
            )
        ]
    )

    payload = build_freeze_audit_snapshot(
        slate_date="2026-09-20",
        model_sha="sha-model",
        frozen_at=dt.datetime(2026, 9, 20, 13, tzinfo=dt.UTC),
        enrichment_rows=[
            {
                "real_sports_player_id": "101",
                "name": "A Player",
                "team": "NYL",
                "opponent": "LAS",
                "position": "F",
                "card_boost": 0.5,
                "captured_at": dt.datetime(2026, 9, 20, 12, 30, tzinfo=dt.UTC),
                "features_json": {"head_features": {"mins_l10": 28.0}},
            }
        ],
        projection_by_pid={
            101: {
                "display_name": "A Player",
                "_prediction_audit": {
                    "tier": "trained_heads",
                    "final_optimizer_score": 17.25,
                },
            }
        },
        scoring_provenance={"optimizer_inputs_sha256": "abc", "model_policy_sha256": "def"},
        source_assurance={"assessment_status": "observed"},
        freeze_context={"frozen_via": "job2_first_fire"},
        conn=conn,
    )

    assert payload["artifact_contract"]["status"] == "available"
    assert payload["players"][0]["prediction_path"]["tier"] == "trained_heads"
    assert payload["players"][0]["serve_contract"]["status"] == "consumed"
    assert payload["players"][0]["serve_contract"]["defaulted_feature_columns"] == ["team_pace"]
    assert payload["players"][0]["identity_resolution"]["wnba_player_id"] == 9001


def test_persist_freeze_audit_snapshot_is_content_addressed() -> None:
    conn = MagicMock()
    payload = {"schema_version": 1, "slate_date": "2026-09-20", "players": []}

    digest = persist_freeze_audit_snapshot(conn, payload)

    call = conn.execute.call_args
    assert call.args[0] == FREEZE_AUDIT_SNAPSHOT_INSERT
    assert call.args[1]["snapshot_sha256"] == digest
    assert len(digest) == 64
