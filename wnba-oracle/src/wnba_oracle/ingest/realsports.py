"""Real Sports (web.realapp.com) WNBA scraper.

Adapted from the MLB Oracle precedent. The Real Sports API is sport-
parameterized: every endpoint that takes `/sport/{sport}` accepts `wnba`.

Two-stage auth, identical to MLB:

1. **Login (rare):** operator runs `oracle-realsports-login` once. Playwright
   logs in with REAL_SPORTS_USERNAME / REAL_SPORTS_PASSWORD, saves
   scraper/storage_state.json with the JWT in localStorage. The JWT is
   long-lived; this only re-runs on rotation or 401-burn.
2. **Capture (per slate):** Playwright reloads realsports.io with the stored
   state; the SPA emits authenticated requests immediately. We harvest
   `real-request-token` + `real-auth-info` from those headers and cache
   them in scraper/request_token_cache.json (30-min TTL).
3. **Use:** `/players/sport/wnba/search?day=DATE&query=Q&searchType=ratingLineup`
   returns the slate's player pool with `multiplierBonus` (card_boost).

Hard Rule 7 (carried from MLB): if any step fails, raise. Never synthesize
`card_boost=0`. The picker is silent when the source can't be trusted.
"""

from __future__ import annotations

import asyncio
import json
import time
import unicodedata as _ud
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from oracle_core.http import (
    HttpxAsyncTransport,
    RetryPolicy,
    async_request_with_retry,
)

from wnba_oracle.common.logging import get_logger
from wnba_oracle.scheduler.antibot import (
    asleep_truncated_gaussian,
)

SCRAPER_DIR = Path(__file__).resolve().parents[3] / "scraper"
SCRAPER_DIR.mkdir(exist_ok=True)
STORAGE_STATE_PATH = SCRAPER_DIR / "storage_state.json"
TOKEN_CACHE_PATH = SCRAPER_DIR / "request_token_cache.json"

TOKEN_TTL_SECONDS = 1800  # 30 min upper bound
BASE = "https://web.realapp.com"
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
SPORT = "wnba"

log = get_logger("oracle.ingest.realsports")

# WNBA position taxonomy. The platform may emit one of these or a hyphenated
# combination (e.g. "G-F"). Pool parser accepts any nonempty string and lets
# the cohort assigner reduce it to G/F/C.
WNBA_POSITIONS = {"G", "F", "C", "G-F", "F-G", "F-C", "C-F"}


@dataclass(frozen=True)
class RequestHeaders:
    real_request_token: str
    real_version: str
    real_device_type: str
    real_device_uuid: str
    real_device_id: str
    real_device_name: str
    real_auth_info: str | None
    user_agent: str
    captured_at: float


@dataclass(frozen=True)
class PlatformPlayer:
    """One row from the rating-lineup pool endpoint."""

    platform_id: str
    first_name: str
    last_name: str
    display_name: str
    position: str
    team: str
    multiplier_bonus: float  # card_boost
    primary_ranking: int | None
    injury_status: str
    # Tip time of the game this player is rostered in ("2026-08-19T23:30:00.000Z",
    # UTC). Empty when the slate payload carried no dateTime for their game.
    game_start_utc: str = ""


class PlatformAuthRequired(RuntimeError):
    """Raised on 401; the orchestrator refreshes headers and retries once."""


class StorageStateMissing(RuntimeError):
    """Storage state not seeded. Operator must run oracle-realsports-login first."""


class StorageStateStale(RuntimeError):
    """Storage state present but session has expired."""


def load_cached_headers() -> RequestHeaders | None:
    if not TOKEN_CACHE_PATH.exists():
        return None
    raw = json.loads(TOKEN_CACHE_PATH.read_text())
    if time.time() - raw.get("captured_at", 0) > TOKEN_TTL_SECONDS:
        return None
    if "real-request-token" not in raw or "real-auth-info" not in raw:
        return None
    return RequestHeaders(
        real_request_token=raw["real-request-token"],
        real_version=raw.get("real-version", "31"),
        real_device_type=raw.get("real-device-type", "desktop_web"),
        real_device_uuid=raw["real-device-uuid"],
        real_device_id=raw.get("real-device-id", raw["real-device-uuid"]),
        real_device_name=raw.get("real-device-name", "wnba-oracle-prod-01"),
        real_auth_info=raw["real-auth-info"],
        user_agent=raw.get("user-agent", DEFAULT_USER_AGENT),
        captured_at=raw["captured_at"],
    )


