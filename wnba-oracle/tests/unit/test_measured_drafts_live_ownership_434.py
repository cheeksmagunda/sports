"""Live ownership capture feeds PIT-safe measured drafts into job2 (#434)."""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

from wnba_oracle.scheduler import job2_io

LOCK = dt.datetime(2026, 8, 30, 23, 0, tzinfo=dt.UTC)


def _row(pid: int, drafts: int, ingested_at: dt.datetime) -> MagicMock:
    m = MagicMock()
    m._mapping = {
        "platform_player_id": pid,
        "drafts": drafts,
        "ingested_at": ingested_at,
    }
    return m


def test_load_measured_drafts_disabled_path_returns_empty_without_engine() -> None:
    with patch("wnba_oracle.scheduler.job2_io.get_engine", side_effect=RuntimeError("no db")):
        assert job2_io._load_measured_drafts("2026-08-30") == {}


def test_load_measured_drafts_as_of_excludes_post_lock_rows() -> None:
    """Same-slate post-lock dayclose drafts must not leak into freeze (#289)."""

    pre = _row(101, 40, LOCK - dt.timedelta(minutes=5))
    other = _row(202, 15, LOCK - dt.timedelta(minutes=1))
    conn = MagicMock()
    # Simulate DB applying ingested_at <= as_of (post-lock 400 drafts excluded).
    conn.execute.return_value.fetchall.return_value = [pre, other]
    eng = MagicMock()
    eng.connect.return_value.__enter__.return_value = conn
    eng.connect.return_value.__exit__.return_value = None

    with patch("wnba_oracle.scheduler.job2_io.get_engine", return_value=eng):
        out = job2_io._load_measured_drafts("2026-08-30", as_of=LOCK)

    assert out == {101: 40, 202: 15}
    sql = str(conn.execute.call_args.args[0])
    params = conn.execute.call_args.args[1]
    assert "ingested_at <=" in sql
    assert params["as_of"] == LOCK


def test_load_measured_drafts_without_as_of_keeps_legacy_query() -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [_row(9, 3, LOCK)]
    eng = MagicMock()
    eng.connect.return_value.__enter__.return_value = conn
    eng.connect.return_value.__exit__.return_value = None

    with patch("wnba_oracle.scheduler.job2_io.get_engine", return_value=eng):
        out = job2_io._load_measured_drafts("2026-08-30")

    assert out == {9: 3}
    sql = str(conn.execute.call_args.args[0])
    assert "ingested_at" not in sql
