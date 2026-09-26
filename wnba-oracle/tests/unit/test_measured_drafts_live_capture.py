"""#434: gate freeze measured_drafts on LIVE_OWNERSHIP_CAPTURE_ENABLED.

Pins the freeze path: disabled → {}; enabled+empty → {}; enabled+pre-lock
rows → those counts; same-slate post-lock dayclose rows (ingested after
as_of) must not leak (#289).
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

from wnba_oracle.scheduler import job2_io

LOCK = dt.datetime(2026, 8, 30, 18, 0, tzinfo=dt.UTC)
PRE_LOCK = LOCK - dt.timedelta(minutes=15)
POST_LOCK = LOCK + dt.timedelta(hours=4)


def _row(pid: int, drafts: int, ingested_at: dt.datetime) -> MagicMock:
    m = MagicMock()
    m._mapping = {
        "platform_player_id": pid,
        "drafts": drafts,
        "ingested_at": ingested_at,
    }
    return m


def test_disabled_returns_empty_even_when_rows_exist() -> None:
    eng = MagicMock()
    with patch("wnba_oracle.scheduler.job2_io.get_engine", return_value=eng):
        out = job2_io._load_measured_drafts(
            "2026-08-30",
            as_of=LOCK,
            live_capture_enabled=False,
        )
    assert out == {}
    eng.connect.assert_not_called()


def test_enabled_empty_returns_empty() -> None:
    eng = MagicMock()
    conn = MagicMock()
    eng.connect.return_value.__enter__.return_value = conn
    eng.connect.return_value.__exit__.return_value = None
    conn.execute.return_value.fetchall.return_value = []

    with patch("wnba_oracle.scheduler.job2_io.get_engine", return_value=eng):
        out = job2_io._load_measured_drafts(
            "2026-08-30",
            as_of=LOCK,
            live_capture_enabled=True,
        )
    assert out == {}
    params = conn.execute.call_args.args[1]
    assert params["as_of"] == LOCK


def test_enabled_prelock_rows_feed_freeze() -> None:
    eng = MagicMock()
    conn = MagicMock()
    eng.connect.return_value.__enter__.return_value = conn
    eng.connect.return_value.__exit__.return_value = None
    # SQL already filters ingested_at <= as_of; mock returns the surviving rows.
    conn.execute.return_value.fetchall.return_value = [
        _row(101, 40, PRE_LOCK),
        _row(102, 12, PRE_LOCK),
    ]

    with patch("wnba_oracle.scheduler.job2_io.get_engine", return_value=eng):
        out = job2_io._load_measured_drafts(
            "2026-08-30",
            as_of=LOCK,
            live_capture_enabled=True,
        )
    assert out == {101: 40, 102: 12}
    sql = str(conn.execute.call_args.args[0])
    assert "ingested_at <=" in sql


def test_enabled_postlock_rows_do_not_leak_past_as_of() -> None:
    """Mirror #289: dayclose rows ingested after freeze as_of stay invisible."""
    eng = MagicMock()
    conn = MagicMock()
    eng.connect.return_value.__enter__.return_value = conn
    eng.connect.return_value.__exit__.return_value = None
    # DB would exclude POST_LOCK via ingested_at <= as_of; simulate that filter.
    conn.execute.return_value.fetchall.return_value = [
        _row(101, 40, PRE_LOCK),
    ]

    with patch("wnba_oracle.scheduler.job2_io.get_engine", return_value=eng):
        out = job2_io._load_measured_drafts(
            "2026-08-30",
            as_of=LOCK,
            live_capture_enabled=True,
        )
    assert out == {101: 40}
    assert 999 not in out.values()
    params = conn.execute.call_args.args[1]
    assert params["as_of"] == LOCK
    # Sanity: a call with a later as_of would see post-lock if present.
    conn.execute.return_value.fetchall.return_value = [
        _row(101, 40, PRE_LOCK),
        _row(101, 999, POST_LOCK),
    ]
    with patch("wnba_oracle.scheduler.job2_io.get_engine", return_value=eng):
        later = job2_io._load_measured_drafts(
            "2026-08-30",
            as_of=POST_LOCK + dt.timedelta(minutes=1),
            live_capture_enabled=True,
        )
    # MAX(drafts) across filtered rows — post-lock can win only when as_of allows it.
    assert later[101] == 999


def test_legacy_unfiltered_when_flag_omitted() -> None:
    eng = MagicMock()
    conn = MagicMock()
    eng.connect.return_value.__enter__.return_value = conn
    eng.connect.return_value.__exit__.return_value = None
    conn.execute.return_value.fetchall.return_value = [_row(7, 55, POST_LOCK)]

    with patch("wnba_oracle.scheduler.job2_io.get_engine", return_value=eng):
        out = job2_io._load_measured_drafts("2026-08-30")
    assert out == {7: 55}
    sql = str(conn.execute.call_args.args[0])
    assert "ingested_at" not in sql
