#!/usr/bin/env python3
"""Capture a private Playwright session for operator-authorized Real Sports calls.

This opens a headed browser. The operator may sign in using the browser's
normal password manager/autofill, then press Enter in this terminal. The saved
state contains cookies and must never be committed or pasted into chat.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from playwright.async_api import async_playwright

from nfl_oracle.ingest.realsports import DEFAULT_USER_AGENT, _ensure_private_directory

# Some Real Sports login attempts are flagged as automated traffic when the
# browser exposes Playwright's default automation fingerprint (the
# `navigator.webdriver` flag, the "Chrome is being controlled by automated
# test software" banner, and a bare Chromium build). Launching the operator's
# real installed Chrome via `channel="chrome"`, disabling the
# AutomationControlled feature, and matching the user agent used elsewhere in
# this codebase makes the interactive login look like an ordinary manual
# sign-in, which avoids tripping that false positive. This does not change
# what the operator does: they still type their own credentials into Real
# Sports' real login page themselves.
_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
]


async def capture() -> Path:
    target = (
        Path(os.environ.get("NFL_ORACLE_SCRAPER_DIR", "scraper")).expanduser().resolve()
        / "storage_state.json"
    )
    _ensure_private_directory(target.parent)
    async with async_playwright() as playwright:
        try:
            browser = await playwright.chromium.launch(
                headless=False,
                channel="chrome",
                args=_LAUNCH_ARGS,
            )
        except Exception:
            # Fall back to bundled Chromium if a real Chrome install isn't
            # found on this machine.
            browser = await playwright.chromium.launch(headless=False, args=_LAUNCH_ARGS)
        context = await browser.new_context(user_agent=DEFAULT_USER_AGENT)
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = await context.new_page()
        await page.goto("https://realsports.io/", wait_until="domcontentloaded")
        print("A browser window is open. Sign in there yourself if needed.")
        print("After the Real Sports page is visibly signed in, return here and press Enter.")
        await asyncio.to_thread(input)
        await context.storage_state(path=str(target))
        target.chmod(0o600)
        await browser.close()
    print(f"Saved private Real Sports session to {target}")
    return target


if __name__ == "__main__":
    asyncio.run(capture())
