"""Same-name identity collision reconciliation (offline, observation only).

Adapts the flag-never-merge posture of nfl-oracle's identity/aliases.py.
drop_ambiguous_identity_rows encodes the NFL incident lesson (commit
508ee81) directly in code: a same-name collision drops the affected rows from
a training set and records why, rather than weakening a training validator
to let ambiguous identities through.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

from nhl_oracle.identity.map import NhlIdentityMap

_NON_ALNUM_RE = re.compile(r"[^a-z0-9\s]+")
_WS_RE = re.compile(r"\s+")


def normalize_display_name(name: str | None) -> str | None:
    if not name:
        return None
    text = name.strip().lower()
    text = _NON_ALNUM_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    return text or None


def reconcile_identity_collisions(identity: NhlIdentityMap) -> dict[str, Any]:
    """Report same-name collisions across distinct player ids.

    Never merges automatically. A collision is a signal to drop the ambiguous
    rows from training data or to queue for human review, not a hint about
    which id is correct.
    """

    by_normalized: dict[str, list[int]] = defaultdict(list)
    for player_id in identity.player_ids():
        record = identity.get(player_id)
        if record is None or not record.display_name:
            continue
        normalized = normalize_display_name(record.display_name)
        if normalized:
            by_normalized[normalized].append(player_id)

    collisions = {key: sorted(set(ids)) for key, ids in by_normalized.items() if len(set(ids)) > 1}
    return {
        "contest_entry": False,
        "observation_only": True,
        "n_identities": len(identity),
        "collision_count": len(collisions),
        "collisions": collisions,
    }


def drop_ambiguous_identity_rows(
    rows: list[dict[str, Any]],
    *,
    identity: NhlIdentityMap,
    id_field: str = "real_player_id",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split training rows into (kept, dropped) based on identity collisions.

    Rows referencing a player id involved in a same-name collision are
    dropped and returned with an audit reason, rather than silently kept or
    used to weaken a training validator.
    """

    report = reconcile_identity_collisions(identity)
    ambiguous_ids: set[int] = set()
    for ids in report["collisions"].values():
        ambiguous_ids.update(ids)

    kept: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for row in rows:
        raw_id = row.get(id_field)
        try:
            player_id = int(raw_id) if raw_id is not None else None
        except (TypeError, ValueError):
            player_id = None
        if player_id is not None and player_id in ambiguous_ids:
            dropped.append({**row, "drop_reason": "ambiguous_identity_same_name_collision"})
        else:
            kept.append(row)
    return kept, dropped
