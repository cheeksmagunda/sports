"""Real Sports (web.realapp.com) WNBA scraper.

Adapted from the MLB Oracle precedent. The Real Sports API is sport-
parameterized: every endpoint that takes `/sport/{sport}` accepts `wnba`.

Authentication uses an operator-seeded browser session:

1. **Operator recovery (rare):** the operator signs in with an ordinary
   interactive browser and iCloud Autofill where applicable, then exports the
   derived session to `scraper/storage_state.json`. Scripted password login is
   rejected by the provider and is not a recovery path.
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
import os
import time
import unicodedata as _ud
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
from oracle_core.artifacts import atomic_write_json
from oracle_core.http import (
    HttpxAsyncTransport,
    RetryPolicy,
    async_request_with_retry,
)

from wnba_oracle.common.logging import get_logger
from wnba_oracle.scheduler.antibot import (
    asleep_truncated_gaussian,
)


def _ensure_private_directory(path: Path) -> None:
    if path.is_symlink():
        raise RuntimeError("Real Sports secret directory must not be a symbolic link")
    if path.exists() and not path.is_dir():
        raise RuntimeError("Real Sports secret directory is not a directory")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    path.chmod(0o700)


def _ensure_private_file(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Real Sports secret path must be a regular file")
    path.chmod(0o600)


def _write_private_json(path: Path, payload: Any) -> None:
    _ensure_private_directory(path.parent)
    atomic_write_json(path, payload, mode=0o600)
    path.chmod(0o600)


SCRAPER_DIR = Path(__file__).resolve().parents[3] / "scraper"
_ensure_private_directory(SCRAPER_DIR)
STORAGE_STATE_PATH = SCRAPER_DIR / "storage_state.json"
TOKEN_CACHE_PATH = SCRAPER_DIR / "request_token_cache.json"
for _secret_path in (STORAGE_STATE_PATH, TOKEN_CACHE_PATH):
    if _secret_path.exists() or _secret_path.is_symlink():
        _ensure_private_file(_secret_path)

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
    # Stable provider game id from /home plus the per-game roster endpoint.
    # Empty for legacy payloads that did not retain roster identity.
    game_id: str = ""


@dataclass(frozen=True, slots=True)
class PlayerGameContext:
    """Authoritative provider identity and tip time for one player's game."""

    game_id: str
    game_start_utc: str


class PlatformAuthRequired(RuntimeError):
    """Raised on 401; the orchestrator refreshes headers and retries once."""


class StorageStateMissing(RuntimeError):
    """Storage state is absent and requires interactive operator recovery."""


class StorageStateStale(RuntimeError):
    """Storage state present but session has expired."""


_POOL_PREFIXES = "abcdefghijklmnopqrstuvwxyz"
_MAX_FALLBACK_QUERIES = 50


@dataclass
class _PoolOverlayState:
    headers: dict[str, str]
    rated_by_id: dict[str, float]
    refreshed: bool = False


def load_cached_headers() -> RequestHeaders | None:
    if not TOKEN_CACHE_PATH.exists():
        return None
    _ensure_private_file(TOKEN_CACHE_PATH)
    raw = json.loads(TOKEN_CACHE_PATH.read_text(encoding="utf-8"))
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
    payload = dict(h)
    payload["captured_at"] = time.time()
    _write_private_json(TOKEN_CACHE_PATH, payload)


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
        raise StorageStateMissing(
            "Real Sports storage state is missing. Recover it with an ordinary "
            "interactive browser, then re-seed the derived session."
        )
    _ensure_private_file(STORAGE_STATE_PATH)

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
                "storage_state.json's session has expired. Recover the session "
                "with an ordinary interactive browser and re-seed "
                "REALSPORTS_STORAGE_STATE_B64GZ on Railway."
            ) from exc

        # Persist any sliding-window cookies updated during this reload.
        refreshed_state = await ctx.storage_state()
        _write_private_json(STORAGE_STATE_PATH, refreshed_state)
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

    Each row carries `gameId` and `gameStartUtc` from the /home game whose
    roster supplied the player. The pool endpoint is slate-wide and does not
    retain that relationship. Downstream, the stable game id identifies
    correlation groups while the tip time scopes pools to games not started.
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
            if not pid:
                continue
            if pid in union:
                existing_game_id = str(union[pid].get("gameId") or "")
                if existing_game_id != str(gid):
                    raise RuntimeError(
                        "provider player appears in multiple game rosters; "
                        "refusing ambiguous game identity"
                    )
                continue
            row = dict(p)
            row["gameId"] = str(gid)
            row["gameStartUtc"] = start_by_game.get(gid, "")
            union[pid] = row
    return union


