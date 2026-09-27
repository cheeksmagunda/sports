"""read_label_corpus trains on Highest value section only (#453 / #505)."""

from __future__ import annotations

from wnba_oracle.db import reads


def test_training_label_section_is_highest_value() -> None:
    assert reads.TRAINING_LABEL_SECTION == "highestBoostedValuePlayers"


def test_read_label_corpus_sql_filters_section_without_date_cap() -> None:
    import inspect

    src = inspect.getsource(reads.read_label_corpus)
    assert "section = :section" in src
    assert "highestBoostedValuePlayers" in reads.TRAINING_LABEL_SECTION
    # No artificial year / date lower bound in the SQL body.
    assert "slate_date >=" not in src
    assert "slate_date >" not in src
