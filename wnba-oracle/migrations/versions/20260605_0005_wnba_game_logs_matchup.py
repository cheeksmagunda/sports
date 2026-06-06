"""wnba_game_logs: add opponent / home_away / game_id matchup fields.

The original wnba_game_logs schema (20260605_0004) dropped MATCHUP and GAME_ID
from the nba_api PlayerGameLogs response. Without an opponent column the model
cannot see who a player faced, which makes matchup-aware features impossible
(opponent pace, opponent def-rtg, position vs opponent, etc.).

This migration adds three nullable columns:
  opponent   (3-char team abbreviation, parsed from MATCHUP)
  home_away  ('home' if MATCHUP contained " vs. ", 'away' if " @ ")
  game_id    (nba_api GAME_ID, 10-char zero-padded string)

Backfill is via scripts/backfill_minutes.py, which now persists these fields
on every UPSERT and replays the full PlayerGameLogs history.

Revision ID: 20260605_0005
Revises: 20260605_0004
Create Date: 2026-06-05
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260605_0005"
down_revision: str | None = "20260605_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "wnba_game_logs", sa.Column("opponent", sa.String(8), nullable=True)
    )
    op.add_column(
        "wnba_game_logs", sa.Column("home_away", sa.String(4), nullable=True)
    )
    op.add_column(
        "wnba_game_logs", sa.Column("game_id", sa.String(16), nullable=True)
    )
    op.create_index(
        "ix_wnba_game_logs_game_id", "wnba_game_logs", ["game_id"]
    )
    op.create_index(
        "ix_wnba_game_logs_opponent", "wnba_game_logs", ["opponent"]
    )


def downgrade() -> None:
    op.drop_index("ix_wnba_game_logs_opponent", "wnba_game_logs")
    op.drop_index("ix_wnba_game_logs_game_id", "wnba_game_logs")
    op.drop_column("wnba_game_logs", "game_id")
    op.drop_column("wnba_game_logs", "home_away")
    op.drop_column("wnba_game_logs", "opponent")
