"""Training label corpus must be Highest value boards, not winning drafts."""

from __future__ import annotations

from unittest.mock import MagicMock

from wnba_oracle.db.reads import TRAINING_LABEL_SECTION, read_label_corpus


def test_training_label_section_is_highest_value_board() -> None:
    assert TRAINING_LABEL_SECTION == "highestBoostedValuePlayers"


def test_read_label_corpus_filters_to_highest_value_section_only() -> None:
    """Winning-draft leaderboard_lineup rows must not enter the train corpus."""

    engine = MagicMock()
    conn = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn
    conn.execute.return_value.fetchall.return_value = []

    read_label_corpus(engine)

    args, kwargs = conn.execute.call_args
    sql = str(args[0])
    params = args[1] if len(args) > 1 else kwargs.get("parameters") or {}
    assert "section" in sql.lower()
    assert params["section"] == "highestBoostedValuePlayers"
    assert "leaderboard_lineup" not in sql
