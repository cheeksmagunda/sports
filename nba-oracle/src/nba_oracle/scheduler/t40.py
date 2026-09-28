"""T-40 publication window for the next still-draftable NBA tip.

The cutoff is the earliest tip still ahead of ``decision_at``, tightened
by an optional contest lock when that lock is sooner. A tipped game does
not close the rest of the slate. Publication may open at cutoff minus
40 minutes and must stop at the cutoff.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from nba_oracle.scheduler.pool import TipGame

T40_OFFSET = timedelta(minutes=40)


@dataclass(frozen=True)
class T40Window:
    """Open interval ``[open_at, cutoff_at)``."""

    cutoff_at: datetime
    open_at: datetime
    offset_minutes: int = 40

    def contains(self, now: datetime) -> bool:
        return self.open_at <= now < self.cutoff_at

    def to_dict(self) -> dict[str, object]:
        return {
            "cutoff_at": self.cutoff_at.isoformat(),
            "open_at": self.open_at.isoformat(),
            "offset_minutes": self.offset_minutes,
        }


def publication_window(
    *,
    games: tuple[TipGame, ...],
    decision_at: datetime,
    lock_at: datetime | None = None,
) -> tuple[T40Window | None, tuple[str, ...]]:
    """Return the active window and any blocking timing reasons.

    ``no_draftable_games`` when every tip is at or before ``decision_at``.
    ``past_cutoff`` when the decision is at or after the lock-tightened
    cutoff. ``before_t40_window`` when the decision is earlier than
    cutoff minus 40 minutes. An empty reason tuple means the decision
    sits inside the window.
    """

    if decision_at.tzinfo is None:
        raise ValueError("decision_at_must_be_timezone_aware")
    if lock_at is not None and lock_at.tzinfo is None:
        raise ValueError("lock_at_must_be_timezone_aware")
    for game in games:
        if game.tip_at.tzinfo is None:
            raise ValueError("tip_at_must_be_timezone_aware")

    remaining = [game.tip_at for game in games if game.tip_at > decision_at]
    if not remaining:
        return None, ("no_draftable_games",)

    cutoff = min(remaining)
    if lock_at is not None:
        cutoff = min(cutoff, lock_at)
    window = T40Window(cutoff_at=cutoff, open_at=cutoff - T40_OFFSET)
    if decision_at >= cutoff:
        return window, ("past_cutoff",)
    if decision_at < window.open_at:
        return window, ("before_t40_window",)
    return window, ()