async def fetch_game_context_by_player(
    slate_date: str,
    headers: RequestHeaders,
    client: httpx.AsyncClient,
    *,
    refresh_headers: Callable[[], Awaitable[RequestHeaders]] | None = None,
) -> dict[str, PlayerGameContext]:
    """Platform player id -> authoritative game identity for tonight's slate.

    Cheap next to fetch_pool_for_date: one /home call plus one roster call
    per game, no a..z card_boost sweep. Used to atomically backfill game_id
    and game_start_utc onto enrichment that an earlier job1 persisted without
    provider game context.
    """
    h = _http_headers(headers)
    union = await _fetch_game_rosters(slate_date, h, client, refresh_headers=refresh_headers)
    return {
        pid: PlayerGameContext(
            game_id=str(player.get("gameId") or "").strip(),
            game_start_utc=str(player.get("gameStartUtc") or "").strip(),
        )
        for pid, player in union.items()
    }


async def fetch_game_start_by_player(
    slate_date: str,
    headers: RequestHeaders,
    client: httpx.AsyncClient,
    *,
    refresh_headers: Callable[[], Awaitable[RequestHeaders]] | None = None,
) -> dict[str, str]:
    """Compatibility wrapper returning only per-player tip times."""
    contexts = await fetch_game_context_by_player(
        slate_date,
        headers,
        client,
        refresh_headers=refresh_headers,
    )
    return {pid: context.game_start_utc for pid, context in contexts.items()}


async def _search_pool_ratings(
    slate_date: str,
    query: str,
    state: _PoolOverlayState,
    client: httpx.AsyncClient,
    refresh_headers: Callable[[], Awaitable[RequestHeaders]] | None,
) -> list[dict[str, Any]]:
    try:
        _status, players = await _search_with_query(slate_date, query, state.headers, client)
        return players
    except PlatformAuthRequired:
        if refresh_headers is None or state.refreshed:
            raise
        state.headers = _http_headers(await refresh_headers())
        state.refreshed = True
        _status, players = await _search_with_query(slate_date, query, state.headers, client)
        return players


def _merge_pool_ratings(
    players: list[dict[str, Any]],
    rated_by_id: dict[str, float],
    *,
    replace: bool,
) -> int:
    added = 0
    for player in players:
        player_id = str(player.get("id", ""))
        multiplier = player.get("multiplierBonus")
        if not player_id or multiplier is None or (not replace and player_id in rated_by_id):
            continue
        try:
            rated_by_id[player_id] = float(multiplier)
            added += 1
        except (TypeError, ValueError):
            continue
    return added


async def _collect_prefix_ratings(
    slate_date: str,
    state: _PoolOverlayState,
    client: httpx.AsyncClient,
    refresh_headers: Callable[[], Awaitable[RequestHeaders]] | None,
) -> None:
    for index, letter in enumerate(_POOL_PREFIXES):
        if index > 0:
            await asleep_truncated_gaussian()
        players = await _search_pool_ratings(slate_date, letter, state, client, refresh_headers)
        _merge_pool_ratings(players, state.rated_by_id, replace=True)


