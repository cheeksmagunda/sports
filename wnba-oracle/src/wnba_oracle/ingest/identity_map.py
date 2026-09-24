"""Canonical Real Sports -> stats.wnba.com identity persistence helpers."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text

from wnba_oracle.common.logging import get_logger
from wnba_oracle.ingest.identity import ResolutionOutcome, Resolver

log = get_logger("oracle.ingest.identity_map")

PROVENANCE_PRIORITY: dict[str, int] = {
    "provider_nba_id": 0,
    "explicit_override": 1,
    "normalized_name_fallback": 2,
}


@dataclass(frozen=True, slots=True)
class CanonicalIdentityMapping:
    real_sports_player_id: str
    wnba_player_id: int
    provenance: str
    provider_nba_id: int | None
    real_sports_display_name: str
    real_sports_first_name: str
    real_sports_last_name: str
    real_sports_team: str
    wnba_full_name: str | None


@dataclass(frozen=True, slots=True)
class CanonicalIdentityBackfillReport:
    mappings: tuple[CanonicalIdentityMapping, ...]
    ambiguous_real_sports_ids: tuple[str, ...]
    unresolved_real_sports_ids: tuple[str, ...]


CANONICAL_IDENTITY_SELECT = text(
    """
    SELECT real_sports_player_id, wnba_player_id
    FROM canonical_player_identities
    WHERE real_sports_player_id = :real_sports_player_id
    FOR UPDATE
    """
)

CANONICAL_IDENTITY_INSERT = text(
    """
    INSERT INTO canonical_player_identities (
        real_sports_player_id,
        wnba_player_id,
        provenance,
        provider_nba_id,
        real_sports_display_name,
        real_sports_first_name,
        real_sports_last_name,
        real_sports_team,
        wnba_full_name,
        first_seen_at,
        last_seen_at
    ) VALUES (
        :real_sports_player_id,
        :wnba_player_id,
        :provenance,
        :provider_nba_id,
        :real_sports_display_name,
        :real_sports_first_name,
        :real_sports_last_name,
        :real_sports_team,
        :wnba_full_name,
        :first_seen_at,
        :last_seen_at
    )
    """
)

CANONICAL_IDENTITY_UPDATE = text(
    """
    UPDATE canonical_player_identities
    SET provenance = :provenance,
        provider_nba_id = :provider_nba_id,
        real_sports_display_name = :real_sports_display_name,
        real_sports_first_name = :real_sports_first_name,
        real_sports_last_name = :real_sports_last_name,
        real_sports_team = :real_sports_team,
        wnba_full_name = :wnba_full_name,
        last_seen_at = :last_seen_at
    WHERE real_sports_player_id = :real_sports_player_id
    """
)


def build_identity_mapping(
    resolver: Resolver,
    *,
    real_sports_id: str,
    display_name: str,
    first_name: str = "",
    last_name: str = "",
    team: str = "",
    nba_id: int | None = None,
) -> CanonicalIdentityMapping | None:
    outcome = resolver.resolve_with_outcome(
        real_sports_id,
        display_name=display_name,
        first_name=first_name,
        last_name=last_name,
        team=team,
        nba_id=nba_id,
    )
    return mapping_from_outcome(
        resolver,
        outcome,
        real_sports_id=real_sports_id,
        display_name=display_name,
        first_name=first_name,
        last_name=last_name,
        team=team,
        nba_id=nba_id,
    )


def mapping_from_outcome(
    resolver: Resolver,
    outcome: ResolutionOutcome,
    *,
    real_sports_id: str,
    display_name: str,
    first_name: str = "",
    last_name: str = "",
    team: str = "",
    nba_id: int | None = None,
) -> CanonicalIdentityMapping | None:
    if outcome.status != "resolved" or outcome.wnba_player_id is None or outcome.provenance is None:
        return None
    return CanonicalIdentityMapping(
        real_sports_player_id=str(real_sports_id),
        wnba_player_id=int(outcome.wnba_player_id),
        provenance=outcome.provenance,
        provider_nba_id=int(nba_id) if nba_id is not None else None,
        real_sports_display_name=str(display_name or ""),
        real_sports_first_name=str(first_name or ""),
        real_sports_last_name=str(last_name or ""),
        real_sports_team=str(team or ""),
        wnba_full_name=outcome.catalog_full_name
        or resolver.catalog_full_name(outcome.wnba_player_id),
    )


def persist_canonical_identity_mappings(
    conn: Any,
    mappings: list[CanonicalIdentityMapping],
    *,
    seen_at: dt.datetime | None = None,
) -> dict[str, int]:
    now = seen_at or dt.datetime.now(dt.UTC)
    inserted = updated = skipped_conflicts = 0
    for mapping in mappings:
        params = {
            "real_sports_player_id": mapping.real_sports_player_id,
            "wnba_player_id": mapping.wnba_player_id,
            "provenance": mapping.provenance,
            "provider_nba_id": mapping.provider_nba_id,
            "real_sports_display_name": mapping.real_sports_display_name,
            "real_sports_first_name": mapping.real_sports_first_name,
            "real_sports_last_name": mapping.real_sports_last_name,
            "real_sports_team": mapping.real_sports_team,
            "wnba_full_name": mapping.wnba_full_name,
            "first_seen_at": now,
            "last_seen_at": now,
        }
        existing = conn.execute(
            CANONICAL_IDENTITY_SELECT,
            {"real_sports_player_id": mapping.real_sports_player_id},
        ).first()
        if existing is None:
            conn.execute(CANONICAL_IDENTITY_INSERT, params)
            inserted += 1
            continue
        existing_pid = int(existing.wnba_player_id)
        if existing_pid != mapping.wnba_player_id:
            skipped_conflicts += 1
            log.warning(
                "canonical_identity_conflict_skipped",
                real_sports_player_id=mapping.real_sports_player_id,
                existing_wnba_player_id=existing_pid,
                incoming_wnba_player_id=mapping.wnba_player_id,
            )
            continue
        conn.execute(CANONICAL_IDENTITY_UPDATE, params)
        updated += 1
    return {"inserted": inserted, "updated": updated, "skipped_conflicts": skipped_conflicts}


def build_unambiguous_backfill(
    resolver: Resolver,
    rows: list[dict[str, object]],
) -> CanonicalIdentityBackfillReport:
    candidates: dict[str, list[CanonicalIdentityMapping]] = {}
    ambiguous_ids: set[str] = set()
    unresolved_ids: set[str] = set()
    for row in rows:
        real_sports_id = str(
            row.get("real_sports_id") or row.get("real_sports_player_id") or ""
        ).strip()
        if not real_sports_id:
            continue
        mapping = build_identity_mapping(
            resolver,
            real_sports_id=real_sports_id,
            display_name=str(row.get("display_name") or ""),
            first_name=str(row.get("first_name") or ""),
            last_name=str(row.get("last_name") or ""),
            team=str(row.get("team") or ""),
            nba_id=_maybe_int(row.get("nba_id")),
        )
        if mapping is None:
            outcome = resolver.resolve_with_outcome(
                real_sports_id,
                display_name=str(row.get("display_name") or ""),
                first_name=str(row.get("first_name") or ""),
                last_name=str(row.get("last_name") or ""),
                team=str(row.get("team") or ""),
                nba_id=_maybe_int(row.get("nba_id")),
            )
            if outcome.status == "ambiguous":
                ambiguous_ids.add(real_sports_id)
            else:
                unresolved_ids.add(real_sports_id)
            continue
        candidates.setdefault(real_sports_id, []).append(mapping)

    mappings: list[CanonicalIdentityMapping] = []
    for real_sports_id, resolved in candidates.items():
        unique_targets = {mapping.wnba_player_id for mapping in resolved}
        if len(unique_targets) != 1:
            ambiguous_ids.add(real_sports_id)
            continue
        best = min(
            resolved,
            key=lambda mapping: PROVENANCE_PRIORITY.get(mapping.provenance, 99),
        )
        mappings.append(best)

    ambiguous_ids.difference_update({mapping.real_sports_player_id for mapping in mappings})
    unresolved_ids.difference_update(ambiguous_ids)
    if ambiguous_ids:
        log.info(
            "canonical_identity_backfill_ambiguous_skipped",
            n_ids=len(ambiguous_ids),
            real_sports_ids=sorted(ambiguous_ids),
        )
    if unresolved_ids:
        log.info(
            "canonical_identity_backfill_unresolved_skipped",
            n_ids=len(unresolved_ids),
            real_sports_ids=sorted(unresolved_ids),
        )
    return CanonicalIdentityBackfillReport(
        mappings=tuple(sorted(mappings, key=lambda mapping: mapping.real_sports_player_id)),
        ambiguous_real_sports_ids=tuple(sorted(ambiguous_ids)),
        unresolved_real_sports_ids=tuple(sorted(unresolved_ids)),
    )


def _maybe_int(value: object) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(str(value))
    except ValueError:
        return None
