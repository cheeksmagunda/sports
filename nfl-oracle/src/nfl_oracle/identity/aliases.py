"""Alias reconciliation for Real-primary identity maps (offline).

Merges external id aliases (gsis, espn, sleeper, etc.) and reports display-name
collisions without enabling contest entry. Observation / research only.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from nfl_oracle.identity.map import IdentityMap, IdentityRecord


def normalize_alias_key(namespace: str, value: str) -> str:
    return f"{namespace.strip().lower()}:{value.strip().lower()}"


def merge_external_ids(*maps: dict[str, str]) -> dict[str, str]:
    """Last-write-wins merge of alias namespaces → external ids."""

    out: dict[str, str] = {}
    for m in maps:
        for key, val in m.items():
            ns = str(key).strip()
            vv = str(val).strip()
            if ns and vv:
                out[ns] = vv
    return out


def upsert_with_aliases(
    identity: IdentityMap,
    record: IdentityRecord,
    *,
    prefer_existing_name: bool = True,
) -> IdentityRecord:
    """Upsert record, merging external_ids with any existing row."""

    existing = identity.get(record.real_player_id)
    if existing is None:
        identity.upsert(record)
        return record
    merged_ids = merge_external_ids(existing.external_ids, record.external_ids)
    display: str | None
    if prefer_existing_name and existing.display_name:
        display = existing.display_name
    else:
        display = record.display_name or existing.display_name
    position = existing.position or record.position
    team_id = existing.team_id if existing.team_id is not None else record.team_id
    merged = IdentityRecord(
        real_player_id=record.real_player_id,
        display_name=display,
        position=position,
        team_id=team_id,
        external_ids=merged_ids,
    )
    identity.upsert(merged)
    return merged


def reconcile_alias_collisions(identity: IdentityMap) -> dict[str, Any]:
    """Report alias / display-name collisions across Real player ids.

    Does not auto-merge distinct Real ids (unsafe without human review).
    """

    by_alias: dict[str, list[int]] = defaultdict(list)
    by_name: dict[str, list[int]] = defaultdict(list)
    n_with_alias = 0
    for pid in identity.player_ids():
        rec = identity.get(pid)
        if rec is None:
            continue
        if rec.external_ids:
            n_with_alias += 1
        if rec.display_name:
            by_name[rec.display_name.strip().lower()].append(pid)
        for ns, val in rec.external_ids.items():
            by_alias[normalize_alias_key(ns, val)].append(pid)
    alias_collisions = {k: v for k, v in sorted(by_alias.items()) if len(set(v)) > 1}
    name_collisions = {k: v for k, v in sorted(by_name.items()) if len(set(v)) > 1}
    return {
        "contest_entry": False,
        "observation_only": True,
        "n_identities": len(identity),
        "n_with_external_alias": n_with_alias,
        "alias_collision_count": len(alias_collisions),
        "display_name_collision_count": len(name_collisions),
        "alias_collisions": {k: sorted(set(v)) for k, v in alias_collisions.items()},
        "display_name_collisions": {k: sorted(set(v)) for k, v in name_collisions.items()},
    }


def apply_alias_table(identity: IdentityMap, rows: list[dict[str, Any]]) -> int:
    """Apply offline alias rows. Returns number of rows applied."""

    applied = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        pid_raw = row.get("real_player_id") or row.get("playerId") or row.get("id")
        if pid_raw is None:
            continue
        try:
            pid = int(pid_raw)
        except (TypeError, ValueError):
            continue
        ext_raw = row.get("external_ids") or {}
        ext: dict[str, str] = {}
        if isinstance(ext_raw, dict):
            ext = {str(k): str(v) for k, v in ext_raw.items() if v is not None}
        for flat_key, ns in (
            ("gsis_id", "gsis"),
            ("espn_id", "espn"),
            ("sleeper_id", "sleeper"),
            ("pfr_id", "pfr"),
        ):
            if row.get(flat_key):
                ext[ns] = str(row[flat_key])
        existing = identity.get(pid)
        team_id = existing.team_id if existing is not None else None
        if row.get("team_id") is not None:
            try:
                team_id = int(row["team_id"])
            except (TypeError, ValueError):
                pass
        display = str(row["display_name"]) if row.get("display_name") else None
        position = str(row["position"]) if row.get("position") else None
        if existing is not None:
            display = display or existing.display_name
            position = position or existing.position
            ext = merge_external_ids(existing.external_ids, ext)
        record = IdentityRecord(
            real_player_id=pid,
            display_name=display,
            position=position,
            team_id=team_id,
            external_ids=ext,
        )
        upsert_with_aliases(identity, record)
        applied += 1
    return applied
