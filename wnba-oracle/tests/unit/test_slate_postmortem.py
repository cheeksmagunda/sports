"""#35 phase 3: unified post-slate dossier composition and failure paths."""

from __future__ import annotations

import datetime as dt
import math
from typing import Any
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from wnba_oracle.api.app import app
from wnba_oracle.lineage import audit as lineage_audit
from wnba_oracle.lineage.postmortem import (
    SECTION_STATUSES,
    compose_box_scores,
    compose_comparison,
    settlement_status,
    source_status,
)

_FROZEN_AT = dt.datetime(2026, 9, 20, 18, tzinfo=dt.UTC)


class _Row:
    def __init__(self, **kwargs: Any) -> None:
        self._mapping = kwargs


class _Result:
    def __init__(self, rows: list[_Row]) -> None:
        self._rows = rows

    def first(self) -> _Row | None:
        return self._rows[0] if self._rows else None

    def fetchall(self) -> list[_Row]:
        return self._rows


class _DispatchConn:
    """Fake connection that answers by table name, not call order."""

    def __init__(self, tables: dict[str, list[_Row]], fail: set[str] | None = None) -> None:
        self.tables = tables
        self.fail = fail or set()
        self.queried: list[str] = []

    def execute(self, query: Any, params: Any = None) -> _Result:
        sql = str(query)
        # Order matters: the freeze-history query also reads frozen_lineups.
        for table in (
            "freeze_audit_snapshots",
            "canonical_player_identities",
            "job1_enrichment",
            "slate_labels",
            "contest_leaderboards",
            "contest_placements",
            "slate_meta",
            "wnba_game_logs",
            "frozen_lineups",
        ):
            if f"FROM {table}" in sql:
                self.queried.append(table)
                if table in self.fail:
                    raise RuntimeError("boom")
                return _Result(self.tables.get(table, []))
        raise AssertionError(f"unexpected query: {sql}")


def _engine(conn: _DispatchConn) -> MagicMock:
    ctx = MagicMock()
    ctx.__enter__.return_value = conn
    ctx.__exit__.return_value = None
    engine = MagicMock()
    engine.connect.return_value = ctx
    return engine


def _assurance(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "assessment_status": "observed",
        "capture": {"rows": 3},
        "observations": {
            "realsports": {"core_rows": 3, "game_time_rows": 3},
            "rotowire": {"starter_rows": 1, "confirmed_rows": 1},
            "the_odds_api": {"vegas_rows": 0, "prop_rows": 0},
            "wnba_stats": {"minutes_rows": 3, "head_feature_rows": 3},
        },
    }
    payload.update(overrides)
    return payload


def _freeze_row(*, audit_snapshot_sha256: str | None = None, **lineup_extra: Any) -> _Row:
    lineup = {
        "player_ids": [1, 2, 3, 4, 5],
        "per_player": [
            {
                "player_id": i,
                "display_name": f"P{i}",
                "team": f"T{i}",
                "position": "F",
                "pred_real_score_p50": float(10 + i),
            }
            for i in range(1, 6)
        ],
        "model_provenance": {
            "enrichment_sequence_sha256": "stored-seq",
            "enrichment_sha256": "stored-can",
            "optimizer_inputs_sha256": "opt-sha",
            "model_policy_sha256": "policy-sha",
            "model_policy": {"max_per_team": 2},
            "optimizer_inputs": {
                "sampling_specs": [
                    {"player_id": i, "mu": math.log(10.0 + i), "sigma": 0.3, "p_active": 1.0}
                    for i in range(1, 8)
                ]
            },
        },
        "source_assurance": _assurance(),
        "serving_knobs": {"max_per_team": 2},
        "payout_curve": {"regime": "top_20"},
    }
    lineup.update(lineup_extra)
    return _Row(
        id=7,
        slate_date="2026-09-20",
        model_sha="sha-model",
        payout_regime="top_20",
        frozen_at=_FROZEN_AT,
        lineup=lineup,
        entry_recommendation="enter",
        expected_payout=1.5,
        metadata_json={},
        freeze_seq=1,
        frozen_via="job2_first_fire",
        operation_key="first",
        audit_snapshot_sha256=audit_snapshot_sha256,
    )


def _label(pid: int, score: float) -> _Row:
    return _Row(
        contest_id="c1",
        slate_date="2026-09-20",
        section="main",
        platform_player_id=pid,
        display_name=f"P{pid}",
        team_key=f"T{pid}",
        card_boost=0.5,
        drafts=10,
        real_score=score,
        ingested_at=_FROZEN_AT + dt.timedelta(days=1),
    )


