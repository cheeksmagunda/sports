"""Read-only slate-timing endpoint for the frontend countdown (D104).

The morning loader counts down to the lineup freeze. job2 freezes at
``first_tip - freeze_lead_minutes`` (tip-relative T-40, D93), which varies by
day because WNBA slates tip at different clock times. The frontend cannot know
that target before the lineup is frozen (``/lineup/{date}`` 404s until then),
so this endpoint exposes the slate's first tip and the derived freeze target.
It mirrors job2's own freeze-deadline math so the on-screen clock matches the
actual freeze, with no hardcoded wall-clock slot.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy import text

from wnba_oracle.common.settings import get_settings
from wnba_oracle.db.engine import get_engine

router = APIRouter(prefix="/slate", tags=["slate"])

# Same column order job2._load_slate_lock_time uses: prefer an explicit contest
# lock, else the first tip (DFS contests lock at first game start).
_SLATE_META_Q = text(
    "SELECT contest_lock_utc, first_tip_utc FROM slate_meta WHERE slate_date = :sd"
)


def _as_utc(value: dt.datetime) -> dt.datetime:
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.UTC)
    return value.astimezone(dt.UTC)


@router.get("/{slate_date}")
def get_slate_meta(slate_date: str) -> dict[str, Any]:
    """Slate timing for the countdown.

    Returns ``first_tip_utc`` and the tip-relative ``freeze_target_utc``
    (= lock - ``freeze_lead_minutes``). 404 until job1 captures the slate's
    game times, which the frontend treats as "no timing yet" and shows a
    neutral waiting state rather than a misleading clock.
    """
    try:
        eng = get_engine()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    with eng.connect() as conn:
        row = conn.execute(_SLATE_META_Q, {"sd": slate_date}).first()

    if row is None:
        raise HTTPException(status_code=404, detail="no slate timing for slate")

    contest_lock, first_tip = row[0], row[1]
    lock = contest_lock or first_tip
    if lock is None:
        # Row exists but job1 could not parse any tip time (e.g. empty slate).
        raise HTTPException(status_code=404, detail="no slate timing for slate")

    lock = _as_utc(lock)
    lead = int(get_settings().freeze_lead_minutes)
    freeze_target = lock - dt.timedelta(minutes=lead)
    return {
        "slate_date": slate_date,
        "first_tip_utc": _as_utc(first_tip).isoformat() if first_tip else None,
        "contest_lock_utc": _as_utc(contest_lock).isoformat() if contest_lock else None,
        "freeze_lead_minutes": lead,
        "freeze_target_utc": freeze_target.isoformat(),
    }
