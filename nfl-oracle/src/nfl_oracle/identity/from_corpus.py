"""Hydrate IdentityMap from Corpus G players payloads (offline)."""

from __future__ import annotations

from typing import Any

from nfl_oracle.identity.map import IdentityMap, IdentityRecord


def _display_name(row: dict[str, Any]) -> str | None:
    for key in ("displayName", "name", "fullName"):
        value = row.get(key)
        if value:
            return str(value)
    first = row.get("firstName")
    last = row.get("lastName")
    parts = [str(p) for p in (first, last) if p]
    if parts:
        return " ".join(parts)
    return None


def upsert_from_players_payload(identity: IdentityMap, payload: dict[str, Any]) -> int:
    """Upsert Real player rows from a redacted `/players` JSON body.

    Returns number of records upserted. Tolerates several common shapes.
    """

    candidates: list[Any] = []
    for key in ("players", "playerList", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            candidates.extend(value)
    if not candidates and isinstance(payload.get("player"), dict):
        candidates.append(payload["player"])

    count = 0
    for row in candidates:
        if not isinstance(row, dict):
            continue
        pid = row.get("playerId") or row.get("id")
        if pid is None:
            continue
        try:
            real_id = int(pid)
        except (TypeError, ValueError):
            continue
        name = _display_name(row)
        position = row.get("position") or row.get("pos")
        team_id_raw = row.get("teamId")
        team_id: int | None
        try:
            team_id = int(team_id_raw) if team_id_raw is not None else None
        except (TypeError, ValueError):
            team_id = None
        identity.upsert(
            IdentityRecord(
                real_player_id=real_id,
                display_name=name,
                position=str(position) if position else None,
                team_id=team_id,
            )
        )
        count += 1
    return count