# ---------------------------------------------------------------------------
# source_status
# ---------------------------------------------------------------------------


def test_source_status_is_per_source_not_slate_wide() -> None:
    assurance = _assurance()
    assert source_status(assurance, "realsports")["status"] == "available"
    assert source_status(assurance, "rotowire")["status"] == "partial"
    odds = source_status(assurance, "the_odds_api")
    assert odds["status"] == "unavailable"
    assert odds["reason"] == "zero_rows_observed_at_capture"
    assert odds["slate_assessment_status"] == "observed"


def test_source_status_reports_assurance_failure_shape() -> None:
    failed = {"assessment_status": "unknown", "error": {"type": "ValueError"}}
    result = source_status(failed, "rotowire")
    assert result["status"] == "unavailable"
    assert result["reason"] == "assurance_failed:ValueError"
    assert result["evidence"] is None


def test_source_status_not_captured_when_observations_absent() -> None:
    result = source_status({"assessment_status": "observed"}, "wnba_stats")
    assert result["status"] == "not_captured"
    assert result["evidence"] is None


# ---------------------------------------------------------------------------
# box scores
# ---------------------------------------------------------------------------


def test_box_scores_never_match_unresolved_identity_by_name() -> None:
    result = compose_box_scores(
        slate_date="2026-09-20",
        selected_ids=["1", "2"],
        identity_rows=[{"real_sports_player_id": "1", "wnba_player_id": 101}],
        game_log_rows=[
            {"player_id": 101, "player_name": "P1", "pts": 20.0, "min": 30.0},
            # Same display name as player 2 but no identity row: must not join.
            {"player_id": 202, "player_name": "P2", "pts": 5.0, "min": 10.0},
        ],
    )
    by_pid = {row["real_sports_player_id"]: row for row in result["players"]}
    assert by_pid["1"]["box_score_status"] == "available"
    assert by_pid["1"]["box_score"]["pts"] == 20.0
    assert by_pid["2"]["identity_status"] == "identity_unresolved"
    assert by_pid["2"]["box_score"] is None
    assert result["status"] == "partial"


def test_box_scores_report_read_failure() -> None:
    result = compose_box_scores(
        slate_date="2026-09-20",
        selected_ids=["1"],
        identity_rows=[{"real_sports_player_id": "1", "wnba_player_id": 101}],
        game_log_rows=[],
        load_error="OperationalError",
    )
    assert result["status"] == "unavailable"
    assert result["reason"] == "game_log_read_failed:OperationalError"


# ---------------------------------------------------------------------------
# comparison
# ---------------------------------------------------------------------------


_LINEUP = {
    "player_ids": [1, 2, 3, 4, 5],
    "per_player": [{"player_id": i, "pred_real_score_p50": 10.0} for i in range(1, 6)],
}
_RESULTS = [
    {"platform_player_id": i, "real_score": float(score), "display_name": f"P{i}"}
    for i, score in [(1, 8), (2, 12), (3, 9), (4, 11), (5, 7), (6, 30), (9, 25)]
]


def test_comparison_uses_snapshot_when_bound() -> None:
    snapshot = [
        {
            "real_sports_player_id": str(i),
            "prediction_path": {"tier": "trained_heads", "final_optimizer_score": 10.0},
            "serve_contract": {"defaulted_feature_columns": []},
            "identity_resolution": {"status": "available"},
        }
        for i in range(1, 6)
    ] + [
        {
            "real_sports_player_id": "6",
            "prediction_path": {
                "tier": "heuristic_fallback",
                "final_optimizer_score": 4.0,
                "availability_probability": 0.3,
            },
            "serve_contract": {},
            "identity_resolution": {"status": "unavailable"},
        }
    ]
    result = compose_comparison(
        lineup_payload=_LINEUP,
        model_provenance={},
        snapshot_players=snapshot,
        result_rows=_RESULTS,
    )
    assert result["status"] == "available"
    assert result["explanation_basis"] == "snapshot_exact"
    assert [row["slot"] for row in result["selected"]] == [1, 2, 3, 4, 5]
    alternatives = {
        row["real_sports_player_id"]: row for row in result["top_realized_not_selected"]
    }
    six = alternatives["6"]
    assert six["predicted"] == 4.0
    assert six["realized_minus_predicted"] == 26.0
    assert "fallback_tier:heuristic_fallback" in six["findings"]
    assert "availability_hurdle_below_0.5" in six["findings"]
    assert "identity_unresolved_at_freeze" in six["findings"]
    # Player 9 realized but was never in the snapshot decision inputs.
    assert alternatives["9"]["in_decision_inputs"] is False
    assert "absent_from_decision_inputs" in alternatives["9"]["findings"]
    assert alternatives["9"]["predicted"] is None


