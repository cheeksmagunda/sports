"""Add immutable freeze audit snapshot bindings.

Revision ID: 20260920_0013
Revises: 20260920_0012
Create Date: 2026-09-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260920_0013"
down_revision: str | None = "20260920_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "freeze_audit_snapshots",
        sa.Column("snapshot_sha256", sa.String(64), primary_key=True),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column(
        "frozen_lineups",
        sa.Column("audit_snapshot_sha256", sa.String(64), nullable=True),
    )
    op.create_index(
        "ix_freeze_audit_snapshots_created_at",
        "freeze_audit_snapshots",
        ["created_at"],
    )
    op.create_index(
        "ix_frozen_lineups_audit_snapshot_sha256",
        "frozen_lineups",
        ["audit_snapshot_sha256"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_frozen_lineups_audit_snapshot_sha256",
        table_name="frozen_lineups",
    )
    op.drop_column("frozen_lineups", "audit_snapshot_sha256")
    op.drop_index(
        "ix_freeze_audit_snapshots_created_at",
        table_name="freeze_audit_snapshots",
    )
    op.drop_table("freeze_audit_snapshots")
