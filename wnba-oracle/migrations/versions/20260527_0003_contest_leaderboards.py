"""contest_leaderboards: top-20 finishers' lineups per finalized contest.

One row per (contest_id, entry_id). The `lineup` JSONB carries the 5-player
draft (each entry has playerId, multiplier, multiplierBonus, value, score,
displayName, team metadata) ingested verbatim from
`/games/playerratingcontest/{id}/entries`. The `user_id` is the platform's
opaque user slug (e.g. "7J6Olwav"); username resolution is a separate
nice-to-have, not required for strategy analysis.

Revision ID: 20260527_0003
Revises: 20260527_0002
Create Date: 2026-05-27
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260527_0003"
down_revision: str | None = "20260527_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contest_leaderboards",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("contest_id", sa.Integer, nullable=False),
        sa.Column("slate_date", sa.String(16), nullable=False),
        sa.Column("entry_id", sa.BigInteger, nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("paged_rank", sa.Integer, nullable=False),
        sa.Column("user_id", sa.String(32), nullable=False),
        sa.Column("score", sa.Float, nullable=False),
        sa.Column("lineup", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("num_brawlers", sa.Integer, nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "contest_id", "entry_id", name="uq_contest_leaderboards_contest_entry"
        ),
    )
    op.create_index(
        "ix_contest_leaderboards_slate_date", "contest_leaderboards", ["slate_date"]
    )
    op.create_index(
        "ix_contest_leaderboards_user_id", "contest_leaderboards", ["user_id"]
    )
    op.create_index(
        "ix_contest_leaderboards_slate_rank",
        "contest_leaderboards",
        ["slate_date", "rank"],
    )


def downgrade() -> None:
    op.drop_index("ix_contest_leaderboards_slate_rank", "contest_leaderboards")
    op.drop_index("ix_contest_leaderboards_user_id", "contest_leaderboards")
    op.drop_index("ix_contest_leaderboards_slate_date", "contest_leaderboards")
    op.drop_table("contest_leaderboards")