def _save_cached_headers(h: dict[str, Any]) -> None:
    h["captured_at"] = time.time()
    TOKEN_CACHE_PATH.write_text(json.dumps(h, indent=2))


async def capture_live_headers(
    device_uuid: str,
    device_name: str,
    *,
    headed: bool = False,
) -> RequestHeaders:
    """Reload realsports.io with the stored state, harvest authenticated
    request headers. Raises StorageStateMissing if storage_state.json is
    absent; StorageStateStale if the page loads but no authenticated
    request is observed within 20s.
    """
    if not STORAGE_STATE_PATH.exists():
        raise StorageStateMissing(f"{STORAGE_STATE_PATH} not found. Run `oracle-realsports-login`.")

    from playwright.async_api import async_playwright

    captured: dict[str, str] = {}
    done = asyncio.Event()

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not headed)
        ctx = await browser.new_context(
            viewport={"width": 599, "height": 868},
            storage_state=str(STORAGE_STATE_PATH),
            user_agent=DEFAULT_USER_AGENT,
        )

        async def on_request(req):
            if "realapp.com" not in req.url:
                return
            h = req.headers
            if "real-request-token" in h and "real-auth-info" in h and not captured:
                for k, v in h.items():
                    captured[k.lower()] = v
                captured["captured_at_url"] = req.url
                done.set()

        ctx.on("request", on_request)
        page = await ctx.new_page()
        try:
            await page.goto("https://realsports.io/", wait_until="domcontentloaded", timeout=25000)
        except Exception:
            pass

        try:
            await asyncio.wait_for(done.wait(), timeout=20.0)
        except TimeoutError as exc:
            await browser.close()
            raise StorageStateStale(
                "Did not capture authenticated headers within 20s. "
                "storage_state.json's session has expired. Re-run "
                "`oracle-realsports-login` locally and re-seed "
                "REALSPORTS_STORAGE_STATE_B64GZ on Railway."
            ) from exc

        # Persist any sliding-window cookies updated during this reload.
        await ctx.storage_state(path=str(STORAGE_STATE_PATH))
        await browser.close()

    captured["real-device-uuid"] = device_uuid
    captured.setdefault("real-device-id", device_uuid)
    captured["real-device-name"] = device_name
    captured.setdefault("real-device-type", "desktop_web")
    captured.setdefault("real-version", "31")

    _save_cached_headers(captured)
    h = load_cached_headers()
    if h is None:
        raise RuntimeError("Captured headers but failed to round-trip through cache")
    return h


async def headers_or_capture(
    device_uuid: str,
    device_name: str,
) -> RequestHeaders:
    """Return cached headers if still valid; otherwise launch Playwright."""
    cached = load_cached_headers()
    if cached is not None:
        return cached
    return await capture_live_headers(device_uuid, device_name)


def _http_headers(h: RequestHeaders) -> dict[str, str]:
    out = {
        "real-request-token": h.real_request_token,
        "real-version": h.real_version,
        "real-device-type": h.real_device_type,
        "real-device-uuid": h.real_device_uuid,
        "real-device-id": h.real_device_id,
        "real-device-name": h.real_device_name,
        "user-agent": h.user_agent,
        "accept": "application/json",
        "content-type": "application/json",
        "referer": "https://realsports.io/",
        "origin": "https://realsports.io",
    }
    if h.real_auth_info:
        out["real-auth-info"] = h.real_auth_info
    return out


async def _real_sports_get_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: dict[str, str],
    params: dict[str, Any] | None = None,
    refresh_headers: Callable[[], Awaitable[RequestHeaders]] | None = None,
    max_attempts: int = 5,
    timeout_s: float = 15.0,
) -> httpx.Response:
    """Bounded shared retry transport with one optional auth refresh.

    - 200: return.
    - 401 + refresh_headers + not yet refreshed: refresh in place, retry once.
      Subsequent 401 raises PlatformAuthRequired.
    - 429/503: honor Retry-After within the shared 60-second delay cap.
    - Transport error: backoff + retry.
    - Other: raise_for_status().
    """
    refreshed = False
    policy = RetryPolicy(
        max_attempts=max_attempts,
        base_delay=1.0,
        max_delay=60.0,
        retry_statuses=frozenset({429, 503}),
    )
    transport = HttpxAsyncTransport(client)
    for _auth_attempt in range(2):
        r = await async_request_with_retry(
            transport,
            "GET",
            url,
            policy=policy,
            params=params,
            headers=headers,
            timeout=timeout_s,
        )
        if r.status_code == 200:
            return r
        if r.status_code == 401:
            if refresh_headers is not None and not refreshed:
                new_headers = await refresh_headers()
                headers.clear()
                headers.update(_http_headers(new_headers))
                refreshed = True
                continue
            raise PlatformAuthRequired(f"401 on {url}")
        r.raise_for_status()
    raise PlatformAuthRequired(f"401 on {url}")


