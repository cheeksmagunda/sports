"""D82: append-only lineup API surface.

/lineup/{date} serves the latest freeze (max freeze_seq) with provenance
fields (freeze_seq, frozen_via, n_freezes); /lineup/{date}/history returns
every appended row oldest-first; /lineup lists one entry per
(slate_date, model_sha).
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from wnba_oracle.api.app import app

FROZEN_AT_1 = dt.datetime(2026, 6, 8, 21, 0, tzinfo=dt.UTC)
FROZEN_AT_2 = dt.datetime(2026, 6, 8, 23, 0, tzinfo=dt.UTC)


class _Row:
    def __init__(self, mapping: dict) -> None:
        self._mapping = mapping


def _row(seq: int, via: str, frozen_at: dt.datetime, n_freezes: int | None = None) -> _Row:
    mapping = {
        "slate_date": dt.date(2026, 6, 8),
        "model_sha": "sha-a",
        "payout_regime": "top_20",
        "frozen_at": frozen_at,
        "lineup": {"player_ids": [1, 2, 3, 4, 5], "per_player": []},
        "entry_recommendation": "enter",
        "expected_payout": 1.4,
        "metadata_json": {"frozen_via": via},
        "freeze_seq": seq,
        "frozen_via": via,
    }
    if n_freezes is not None:
        mapping["n_freezes"] = n_freezes
    return _Row(mapping)


def _engine_first(row: _Row | None) -> MagicMock:
    eng = MagicMock()
    result = MagicMock()
    result.first.return_value = row
    conn = MagicMock()
    conn.execute.return_value = result
    eng.connect.return_value.__enter__.return_value = conn
    return eng


def _engine_rows(rows: list[_Row]) -> MagicMock:
    eng = MagicMock()
    conn = MagicMock()
    conn.execute.return_value = iter(rows)
    eng.connect.return_value.__enter__.return_value = conn
    return eng


def test_get_lineup_serves_latest_with_provenance() -> None:
    eng = _engine_first(_row(2, "job2_late_refreeze", FROZEN_AT_2, n_freezes=2))
    with patch("wnba_oracle.api.lineup.get_engine", return_value=eng):
        resp = TestClient(app).get("/lineup/2026-06-08")
    assert resp.status_code == 200
    body = resp.json()
    assert body["freeze_seq"] == 2
    assert body["frozen_via"] == "job2_late_refreeze"
    assert body["n_freezes"] == 2
    sql = str(eng.connect.return_value.__enter__.return_value.execute.call_args.args[0])
    assert "ORDER BY freeze_seq DESC" in sql


def test_history_returns_all_rows_oldest_first() -> None:
    rows = [
        _row(1, "job2_first_fire", FROZEN_AT_1),
        _row(2, "job2_late_refreeze", FROZEN_AT_2),
    ]
    eng = _engine_rows(rows)
    with patch("wnba_oracle.api.lineup.get_engine", return_value=eng):
        resp = TestClient(app).get("/lineup/2026-06-08/history")
    assert resp.status_code == 200
    body = resp.json()
    assert [r["freeze_seq"] for r in body] == [1, 2]
    assert [r["frozen_via"] for r in body] == ["job2_first_fire", "job2_late_refreeze"]
    assert all("lineup" in r for r in body)
    sql = str(eng.connect.return_value.__enter__.return_value.execute.call_args.args[0])
    assert "ORDER BY freeze_seq ASC" in sql


def test_history_404_when_no_rows() -> None:
    eng = _engine_rows([])
    with patch("wnba_oracle.api.lineup.get_engine", return_value=eng):
        resp = TestClient(app).get("/lineup/2026-06-08/history")
    assert resp.status_code == 404


def test_list_recent_dedupes_per_slate_and_model() -> None:
    eng = _engine_rows([_row(2, "job2_late_refreeze", FROZEN_AT_2)])
    with patch("wnba_oracle.api.lineup.get_engine", return_value=eng):
        resp = TestClient(app).get("/lineup")
    assert resp.status_code == 200
    body = resp.json()
    assert body[0]["freeze_seq"] == 2
    assert body[0]["frozen_via"] == "job2_late_refreeze"
    sql = str(eng.connect.return_value.__enter__.return_value.execute.call_args.args[0])
    assert "DISTINCT ON (slate_date, model_sha)" in sql
