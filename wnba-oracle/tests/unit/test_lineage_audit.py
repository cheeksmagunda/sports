from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

from oracle_core import Dossier, DossierEntry, EntryKind, Exactness, Gap

from wnba_oracle.lineage import audit as lineage_audit


class _Result:
    def __init__(self, first_row=None, rows=None):
        self._first_row = first_row
        self._rows = rows or []

    def first(self):
        return self._first_row

    def fetchall(self):
        return self._rows


class _Row:
    def __init__(self, **kwargs):
        self._mapping = kwargs


_LEGACY = Dossier(
    slate_date="2026-09-20",
    entries={
        EntryKind.COMMITTED: DossierEntry(
            kind=EntryKind.COMMITTED,
            score=99.0,
            achievable=True,
            slot_order_basis="committed",
        ),
        EntryKind.FIELD_BEST: DossierEntry(
            kind=EntryKind.FIELD_BEST,
            score=109.0,
            achievable=True,
            slot_order_basis="as_entered",
        ),
        EntryKind.THEORETICAL_CEILING: DossierEntry(
            kind=EntryKind.THEORETICAL_CEILING,
            score=129.0,
            achievable=False,
            slot_order_basis="optimal_resort",
        ),
    },
    gap_to_field=Gap(
        from_kind=EntryKind.COMMITTED,
        to_kind=EntryKind.FIELD_BEST,
        value=10.0,
        exactness=Exactness.EXACT,
    ),
    gap_field_to_ceiling=Gap(
        from_kind=EntryKind.FIELD_BEST,
        to_kind=EntryKind.THEORETICAL_CEILING,
        value=20.0,
        exactness=Exactness.LOWER_BOUND,
    ),
    gap_to_ceiling=Gap(
        from_kind=EntryKind.COMMITTED,
        to_kind=EntryKind.THEORETICAL_CEILING,
        value=30.0,
        exactness=Exactness.LOWER_BOUND,
    ),
)


def _fake_connect(conn):
    ctx = MagicMock()
    ctx.__enter__.return_value = conn
    ctx.__exit__.return_value = None
    return ctx


@patch("wnba_oracle.lineage.audit.build_dossier", return_value=_LEGACY)
@patch(
    "wnba_oracle.lineage.audit._load_artifact_contract",
    return_value={
        "status": "available",
        "artifact_sha256": "sha-model",
        "feature_subset_per_head": {"minutes:F": ["mins_l10"]},
    },
)
def test_build_slate_audit_uses_snapshot_when_present(_artifact, _legacy) -> None:
    freeze_row = _Row(
        id=1,
        slate_date="2026-09-20",
        model_sha="sha-model",
        payout_regime="top_20",
        frozen_at=dt.datetime(2026, 9, 20, 18, tzinfo=dt.UTC),
        lineup={
            "player_ids": [1, 2, 3, 4, 5],
            "per_player": [
                {"display_name": f"P{i}", "team": f"T{i}", "position": "F"} for i in range(1, 6)
            ],
            "model_provenance": {
                "enrichment_sequence_sha256": "stored-seq",
                "enrichment_sha256": "stored-can",
                "optimizer_inputs_sha256": "opt-sha",
                "model_policy_sha256": "policy-sha",
            },
            "source_assurance": {"assessment_status": "observed", "observations": {}},
            "serving_knobs": {"max_per_team": 2},
            "payout_curve": {"regime": "top_20"},
        },
        entry_recommendation="enter",
        expected_payout=1.5,
        metadata_json={"frozen_via": "job2_first_fire"},
        freeze_seq=1,
        frozen_via="job2_first_fire",
        operation_key="first",
        audit_snapshot_sha256="snap-123",
    )
    conn = MagicMock()
    conn.execute.side_effect = [
        _Result(first_row=freeze_row),
        _Result(rows=[]),
        _Result(rows=[]),
        _Result(rows=[]),
        _Result(rows=[]),
        _Result(rows=[]),
        _Result(rows=[]),
        _Result(
            first_row=_Row(
                snapshot_sha256="snap-123",
                schema_version=1,
                created_at=dt.datetime(2026, 9, 20, 18, tzinfo=dt.UTC),
                payload_json={
                    "players": [
                        {"real_sports_player_id": "1", "prediction_path": {"tier": "trained_heads"}}
                    ]
                },
            )
        ),
    ]
    engine = MagicMock()
    engine.connect.return_value = _fake_connect(conn)

    payload = lineage_audit.build_slate_audit("2026-09-20", engine=engine)

    assert payload is not None
    assert payload["input_snapshot"]["status"] == "bound_snapshot_available"
    assert payload["prediction_paths"]["status"] == "captured_in_immutable_snapshot"
    assert payload["frozen_lineup"]["audit_snapshot_sha256"] == "snap-123"


@patch("wnba_oracle.lineage.audit.build_dossier", return_value=_LEGACY)
@patch(
    "wnba_oracle.lineage.audit._load_artifact_contract",
    return_value={"status": "unavailable", "artifact_sha256": "sha-model", "reason": "missing"},
)
@patch(
    "wnba_oracle.lineage.audit.canonical_enrichment_payload",
    return_value=b"current-canonical",
)
@patch(
    "wnba_oracle.lineage.audit.enrichment_sequence_payload",
    return_value=b"current-sequence",
)
def test_build_slate_audit_marks_missing_pre_phase2_state(
    _sequence,
    _canonical,
    _artifact,
    _legacy,
) -> None:
    freeze_row = _Row(
        id=1,
        slate_date="2026-09-20",
        model_sha="sha-model",
        payout_regime="top_20",
        frozen_at=dt.datetime(2026, 9, 20, 18, tzinfo=dt.UTC),
        lineup={
            "player_ids": [1, 2, 3, 4, 5],
            "per_player": [
                {"display_name": f"P{i}", "team": f"T{i}", "position": "F"} for i in range(1, 6)
            ],
            "model_provenance": {
                "enrichment_sequence_sha256": "stored-seq",
                "enrichment_sha256": "stored-can",
            },
            "source_assurance": {"assessment_status": "observed", "observations": {}},
        },
        entry_recommendation="enter",
        expected_payout=1.5,
        metadata_json={"frozen_via": "job2_first_fire"},
        freeze_seq=1,
        frozen_via="job2_first_fire",
        operation_key="first",
        audit_snapshot_sha256=None,
    )
    conn = MagicMock()
    conn.execute.side_effect = [
        _Result(first_row=freeze_row),
        _Result(
            rows=[
                _Row(
                    real_sports_player_id="1",
                    name="A",
                    team="NYL",
                    opponent="LAS",
                    position="F",
                    card_boost=0.5,
                    features_json={},
                    captured_at=dt.datetime(2026, 9, 20, 17, tzinfo=dt.UTC),
                )
            ]
        ),
        _Result(rows=[]),
        _Result(rows=[]),
        _Result(rows=[]),
        _Result(rows=[]),
        _Result(rows=[]),
        _Result(rows=[]),
    ]
    engine = MagicMock()
    engine.connect.return_value = _fake_connect(conn)

    payload = lineage_audit.build_slate_audit("2026-09-20", engine=engine)

    assert payload is not None
    assert payload["input_snapshot"]["status"] == "current_rows_do_not_match_freeze"
    assert payload["prediction_paths"]["status"] == "not_captured"
    assert "freeze_audit_snapshot" in payload["data_quality_and_censoring"]["missing_sources"]
