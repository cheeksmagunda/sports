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
# test software" banner, a bare Chromium build, and -- just as importantly --
# a brand-new, empty profile with no browsing history on every single run.
# Launching the operator's real installed Chrome via `channel="chrome"`,
# disabling the AutomationControlled feature, masking `navigator.webdriver`,
# matching the user agent already used elsewhere in this codebase, and
# reusing one persistent private profile directory across runs (instead of a
# disposable one each time) makes the interactive login look like an
# ordinary, returning manual sign-in. This does not change what the operator
# does: they still type their own credentials into Real Sports' real login
# page themselves, in a real window they can see.
_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
]


def _profile_dir() -> Path:
    override = os.environ.get("NFL_ORACLE_SCRAPER_DIR", "scraper")
    scraper_dir = Path(override).expanduser().resolve()
    profile = scraper_dir / "chrome_profile"
    _ensure_private_directory(scraper_dir)
    _ensure_private_directory(profile)
    return profile


async def capture() -> Path:
    scraper_dir = Path(os.environ.get("NFL_ORACLE_SCRAPER_DIR", "scraper")).expanduser().resolve()
    target = scraper_dir / "storage_state.json"
    _ensure_private_directory(target.parent)
    profile_dir = _profile_dir()

    async with async_playwright() as playwright:
        try:
            context = await playwright.chromium.launch_persistent_context(
                str(profile_dir),
                headless=False,
                channel="chrome",
                args=_LAUNCH_ARGS,
                user_agent=DEFAULT_USER_AGENT,
            )
        except Exception:
            # Fall back to bundled Chromium if a real Chrome install isn't
            # found on this machine.
            context = await playwright.chromium.launch_persistent_context(
                str(profile_dir),
                headless=False,
                args=_LAUNCH_ARGS,
                user_agent=DEFAULT_USER_AGENT,
            )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        )
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://realsports.io/", wait_until="domcontentloaded")
        print("A browser window is open. Sign in there yourself if needed.")
        print("After the Real Sports page is visibly signed in, return here and press Enter.")
        await asyncio.to_thread(input)
        await context.storage_state(path=str(target))
        target.chmod(0o600)
        await context.close()
    print(f"Saved private Real Sports session to {target}")
    print(f"Reused browser profile kept at {profile_dir} for future recaptures.")
    return target


if __name__ == "__main__":
    asyncio.run(capture())
