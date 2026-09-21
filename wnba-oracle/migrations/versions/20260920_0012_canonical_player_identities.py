"""Persist canonical Real Sports -> stats.wnba.com player identities.

Revision ID: 20260920_0012
Revises: 20260919_0011
Create Date: 2026-09-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260920_0012"
down_revision: str | None = "20260919_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "canonical_player_identities",
        sa.Column("real_sports_player_id", sa.String(64), primary_key=True),
        sa.Column("wnba_player_id", sa.BigInteger(), nullable=False),
        sa.Column("provenance", sa.String(32), nullable=False),
        sa.Column("provider_nba_id", sa.BigInteger(), nullable=True),
        sa.Column("real_sports_display_name", sa.String(128), nullable=False),
        sa.Column("real_sports_first_name", sa.String(64), nullable=False),
        sa.Column("real_sports_last_name", sa.String(64), nullable=False),
        sa.Column("real_sports_team", sa.String(8), nullable=False),
        sa.Column("wnba_full_name", sa.String(128), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "provenance IN ("
            "'provider_nba_id', "
            "'explicit_override', "
            "'normalized_name_fallback'"
            ")",
            name="ck_canonical_player_identities_provenance",
        ),
    )
    op.create_index(
        "ix_canonical_player_identities_wnba_player_id",
        "canonical_player_identities",
        ["wnba_player_id"],
    )
    op.create_index(
        "ix_canonical_player_identities_last_seen_at",
        "canonical_player_identities",
        ["last_seen_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_canonical_player_identities_last_seen_at",
        table_name="canonical_player_identities",
    )
    op.drop_index(
        "ix_canonical_player_identities_wnba_player_id",
        table_name="canonical_player_identities",
    )
    op.drop_table("canonical_player_identities")