async def _search_with_query(
    slate_date: str,
    query: str,
    headers: dict[str, str],
    client: httpx.AsyncClient,
) -> tuple[int, list[dict[str, Any]]]:
    """One /players/sport/wnba/search call. Returns (200, players[]).

    WNBA-specific: the search endpoint does NOT accept a `day` parameter
    (unlike MLB). Probe 2026-05-26 confirmed that passing `day=YYYY-MM-DD`
    returns an empty player list; omitting it returns the full currently-
    rated set. `slate_date` is retained in the signature for caller
    parity but unused on the wire.
    """
    _ = slate_date  # acknowledge unused param
    r = await _real_sports_get_with_retry(
        client,
        f"{BASE}/players/sport/{SPORT}/search",
        headers=headers,
        params={"query": query, "searchType": "ratingLineup"},
    )
    return 200, (r.json() or {}).get("players", []) or []


async def fetch_slate_game_times(
    headers: RequestHeaders,
    client: httpx.AsyncClient,
    *,
    refresh_headers: Callable[[], Awaitable[RequestHeaders]] | None = None,
) -> list[str]:
    """Per-game tip times for the current slate from /home/wnba/next.

    Returns the raw `dateTime` ISO strings of `latestDayContent.games`
    (UTC, e.g. "2026-05-27T23:00:00.000Z"). The platform exposes no
    contest lock timestamp (only a live `isLocked` boolean on the contest
    payload), so the earliest game time is the contest-lock proxy the D83
    late-refreeze gate uses. Empty list on a payload without games.
    """
    h = _http_headers(headers)
    r = await _real_sports_get_with_retry(
        client,
        f"{BASE}/home/{SPORT}/next",
        headers=h,
        params={"cohort": 0},
        refresh_headers=refresh_headers,
    )
    games = (r.json().get("latestDayContent") or {}).get("games") or []
    out: list[str] = []
    for g in games:
        t = str(g.get("dateTime") or "").strip()
        if t:
            out.append(t)
    return out


async def _fetch_game_rosters(
    slate_date: str,
    h: dict[str, str],
    client: httpx.AsyncClient,
    *,
    refresh_headers: Callable[[], Awaitable[RequestHeaders]] | None = None,
) -> dict[str, dict[str, Any]]:
    """Union of tonight's per-game rosters, keyed by platform player id.

    Each row carries `gameStartUtc`, the `dateTime` of the game it was
    rostered in. That is the only place the platform ties a player to a
    tip time: the pool endpoint is slate-wide and the /home payload lists
    games without rosters. Downstream, features_json["game_start_utc"]
    lets job2 scope the pool to games that have not started.
    """
    home_r = await _real_sports_get_with_retry(
        client,
        f"{BASE}/home/{SPORT}/next",
        headers=h,
        params={"cohort": 0},
        refresh_headers=refresh_headers,
    )
    games = (home_r.json().get("latestDayContent") or {}).get("games") or []
    game_ids: list[int] = []
    start_by_game: dict[int, str] = {}
    for g in games:
        gid = g.get("id")
        if gid is None:
            continue
        game_ids.append(int(gid))
        start_by_game[int(gid)] = str(g.get("dateTime") or "").strip()
    if not game_ids:
        raise RuntimeError(f"no games found in /home/{SPORT}/next for slate_date={slate_date}")

    sem = asyncio.Semaphore(4)

    async def _one_game(gid: int) -> tuple[int, list[dict[str, Any]]]:
        async with sem:
            r = await _real_sports_get_with_retry(
                client,
                f"{BASE}/games/{gid}/sport/{SPORT}/players",
                headers=h,
                refresh_headers=refresh_headers,
            )
            return gid, (r.json().get("players", []) or [])

    async with asyncio.TaskGroup() as tg:
        tasks = [tg.create_task(_one_game(gid)) for gid in game_ids]
    union: dict[str, dict[str, Any]] = {}
    for t in tasks:
        gid, players = t.result()
        for p in players:
            pid = str(p.get("id", ""))
            if not pid or pid in union:
                continue
            row = dict(p)
            row["gameStartUtc"] = start_by_game.get(gid, "")
            union[pid] = row
    return union


