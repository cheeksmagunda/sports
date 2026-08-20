"""D75: late re-freeze path in job2._freeze(force=True).

When LATE_REFREEZE_ENABLED=true and the current UTC time is past
LATE_REFREEZE_AFTER_UTC, _freeze() is called with force=True. The force
path skips the Postgres existence check, uses the wnba.late_frozen.{sd}
Redis key (first-fire-wins, 24h TTL), and (since D82) APPENDS a new
frozen row via FROZEN_APPEND so the 21:00 UTC freeze stays intact.
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from wnba_oracle.picker.optimize import LineupRecommendation
from wnba_oracle.scheduler import job2


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


def _fake_engine_for_force(upsert_returns_row: bool = True) -> MagicMock:
    """Engine mock for force=True path: begin() fires (no connect() needed)."""
    eng = MagicMock()
    upsert_result = MagicMock()
    upsert_result.first.return_value = (99, 2) if upsert_returns_row else None
    upsert_conn = MagicMock()
    upsert_conn.execute.return_value = upsert_result
    eng.begin.return_value.__enter__.return_value = upsert_conn
    return eng


def _fake_redis(lock_wins: bool) -> MagicMock:
    rd = MagicMock()
    rd.set.return_value = lock_wins
    return rd


def test_force_skips_postgres_existence_check() -> None:
    """force=True never calls connect(); the existence check is bypassed."""
    eng = _fake_engine_for_force(upsert_returns_row=True)
    rd = _fake_redis(lock_wins=True)
    with (
        patch.object(job2, "get_engine", return_value=eng),
        patch.object(job2, "get_redis", return_value=rd),
    ):
        out = job2._freeze("2026-06-07", "heuristic-v1", _rec(), "top_20", _proj(), force=True)
    assert out is True
    eng.connect.assert_not_called()
    eng.begin.assert_called_once()


def test_force_acquires_late_frozen_redis_key() -> None:
    """force=True uses wnba.late_frozen.{sd} with NX and 24h TTL."""
    eng = _fake_engine_for_force()
    rd = _fake_redis(lock_wins=True)
    with (
        patch("oracle_core.storage.secrets.token_urlsafe", return_value="late-owner-token"),
        patch.object(job2, "get_engine", return_value=eng),
        patch.object(job2, "get_redis", return_value=rd),
    ):
        job2._freeze("2026-06-07", "heuristic-v1", _rec(), "top_20", _proj(), force=True)
    rd.set.assert_called_once_with(
        "wnba.late_frozen.2026-06-07", "late-owner-token", nx=True, ex=24 * 3600
    )


def test_force_append_failure_releases_matching_owner_token() -> None:
    """A failed append releases only the lease token acquired by this fire."""
    eng = _fake_engine_for_force()
    eng.begin.return_value.__enter__.return_value.execute.side_effect = RuntimeError("write failed")
    rd = _fake_redis(lock_wins=True)
    with (
        patch("oracle_core.storage.secrets.token_urlsafe", return_value="late-owner-token"),
        patch.object(job2, "get_engine", return_value=eng),
        patch.object(job2, "get_redis", return_value=rd),
        pytest.raises(RuntimeError, match="failed to append"),
    ):
        job2._freeze("2026-06-07", "heuristic-v1", _rec(), "top_20", _proj(), force=True)

    rd.set.assert_called_once_with(
        "wnba.late_frozen.2026-06-07", "late-owner-token", nx=True, ex=24 * 3600
    )
    assert rd.eval.call_count == 1
    assert rd.eval.call_args.args[1:] == (
        1,
        "wnba.late_frozen.2026-06-07",
        "late-owner-token",
    )


def test_force_second_fire_bails_on_late_frozen_key() -> None:
    """If wnba.late_frozen.{sd} is already set, the second late-fire bails
    without touching Postgres, which prevents overwriting twice."""
    eng = _fake_engine_for_force()
    rd = _fake_redis(lock_wins=False)
    with (
        patch.object(job2, "get_engine", return_value=eng),
        patch.object(job2, "get_redis", return_value=rd),
    ):
        out = job2._freeze("2026-06-07", "heuristic-v1", _rec(), "top_20", _proj(), force=True)
    assert out is False
    eng.begin.assert_not_called()


def test_force_append_payload_frozen_via_late_refreeze() -> None:
    """Both the frozen_via column and the metadata_json copy mark the row
    as a late re-freeze."""
    eng = _fake_engine_for_force()
    rd = _fake_redis(lock_wins=True)
    with (
        patch.object(job2, "get_engine", return_value=eng),
        patch.object(job2, "get_redis", return_value=rd),
    ):
        job2._freeze("2026-06-07", "heuristic-v1", _rec(), "top_20", _proj(), force=True)
    call_args = eng.begin.return_value.__enter__.return_value.execute.call_args
    payload = call_args.args[1]
    assert payload["frozen_via"] == "job2_late_refreeze"
    meta = json.loads(payload["metadata_json"])
    assert meta["frozen_via"] == "job2_late_refreeze"


def test_force_uses_append_statement_not_update() -> None:
    """D82: the force path appends a new row; the SQL must not contain an
    ON CONFLICT ... DO UPDATE clause that could touch the earlier freeze."""
    eng = _fake_engine_for_force()
    rd = _fake_redis(lock_wins=True)
    with (
        patch.object(job2, "get_engine", return_value=eng),
        patch.object(job2, "get_redis", return_value=rd),
    ):
        job2._freeze("2026-06-07", "heuristic-v1", _rec(), "top_20", _proj(), force=True)
    call_args = eng.begin.return_value.__enter__.return_value.execute.call_args
    sql = str(call_args.args[0])
    assert "DO UPDATE" not in sql
    assert "DO NOTHING" in sql
    assert "freeze_seq" in sql


def test_force_false_preserves_normal_flow() -> None:
    """force=False (the default) still goes through the existence check path."""
    eng = MagicMock()
    select_result = MagicMock()
    select_result.first.return_value = (1,)  # row already exists
    select_conn = MagicMock()
    select_conn.execute.return_value = select_result
    eng.connect.return_value.__enter__.return_value = select_conn
    rd = _fake_redis(lock_wins=True)
    with (
        patch.object(job2, "get_engine", return_value=eng),
        patch.object(job2, "get_redis", return_value=rd),
    ):
        out = job2._freeze("2026-06-07", "heuristic-v1", _rec(), "top_20", _proj(), force=False)
    assert out is False
    eng.connect.assert_called_once()
    eng.begin.assert_not_called()
