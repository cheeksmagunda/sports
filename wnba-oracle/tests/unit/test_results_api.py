"""Read-only results API over realized Real Sports slate outcomes (issue #34).

`/results/{slate_date}` must never recompute `real_score`; it serves the
verbatim provider value already ingested into `slate_labels`, and must
report a clear pending state (not a 404) when a date has no rows yet.
"""

from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from wnba_oracle.api.app import app

INGESTED_AT = dt.datetime(2026, 6, 8, 23, 30, tzinfo=dt.UTC)


class _Row:
    def __init__(self, mapping: dict) -> None:
        self._mapping = mapping


def _row(
    contest_id: int,
    section: str,
    player_id: int,
    display_name: str,
    real_score: float | None,
    card_boost: float = 1.0,
    drafts: int | None = 100,
) -> _Row:
    return _Row(
        {
            "contest_id": contest_id,
            "slate_date": "2026-06-08",
            "section": section,
            "platform_player_id": player_id,
            "display_name": display_name,
            "team_key": "LVA",
            "card_boost": card_boost,
            "drafts": drafts,
            "real_score": real_score,
            "ingested_at": INGESTED_AT,
        }
    )


def _engine_rows(rows: list[_Row]) -> MagicMock:
    eng = MagicMock()
    conn = MagicMock()
    conn.execute.return_value = iter(rows)
    eng.connect.return_value.__enter__.return_value = conn
    return eng


def test_pending_status_when_no_rows_ingested_yet() -> None:
    eng = _engine_rows([])
    with patch("wnba_oracle.api.results.get_engine", return_value=eng):
        resp = TestClient(app).get("/results/2026-06-08")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {
        "slate_date": "2026-06-08",
        "status": "pending",
        "rows": [],
        "top_value": [],
    }


def test_available_status_returns_rows_verbatim() -> None:
    rows = [_row(1, "highestBoostedValuePlayers", 11, "A. Wilson", 42.5)]
    eng = _engine_rows(rows)
    with patch("wnba_oracle.api.results.get_engine", return_value=eng):
        resp = TestClient(app).get("/results/2026-06-08")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "available"
    assert body["rows"][0]["real_score"] == 42.5
    assert body["rows"][0]["ingested_at"] == "2026-06-08T23:30:00+00:00"
    assert body["rows"][0]["display_name"] == "A. Wilson"


def test_top_value_dedupes_player_across_sections_keeping_highest_score() -> None:
    rows = [
        _row(1, "highestBoostedValuePlayers", 11, "A. Wilson", 30.0),
        _row(2, "mostValuablePlayers", 11, "A. Wilson", 42.5),
        _row(3, "highestBoostedValuePlayers", 22, "B. Stewart", 40.0),
    ]
    eng = _engine_rows(rows)
    with patch("wnba_oracle.api.results.get_engine", return_value=eng):
        resp = TestClient(app).get("/results/2026-06-08")
    body = resp.json()
    top = body["top_value"]
    assert [r["platform_player_id"] for r in top] == [11, 22]
    assert top[0]["real_score"] == 42.5
    assert sorted(top[0]["sections"]) == ["highestBoostedValuePlayers", "mostValuablePlayers"]


def test_top_value_is_capped_and_deterministic_on_ties() -> None:
    rows = [
        _row(idx, "highestBoostedValuePlayers", 100 + idx, f"Player {idx}", 20.0)
        for idx in range(6)
    ]
    eng = _engine_rows(rows)
    with patch("wnba_oracle.api.results.get_engine", return_value=eng):
        resp = TestClient(app).get("/results/2026-06-08")
    top = resp.json()["top_value"]
    assert len(top) == 5
    # Equal real_score ties break deterministically by ascending player id.
    assert [r["platform_player_id"] for r in top] == [100, 101, 102, 103, 104]


def test_top_value_ranks_null_real_score_last() -> None:
    rows = [
        _row(1, "highestBoostedValuePlayers", 11, "No Score Yet", None),
        _row(2, "highestBoostedValuePlayers", 22, "Scored", 15.0),
    ]
    eng = _engine_rows(rows)
    with patch("wnba_oracle.api.results.get_engine", return_value=eng):
        resp = TestClient(app).get("/results/2026-06-08")
    top = resp.json()["top_value"]
    assert [r["platform_player_id"] for r in top] == [22, 11]
