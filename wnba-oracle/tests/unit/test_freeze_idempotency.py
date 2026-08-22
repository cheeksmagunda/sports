"""Lock the true-freeze semantics in job2._freeze.

Once the operator submits a lineup based on the first frozen row, the
row must not be replaced underneath them by a later cron-job2 fire
(even if newer slate_labels draft data would have shifted the
contrarian adjustment). Postgres `(slate_date, model_sha)` is the
canonical lock; Redis SETNX is a fast-path soft-lock to avoid
intra-window races.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from wnba_oracle.modeling.policy import ModelPolicy
from wnba_oracle.modeling.provenance import ScoringProvenance
from wnba_oracle.picker.optimize import LineupRecommendation, OptimizeConfig
from wnba_oracle.picker.payout import default_curve_for_regime
from wnba_oracle.scheduler import job2, job2_freeze


def _rec() -> LineupRecommendation:
    return LineupRecommendation(
        player_ids=(1, 2, 3, 4, 5),
        slot_multipliers=(1.5, 1.3, 1.2, 1.1, 1.0),
        lineup_score_p10=120.0,
        lineup_score_p50=180.0,
        lineup_score_p90=240.0,
        entry_flag="enter",
        expected_payout=1.4,
    )


def _proj() -> dict[int, dict[str, Any]]:
    return {
        pid: {
            "display_name": f"P{pid}",
            "team": "LVA",
            "opponent": "NYL",
            "position": "F",
            "card_boost": 0.1,
            "pred_real_score_p50": 30.0,
        }
        for pid in (1, 2, 3, 4, 5)
    }


def _fake_engine(existing_row: bool, insert_returns_row: bool = True) -> MagicMock:
    eng = MagicMock()
    # `.connect()` returns a context manager whose conn.execute(FROZEN_EXISTS)
    # returns a result with `.first()` returning either a row or None.
    select_result = MagicMock()
    select_result.first.return_value = (1,) if existing_row else None
    select_conn = MagicMock()
    select_conn.execute.return_value = select_result
    eng.connect.return_value.__enter__.return_value = select_conn

    # `.begin()` returns a context manager whose conn.execute(FROZEN_INSERT)
    # returns a result with `.first()` returning the inserted row id or None.
    insert_result = MagicMock()
    insert_result.first.return_value = (42, 1) if insert_returns_row else None
    insert_conn = MagicMock()
    insert_conn.execute.return_value = insert_result
    eng.begin.return_value.__enter__.return_value = insert_conn
    return eng


def _fake_redis(lock_wins: bool) -> MagicMock:
    rd = MagicMock()
    rd.set.return_value = lock_wins
    return rd


def test_first_fire_writes_and_returns_true() -> None:
    eng = _fake_engine(existing_row=False, insert_returns_row=True)
    rd = _fake_redis(lock_wins=True)
    with (
        patch.object(job2_freeze, "get_engine", return_value=eng),
        patch.object(job2_freeze, "get_redis", return_value=rd),
    ):
        out = job2._freeze("2026-05-27", "heuristic-v1", _rec(), "top_20", _proj())
    assert out is True
    # SELECT (existence check) and INSERT both fired.
    eng.connect.return_value.__enter__.return_value.execute.assert_called_once()
    eng.begin.return_value.__enter__.return_value.execute.assert_called_once()


def test_second_fire_short_circuits_at_existence_check() -> None:
    """When Postgres already has the freeze row, neither Redis nor INSERT fire."""
    eng = _fake_engine(existing_row=True)
    rd = _fake_redis(lock_wins=True)
    with (
        patch.object(job2_freeze, "get_engine", return_value=eng),
        patch.object(job2_freeze, "get_redis", return_value=rd),
    ):
        out = job2._freeze("2026-05-27", "heuristic-v1", _rec(), "top_20", _proj())
    assert out is False
    rd.set.assert_not_called()
    eng.begin.assert_not_called()


def test_redis_lock_loss_bails_without_writing() -> None:
    """Concurrent cron fires race; loser of the Redis SETNX bails before INSERT."""
    eng = _fake_engine(existing_row=False)
    rd = _fake_redis(lock_wins=False)
    with (
        patch.object(job2_freeze, "get_engine", return_value=eng),
        patch.object(job2_freeze, "get_redis", return_value=rd),
    ):
        out = job2._freeze("2026-05-27", "heuristic-v1", _rec(), "top_20", _proj())
    assert out is False
    eng.begin.assert_not_called()


def test_unresolved_insert_race_raises_for_retry() -> None:
    """Two unexplained conflicts are a failed run, not a false success."""
    eng = _fake_engine(existing_row=False, insert_returns_row=False)
    rd = _fake_redis(lock_wins=True)
    with (
        patch.object(job2_freeze, "get_engine", return_value=eng),
        patch.object(job2_freeze, "get_redis", return_value=rd),
        pytest.raises(RuntimeError, match="sequence race"),
    ):
        job2._freeze("2026-05-27", "heuristic-v1", _rec(), "top_20", _proj())


def test_same_operation_race_returns_expected_noop() -> None:
    eng = _fake_engine(existing_row=False, insert_returns_row=False)
    select_conn = eng.connect.return_value.__enter__.return_value
    initial = MagicMock()
    initial.first.return_value = None
    duplicate = MagicMock()
    duplicate.first.return_value = (1,)
    select_conn.execute.side_effect = [initial, duplicate]
    rd = _fake_redis(lock_wins=True)
    with (
        patch.object(job2_freeze, "get_engine", return_value=eng),
        patch.object(job2_freeze, "get_redis", return_value=rd),
    ):
        out = job2._freeze("2026-05-27", "heuristic-v1", _rec(), "top_20", _proj())
    assert out is False


def test_freeze_payload_includes_per_player() -> None:
    """The JSONB lineup blob carries the per_player contract, verified by
    inspecting the INSERT bind params."""
    eng = _fake_engine(existing_row=False, insert_returns_row=True)
    rd = _fake_redis(lock_wins=True)
    with (
        patch.object(job2_freeze, "get_engine", return_value=eng),
        patch.object(job2_freeze, "get_redis", return_value=rd),
    ):
        job2._freeze(
            "2026-05-27",
            "heuristic-v1",
            _rec(),
            "top_20",
            _proj(),
            model_provenance={"model_policy_sha256": "policy-sha"},
            source_assurance={
                "assessment_status": "observed",
                "decision_input_sha256": "input-sha",
            },
        )
    insert_call = eng.begin.return_value.__enter__.return_value.execute.call_args
    payload = insert_call.args[1]
    import json

    lineup = json.loads(payload["lineup"])
    assert "per_player" in lineup
    assert len(lineup["per_player"]) == 5
    assert {row["player_id"] for row in lineup["per_player"]} == {1, 2, 3, 4, 5}
    assert lineup["model_provenance"] == {"model_policy_sha256": "policy-sha"}
    assert lineup["source_assurance"] == {
        "assessment_status": "observed",
        "decision_input_sha256": "input-sha",
    }


def test_freeze_recommendation_records_curve_and_serving_knobs() -> None:
    curve = default_curve_for_regime("top_20")
    cfg = OptimizeConfig(n_samples=250, n_field_lineups=125, min_anchors=2)
    policy = ModelPolicy(artifact_sha="a" * 64, optimizer=cfg)
    provenance = ScoringProvenance.capture(
        model_policy=policy,
        enrichment=[],
        sampling_specs=[],
        field_specs=[],
        payout_curve=curve,
    )
    with patch.object(job2, "_freeze", return_value=True) as freeze:
        frozen, status = job2._freeze_recommendation(
            slate_date="2026-05-27",
            model_sha="sha",
            recommendation=_rec(),
            curve=curve,
            cfg=cfg,
            projection_by_pid=_proj(),
            force_refreeze=False,
            frozen_via_override=None,
            scoring_provenance=provenance,
            source_assurance={"decision_input_sha256": provenance.enrichment_sha256},
        )

    assert frozen is True
    assert status == "ok"
    call = freeze.call_args
    assert call.kwargs["payout_curve"]["regime"] == "top_20"
    assert call.kwargs["serving_knobs"]["n_samples"] == 250
    assert call.kwargs["serving_knobs"]["n_field_lineups"] == 125
    assert call.kwargs["serving_knobs"]["min_anchors"] == 2
    assert call.kwargs["model_provenance"]["model_policy_sha256"] == policy.sha256
    assert call.kwargs["model_provenance"]["enrichment_rows"] == 0
    assert len(call.kwargs["model_provenance"]["optimizer_inputs_sha256"]) == 64
    assert call.kwargs["source_assurance"] == {
        "decision_input_sha256": provenance.enrichment_sha256
    }
