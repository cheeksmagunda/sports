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

`ingest.realsports.discover_wnba_contest_id` returns only `max(seen_ids)`,
which silently picks the wrong sport once more than two sports are active on
the account at once (observed 2026-08-30: a max-id soccer contest sat above
the real WNBA one). `_discover_and_capture` below tries every id observed
during the same browse, highest first, and uses whichever one first
validates as an available WNBA contest -- the existing single-shot discovery
is left as-is elsewhere since day-close's own windowed backfill already
tolerates it by scanning a range, not trusting one id.

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
        DEFAULT_USER_AGENT,
        STORAGE_STATE_PATH,
        StorageStateMissing,
        headers_or_capture,
    )
    from wnba_oracle.scheduler.job1 import _device_name, _device_uuid

    if not STORAGE_STATE_PATH.exists():
        raise StorageStateMissing(f"{STORAGE_STATE_PATH} not found")

    from playwright.async_api import async_playwright

    seen_ids: list[int] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 599, "height": 868},
            storage_state=str(STORAGE_STATE_PATH),
            user_agent=DEFAULT_USER_AGENT,
        )

        def on_req(req: object) -> None:
            url = getattr(req, "url", "")
            if "/games/playerratingcontest/" not in url:
                return
            try:
                tail = url.split("/games/playerratingcontest/")[1]
                cid = int(tail.split("?")[0].split("/")[0])
                if cid not in seen_ids:
                    seen_ids.append(cid)
            except (ValueError, IndexError):
                pass

        page = await ctx.new_page()
        page.on("request", on_req)
        try:
            await page.goto("https://realsports.io/", wait_until="domcontentloaded", timeout=15000)
            await page.evaluate("localStorage.setItem('selectedSport', 'wnba');")
            await page.goto("https://realsports.io/", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)
            try:
                await page.locator("text=/WNBA/i").first.click(timeout=3000)
                await page.wait_for_timeout(2500)
            except Exception:
                pass
        except Exception:
            pass
        await browser.close()

    if not seen_ids:
        return {"status": "no_contest_id_observed"}

    headers = await headers_or_capture(_device_uuid(), _device_name())

    import httpx

    with httpx.Client(timeout=20.0) as client:
        for cid in sorted(seen_ids, reverse=True):
            try:
                labels = fetch_contest_stats(cid, headers, client)
            except ContestUnavailable:
                continue
            if not labels:
                return {"status": "pregame_empty", "contest_id": cid}
            from wnba_oracle.ingest.backfill import persist_labels

            n_persisted = persist_labels(labels)
            return {"status": "captured", "contest_id": cid, "n_players": n_persisted}
    return {"status": "no_wnba_contest_validated", "candidates": seen_ids}


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
