"""Read-only API endpoint over realized Real Sports slate results.

`/lineup/{date}` answers "what did Oracle freeze"; this answers "what
actually happened" using only already-ingested canonical PostgreSQL state
(``slate_labels``). ``real_score`` is the Real Sports provider ``player.value``
ingested verbatim by Job 1/backfill and is never recomputed here (issue #34).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from wnba_oracle.db.engine import get_api_engine as get_engine

router = APIRouter(prefix="/results", tags=["results"])

_ROW_SQL = text(
    "SELECT contest_id, slate_date, section, platform_player_id, display_name, "
    "team_key, card_boost, drafts, real_score, ingested_at "
    "FROM slate_labels WHERE slate_date = :sd "
    "ORDER BY section, real_score DESC NULLS LAST, platform_player_id"
)


def _top_value(rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    """Top-N by realized ``real_score``, deduped by player across sections.

    A player can appear in more than one Real Sports section on the same
    slate (e.g. a value-eligible pool plus a boosted pool). Dedup keeps the
    highest-``real_score`` row for that player and records every section
    they appeared in for provenance, per acceptance item 4.
    """
    best: dict[int, dict[str, Any]] = {}
    sections: dict[int, list[str]] = {}
    for row in rows:
        pid = row["platform_player_id"]
        sections.setdefault(pid, [])
        if row["section"] not in sections[pid]:
            sections[pid].append(row["section"])
        score = row["real_score"]
        current = best.get(pid)
        if current is None:
            best[pid] = row
            continue
        current_score = current["real_score"]
        # NULLS treated as lowest; deterministic tiebreak by platform_player_id.
        if (score is None, -(score or 0.0), pid) < (
            current_score is None,
            -(current_score or 0.0),
            pid,
        ):
            best[pid] = row

    ranked = sorted(
        best.values(),
        key=lambda r: (
            r["real_score"] is None,
            -(r["real_score"] or 0.0),
            r["platform_player_id"],
        ),
    )
    out: list[dict[str, Any]] = []
    for row in ranked[:limit]:
        entry = dict(row)
        entry["sections"] = sections[row["platform_player_id"]]
        out.append(entry)
    return out


@router.get("/{slate_date}")
def get_results(slate_date: str) -> dict[str, Any]:
    """Realized Real Sports results for ``slate_date`` from ``slate_labels``.

    Returns an explicit machine-readable ``pending`` status (200, not 404)
    when the date is a plausible slate date with no ingested rows yet, so
    callers can distinguish "not ingested yet" from a malformed request.
    """
    try:
        eng = get_engine()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    with eng.connect() as conn:
        rows = list(conn.execute(_ROW_SQL, {"sd": slate_date}))

    if not rows:
        return {
            "slate_date": slate_date,
            "status": "pending",
            "rows": [],
            "top_value": [],
        }

    out_rows: list[dict[str, Any]] = []
    for r in rows:
        rec = dict(r._mapping)
        rec["ingested_at"] = rec["ingested_at"].isoformat() if rec.get("ingested_at") else None
        out_rows.append(rec)

    return {
        "slate_date": slate_date,
        "status": "available",
        "rows": out_rows,
        "top_value": _top_value(out_rows),
    }
