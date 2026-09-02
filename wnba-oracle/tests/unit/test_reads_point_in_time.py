"""Point-in-time safeguards on the label-corpus read helpers.

``read_player_history`` feeds job2's fallback prediction tier. Without an
as-of bound its per-player mean is a global average over every stored label,
which is fine at a live freeze (today's labels do not exist yet) but leaks the
target slate's realized score into any historical replay. These tests pin the
``as_of_slate_date`` contract against a SQLite mirror of ``slate_labels``.
"""

from __future__ import annotations

import sqlalchemy as sa

from wnba_oracle.db.reads import read_player_history

_ROWS = [
    # (platform_player_id, slate_date, real_score)
    (1, "2026-05-01", 2.0),
    (1, "2026-05-02", 4.0),
    (1, "2026-05-03", 9.0),
    (2, "2026-05-03", 1.0),
    (3, "2026-05-01", None),
]


def _engine() -> sa.Engine:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "CREATE TABLE slate_labels ("
                "platform_player_id INTEGER, slate_date VARCHAR(16), real_score FLOAT)"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO slate_labels (platform_player_id, slate_date, real_score) "
                "VALUES (:pid, :sd, :rs)"
            ),
            [{"pid": p, "sd": d, "rs": r} for p, d, r in _ROWS],
        )
    return engine


def test_read_player_history_default_is_global_mean() -> None:
    out = read_player_history(_engine())
    assert out == {1: 5.0, 2: 1.0}


def test_read_player_history_as_of_excludes_target_slate_and_later() -> None:
    out = read_player_history(_engine(), as_of_slate_date="2026-05-03")
    # Player 1: only 05-01 and 05-02 remain; player 2 first appears on the
    # target slate and must be absent so the caller falls back to its prior.
    assert out == {1: 3.0}


def test_read_player_history_as_of_before_any_label_is_empty() -> None:
    assert read_player_history(_engine(), as_of_slate_date="2026-05-01") == {}


def test_read_player_history_as_of_after_all_labels_matches_global() -> None:
    assert read_player_history(_engine(), as_of_slate_date="2026-06-01") == {1: 5.0, 2: 1.0}
