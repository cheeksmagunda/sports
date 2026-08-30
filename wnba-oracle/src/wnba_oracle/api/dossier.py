"""Read-only API endpoint for the post-slate dossier (#35 phase 3, #39).

Composes the canonical committed/field-winner/theoretical-ceiling records
(frozen_lineups, contest_leaderboards, slate_labels) into a single response
instead of requiring a separate offline script run.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from wnba_oracle.db.engine import get_api_engine as get_engine
from wnba_oracle.dossier import build_dossier

router = APIRouter(prefix="/dossier", tags=["dossier"])


@router.get("/{slate_date}")
def get_dossier(slate_date: str) -> dict[str, Any]:
    """Return the finalized-slate dossier for slate_date.

    Includes our committed entry, the best observed field entry, and the
    theoretical ceiling, each with explicit achievability, censoring, and
    gap-exactness metadata. 404s until the slate has a frozen lineup, a
    captured leaderboard, and realized labels.
    """
    try:
        eng = get_engine()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    dossier = build_dossier(slate_date, engine=eng)
    if dossier is None:
        raise HTTPException(status_code=404, detail="no dossier for slate")
    return dossier.to_dict()
