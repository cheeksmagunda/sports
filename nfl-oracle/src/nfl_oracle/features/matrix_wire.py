"""Apply portfolio FEATURE_MATRIX serve-on keys to an NFL context vector (#583)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from oracle_core.feature_matrix import wire_available_to_freeze


def apply_feature_matrix(
    vector: dict[str, float],
    *,
    season_averages: Mapping[str, Any] | None = None,
) -> dict[str, float]:
    """Copy serve-on signals onto ``vector`` in place and return it.

    Moneyline and rank already written by the context extractors are passed
    back through the matrix so a serve-off row cannot be smuggled in, and
    ``seasonAverages`` flatten onto ``season_avg_*`` when the pool sent them.
    """

    available: dict[str, Any] = {
        "team_moneyline": vector.get("team_moneyline"),
        "opponent_moneyline": vector.get("opponent_moneyline"),
        "moneyline_available": vector.get("moneyline_available", 0.0),
        "overall_rank": vector.get("overall_rank"),
        "season_averages": season_averages,
    }
    vector.update(wire_available_to_freeze("nfl", available))
    return vector
