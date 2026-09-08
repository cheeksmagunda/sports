"""Ad-hoc headless Playwright sniff for the active NFL playerratingcontest id.

Adapts wnba_oracle.ingest.realsports.discover_wnba_contest_id for nfl.
Read-only, not part of any application.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "wnba-oracle" / "src"))

from wnba_oracle.ingest.realsports import (  # noqa: E402
    BASE,
    STORAGE_STATE_PATH,
    DEFAULT_USER_AGENT,
    StorageStateMissing,
    _http_headers,
    headers_or_capture,
)

OUT_DIR = REPO_ROOT / "drive" / "nfl_fixtures"


async def discover_nfl_contest_id() -> int | None:
    if not STORAGE_STATE_PATH.exists():
        raise StorageStateMissing(f"{STORAGE_STATE_PATH} not found.")
    from playwright.async_api import async_playwright

    seen_ids: list[int] = []
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 599, "height": 868},
            storage_state=str(STORAGE_STATE_PATH),
            user_agent=DEFAULT_USER_AGENT,
        )

        def on_req(req):
            url = req.url
            if "/games/playerratingcontest/" not in url:
                return
            try:
                tail = url.split("/games/playerratingcontest/")[1]
                cid = int(tail.split("?")[0].split("/")[0])
                seen_ids.append(cid)
            except (ValueError, IndexError):
                pass

        page = await ctx.new_page()
        page.on("request", on_req)
        try:
            await page.goto("https://realsports.io/", wait_until="domcontentloaded", timeout=15000)
            await page.evaluate("localStorage.setItem('selectedSport', 'nfl');")
            await page.goto("https://realsports.io/", wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(4000)
            try:
                await page.locator("text=/NFL/i").first.click(timeout=3000)
                await page.wait_for_timeout(3000)
            except Exception:
                pass
        except Exception as exc:
            print(f"[nav warn] {exc}", file=sys.stderr)
        await browser.close()

    print(f"seen contest ids: {sorted(set(seen_ids))}")
    return sorted(set(seen_ids), reverse=True)[0] if seen_ids else None


async def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cid = await discover_nfl_contest_id()
    if cid is None:
        print("no contest id observed")
        return 1
    print(f"candidate contest id: {cid}")

    headers = await headers_or_capture("nfl-probe-02", "nfl-probe-02")
    h = _http_headers(headers)
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=10.0)) as client:
        for suffix, params in [
            ("", {"contestType": "sport", "source": "home"}),
            ("/draftinfo", {}),
            ("/stats", {}),
            ("/payoutinfo", {}),
        ]:
            url = f"{BASE}/games/playerratingcontest/{cid}{suffix}"
            try:
                r = await client.get(url, headers=h, params=params)
            except Exception as exc:
                print(f"[ERR] {url}: {exc}", file=sys.stderr)
                continue
            name = f"contest_{cid}{suffix.replace('/', '_') or '_meta'}.json"
            (OUT_DIR / name).write_text(r.text)
            print(f"GET {url} -> status={r.status_code} bytes={len(r.text)} -> {name}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
