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

from nfl_oracle.ingest.realsports import _ensure_private_directory


async def capture() -> Path:
    target = Path(
        os.environ.get("NFL_ORACLE_SCRAPER_DIR", "scraper")
    ).expanduser().resolve() / "storage_state.json"
    _ensure_private_directory(target.parent)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://realsports.io/", wait_until="domcontentloaded")
        print("A browser window is open. Sign in there if needed.")
        print("After the Real Sports page is visibly signed in, return here and press Enter.")
        await asyncio.to_thread(input)
        await context.storage_state(path=str(target))
        target.chmod(0o600)
        await browser.close()
    print(f"Saved private Real Sports session to {target}")
    return target


if __name__ == "__main__":
    asyncio.run(capture())
