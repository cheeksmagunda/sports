"""Same-day live ownership capture (#38 / F6 / #434).

Attempts Real Sports' /stats endpoint on every job2 dispatch once we're near
lock, so `slate_labels.drafts` -- and therefore `player_slate_ownership`'s
actual side and `field.project_ownership`'s measured path -- can start
filling in from the moment the platform's `draftStats` stops being empty,
instead of waiting for next-day day-close.

When ``LIVE_OWNERSHIP_CAPTURE_ENABLED`` is on, successful capture returns
draft counts to job2 on the same dispatch so `_build_specs` can attach
measured ownership to field specs (#434). Empirically confirmed 2026-08-30:
`/stats` returns `draftStats == []` while a contest is pregame, so this is
often a no-op for hours before lock (see CAPTURE_WINDOW_BEFORE_LOCK); the
gate stays default-off until offline TV capture shows non-regression.

`ingest.realsports.discover_wnba_contest_id` validates the sport of every
observed contest id before returning the newest WNBA contest. This module
therefore needs only to capture that single validated contest.

Every failure mode here (missing session, network, ambiguous discovery,
timeout) must degrade to an empty dict: this runs inside job2's dispatch and
must never raise into the freeze decision.
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


def _drafts_from_labels(labels: list[object]) -> dict[int, int]:
    """Extract platform_player_id -> drafts for job2 measured ownership (#434)."""

    out: dict[int, int] = {}
    for label in labels:
        pid = getattr(label, "platform_player_id", None)
        drafts = getattr(label, "drafts", None)
        if pid is None or drafts is None:
            continue
        out[int(pid)] = int(drafts)
    return out


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
        return {"status": "no_contest_id_observed", "drafts": {}}

    import httpx

    with httpx.Client(timeout=20.0) as client:
        try:
            labels = fetch_contest_stats(contest_id, headers, client)
        except ContestUnavailable:
            return {
                "status": "no_wnba_contest_validated",
                "contest_id": contest_id,
                "drafts": {},
            }
        if not labels:
            return {"status": "pregame_empty", "contest_id": contest_id, "drafts": {}}
        from wnba_oracle.ingest.backfill import persist_labels

        n_persisted = persist_labels(labels)
        drafts = _drafts_from_labels(labels)
        return {
            "status": "captured",
            "contest_id": contest_id,
            "n_players": n_persisted,
            "drafts": drafts,
        }


def capture_live_ownership_safe(
    *, now_utc: dt.datetime, lock_time: dt.datetime | None
) -> dict[int, int]:
    """Best-effort, timeout-bounded, never-raises entry point for job2.

    Returns pre-lock draft counts when capture succeeds so job2 can feed
    ``_build_specs`` / measured ownership without waiting on a later DB
    round-trip (#434). Empty dict on skip / failure / empty pregame.
    """
    if not should_attempt_capture(now_utc=now_utc, lock_time=lock_time):
        return {}
    try:
        result = asyncio.run(
            asyncio.wait_for(_discover_and_capture(), timeout=CAPTURE_TIMEOUT_SECONDS)
        )
        drafts_raw = result.pop("drafts", {}) if isinstance(result, dict) else {}
        log.info("live_ownership_capture", **result)
        if not isinstance(drafts_raw, dict):
            return {}
        return {int(pid): int(count) for pid, count in drafts_raw.items()}
    except TimeoutError:
        log.warning("live_ownership_capture_timeout", timeout_s=CAPTURE_TIMEOUT_SECONDS)
        return {}
    except Exception as exc:
        log.warning("live_ownership_capture_failed", error_type=type(exc).__name__)
        return {}
