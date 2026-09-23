"""Guaranteed-cleanup Playwright browser sessions.

Provider-neutral: this module knows nothing about Real Sports, NFL, WNBA, or
any other domain. It exists because the same pattern — launch a headless
Chromium session, harvest something from it, always release the browser
process — was duplicated across ``nfl_oracle.ingest.realsports`` and
``wnba_oracle.ingest.realsports`` with only 2 of several exit paths calling
``browser.close()``. A container that leaks one Chromium process per missed
close path accumulates threads/handles until the host runs out of resources
(observed in production as a 96-thread NFL worker container on 2026-09-20).

``launch_chromium_session`` is an async context manager: whatever happens
inside the ``async with`` block, including an exception raised by the
caller's own harvesting code, the browser is closed exactly once on the way
out.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from playwright.async_api import Browser, BrowserContext, Page

# A container's default /dev/shm is 64MB and Chromium commonly runs as a
# non-root user inside these images; without both flags the browser dies on
# startup rather than failing a navigation, which surfaces as a bare
# TargetClosedError instead of a meaningful provider-specific error.
DEFAULT_LAUNCH_ARGS: tuple[str, ...] = ("--no-sandbox", "--disable-dev-shm-usage")


@dataclass(frozen=True)
class BrowserSession:
    """The live objects a caller needs from one launched session."""

    browser: Browser
    context: BrowserContext
    page: Page


@asynccontextmanager
async def launch_chromium_session(
    *,
    headless: bool = True,
    launch_args: Sequence[str] = DEFAULT_LAUNCH_ARGS,
    viewport: dict[str, int] | None = None,
    storage_state: str | Path | None = None,
    user_agent: str | None = None,
) -> AsyncIterator[BrowserSession]:
    """Launch Chromium, yield a ready page, and always close the browser.

    Any exception raised inside the ``async with`` block (including a
    timeout waiting on a harvested value) propagates to the caller after the
    browser is closed. ``playwright`` is imported lazily so importing this
    module never requires the package to be installed.
    """

    from playwright.async_api import async_playwright

    context_kwargs: dict[str, Any] = {}
    if viewport is not None:
        context_kwargs["viewport"] = viewport
    if storage_state is not None:
        context_kwargs["storage_state"] = str(storage_state)
    if user_agent is not None:
        context_kwargs["user_agent"] = user_agent

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=headless, args=list(launch_args))
        try:
            context = await browser.new_context(**context_kwargs)
            try:
                page = await context.new_page()
                yield BrowserSession(browser=browser, context=context, page=page)
            finally:
                await context.close()
        finally:
            await browser.close()
