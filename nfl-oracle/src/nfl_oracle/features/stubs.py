"""Offline stub feature values for pre-lock FeatureSpecs (observation only).

Emits null / false placeholders with clear live_ok + stub flags. Does not invent
injury/weather/pace numbers. No contest entry.
"""

from __future__ import annotations

from typing import Any

from nfl_oracle.features.schema import offline_stub_feature_names


def offline_stub_feature_row(
    *,
    player_id: int | None = None,
    season: int | None = None,
    week: int | None = None,
) -> dict[str, Any]:
    """One row of offline stubs for injury/weather/pace/opponent-adjusted specs."""

    stubs = offline_stub_feature_names()
    row: dict[str, Any] = {
        "live_ok": True,
        "contest_entry": False,
        "observation_only": True,
        "values_are_stubs": True,
        "stub_features": list(stubs),
    }
    if player_id is not None:
        row["player_id"] = player_id
    if season is not None:
        row["season"] = season
    if week is not None:
        row["week"] = week
    # Explicit nulls / false — never fabricate magnitudes.
    for name in stubs:
        if name.endswith("_available"):
            row[name] = False
        elif name == "is_divisional":
            row[name] = None
        else:
            row[name] = None
    return row
