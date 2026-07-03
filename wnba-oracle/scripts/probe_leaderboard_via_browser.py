"""Find the real Real Sports leaderboard endpoint by driving the SPA in
Playwright and capturing every realapp.com network request while clicking
through to the WNBA leaderboard view.

Strategy:
  1. Load realsports.io with storage_state.
  2. Set selectedSport=wnba in localStorage and reload.
  3. Look for and click links/buttons matching /leader|results|finished|may 25/i.
  4. Spend ~30s in the SPA, capturing all requests.
  5. Dump every URL hit, every response status, and the first chunk of body.

Output: /tmp/wnba-probes/browser_traffic.jsonl + summary.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

OUT_DIR = Path("/tmp/wnba-probes")
OUT_DIR.mkdir(parents=True, exist_ok=True)
TRAFFIC_LOG = OUT_DIR / "browser_traffic.jsonl"


async def amain():
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from playwright.async_api import async_playwright

    from wnba_oracle.ingest.realsports import (
        DEFAULT_USER_AGENT,
        STORAGE_STATE_PATH,
    )

    if not STORAGE_STATE_PATH.exists():
        print("ERROR: storage_state.json missing")
        return 1

    traffic = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            viewport={"width": 599, "height": 868},
            storage_state=str(STORAGE_STATE_PATH),
            user_agent=DEFAULT_USER_AGENT,
        )

        async def on_response(response):
            url = response.url
            if "realapp.com" not in url:
                return
            try:
                body = (await response.text())[:2000]
            except Exception:
                body = ""
            traffic.append({
                "url": url,
                "method": response.request.method,
                "status": response.status,
                "body": body,
            })

        ctx.on("response", lambda r: asyncio.create_task(on_response(r)))

        page = await ctx.new_page()
        print("Loading realsports.io with sport=wnba ...", flush=True)
        await page.goto("https://realsports.io/", wait_until="domcontentloaded", timeout=20000)
        await page.evaluate("localStorage.setItem('selectedSport', 'wnba');")
        await page.goto("https://realsports.io/", wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(4000)

        # Try clicking the WNBA tab if visible
        for label in ["WNBA", "wnba"]:
            try:
                await page.locator(f"text=/{label}/i").first.click(timeout=3000)
                await page.wait_for_timeout(2500)
                break
            except Exception:
                continue

        # Take a screenshot for reference
        await page.screenshot(path=str(OUT_DIR / "after_wnba_click.png"))

        # Look for any element matching leaderboard / standings / results
        body_text = await page.evaluate("() => document.body.innerText")
        (OUT_DIR / "body_after_wnba_click.txt").write_text(body_text or "")
        print(f"Body text after WNBA click ({len(body_text or '')} chars). Snippet:", flush=True)
        print((body_text or "")[:600], flush=True)

        # Try clicking on labels that smell like leaderboard
        for pattern in [
            "Leaderboard", "Results", "May 25", "Finalized",
            "View results", "Past", "Standings", "Yesterday",
        ]:
            try:
                el = page.locator(f"text=/{pattern}/i").first
                if await el.count() > 0:
                    print(f"  Clicking '{pattern}' ...", flush=True)
                    await el.click(timeout=3000)
                    await page.wait_for_timeout(3500)
                    await page.screenshot(path=str(OUT_DIR / f"after_{pattern.lower().replace(' ', '_')}.png"))
            except Exception:
                continue

        # Try navigating directly to a finalized contest URL
        for cid in [1831, 1829]:
            try:
                print(f"  Navigating to contest {cid} ...", flush=True)
                await page.goto(
                    f"https://realsports.io/draft/{cid}",
                    wait_until="domcontentloaded",
                    timeout=15000,
                )
                await page.wait_for_timeout(3500)
            except Exception:
                pass

        # Also try a /post/{postId} URL pattern (postId 845792 from contest meta)
        try:
            await page.goto(
                "https://realsports.io/post/845792",
                wait_until="domcontentloaded",
                timeout=15000,
            )
            await page.wait_for_timeout(3500)
        except Exception:
            pass

        await browser.close()

    # Dump traffic
    with TRAFFIC_LOG.open("w") as f:
        for t in traffic:
            f.write(json.dumps(t) + "\n")

    # Summary: unique URL patterns, status codes
    seen = {}
    for t in traffic:
        path = t["url"].replace("https://web.realapp.com", "").split("?")[0]
        seen.setdefault(path, []).append(t["status"])
    print("\n=== Unique paths ===", flush=True)
    for p in sorted(seen.keys()):
        statuses = list(set(seen[p]))
        print(f"  {p}  statuses={statuses}  hits={len(seen[p])}", flush=True)

    # Highlight any that look leaderboard-y
    print("\n=== Interesting (containing 'leader/entry/rank/standing/result/feed') ===", flush=True)
    keywords = ("leader", "entry", "entries", "rank", "standing", "result", "feed", "post")
    for t in traffic:
        for kw in keywords:
            if kw in t["url"].lower():
                print(f"  {t['status']}  {t['method']}  {t['url']}", flush=True)
                break

    print(f"\nFull traffic: {TRAFFIC_LOG}")


if __name__ == "__main__":
    asyncio.run(amain())