def test_comparison_falls_back_to_optimizer_inputs_pre_phase2() -> None:
    provenance = {
        "optimizer_inputs": {
            "sampling_specs": [{"player_id": i, "mu": math.log(9.0)} for i in range(1, 7)]
        }
    }
    result = compose_comparison(
        lineup_payload=_LINEUP,
        model_provenance=provenance,
        snapshot_players=None,
        result_rows=_RESULTS,
    )
    assert result["status"] == "partial"
    assert result["explanation_basis"] == "optimizer_inputs"
    selected = result["selected"][0]
    assert selected["predicted_basis"] == "frozen_lineup.pred_real_score_p50"
    six = next(r for r in result["top_realized_not_selected"] if r["real_sports_player_id"] == "6")
    assert six["predicted_basis"] == "exp(sampling_spec.mu)"
    assert abs(six["predicted"] - 9.0) < 1e-9
    assert six["prediction_tier"] is None


def test_comparison_pending_and_unavailable() -> None:
    pending = compose_comparison(
        lineup_payload=_LINEUP, model_provenance={}, snapshot_players=None, result_rows=[]
    )
    assert pending["status"] == "pending"
    assert pending["explanation_basis"] == "selected_players_only"
    assert all(row["realized_status"] == "pending" for row in pending["selected"])

    unavailable = compose_comparison(
        lineup_payload={"player_ids": [1]},
        model_provenance={},
        snapshot_players=None,
        result_rows=_RESULTS,
    )
    assert unavailable["status"] == "unavailable"
    assert unavailable["reason"] == "no_persisted_prediction_for_freeze"


# ---------------------------------------------------------------------------
# end-to-end composition over a fake database
# ---------------------------------------------------------------------------


def _build(conn: _DispatchConn) -> dict[str, Any] | None:
    with (
        patch.object(lineage_audit, "build_dossier", return_value=None),
        patch.object(
            lineage_audit,
            "_load_artifact_contract",
            return_value={"status": "unavailable", "artifact_sha256": "sha-model", "reason": "x"},
        ),
    ):
        return lineage_audit.build_post_slate_dossier("2026-09-20", engine=_engine(conn))


def test_pending_slate_has_explicit_status_in_every_section() -> None:
    conn = _DispatchConn({"frozen_lineups": [_freeze_row()]})

    payload = _build(conn)

    assert payload is not None
    assert payload["status"] == "pending"
    assert payload["status_reason"] == "slate_labels_not_ingested_yet"
    assert payload["dossier_schema_version"] == 1
    assert payload["entries_status"]["status"] == "pending"
    assert "entries" not in payload
    sections = payload["sections"]
    assert [section["point"] for section in sections] == list(range(1, 13))
    for section in sections:
        assert section["status"] in SECTION_STATUSES, section
        if section["status"] != "available":
            assert section["reason"], section
    by_name = {section["name"]: section for section in sections}
    assert by_name["realized_outcome"]["status"] == "pending"
    assert by_name["comparison"]["status"] == "pending"
    assert by_name["prediction_path"]["status"] == "not_captured"
    assert by_name["training_contract"]["status"] == "unavailable"
    assert by_name["freeze_audit_state"]["status"] == "partial"
    assert payload["contest_results"]["leaderboard_status"]["status"] == "pending"
    assert payload["our_outcome"]["status"] == "pending"
    assert payload["our_outcome"]["reason"]
    # No identity rows, so the game log table is never queried by name.
    assert "wnba_game_logs" not in conn.queried
    assert payload["box_scores"]["status"] == "unavailable"


def test_missing_assurance_and_provenance_are_explicit() -> None:
    freeze = _freeze_row(
        source_assurance={"assessment_status": "unknown", "error": {"type": "TypeError"}},
        model_provenance={},
        payout_curve={},
    )
    payload = _build(_DispatchConn({"frozen_lineups": [freeze]}))

    assert payload is not None
    for source in ("realsports", "rotowire", "the_odds_api", "wnba_stats"):
        assert payload["sources"][source]["status"] == "unavailable"
        assert payload["sources"][source]["reason"] == "assurance_failed:TypeError"
    assert payload["sources"]["payout_archive"]["status"] == "not_captured"
    assert payload["optimizer"]["status"] == "not_captured"
    by_name = {section["name"]: section for section in payload["sections"]}
    assert by_name["optimizer_state"]["status"] == "not_captured"
    assert by_name["policy_configuration"]["status"] == "not_captured"
    assert by_name["comparison"]["status"] == "pending"
    assert payload["comparison"]["explanation_basis"] == "selected_players_only"


