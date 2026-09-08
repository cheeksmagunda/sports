"""Offline identity map loaders (observation only; no network)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nfl_oracle.common.paths import resolve_project_root
from nfl_oracle.identity.aliases import reconcile_alias_collisions
from nfl_oracle.identity.density import IdentityDensity, summarize_identity_density
from nfl_oracle.identity.from_corpus import upsert_from_players_payload
from nfl_oracle.identity.map import IdentityMap


def identity_players_file(project_root: Path | None = None) -> Path:
    """Default offline players fixture path under data/identity/players.json."""

    root = project_root or resolve_project_root(__file__)
    return root / "data" / "identity" / "players.json"


def load_identity_map_from_players_file(path: Path) -> IdentityMap:
    """Load an IdentityMap from a redacted /players-shaped JSON file."""

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise TypeError("identity players file must be a JSON object")
    identity = IdentityMap()
    upsert_from_players_payload(identity, raw)
    return identity


def research_identity_summary(
    *,
    project_root: Path | None = None,
    players_path: Path | None = None,
) -> dict[str, Any]:
    """Read-only identity density for research status / routes."""

    target = players_path or identity_players_file(project_root)
    if not target.is_file():
        return {
            "contest_entry": False,
            "observation_only": True,
            "path_exists": False,
            "error": "identity_players_missing",
            "density": None,
            "n_identities": 0,
        }
    try:
        identity = load_identity_map_from_players_file(target)
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return {
            "contest_entry": False,
            "observation_only": True,
            "path_exists": True,
            "error": type(exc).__name__,
            "density": None,
            "n_identities": 0,
        }
    density: IdentityDensity = summarize_identity_density(identity)
    aliases = reconcile_alias_collisions(identity)
    return {
        "contest_entry": False,
        "observation_only": True,
        "path_exists": True,
        "error": None,
        "n_identities": len(identity),
        "density": density.to_dict(),
        "aliases": {
            "n_with_external_alias": aliases["n_with_external_alias"],
            "alias_collision_count": aliases["alias_collision_count"],
            "display_name_collision_count": aliases["display_name_collision_count"],
            "normalized_name_collision_count": aliases["normalized_name_collision_count"],
            "soft_name_collision_count": aliases["soft_name_collision_count"],
        },
    }
