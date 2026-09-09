"""Read-only sweep of the Real Sports contest id space.

The ``playerratingcontest`` id space is a single global sequence shared by every
sport, allocated roughly one contest per sport per day. Finding the NFL history
therefore means walking the sequence, reading each contest's cheap meta route,
and descending into the four sub-routes only when ``sport == "nfl"``.

Absence is data. An id the provider refuses with 403/404 is recorded as absent
with its status code rather than silently skipped, because "no contest was ever
created" and "the contest expired out of the read window" are different facts
and only the archive can tell them apart later.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from nfl_oracle.contests.store import (
    NFL_SUB_ROUTES,
    ContestProvenance,
    ContestStore,
    RouteName,
    ScanCursor,
)
from nfl_oracle.ingest.realsports import BASE, RequestHeaders, http_headers

# The provider rejects /entries without this pair; with it, historical contests
# serve their saved top-20 leaderboard. Verified live on contest 870.
CONTEST_PARAMS: dict[str, Any] = {"contestType": "sport", "source": "home"}

# Statuses that mean "this id holds nothing for us", not "the request failed".
ABSENT_STATUSES = frozenset({400, 403, 404})
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})


class ContestScanError(RuntimeError):
    """Value-free scan failure suitable for a run record."""


@dataclass(frozen=True)
class ContestOutcome:
    contest_id: int
    kind: str  # "nfl" | "other_sport" | "absent" | "failed"
    sport: str | None = None
    day: str | None = None
    is_finalized: bool | None = None
    entrants: int | None = None
    http_status: int | None = None
    routes: tuple[str, ...] = ()
    detail: str | None = None


def contest_url(contest_id: int, route: RouteName) -> str:
    base = f"{BASE}/games/playerratingcontest/{contest_id}"
    return base if route == "meta" else f"{base}/{route}"


class ContestScanner:
    """Bounded, retrying, read-only reader for the contest read family."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        headers: RequestHeaders,
        store: ContestStore,
        *,
        refresh_headers: Callable[[], Awaitable[RequestHeaders]] | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        request_pause_s: float = 0.05,
        max_attempts: int = 4,
        timeout_s: float = 25.0,
    ) -> None:
        self.client = client
        self.headers = http_headers(headers)
        self.store = store
        self.refresh_headers = refresh_headers
        self.clock = clock
        self.request_pause_s = request_pause_s
        self.max_attempts = max_attempts
        self.timeout_s = timeout_s
        self.requests = 0
        self._refreshed = False

    async def _get(self, url: str) -> httpx.Response:
        delay = 1.0
        for attempt in range(self.max_attempts):
            self.requests += 1
            try:
                response = await self.client.get(
                    url, headers=self.headers, params=CONTEST_PARAMS, timeout=self.timeout_s
                )
            except httpx.HTTPError as error:
                if attempt == self.max_attempts - 1:
                    raise ContestScanError(f"transport:{type(error).__name__}") from None
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)
                continue
            if response.status_code == 401 and self.refresh_headers and not self._refreshed:
                self.headers = http_headers(await self.refresh_headers())
                self._refreshed = True
                continue
            if response.status_code in RETRY_STATUSES and attempt < self.max_attempts - 1:
                await asyncio.sleep(delay)
                delay = min(delay * 2, 30.0)
                continue
            return response
        raise ContestScanError("retries_exhausted")

    async def fetch_route(
        self, contest_id: int, route: RouteName
    ) -> tuple[int, dict[str, Any] | None]:
        response = await self._get(contest_url(contest_id, route))
        if response.status_code in ABSENT_STATUSES:
            return response.status_code, None
        if response.status_code != 200:
            raise ContestScanError(f"http_{response.status_code}")
        try:
            payload = response.json()
        except ValueError:
            raise ContestScanError("non_json_body") from None
        if not isinstance(payload, dict):
            raise ContestScanError("object_body_required")
        return response.status_code, payload

    async def collect(self, contest_id: int, *, sport: str = "nfl") -> ContestOutcome:
        """Resolve one contest id, descending into sub-routes only on a match."""
        status, meta = await self.fetch_route(contest_id, "meta")
        if meta is None:
            return ContestOutcome(contest_id, "absent", http_status=status)
        info = meta.get("info")
        contest = info.get("contest") if isinstance(info, dict) else None
        if not isinstance(contest, dict) or contest.get("id") != contest_id:
            return ContestOutcome(contest_id, "failed", detail="meta_identity_mismatch")
        observed_sport = contest.get("sport")
        day = contest.get("day")
        finalized = contest.get("isFinalized")
        if observed_sport != sport:
            return ContestOutcome(
                contest_id, "other_sport", sport=str(observed_sport), day=str(day) if day else None
            )

        captured_at = self.clock()
        provenances: list[ContestProvenance] = [
            self.store.write_route(
                contest_id,
                "meta",
                meta,
                source_url=contest_url(contest_id, "meta"),
                http_status=status,
                captured_at=captured_at,
                contest_day=str(day) if day else None,
                sport=str(observed_sport),
                is_finalized=finalized if isinstance(finalized, bool) else None,
            )
        ]
        missing: list[str] = []
        for route in NFL_SUB_ROUTES:
            await asyncio.sleep(self.request_pause_s)
            sub_status, payload = await self.fetch_route(contest_id, route)
            if payload is None:
                missing.append(f"{route}:{sub_status}")
                continue
            provenances.append(
                self.store.write_route(
                    contest_id,
                    route,
                    payload,
                    source_url=contest_url(contest_id, route),
                    http_status=sub_status,
                    captured_at=self.clock(),
                    contest_day=str(day) if day else None,
                    sport=str(observed_sport),
                    is_finalized=finalized if isinstance(finalized, bool) else None,
                )
            )
        entrants = contest.get("numBrawlers")
        self.store.write_manifest(
            contest_id,
            provenances,
            sport=observed_sport,
            day=str(day) if day else None,
            is_finalized=finalized,
            entrants=entrants if isinstance(entrants, int) else None,
            missing_routes=missing,
        )
        return ContestOutcome(
            contest_id,
            "nfl",
            sport=str(observed_sport),
            day=str(day) if day else None,
            is_finalized=finalized if isinstance(finalized, bool) else None,
            entrants=entrants if isinstance(entrants, int) else None,
            routes=tuple(p.route for p in provenances),
            detail=",".join(missing) or None,
        )