def test_settled_slate_with_box_scores_and_snapshot() -> None:
    snapshot_payload = {
        "players": [
            {
                "real_sports_player_id": str(i),
                "display_name": f"P{i}",
                "prediction_path": {"tier": "trained_heads", "final_optimizer_score": 10.0},
                "serve_contract": {"status": "consumed", "defaulted_feature_columns": []},
                "identity_resolution": {"status": "available"},
            }
            for i in range(1, 6)
        ]
    }
    conn = _DispatchConn(
        {
            "frozen_lineups": [_freeze_row(audit_snapshot_sha256="snap-1")],
            "freeze_audit_snapshots": [
                _Row(
                    snapshot_sha256="snap-1",
                    schema_version=1,
                    created_at=_FROZEN_AT,
                    payload_json=snapshot_payload,
                )
            ],
            "job1_enrichment": [
                _Row(
                    real_sports_player_id=str(i),
                    name=f"P{i}",
                    team=f"T{i}",
                    opponent="X",
                    position="F",
                    card_boost=0.5,
                    features_json={},
                    captured_at=_FROZEN_AT,
                )
                for i in range(1, 6)
            ],
            "canonical_player_identities": [
                _Row(
                    real_sports_player_id=str(i),
                    wnba_player_id=100 + i,
                    provenance="exact",
                    provider_nba_id=None,
                    real_sports_display_name=f"P{i}",
                    real_sports_team=f"T{i}",
                    wnba_full_name=f"P{i}",
                    first_seen_at=_FROZEN_AT,
                    last_seen_at=_FROZEN_AT,
                )
                for i in range(1, 6)
            ],
            "slate_labels": [_label(i, 10.0 + i) for i in range(1, 7)],
            "contest_leaderboards": [
                _Row(
                    contest_id="c1",
                    entry_id="e1",
                    rank=1,
                    paged_rank=1,
                    user_id="u1",
                    score=200.0,
                    lineup=[],
                    num_brawlers=1000,
                    ingested_at=_FROZEN_AT,
                )
            ],
            "contest_placements": [
                _Row(
                    slate_date="2026-09-20",
                    contest_id="c1",
                    recorded_at=_FROZEN_AT,
                    source="dayclose",
                    entry_rank=40,
                    entry_count=1000,
                    entry_score=150.0,
                    payout_received_cents=500,
                    entry_fee_cents=100,
                    finish_percentile=0.96,
                    cashed=True,
                    top_10pct=True,
                    top_1pct=False,
                    roi=4.0,
                    freeze_model_sha="sha-model",
                    expected_payout=1.5,
                    lineup_score_p10=None,
                    lineup_score_p50=None,
                    lineup_score_p90=None,
                    payout_curve_json=None,
                    freeze_config_json=None,
                    predicted_ownership_json=None,
                    actual_ownership_json=None,
                    metadata_json=None,
                )
            ],
            "wnba_game_logs": [
                _Row(
                    game_date="2026-09-20",
                    player_id=100 + i,
                    player_name=f"P{i}",
                    team=f"T{i}",
                    opponent="X",
                    game_id="g1",
                    min=30.0,
                    pts=15.0,
                    reb=5.0,
                    ast=3.0,
                    stl=1.0,
                    blk=0.0,
                    tov=2.0,
                    fgm=6.0,
                    fga=12.0,
                    fg3m=1.0,
                    ftm=2.0,
                    fta=2.0,
                    ingested_at=_FROZEN_AT,
                )
                for i in range(1, 6)
            ],
        }
    )

    payload = _build(conn)

    assert payload is not None
    assert payload["status"] == "finalized"
    assert payload["status_reason"] is None
    assert payload["box_scores"]["status"] == "available"
    assert payload["comparison"]["status"] == "available"
    assert payload["comparison"]["explanation_basis"] == "snapshot_exact"
    assert payload["sources"]["identity_mapping"]["coverage"]["unresolved"] == []
    by_name = {section["name"]: section for section in payload["sections"]}
    assert by_name["captured_state"]["status"] == "available"
    assert by_name["prediction_path"]["status"] == "available"
    assert by_name["identity_resolution"]["status"] == "available"
    assert by_name["freeze_audit_state"]["status"] == "available"
    assert by_name["realized_outcome"]["status"] == "available"
    assert payload["our_outcome"]["payout_received"] == 5.0


