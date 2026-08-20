"""Add durable job lifecycle heartbeats.

Revision ID: 20260820_0010
Revises: 20260820_0009
Create Date: 2026-08-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0010"
down_revision: str | None = "20260820_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_runs",
        sa.Column("run_id", sa.String(64), primary_key=True),
        sa.Column("job_name", sa.String(64), nullable=False),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("slate_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("exit_code", sa.Integer, nullable=True),
        sa.Column("details_json", sa.dialects.postgresql.JSONB, nullable=False),
    )
    op.create_index("ix_job_runs_slate_date", "job_runs", ["slate_date"])
    op.create_index(
        "ix_job_runs_job_started",
        "job_runs",
        ["job_name", "started_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_job_runs_job_started", table_name="job_runs")
    op.drop_index("ix_job_runs_slate_date", table_name="job_runs")
    op.drop_table("job_runs")
