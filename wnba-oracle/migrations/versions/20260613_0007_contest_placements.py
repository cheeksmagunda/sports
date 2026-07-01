"""contest_placements: closed-loop placement / calibration tracking (D90).

Before this migration the project had no schema for tracking where the entered
lineup actually finished. Every optimizer tune was driven by offline projection
accuracy. The placement feedback loop is the keystone instrumentation phase:
without it no later objective change can be calibrated, and small-sample
overfitting on PROP_SIGNAL_SCALE / leverage / duplication weights is the
dominant failure mode of every tuned parameter.

This migration adds two append-only tables:

  contest_placements
    One row per (slate_date, contest_id) capturing what we entered, what
    the field looked like at lock, where we finished, and the snapshot of
    the model + serving knobs that produced the lineup. Append-only via
    PRIMARY KEY (slate_date, contest_id, recorded_at) so a re-record
    keeps history; the analysis layer reads the latest row per
    (slate_date, contest_id) by recorded_at DESC.

  player_slate_ownership
    Per (slate_date, player_id) projected vs actual ownership for the
    calibration loop. Projected at freeze (from the field model), actual
    measured at lock (from slate_labels.drafts or post-contest data).

Both tables are populated by the new scheduler/placements.py module, called
either from a CLI (oracle-placements) or programmatically from
job_dayclose.py once the contest finalizes.

Revision ID: 20260613_0007
Revises: 20260610_0006
Create Date: 2026-06-13
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "20260613_0007"
down_revision: str | None = "20260610_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contest_placements",
        sa.Column("slate_date", sa.Date, nullable=False),
        sa.Column("contest_id", sa.BigInteger, nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(32), nullable=False),
        # Outcome
        sa.Column("entry_rank", sa.Integer, nullable=True),
        sa.Column("entry_count", sa.Integer, nullable=True),
        sa.Column("entry_score", sa.Numeric(10, 4), nullable=True),
        sa.Column("payout_received_cents", sa.BigInteger, nullable=True),
        sa.Column("entry_fee_cents", sa.BigInteger, nullable=True),
        sa.Column("finish_percentile", sa.Numeric(8, 6), nullable=True),
        sa.Column("cashed", sa.Boolean, nullable=True),
        sa.Column("top_10pct", sa.Boolean, nullable=True),
        sa.Column("top_1pct", sa.Boolean, nullable=True),
        sa.Column("roi", sa.Numeric(10, 4), nullable=True),
        # Calibration: forecast snapshot at freeze (from frozen_lineups)
        sa.Column("freeze_model_sha", sa.String(40), nullable=True),
        sa.Column("expected_payout", sa.Numeric(10, 4), nullable=True),
        sa.Column("lineup_score_p10", sa.Numeric(10, 4), nullable=True),
        sa.Column("lineup_score_p50", sa.Numeric(10, 4), nullable=True),
        sa.Column("lineup_score_p90", sa.Numeric(10, 4), nullable=True),
        sa.Column("payout_curve_json", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("freeze_config_json", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("predicted_ownership_json", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("actual_ownership_json", sa.dialects.postgresql.JSONB, nullable=True),
        sa.Column("metadata_json", sa.dialects.postgresql.JSONB, nullable=True),
        sa.PrimaryKeyConstraint(
            "slate_date", "contest_id", "recorded_at", name="pk_contest_placements"
        ),
    )
    op.create_index(
        "ix_contest_placements_slate_date",
        "contest_placements",
        ["slate_date"],
    )
    op.create_index(
        "ix_contest_placements_recorded_at",
        "contest_placements",
        ["recorded_at"],
    )

    op.create_table(
        "player_slate_ownership",
        sa.Column("slate_date", sa.Date, nullable=False),
        sa.Column("player_id", sa.BigInteger, nullable=False),
        sa.Column("projected_ownership", sa.Numeric(10, 8), nullable=True),
        sa.Column("actual_ownership", sa.Numeric(10, 8), nullable=True),
        sa.Column("projected_drafts", sa.Integer, nullable=True),
        sa.Column("actual_drafts", sa.Integer, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint(
            "slate_date", "player_id", name="pk_player_slate_ownership"
        ),
    )
    op.create_index(
        "ix_player_slate_ownership_slate_date",
        "player_slate_ownership",
        ["slate_date"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_player_slate_ownership_slate_date", table_name="player_slate_ownership"
    )
    op.drop_table("player_slate_ownership")
    op.drop_index(
        "ix_contest_placements_recorded_at", table_name="contest_placements"
    )
    op.drop_index(
        "ix_contest_placements_slate_date", table_name="contest_placements"
    )
    op.drop_table("contest_placements")
