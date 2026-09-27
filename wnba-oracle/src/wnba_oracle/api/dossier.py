"""Read-only API endpoint for the unified post-slate dossier (#35 phase 3, #39).

Composes already-persisted canonical records (frozen_lineups, the immutable
freeze_audit_snapshots payload, ScoringProvenance, job1_enrichment,
canonical_player_identities, slate_labels, contest_leaderboards,
contest_placements, wnba_game_logs) into one response. Nothing is
recomputed from current prediction or optimizer code; see
``wnba_oracle.lineage.postmortem`` for the section contract.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from wnba_oracle.db.engine import get_api_engine as get_engine
from wnba_oracle.lineage.audit import build_post_slate_dossier

router = APIRouter(prefix="/dossier", tags=["dossier"])


@router.get("/{slate_date}")
def get_dossier(slate_date: str) -> dict[str, Any]:
    """Return the unified post-slate dossier for slate_date.

    404 only when no frozen lineup exists for the slate. Once a freeze exists
    the response is 200 with a top-level ``status`` (``pending`` before
    slate_labels are ingested, ``partial`` when leaderboard or placement is
    missing, ``finalized`` otherwise) and a ``sections`` index over the 12
    issue #35 points, each carrying an explicit ``status`` and ``reason``.
    The committed/field_best/theoretical_ceiling ``entries`` and gaps appear
    only when all three inputs exist; ``entries_status`` says why otherwise.
    """
    try:
        eng = get_engine()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    dossier = build_post_slate_dossier(slate_date, engine=eng)
    if dossier is None:
        raise HTTPException(status_code=404, detail="no frozen lineup for slate")
    return dossier
