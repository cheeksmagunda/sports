"""Same-day live ownership capture (#38 / F6).

Attempts Real Sports' /stats endpoint on every job2 dispatch once we're near
lock, so `slate_labels.drafts` -- and therefore `player_slate_ownership`'s
actual side and `field.project_ownership`'s measured path -- can start
filling in from the moment the platform's `draftStats` stops being empty,
instead of waiting for next-day day-close.

Empirically confirmed 2026-08-30: /stats returns `draftStats == []` while a
contest is pregame, so this is a no-op for hours before lock by design (see
CAPTURE_WINDOW_BEFORE_LOCK) -- that's fine, it exists to move measured
ownership from next-day to same-hour for the calibration loop and any late
re-freeze, not to change today's own freeze decision.

`ingest.realsports.discover_wnba_contest_id` validates the sport of every
observed contest id before returning the newest WNBA contest. This module
therefore needs only to capture that single validated contest.

Every failure mode here (missing session, network, ambiguous discovery,
timeout) must degrade to a no-op: this runs inside job2's dispatch and must
never affect the freeze decision.
"""

from __future__ import annotations

import asyncio
import datetime as dt

from wnba_oracle.common.logging import get_logger

log = get_logger("oracle.live_ownership")

CAPTURE_TIMEOUT_SECONDS = 25.0
# The endpoint is empty for hours before lock (confirmed empirically), so
# don't spend a Playwright launch on every 5-minute dispatch all afternoon --
# only attempt once we're within this window of (or past) lock.
CAPTURE_WINDOW_BEFORE_LOCK = dt.timedelta(minutes=30)


def should_attempt_capture(*, now_utc: dt.datetime, lock_time: dt.datetime | None) -> bool:
    """Gate the (comparatively expensive) browser-based attempt to the window
    where the platform might plausibly have transitioned out of pregame.
    ``lock_time`` is None when slate_meta has no tip yet -- skip rather than
    guess, the next dispatch will have it."""
    if lock_time is None:
        return False
    return now_utc >= lock_time - CAPTURE_WINDOW_BEFORE_LOCK


async def _discover_and_capture() -> dict[str, object]:
    from wnba_oracle.ingest.contest_stats import ContestUnavailable, fetch_contest_stats
    from wnba_oracle.ingest.realsports import (
        discover_wnba_contest_id,
        headers_or_capture,
    )
    from wnba_oracle.scheduler.job1 import _device_name, _device_uuid

    headers = await headers_or_capture(_device_uuid(), _device_name())
    contest_id = await discover_wnba_contest_id(headers=headers)
    if contest_id is None:
        return {"status": "no_contest_id_observed"}

    import httpx

    with httpx.Client(timeout=20.0) as client:
        try:
            labels = fetch_contest_stats(contest_id, headers, client)
        except ContestUnavailable:
            return {"status": "no_wnba_contest_validated", "contest_id": contest_id}
        if not labels:
            return {"status": "pregame_empty", "contest_id": contest_id}
        from wnba_oracle.ingest.backfill import persist_labels

        n_persisted = persist_labels(labels)
        return {"status": "captured", "contest_id": contest_id, "n_players": n_persisted}


def capture_live_ownership_safe(*, now_utc: dt.datetime, lock_time: dt.datetime | None) -> None:
    """Best-effort, timeout-bounded, never-raises entry point for job2."""
    if not should_attempt_capture(now_utc=now_utc, lock_time=lock_time):
        return
    try:
        result = asyncio.run(
            asyncio.wait_for(_discover_and_capture(), timeout=CAPTURE_TIMEOUT_SECONDS)
        )
        log.info("live_ownership_capture", **result)
    except TimeoutError:
        log.warning("live_ownership_capture_timeout", timeout_s=CAPTURE_TIMEOUT_SECONDS)
    except Exception as exc:
        log.warning("live_ownership_capture_failed", error_type=type(exc).__name__)