async def scan_range(
    scanner: ContestScanner,
    ids: Sequence[int],
    cursor: ScanCursor,
    cursor_file: Any,
    *,
    sport: str = "nfl",
    save_every: int = 25,
    on_outcome: Callable[[ContestOutcome], None] | None = None,
    max_requests: int | None = None,
) -> list[ContestOutcome]:
    """Walk ids in order, persisting the cursor so an interrupted run resumes."""
    outcomes: list[ContestOutcome] = []
    for index, contest_id in enumerate(ids, start=1):
        if max_requests is not None and scanner.requests >= max_requests:
            break
        try:
            outcome = await scanner.collect(contest_id, sport=sport)
        except ContestScanError as error:
            outcome = ContestOutcome(contest_id, "failed", detail=str(error))
        outcomes.append(outcome)
        if on_outcome is not None:
            on_outcome(outcome)
        if outcome.kind == "nfl":
            cursor.nfl_collected.append(contest_id)
            cursor.failed.pop(str(contest_id), None)
        elif outcome.kind == "other_sport":
            cursor.other_sport[str(contest_id)] = outcome.sport or "unknown"
            cursor.failed.pop(str(contest_id), None)
        elif outcome.kind == "absent":
            cursor.absent[str(contest_id)] = outcome.http_status or 0
            cursor.failed.pop(str(contest_id), None)
        else:
            cursor.failed[str(contest_id)] = outcome.detail or "unknown"
        cursor.highest_examined = max(cursor.highest_examined, contest_id)
        if index % save_every == 0:
            cursor.save(cursor_file)
        await asyncio.sleep(scanner.request_pause_s)
    cursor.save(cursor_file)
    return outcomes
