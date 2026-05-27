"""Read-only API endpoints for the frozen lineup."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text

from wnba_oracle.db.engine import get_engine

router = APIRouter(prefix="/lineup", tags=["lineup"])


@router.get("/{slate_date}")
def get_lineup(slate_date: str, model_sha: str = Query(default="")) -> dict[str, Any]:
    """Return the frozen lineup for slate_date.

    If `model_sha` is provided, return that specific frozen artifact; else
    return the most recently frozen lineup for the day.
    """
    try:
        eng = get_engine()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    if model_sha:
        q = text(
            "SELECT slate_date, model_sha, payout_regime, frozen_at, lineup, "
            "entry_recommendation, expected_payout, metadata_json "
            "FROM frozen_lineups WHERE slate_date = :sd AND model_sha = :sha"
        )
        with eng.connect() as conn:
            row = conn.execute(q, {"sd": slate_date, "sha": model_sha}).first()
    else:
        q = text(
            "SELECT slate_date, model_sha, payout_regime, frozen_at, lineup, "
            "entry_recommendation, expected_payout, metadata_json "
            "FROM frozen_lineups WHERE slate_date = :sd "
            "ORDER BY frozen_at DESC LIMIT 1"
        )
        with eng.connect() as conn:
            row = conn.execute(q, {"sd": slate_date}).first()

    if row is None:
        raise HTTPException(status_code=404, detail="no frozen lineup for slate")

    rec = dict(row._mapping)
    rec["frozen_at"] = rec["frozen_at"].isoformat() if rec.get("frozen_at") else None
    # JSONB columns come back as already-parsed dicts via psycopg.
    return rec


@router.get("")
def list_recent_lineups(limit: int = Query(default=10, ge=1, le=60)) -> list[dict[str, Any]]:
    try:
        eng = get_engine()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    q = text(
        "SELECT slate_date, model_sha, payout_regime, frozen_at, "
        "entry_recommendation, expected_payout "
        "FROM frozen_lineups ORDER BY slate_date DESC, frozen_at DESC LIMIT :n"
    )
    with eng.connect() as conn:
        rows = list(conn.execute(q, {"n": limit}))
    return [
        {
            "slate_date": str(r._mapping["slate_date"]),
            "model_sha": r._mapping["model_sha"],
            "payout_regime": r._mapping["payout_regime"],
            "frozen_at": r._mapping["frozen_at"].isoformat()
            if r._mapping.get("frozen_at")
            else None,
            "entry_recommendation": r._mapping["entry_recommendation"],
            "expected_payout": r._mapping["expected_payout"],
        }
        for r in rows
    ]


_ = json
