"""Sport-neutral wall-clock timing helpers for scheduled decision gates.

Every sport application currently derives its own "how long until we must
act" math inline (NFL's T-40 freeze gate, WNBA's job1/job1late/job2
deadlines). This module holds only the provider-neutral arithmetic —
comparing "now" to a target instant and a lead time — so a sport can call
one tested helper instead of re-deriving `timedelta` subtraction each time.
It has no opinion about what "act" means for a given sport (freeze a
lineup, submit a contest, refresh a token): that decision, and any related
business-state (already frozen, contest locked, and so on), stays owned by
each application.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class WindowDecision:
    """Whether *now* has reached a target instant minus a lead time."""

    due: bool
    due_at: datetime
    target_at: datetime
    seconds_remaining: float

    def as_details(self) -> dict[str, str]:
        """A JSON-safe summary suitable for a job's ``record_run`` details."""

        return {"next_due": self.due_at.isoformat(), "target_at": self.target_at.isoformat()}


def window_decision(
    *,
    now: datetime,
    target_at: datetime,
    lead: timedelta,
) -> WindowDecision:
    """Report whether *now* is at or past ``target_at - lead``.

    All datetimes must be timezone-aware and comparable; this function does
    not normalize naive datetimes, matching the rest of the portfolio's
    "always pass an aware UTC datetime" convention.
    """

    due_at = target_at - lead
    remaining = (due_at - now).total_seconds()
    return WindowDecision(
        due=now >= due_at,
        due_at=due_at,
        target_at=target_at,
        seconds_remaining=remaining,
    )
