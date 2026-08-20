"""D82: append-only freeze writes in job2._freeze.

Every freeze fire appends a new frozen_lineups row keyed on
(slate_date, model_sha, freeze_seq). The seq is computed inside
FROZEN_APPEND's source SELECT; a seq collision surfaces as an empty
RETURNING, which _freeze retries exactly once.
"""

from __future__ import annotations

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


def _fake_redis(lock_wins: bool = True) -> MagicMock:
    rd = MagicMock()
    rd.set.return_value = lock_wins
    return rd


def _engine_with_results(first_returns: list) -> MagicMock:
    """Engine mock whose begin().execute().first() walks `first_returns`.
    connect() (existence check) always reports no existing row."""
    eng = MagicMock()
    select_result = MagicMock()
    select_result.first.return_value = None
    select_conn = MagicMock()
    select_conn.execute.return_value = select_result
    eng.connect.return_value.__enter__.return_value = select_conn

    insert_result = MagicMock()
    insert_result.first.side_effect = first_returns
    insert_conn = MagicMock()
    insert_conn.execute.return_value = insert_result
    eng.begin.return_value.__enter__.return_value = insert_conn
    return eng


def test_first_fire_sets_frozen_via_column() -> None:
    eng = _engine_with_results([(42, 1)])
    rd = _fake_redis()
    with (
        patch.object(job2, "get_engine", return_value=eng),
        patch.object(job2, "get_redis", return_value=rd),
    ):
        out = job2._freeze("2026-06-10", "sha-a", _rec(), "top_20", _proj())
    assert out is True
    payload = eng.begin.return_value.__enter__.return_value.execute.call_args.args[1]
    assert payload["frozen_via"] == "job2_first_fire"


def test_seq_race_retries_once_then_succeeds() -> None:
    """Empty RETURNING (lost seq race) triggers exactly one retry."""
    eng = _engine_with_results([None, (43, 2)])
    rd = _fake_redis()
    with (
        patch.object(job2, "get_engine", return_value=eng),
        patch.object(job2, "get_redis", return_value=rd),
    ):
        out = job2._freeze("2026-06-10", "sha-a", _rec(), "top_20", _proj())
    assert out is True
    insert_conn = eng.begin.return_value.__enter__.return_value
    assert insert_conn.execute.call_count == 2


def test_seq_race_gives_up_after_two_attempts() -> None:
    eng = _engine_with_results([None, None])
    rd = _fake_redis()
    with (
        patch.object(job2, "get_engine", return_value=eng),
        patch.object(job2, "get_redis", return_value=rd),
        pytest.raises(RuntimeError, match="sequence race"),
    ):
        job2._freeze("2026-06-10", "sha-a", _rec(), "top_20", _proj())
    insert_conn = eng.begin.return_value.__enter__.return_value
    assert insert_conn.execute.call_count == 2


def test_append_sql_computes_next_seq_from_existing_rows() -> None:
    """The INSERT sources its freeze_seq from MAX(freeze_seq)+1 for the key
    and conflicts on the (slate_date, model_sha, freeze_seq) constraint."""
    sql = str(job2.FROZEN_APPEND)
    assert "COALESCE(MAX(freeze_seq), 0) + 1" in sql
    assert "operation_key" in sql
    assert "ON CONFLICT DO NOTHING" in sql
    assert "RETURNING id, freeze_seq" in sql
