"""Offline placeholder values for any FeatureSpec still marked ``offline_stub``.

Emits null / false placeholders with clear live_ok + stub flags. Never invents
injury, weather, pace, or opponent-defense magnitudes. No contest entry.

As of #189 every registry entry has a live capture path, so the stub list is
normally empty and ``values_are_stubs`` is False. The helper stays because the
registry may add a spec ahead of its capture path again; it reports the current
registry rather than a frozen list.
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
    """One row of offline stubs for whichever specs are still unwired."""

    stubs = offline_stub_feature_names()
    row: dict[str, Any] = {
        "live_ok": True,
        "contest_entry": False,
        "observation_only": True,
        "values_are_stubs": bool(stubs),
        "stub_features": list(stubs),
    }
    if player_id is not None:
        row["player_id"] = player_id
    if season is not None:
        row["season"] = season
    if week is not None:
        row["week"] = week
    # Explicit nulls / false. Never fabricate magnitudes.
    for name in stubs:
        row[name] = False if name.endswith("_available") else None
    return row