async def fetch_game_start_by_player(
    slate_date: str,
    headers: RequestHeaders,
    client: httpx.AsyncClient,
    *,
    refresh_headers: Callable[[], Awaitable[RequestHeaders]] | None = None,
) -> dict[str, str]:
    """Platform player id -> their game's tip time, for tonight's slate.

    Cheap next to fetch_pool_for_date: one /home call plus one roster call
    per game, no a..z card_boost sweep. Used to backfill game_start_utc
    onto enrichment that a pre-tip-time job1 run persisted without it.
    """
    h = _http_headers(headers)
    union = await _fetch_game_rosters(slate_date, h, client, refresh_headers=refresh_headers)
    return {pid: str(p.get("gameStartUtc") or "") for pid, p in union.items()}


async def fetch_pool_for_date(
    slate_date: str,
    headers: RequestHeaders,
    client: httpx.AsyncClient,
    *,
    refresh_headers: Callable[[], Awaitable[RequestHeaders]] | None = None,
) -> list[PlatformPlayer]:
    """Fetch the slate's full eligibility set + overlay card_boost.

    Two API surfaces:

    1. Per-game roster union via /home/wnba/next?cohort=0 + /games/{gid}/sport/wnba/players.
       For ~6 WNBA games per slate that yields ~80-90 unique player ids.
    2. Prefix-iterated card_boost overlay across a..z on /players/sport/wnba/search.

    Pool membership is the intersection. A player Real Sports does not
    surface across any a..z prefix is not draftable today.
    """
    h = _http_headers(headers)

    union = await _fetch_game_rosters(slate_date, h, client, refresh_headers=refresh_headers)

    # Prefix-iterated card_boost overlay
    rated_by_id: dict[str, float] = {}
    letters = "abcdefghijklmnopqrstuvwxyz"
    refreshed_during_overlay = False
    for i, letter in enumerate(letters):
        if i > 0:
            await asleep_truncated_gaussian()
        try:
            _status, players = await _search_with_query(slate_date, letter, h, client)
        except PlatformAuthRequired:
            if refresh_headers is not None and not refreshed_during_overlay:
                h = _http_headers(await refresh_headers())
                refreshed_during_overlay = True
                _status, players = await _search_with_query(slate_date, letter, h, client)
            else:
                raise
        for rp in players:
            rid = str(rp.get("id", ""))
            mb = rp.get("multiplierBonus")
            if not rid or mb is None:
                continue
            try:
                rated_by_id[rid] = float(mb)
            except (TypeError, ValueError):
                continue

    # Targeted-search fallback. The single-letter prefix sweep caps results
    # per query and misses players deep in the alphabetical ordering. Live
    # audits showed winning-lineup picks missing from the optimizer pool, all
    # draftable players the prefix
    # sweep silently dropped (A. Stevens, S. Sabally, J. Jocyte, M. Akoa
    # Makani, C. McMahon, K. Bell, ...). For each player in the per-game
    # union not yet in rated_by_id, we query their last name (first 3
    # chars, lowercased + ASCII-folded) as the search query and merge any
    # multiplierBonus that comes back. Capped at MAX_FALLBACK_QUERIES per
    # slate to bound latency.
    MAX_FALLBACK_QUERIES = 50
    fallback_queried = 0
    fallback_added = 0
    fallback_still_missing: list[str] = []
    unmatched = [(pid, p) for pid, p in union.items() if pid not in rated_by_id]
    queried_prefixes: set[str] = set(letters)  # don't re-query single letters
    for pid, p in unmatched:
        if fallback_queried >= MAX_FALLBACK_QUERIES:
            fallback_still_missing.append(pid)
            continue
        last = str(p.get("lastName") or "").strip()
        first = str(p.get("firstName") or "").strip()
        seed = last or first
        if not seed:
            fallback_still_missing.append(pid)
            continue
        # ASCII-fold to mirror the prefix sweep's behaviour on accented
        # names (Jocyte vs Jocyteė). 3 chars covers the common case
        # without over-narrowing.
        folded = _ud.normalize("NFKD", seed).encode("ascii", "ignore").decode().lower()
        query = folded[:3].strip()
        if not query or query in queried_prefixes:
            if pid not in rated_by_id:
                fallback_still_missing.append(pid)
            continue
        queried_prefixes.add(query)
        await asleep_truncated_gaussian()
        try:
            _status, players = await _search_with_query(slate_date, query, h, client)
        except PlatformAuthRequired:
            if refresh_headers is not None and not refreshed_during_overlay:
                h = _http_headers(await refresh_headers())
                refreshed_during_overlay = True
                _status, players = await _search_with_query(slate_date, query, h, client)
            else:
                raise
        fallback_queried += 1
        added_this_query = 0
        for rp in players:
            rid = str(rp.get("id", ""))
            mb = rp.get("multiplierBonus")
            if not rid or mb is None or rid in rated_by_id:
                continue
            try:
                rated_by_id[rid] = float(mb)
                added_this_query += 1
            except (TypeError, ValueError):
                continue
        if pid in rated_by_id:
            fallback_added += 1
        else:
            fallback_still_missing.append(pid)
    log.info(
        "fetch_pool_fallback",
        n_unmatched_after_az=len(unmatched),
        n_queries=fallback_queried,
        n_added=fallback_added,
        n_still_missing=len(fallback_still_missing),
        cap=MAX_FALLBACK_QUERIES,
    )

    overlaid: list[dict[str, Any]] = []
    for pid, p in union.items():
        if pid not in rated_by_id:
            continue
        p = dict(p)
        p["multiplierBonus"] = rated_by_id[pid]
        overlaid.append(p)
    return _parse_pool({"players": overlaid})


