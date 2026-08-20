"""D104: /slate/{date} timing endpoint feeding the tip-relative countdown.

The frontend loader counts down to the freeze, which job2 anchors to
first_tip - freeze_lead_minutes. This endpoint exposes that target so the
on-screen clock is tip-relative, not a hardcoded UTC slot.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from wnba_oracle.api.app import app
from wnba_oracle.common.clock import slate_date
from wnba_oracle.common.settings import Settings

FIRST_TIP = dt.datetime(2026, 6, 22, 23, 0, tzinfo=dt.UTC)


def _engine_first(row: object) -> MagicMock:
    eng = MagicMock()
    result = MagicMock()
    result.first.return_value = row
    conn = MagicMock()
    conn.execute.return_value = result
    eng.connect.return_value.__enter__.return_value = conn
    return eng


def test_freeze_target_is_first_tip_minus_lead() -> None:
    # Row is (contest_lock_utc, first_tip_utc); no explicit lock -> use first tip.
    eng = _engine_first((None, FIRST_TIP))
    with patch("wnba_oracle.api.slate.get_engine", return_value=eng):
        resp = TestClient(app).get("/slate/2026-06-22")
    assert resp.status_code == 200
    body = resp.json()
    assert body["first_tip_utc"] == "2026-06-22T23:00:00+00:00"
    assert body["freeze_lead_minutes"] == 40
    # 23:00 - 40min = 22:20 UTC, the T-40 freeze target.
    assert body["freeze_target_utc"] == "2026-06-22T22:20:00+00:00"


def test_explicit_contest_lock_wins_over_first_tip() -> None:
    lock = dt.datetime(2026, 6, 22, 22, 30, tzinfo=dt.UTC)
    eng = _engine_first((lock, FIRST_TIP))
    with patch("wnba_oracle.api.slate.get_engine", return_value=eng):
        resp = TestClient(app).get("/slate/2026-06-22")
    body = resp.json()
    # 22:30 lock - 40min = 21:50 UTC.
    assert body["freeze_target_utc"] == "2026-06-22T21:50:00+00:00"


def test_404_when_no_row() -> None:
    eng = _engine_first(None)
    with patch("wnba_oracle.api.slate.get_engine", return_value=eng):
        resp = TestClient(app).get("/slate/2026-06-22")
    assert resp.status_code == 404


def test_404_when_row_has_no_timing() -> None:
    # job1 wrote a row but could not parse any tip (empty/odd slate).
    eng = _engine_first((None, None))
    with patch("wnba_oracle.api.slate.get_engine", return_value=eng):
        resp = TestClient(app).get("/slate/2026-06-22")
    assert resp.status_code == 404


def test_paused_returns_200_without_touching_the_db() -> None:
    today = slate_date()
    end = today + dt.timedelta(days=1)
    paused = Settings(PICKS_PAUSE_START=today.isoformat(), PICKS_PAUSE_END=end.isoformat())
    with (
        patch("wnba_oracle.api.slate.get_settings", return_value=paused),
        patch("wnba_oracle.api.slate.get_engine") as mock_engine,
    ):
        resp = TestClient(app).get("/slate/2026-07-27")
    assert resp.status_code == 200
    body = resp.json()
    assert body["picks_paused"] is True
    assert body["resumes_on"] == (end + dt.timedelta(days=1)).isoformat()
    assert body["freeze_target_utc"] is None
    mock_engine.assert_not_called()


def test_not_paused_reports_picks_paused_false() -> None:
    eng = _engine_first((None, FIRST_TIP))
    with patch("wnba_oracle.api.slate.get_engine", return_value=eng):
        resp = TestClient(app).get("/slate/2026-06-22")
    body = resp.json()
    assert body["picks_paused"] is False
    assert body["resumes_on"] is None
