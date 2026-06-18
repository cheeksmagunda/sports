"""Regression tests for the 2026-06-13 freeze outage.

Two bugs silently blocked every freeze:
1. FROZEN_APPEND reused the :model_sha bind param in the SELECT and the WHERE.
   After migration 0008 widened the column to varchar(64), Postgres deduced
   inconsistent types ("text versus character varying") and raised
   AmbiguousParameter on every append. Fixed by an explicit CAST(... AS varchar).
2. The Redis freeze lock is taken before the append with a 24h TTL. When the
   append then failed, the lock stayed set and deferred every later fire for a
   full day, wedging the slate. Fixed by releasing the lock on append failure.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

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


def test_frozen_append_casts_model_sha() -> None:
    """The reused :model_sha param is cast to varchar in both the SELECT and
    the WHERE so Postgres unifies its type (the AmbiguousParameter fix)."""
    sql = str(job2.FROZEN_APPEND)
    assert sql.count("CAST(:model_sha AS varchar)") == 2


def test_release_freeze_lock_first_fire_key() -> None:
    rd = MagicMock()
    with patch.object(job2, "get_redis", return_value=rd):
        job2._release_freeze_lock("2026-06-18", force=False)
    rd.delete.assert_called_once_with("wnba.frozen.2026-06-18")


def test_release_freeze_lock_late_refreeze_key() -> None:
    rd = MagicMock()
    with patch.object(job2, "get_redis", return_value=rd):
        job2._release_freeze_lock("2026-06-18", force=True)
    rd.delete.assert_called_once_with("wnba.late_frozen.2026-06-18")


def test_release_freeze_lock_swallows_redis_error() -> None:
    rd = MagicMock()
    rd.delete.side_effect = RuntimeError("redis down")
    with patch.object(job2, "get_redis", return_value=rd):
        job2._release_freeze_lock("2026-06-18", force=False)  # must not raise


def test_freeze_releases_lock_when_append_raises() -> None:
    """A failing append releases the Redis lock and returns False, so the next
    fire retries instead of waiting out the 24h TTL."""
    eng = MagicMock()
    # existence check: no row
    select_conn = MagicMock()
    select_conn.execute.return_value.first.return_value = None
    eng.connect.return_value.__enter__.return_value = select_conn
    # append raises
    eng.begin.return_value.__enter__.return_value.execute.side_effect = RuntimeError(
        "AmbiguousParameter"
    )
    rd = MagicMock()
    rd.set.return_value = True  # lock acquired
    with patch.object(job2, "get_engine", return_value=eng), patch.object(
        job2, "get_redis", return_value=rd
    ):
        out = job2._freeze("2026-06-18", "sha", _rec(), "top_20", _proj(), force=False)
    assert out is False
    rd.delete.assert_called_once_with("wnba.frozen.2026-06-18")