def _parse_pool(body: dict[str, Any]) -> list[PlatformPlayer]:
    out: list[PlatformPlayer] = []
    players = body.get("players", []) or body.get("data", []) or []
    for p in players:
        boost = p.get("multiplierBonus")
        if boost is None:
            boost = p.get("multiplier_bonus")
        if boost is None:
            raise RuntimeError(
                f"Pool row missing multiplierBonus (id={p.get('id')}); "
                "platform schema may have changed - halting fetch."
            )
        boost_f = float(boost)
        if not (0.0 <= boost_f <= 3.0):
            raise RuntimeError(
                f"multiplierBonus out of range [0,3]: {boost_f} for "
                f"id={p.get('id')}; halting fetch."
            )
        team_obj = p.get("team")
        if isinstance(team_obj, dict):
            team = (team_obj.get("key") or team_obj.get("abbreviation") or "").upper()
        else:
            team = (team_obj or "").upper()
        out.append(
            PlatformPlayer(
                platform_id=str(p.get("id", "")),
                first_name=p.get("firstName") or "",
                last_name=p.get("lastName") or "",
                display_name=p.get("displayName")
                or (f"{p.get('firstName') or ''} {p.get('lastName') or ''}".strip()),
                position=p.get("position") or "",
                team=team,
                multiplier_bonus=boost_f,
                primary_ranking=p.get("primaryRanking"),
                injury_status=p.get("injuryStatus") or "",
                game_start_utc=str(p.get("gameStartUtc") or ""),
            )
        )
    return out


async def fetch_contest_meta(
    contest_id: int,
    headers: RequestHeaders,
    client: httpx.AsyncClient,
) -> dict[str, Any]:
    """GET /games/playerratingcontest/{id}?contestType=sport&source=home

    Returns the daily-draft contest metadata. Pregame, `info.contest`
    has `id`, `day`, `sport`, `isFinalized`, `additionalInfo.lineupSize`.
    Post-tip, `info.rankDisplayInfos` populates with the payout/leaderboard
    structure the lineup optimizer consumes.

    WNBA-specific note: unlike MLB, there is no `/home/{sport}/day/next`
    endpoint to enumerate the current contest id; that endpoint returns
    500 for WNBA. Use `discover_wnba_contest_id` (Playwright-based) to
    find the active WNBA contest id, then call this with that id.
    """
    h = _http_headers(headers)
    r = await _real_sports_get_with_retry(
        client,
        f"{BASE}/games/playerratingcontest/{contest_id}",
        headers=h,
        params={"contestType": "sport", "source": "home"},
    )
    return r.json() or {}


async def discover_wnba_contest_id() -> int | None:
    """Headless-browse realsports.io/?sport=wnba and capture the contest id
    from the /games/playerratingcontest/{id} URL the SPA hits.

    Returns the int contest id, or None if no WNBA contest URL is observed.
    Cheap to call (one Playwright session, ~5s); Job 1 calls it once per
    fire to seed the day's contest id into Redis.
    """
    if not STORAGE_STATE_PATH.exists():
        raise StorageStateMissing(f"{STORAGE_STATE_PATH} not found; cannot discover contest id.")
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

    # Need to distinguish WNBA contest from MLB. The discovered id list will
    # include both if the user has both sports active. Caller validates with
    # fetch_contest_meta and confirms info.contest.sport == "wnba".
    if not seen_ids:
        return None
    # Return the maximum (most recent) id; both MLB and WNBA increment together.
    # Caller validates sport.
    return max(seen_ids)
