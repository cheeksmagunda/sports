"""init: core picker tables.

Revision ID: 20260526_0001
Revises:
Create Date: 2026-05-26
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260526_0001"
down_revision: str | None = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # frozen_lineups: Job 2 output. (slate_date, model_sha) is unique. UPSERT
    # on conflict for the freeze invariant. Lineup payload is JSONB.
    op.create_table(
        "frozen_lineups",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("slate_date", sa.Date, nullable=False),
        sa.Column("model_sha", sa.String(64), nullable=False),
        sa.Column("payout_regime", sa.String(16), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("lineup", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("entry_recommendation", sa.String(24), nullable=False),
        sa.Column("expected_payout", sa.Float, nullable=True),
        sa.Column("metadata_json", sa.dialects.postgresql.JSONB, nullable=True),
        sa.UniqueConstraint("slate_date", "model_sha", name="uq_frozen_lineups_slate_model"),
    )
    op.create_index("ix_frozen_lineups_slate_date", "frozen_lineups", ["slate_date"])

    # job1_enrichment: morning scrape output. One row per (slate_date, player_id).
    op.create_table(
        "job1_enrichment",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("slate_date", sa.Date, nullable=False),
        sa.Column("player_id", sa.BigInteger, nullable=False),
        sa.Column("real_sports_player_id", sa.String(64), nullable=True),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("team", sa.String(8), nullable=False),
        sa.Column("opponent", sa.String(8), nullable=False),
        sa.Column("position", sa.String(4), nullable=False),
        sa.Column("card_boost", sa.Float, nullable=False),
        sa.Column("features_json", sa.dialects.postgresql.JSONB, nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slate_date", "player_id", name="uq_job1_slate_player"),
    )
    op.create_index("ix_job1_enrichment_slate_date", "job1_enrichment", ["slate_date"])

    # model_registry: artifact provenance.
    op.create_table(
        "model_registry",
        sa.Column("sha256", sa.String(64), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("git_sha", sa.String(40), nullable=True),
        sa.Column("training_rows", sa.Integer, nullable=False),
        sa.Column("cv_crps", sa.Float, nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="challenger"),
        sa.Column("metadata_json", sa.dialects.postgresql.JSONB, nullable=True),
    )

    # model_shadow_runs: rotation gate input. challenger predictions vs realized.
    op.create_table(
        "model_shadow_runs",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("slate_date", sa.Date, nullable=False),
        sa.Column("challenger_sha", sa.String(64), nullable=False),
        sa.Column("incumbent_sha", sa.String(64), nullable=False),
        sa.Column("rbo_at_5", sa.Float, nullable=True),
        sa.Column("ndcg_at_5", sa.Float, nullable=True),
        sa.Column("realized_value_delta", sa.Float, nullable=True),
        sa.Column("payload_json", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("slate_date", "challenger_sha", name="uq_shadow_slate_challenger"),
    )

    # watchdog_events: six-trigger flagged events.
    op.create_table(
        "watchdog_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("slate_date", sa.Date, nullable=False),
        sa.Column("trigger", sa.String(48), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("payload_json", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_watchdog_events_slate_date", "watchdog_events", ["slate_date"])


def downgrade() -> None:
    op.drop_table("watchdog_events")
    op.drop_table("model_shadow_runs")
    op.drop_table("model_registry")
    op.drop_table("job1_enrichment")
    op.drop_table("frozen_lineups")
