"""Pandera schemas at every module boundary.

Each DataFrame produced by an ingest module passes through `validate(df)`
against the corresponding schema before downstream consumers see it.
A schema violation raises pandera.errors.SchemaError and the calling
pipeline halts (Hard Rule 7).

Schema evolution is recorded in DECISIONS.md as a diff entry. Never
silently weaken a constraint to make a failing run pass.
"""

from wnba_oracle.schemas.ingest import (
    OddsSchema,
    PlayerGameLogSchema,
    PlayerPoolSchema,
    PlayerSeasonAveragesSchema,
    RotowireLineupSchema,
    TeamPaceSchema,
)

__all__ = [
    "OddsSchema",
    "PlayerGameLogSchema",
    "PlayerPoolSchema",
    "PlayerSeasonAveragesSchema",
    "RotowireLineupSchema",
    "TeamPaceSchema",
]
