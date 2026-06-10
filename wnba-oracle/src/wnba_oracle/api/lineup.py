"""Read-only API endpoints for the frozen lineup."""

from __future__ import annotations

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

    # D82: frozen_lineups is append-only. Serve the latest freeze
    # (max freeze_seq) and surface provenance so a re-frozen slate is
    # visible without digging into metadata_json. n_freezes counts every
    # row the WHERE clause matched, i.e. how many freezes this slate has.
    if model_sha:
        q = text(
            "SELECT slate_date, model_sha, payout_regime, frozen_at, lineup, "
            "entry_recommendation, expected_payout, metadata_json, "
            "freeze_seq, frozen_via, COUNT(*) OVER () AS n_freezes "
            "FROM frozen_lineups WHERE slate_date = :sd AND model_sha = :sha "
            "ORDER BY freeze_seq DESC, frozen_at DESC LIMIT 1"
        )
        with eng.connect() as conn:
            row = conn.execute(q, {"sd": slate_date, "sha": model_sha}).first()
    else:
        q = text(
            "SELECT slate_date, model_sha, payout_regime, frozen_at, lineup, "
            "entry_recommendation, expected_payout, metadata_json, "
            "freeze_seq, frozen_via, COUNT(*) OVER () AS n_freezes "
            "FROM frozen_lineups WHERE slate_date = :sd "
            "ORDER BY freeze_seq DESC, frozen_at DESC LIMIT 1"
        )
        with eng.connect() as conn:
            row = conn.execute(q, {"sd": slate_date}).first()

    if row is None:
        raise HTTPException(status_code=404, detail="no frozen lineup for slate")

    rec = dict(row._mapping)
    rec["frozen_at"] = rec["frozen_at"].isoformat() if rec.get("frozen_at") else None
    # JSONB columns come back as already-parsed dicts via psycopg.
    return rec


@router.get("/{slate_date}/history")
def get_lineup_history(slate_date: str) -> list[dict[str, Any]]:
    """Every freeze appended for slate_date, oldest first (audit surface).

    `/lineup/{date}` answers "what is the lineup"; this answers "what did
    the system show at each point in time", which is what the operator
    needs to reconstruct what they acted on.
    """
    try:
        eng = get_engine()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    q = text(
        "SELECT slate_date, model_sha, payout_regime, frozen_at, lineup, "
        "entry_recommendation, expected_payout, metadata_json, "
        "freeze_seq, frozen_via "
        "FROM frozen_lineups WHERE slate_date = :sd "
        "ORDER BY freeze_seq ASC, frozen_at ASC"
    )
    with eng.connect() as conn:
        rows = list(conn.execute(q, {"sd": slate_date}))
    if not rows:
        raise HTTPException(status_code=404, detail="no frozen lineup for slate")

    out: list[dict[str, Any]] = []
    for r in rows:
        rec = dict(r._mapping)
        rec["slate_date"] = str(rec["slate_date"])
        rec["frozen_at"] = rec["frozen_at"].isoformat() if rec.get("frozen_at") else None
        out.append(rec)
    return out


@router.get("")
def list_recent_lineups(limit: int = Query(default=10, ge=1, le=60)) -> list[dict[str, Any]]:
    try:
        eng = get_engine()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # D82: one entry per (slate_date, model_sha), showing the latest freeze.
    # The /lineup/{date}/history endpoint is the audit surface for all rows.
    q = text(
        "SELECT DISTINCT ON (slate_date, model_sha) "
        "slate_date, model_sha, payout_regime, frozen_at, "
        "entry_recommendation, expected_payout, freeze_seq, frozen_via "
        "FROM frozen_lineups "
        "ORDER BY slate_date DESC, model_sha, freeze_seq DESC LIMIT :n"
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
            "freeze_seq": r._mapping["freeze_seq"],
            "frozen_via": r._mapping["frozen_via"],
        }
        for r in rows
    ]
