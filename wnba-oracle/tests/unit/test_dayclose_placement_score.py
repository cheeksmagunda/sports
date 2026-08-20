"""The realized score dayclose records must be the committed-order score.

Until 2026-08-19 ``_auto_record_placement`` ranked the five picks by realized
score and then applied the slot multipliers down that ranking. That awards the
2.0x base to whoever spiked, which an entrant who commits an order before tip
cannot do, so every ``contest_placements.entry_score`` read high -- and with it
``entry_rank``, ``finish_percentile``, ``cashed``, ``top_10pct`` and
``top_1pct``, all of which are derived from it.

The fixture below is built so the two conventions cannot agree: the pick sitting
in the LOWEST slot is the one that scored highest.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import polars as pl
import pytest

from wnba_oracle.scheduler import job_dayclose

SLATE = "2026-08-18"

# player_id -> (real_score, card_boost). Committed slot order is the PLAYER_IDS
# order below; note pid 5 (the 1.2x slot) has by far the best realized score.
PICKS = {
    1: (2.0, 0.0),
    2: (2.0, 0.0),
    3: (2.0, 0.0),
    4: (2.0, 0.0),
    5: (10.0, 0.0),
}
PLAYER_IDS = [1, 2, 3, 4, 5]

# Committed: 2*2.0 + 2*1.8 + 2*1.6 + 2*1.4 + 10*1.2 = 25.6
COMMITTED = 25.6
# Hindsight (the old behaviour): 10*2.0 + 2*1.8 + 2*1.6 + 2*1.4 + 2*1.2 = 32.0
HINDSIGHT = 32.0


def _run_dayclose(player_ids: list[int]) -> MagicMock:
    """Drive _auto_record_placement over the fixture, return the record mock."""
    labels = pl.DataFrame(
        {
            "slate_date": [SLATE] * len(PICKS),
            "platform_player_id": list(PICKS),
            "real_score": [rs for rs, _ in PICKS.values()],
            "card_boost": [cb for _, cb in PICKS.values()],
        }
    )
    board = pl.DataFrame(
        {"slate_date": [SLATE], "score": [50.0], "contest_id": [2078], "num_brawlers": [7826]}
    )

    conn = MagicMock()
    conn.execute.return_value.first.return_value = (
        json.dumps({"player_ids": player_ids, "slot_multipliers": [2.0, 1.8, 1.6, 1.4, 1.2]}),
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
        ) as record,
    ):
        job_dayclose._auto_record_placement(SLATE)
    return record


def test_entry_score_uses_the_committed_slot_order() -> None:
    record = _run_dayclose(PLAYER_IDS)

    record.assert_called_once()
    entry_score = record.call_args.kwargs["entry_score"]
    assert entry_score == pytest.approx(COMMITTED)
    assert entry_score != pytest.approx(HINDSIGHT)


def test_entry_score_tracks_the_order_we_actually_committed() -> None:
    """Reordering the committed lineup must change the recorded score.

    Under the old rank-then-multiply behaviour both orders produced 32.0, so
    this is the assertion that would have caught the bug.
    """
    best_first = _run_dayclose([5, 1, 2, 3, 4])

    # 10*2.0 + 2*1.8 + 2*1.6 + 2*1.4 + 2*1.2 = 32.0
    assert best_first.call_args.kwargs["entry_score"] == pytest.approx(32.0)
    assert best_first.call_args.kwargs["entry_score"] != pytest.approx(COMMITTED)


def test_short_lineup_records_nothing() -> None:
    """A malformed freeze must not be scored against the wrong slot bases."""
    record = _run_dayclose([1, 2, 3])

    record.assert_not_called()


def test_retention_cleanup_never_deletes_frozen_lineups() -> None:
    """Day-close retention may prune events, never the lineup audit trail."""
    conn = MagicMock()
    conn.execute.return_value.rowcount = 3
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn

    with (
        patch.object(job_dayclose, "get_settings", return_value=MagicMock(database_url="x")),
        patch("wnba_oracle.db.engine.get_engine", return_value=engine),
    ):
        job_dayclose._cleanup_append_only_tables(retention_days=14)

    statements = [str(call.args[0]) for call in conn.execute.call_args_list]
    assert len(statements) == 1
    assert "DELETE FROM watchdog_events" in statements[0]
    assert all("frozen_lineups" not in statement for statement in statements)