def _fallback_query(player: dict[str, Any]) -> str:
    last_name = str(player.get("lastName") or "").strip()
    first_name = str(player.get("firstName") or "").strip()
    seed = last_name or first_name
    if not seed:
        return ""
    folded = _ud.normalize("NFKD", seed).encode("ascii", "ignore").decode().lower()
    return folded[:3].strip()


async def _collect_fallback_ratings(
    slate_date: str,
    union: dict[str, dict[str, Any]],
    state: _PoolOverlayState,
    client: httpx.AsyncClient,
    refresh_headers: Callable[[], Awaitable[RequestHeaders]] | None,
) -> None:
    unmatched = [
        (player_id, player)
        for player_id, player in union.items()
        if player_id not in state.rated_by_id
    ]
    queried_prefixes = set(_POOL_PREFIXES)
    queried = 0
    added = 0
    still_missing: list[str] = []

    for player_id, player in unmatched:
        if queried >= _MAX_FALLBACK_QUERIES:
            still_missing.append(player_id)
            continue
        query = _fallback_query(player)
        if not query or query in queried_prefixes:
            if player_id not in state.rated_by_id:
                still_missing.append(player_id)
            continue
        queried_prefixes.add(query)
        await asleep_truncated_gaussian()
        players = await _search_pool_ratings(slate_date, query, state, client, refresh_headers)
        queried += 1
        _merge_pool_ratings(players, state.rated_by_id, replace=False)
        if player_id in state.rated_by_id:
            added += 1
        else:
            still_missing.append(player_id)

    log.info(
        "fetch_pool_fallback",
        n_unmatched_after_az=len(unmatched),
        n_queries=queried,
        n_added=added,
        n_still_missing=len(still_missing),
        cap=_MAX_FALLBACK_QUERIES,
    )


def _overlay_pool(
    union: dict[str, dict[str, Any]],
    rated_by_id: dict[str, float],
) -> list[PlatformPlayer]:
    overlaid: list[dict[str, Any]] = []
    for player_id, player in union.items():
        if player_id not in rated_by_id:
            continue
        row = dict(player)
        row["multiplierBonus"] = rated_by_id[player_id]
        overlaid.append(row)
    return _parse_pool({"players": overlaid})


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
    request_headers = _http_headers(headers)
    union = await _fetch_game_rosters(
        slate_date,
        request_headers,
        client,
        refresh_headers=refresh_headers,
    )
    state = _PoolOverlayState(headers=request_headers, rated_by_id={})
    await _collect_prefix_ratings(slate_date, state, client, refresh_headers)
    await _collect_fallback_ratings(slate_date, union, state, client, refresh_headers)
    return _overlay_pool(union, state.rated_by_id)


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
                game_id=str(p.get("gameId") or "").strip(),
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


def _validated_wnba_contest_id(
    seen_ids: list[int],
    headers: RequestHeaders,
    client: httpx.Client,
) -> int | None:
    """Return the newest observed contest that the stats endpoint confirms is WNBA."""
    from wnba_oracle.ingest.contest_stats import ContestUnavailable, fetch_contest_stats

    for contest_id in sorted(set(seen_ids), reverse=True):
        try:
            fetch_contest_stats(contest_id, headers, client)
        except ContestUnavailable:
            continue
        return contest_id
    return None


async def discover_wnba_contest_id(headers: RequestHeaders | None = None) -> int | None:
    """Headless-browse realsports.io/?sport=wnba and capture the contest id
    from the /games/playerratingcontest/{id} URL the SPA hits.

    Returns the newest int contest id that the stats endpoint confirms is WNBA,
    or None if no such contest is observed. The browse can surface contests from
    other sports, even after selecting WNBA in the SPA.
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

    if not seen_ids:
        return None
    if headers is None:
        headers = await headers_or_capture(
            os.environ.get("WNBA_DEVICE_UUID", "wnba-oracle-prod-01-device"),
            os.environ.get("WNBA_DEVICE_NAME", "wnba-oracle-prod-01"),
        )
    with httpx.Client(timeout=20.0) as client:
        return _validated_wnba_contest_id(seen_ids, headers, client)
