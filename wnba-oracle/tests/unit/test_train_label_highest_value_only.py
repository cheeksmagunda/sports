"""Training label corpus must be Highest value boards, not winning drafts."""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock

from wnba_oracle.db import reads
from wnba_oracle.db.reads import TRAINING_LABEL_SECTION, read_label_corpus


def test_training_label_section_is_highest_value_board() -> None:
    assert TRAINING_LABEL_SECTION == "highestBoostedValuePlayers"
    assert reads.TRAINING_LABEL_SECTION == "highestBoostedValuePlayers"


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


def test_read_label_corpus_sql_filters_section_without_date_cap() -> None:
    src = inspect.getsource(reads.read_label_corpus)
    assert "section = :section" in src
    assert "highestBoostedValuePlayers" in reads.TRAINING_LABEL_SECTION
    # No artificial year / date lower bound in the SQL body.
    assert "slate_date >=" not in src
    assert "slate_date >" not in src


def test_read_label_corpus_joins_pool_position_instead_of_stamping_f() -> None:
    """HV training alignment (#623): position comes from job1, not a literal F."""

    src = inspect.getsource(reads.read_label_corpus)
    assert "LEFT JOIN job1_enrichment" in src
    assert "e.position" in src
    assert "e.slate_date::text = l.slate_date" in src
    assert "e.player_id = l.platform_player_id" in src
    assert "'F' AS position" not in src
    assert "COALESCE(NULLIF(BTRIM(e.position), ''), 'F')" in src
