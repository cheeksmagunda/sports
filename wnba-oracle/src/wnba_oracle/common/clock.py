"""WNBA slate-calendar conversion over an injected UTC instant."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

SLATE_TIME_ZONE = ZoneInfo("America/New_York")


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def slate_date(now: dt.datetime | None = None) -> dt.date:
    """Return the WNBA contest date for a UTC-aware instant.

    Railway schedules are expressed in UTC, but slates remain on the Eastern
    basketball calendar. In particular, a job2 fire between 00:00 and 03:59
    UTC still belongs to the previous Eastern date.
    """
    instant = now or utc_now()
    if instant.tzinfo is None:
        raise ValueError("slate_date requires a timezone-aware instant")
    return instant.astimezone(SLATE_TIME_ZONE).date()


def previous_slate_date(now: dt.datetime | None = None) -> dt.date:
    return slate_date(now) - dt.timedelta(days=1)