def test_game_log_read_failure_does_not_fail_dossier() -> None:
    conn = _DispatchConn(
        {
            "frozen_lineups": [_freeze_row()],
            "job1_enrichment": [
                _Row(
                    real_sports_player_id="1",
                    name="P1",
                    team="T1",
                    opponent="X",
                    position="F",
                    card_boost=0.5,
                    features_json={},
                    captured_at=_FROZEN_AT,
                )
            ],
            "canonical_player_identities": [
                _Row(
                    real_sports_player_id="1",
                    wnba_player_id=101,
                    provenance="exact",
                    provider_nba_id=None,
                    real_sports_display_name="P1",
                    real_sports_team="T1",
                    wnba_full_name="P1",
                    first_seen_at=_FROZEN_AT,
                    last_seen_at=_FROZEN_AT,
                )
            ],
            "slate_labels": [_label(1, 12.0)],
        },
        fail={"wnba_game_logs"},
    )

    payload = _build(conn)

    assert payload is not None
    assert payload["status"] == "partial"
    assert "contest_leaderboards" in payload["status_reason"]
    assert payload["box_scores"]["status"] == "unavailable"
    assert payload["box_scores"]["reason"] == "game_log_read_failed:RuntimeError"
    coverage = payload["sources"]["identity_mapping"]["coverage"]
    assert coverage == {"pool_players": 1, "resolved": 1, "unresolved": []}


def test_box_scores_resolve_committed_five_without_job1_enrichment() -> None:
    identities = [
        _Row(
            real_sports_player_id=str(i),
            wnba_player_id=100 + i,
            provenance="exact",
            provider_nba_id=None,
            real_sports_display_name=f"P{i}",
            real_sports_team=f"T{i}",
            wnba_full_name=f"P{i}",
            first_seen_at=_FROZEN_AT,
            last_seen_at=_FROZEN_AT,
        )
        for i in range(1, 6)
    ]
    logs = [
        _Row(
            game_date="2026-09-20",
            player_id=100 + i,
            player_name=f"P{i}",
            team=f"T{i}",
            opponent="X",
            game_id="g1",
            min=30.0,
            pts=15.0,
            reb=5.0,
            ast=3.0,
            stl=1.0,
            blk=0.0,
            tov=2.0,
            fgm=6.0,
            fga=12.0,
            fg3m=1.0,
            ftm=2.0,
            fta=2.0,
            ingested_at=_FROZEN_AT,
        )
        for i in range(1, 6)
    ]
    conn = _DispatchConn(
        {
            "frozen_lineups": [_freeze_row()],
            "canonical_player_identities": identities,
            "wnba_game_logs": logs,
            "slate_labels": [_label(i, 10.0) for i in range(1, 6)],
        }
    )

    payload = _build(conn)

    assert payload is not None
    # The pool lookup had no job1_enrichment rows to key off, so the pool-level
    # identity_mapping stays unavailable, but the committed five still resolve
    # through canonical_player_identities.
    assert payload["sources"]["identity_mapping"]["status"] == "unavailable"
    assert payload["box_scores"]["status"] == "available"
    assert all(p["identity_status"] == "resolved" for p in payload["box_scores"]["players"])


def test_no_freeze_returns_none() -> None:
    assert _build(_DispatchConn({})) is None


def test_settlement_status_rules() -> None:
    assert settlement_status({"realized_player_results": {"status": "pending"}})[0] == "pending"
    partial = settlement_status(
        {
            "realized_player_results": {"status": "available"},
            "contest_results": {"leaderboard_status": {"status": "available"}},
            "our_outcome": {"status": "unavailable"},
        }
    )
    assert partial == ("partial", "missing:contest_placements")


# ---------------------------------------------------------------------------
# API surface
# ---------------------------------------------------------------------------


def test_api_returns_pending_dossier_with_200() -> None:
    body = {"slate_date": "2026-09-20", "status": "pending", "sections": []}
    with (
        patch("wnba_oracle.api.dossier.get_engine", return_value="fake-engine"),
        patch("wnba_oracle.api.dossier.build_post_slate_dossier", return_value=body),
    ):
        resp = TestClient(app).get("/dossier/2026-09-20")
    assert resp.status_code == 200
    assert resp.json()["status"] == "pending"


def test_api_404_detail_names_missing_freeze() -> None:
    with (
        patch("wnba_oracle.api.dossier.get_engine", return_value="fake-engine"),
        patch("wnba_oracle.api.dossier.build_post_slate_dossier", return_value=None),
    ):
        resp = TestClient(app).get("/dossier/2026-09-20")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "no frozen lineup for slate"
