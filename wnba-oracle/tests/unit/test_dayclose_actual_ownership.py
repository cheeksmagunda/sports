"""D90/#38: _auto_record_placement also persists per-player actual_ownership
into player_slate_ownership at day-close, from the same slate_labels.drafts
used to build contest_placements.actual_ownership_json.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import polars as pl

from wnba_oracle.scheduler import job_dayclose

SLATE = "2026-08-29"
PLAYER_IDS = [1, 2, 3, 4, 5]


def _run(drafts: list[int | None]) -> tuple[dict, MagicMock]:
    labels = pl.DataFrame(
        {
            "slate_date": [SLATE] * 5,
            "platform_player_id": PLAYER_IDS,
            "real_score": [2.0, 2.0, 2.0, 2.0, 10.0],
            "card_boost": [0.0] * 5,
            "drafts": drafts,
        }
    )
    board = pl.DataFrame(
        {"slate_date": [SLATE], "score": [50.0], "contest_id": [2078], "num_brawlers": [7826]}
    )

    conn = MagicMock()
    conn.execute.return_value.first.return_value = (
        json.dumps({"player_ids": PLAYER_IDS, "slot_multipliers": [2.0, 1.8, 1.6, 1.4, 1.2]}),
    )
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn

    with (
        patch.object(job_dayclose, "get_settings", return_value=MagicMock(database_url="x")),
        patch("wnba_oracle.db.reads.read_slate_labels", return_value=labels),
        patch("wnba_oracle.db.reads.read_leaderboards", return_value=board),
        patch("wnba_oracle.db.engine.get_engine", return_value=engine),
        patch(
            "wnba_oracle.scheduler.placements.auto_record_from_dayclose",
            return_value=MagicMock(),
        ),
        patch("wnba_oracle.scheduler.placements.record_actual_ownership") as record,
    ):
        outcome = job_dayclose._auto_record_placement(SLATE)
    return outcome, record


def test_actual_ownership_recorded_from_drafts() -> None:
    outcome, record = _run([2, 4, 1, 1800, 2000])
    assert outcome["status"] == "success"
    record.assert_called_once()
    kwargs = record.call_args.kwargs
    assert kwargs["slate_date"] == SLATE
    assert kwargs["actual_drafts"] == {1: 2, 2: 4, 3: 1, 4: 1800, 5: 2000}
    total = 2 + 4 + 1 + 1800 + 2000
    assert kwargs["actual_ownership"][1] == 2 / total
    assert abs(sum(kwargs["actual_ownership"].values()) - 1.0) < 1e-9


def test_skips_ownership_write_when_no_drafts_known() -> None:
    outcome, record = _run([None, None, None, None, None])
    assert outcome["status"] == "success"
    record.assert_not_called()


def test_placement_still_recorded_when_ownership_write_fails() -> None:
    labels = pl.DataFrame(
        {
            "slate_date": [SLATE] * 5,
            "platform_player_id": PLAYER_IDS,
            "real_score": [2.0, 2.0, 2.0, 2.0, 10.0],
            "card_boost": [0.0] * 5,
            "drafts": [2, 4, 1, 1800, 2000],
        }
    )
    board = pl.DataFrame(
        {"slate_date": [SLATE], "score": [50.0], "contest_id": [2078], "num_brawlers": [7826]}
    )
    conn = MagicMock()
    conn.execute.return_value.first.return_value = (
        json.dumps({"player_ids": PLAYER_IDS, "slot_multipliers": [2.0, 1.8, 1.6, 1.4, 1.2]}),
    )
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn

    with (
        patch.object(job_dayclose, "get_settings", return_value=MagicMock(database_url="x")),
        patch("wnba_oracle.db.reads.read_slate_labels", return_value=labels),
        patch("wnba_oracle.db.reads.read_leaderboards", return_value=board),
        patch("wnba_oracle.db.engine.get_engine", return_value=engine),
        patch(
            "wnba_oracle.scheduler.placements.auto_record_from_dayclose",
            return_value=MagicMock(),
        ),
        patch(
            "wnba_oracle.scheduler.placements.record_actual_ownership",
            side_effect=Exception("boom"),
        ),
    ):
        outcome = job_dayclose._auto_record_placement(SLATE)
    assert outcome["status"] == "success"
