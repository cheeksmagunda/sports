"""Live NHL contract discovery: find real Real Sports NHL contests, persist
redacted fixtures with provenance, and report what the evidence does and
does not confirm.

Read-only. No contest entry anywhere in this module. Two entry points:

- `probe_next_slate`: is a live, draftable NHL contest currently advertised?
- `scan_contest_range`: walk a contest-ID range (the shared, cross-sport
  global sequence NFL's contests.collector documents) for NHL contests,
  fetching what sub-route data still exists for each and persisting it.

Both degrade a single item's failure to a recorded outcome rather than
raising, so one bad ID or one 500 on a sub-route cannot stop the rest of a
scan -- the same discipline nfl_oracle.recommendations.dayclose applies to a
single day's grading.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from nhl_oracle.calendar.season import season_label_for_date
from nhl_oracle.ingest.provenance import NhlCorpusStore
from nhl_oracle.ingest.realsports import (
    CONTEST_ROUTES,
    RequestHeaders,
    capture_live_headers,
    fetch_contest_route,
    fetch_home_next,
)

ABSENT_STATUSES = frozenset({400, 403, 404})


class ContestIdentityMismatch(RuntimeError):
    """A sub-route echoed a different contest than the one requested.

    Observed live (2026-09-12) on stale, archived NHL contest IDs: the
    `stats` route can return HTTP 200 with a well-formed but entirely
    unrelated contest embedded (a different id, sport, and day) instead of
    an error. Every sub-route response's own embedded contest identity must
    be checked against what was requested before the payload is trusted or
    persisted -- a 200 status alone is not sufficient proof the payload is
    about the contest the URL named.
    """


def _verify_contest_identity(payload: dict[str, Any], *, contest_id: int) -> None:
    contest = payload.get("contest")
    if not isinstance(contest, dict):
        return
    echoed_id = contest.get("id")
    if isinstance(echoed_id, int) and echoed_id != contest_id:
        raise ContestIdentityMismatch(
            f"requested contest {contest_id}, route echoed contest {echoed_id} "
            f"(sport={contest.get('sport')!r})"
        )


@dataclass(frozen=True)
class SlateProbe:
    """Result of checking whether Real Sports currently advertises a
    draftable NHL contest."""

    latest_day: str | None
    has_draft_info: bool
    contest_ids: tuple[int, ...]
    raw_days: tuple[dict[str, Any], ...]


async def probe_next_slate(client: httpx.AsyncClient, headers: RequestHeaders) -> SlateProbe:
    payload = await fetch_home_next(client, headers, refresh_headers=capture_live_headers)
    latest_day = payload.get("latestDay")
    content = payload.get("latestDayContent") or {}
    config = content.get("config") or {}
    draft_info = config.get("dailyDraftInfo")
    ids: tuple[int, ...] = ()
    if isinstance(draft_info, dict):
        raw_ids = draft_info.get("contests") or []
        ids = tuple(
            int(item["id"])
            for item in raw_ids
            if isinstance(item, dict) and isinstance(item.get("id"), int)
        )
    return SlateProbe(
        latest_day=latest_day if isinstance(latest_day, str) else None,
        has_draft_info=isinstance(draft_info, dict),
        contest_ids=ids,
        raw_days=tuple(payload.get("days") or ()),
    )


@dataclass(frozen=True)
class ContestSample:
    """One contest ID's outcome from a range scan."""

    contest_id: int
    kind: str  # "nhl" | "other_sport" | "absent" | "failed"
    sport: str | None = None
    day: str | None = None
    game_id: int | None = None
    is_finalized: bool | None = None
    entrants: int | None = None
    routes_persisted: tuple[str, ...] = ()
    routes_unavailable: tuple[str, ...] = ()
    detail: str | None = None


async def _fetch_meta(
    client: httpx.AsyncClient, headers: RequestHeaders, contest_id: int
) -> dict[str, Any]:
    return await fetch_contest_route(
        client, contest_id, "meta", headers, refresh_headers=capture_live_headers
    )


async def sample_contest(
    client: httpx.AsyncClient,
    headers: RequestHeaders,
    contest_id: int,
    *,
    store: NhlCorpusStore | None = None,
    fetch_sub_routes: bool = True,
) -> ContestSample:
    """Fetch one contest's meta route, and its sub-routes if it is NHL and
    `fetch_sub_routes` is set. Persists whatever sub-route data is fetched.
    """

    try:
        meta = await _fetch_meta(client, headers, contest_id)
    except httpx.HTTPStatusError as error:
        status = error.response.status_code
        if status in ABSENT_STATUSES:
            return ContestSample(contest_id, "absent", detail=str(status))
        return ContestSample(contest_id, "failed", detail=f"meta_http_{status}")
    except Exception as error:  # noqa: BLE001 - one id's failure must not stop a scan
        return ContestSample(contest_id, "failed", detail=type(error).__name__)

    info = meta.get("info") if isinstance(meta, dict) else None
    contest = info.get("contest") if isinstance(info, dict) else None
    if not isinstance(contest, dict):
        return ContestSample(contest_id, "failed", detail="meta_missing_contest")
    sport = contest.get("sport")
    if sport != "nhl":
        return ContestSample(contest_id, "other_sport", sport=sport)

    day_str = contest.get("day")
    game_id = contest.get("gameId")
    sample = ContestSample(
        contest_id=contest_id,
        kind="nhl",
        sport="nhl",
        day=day_str if isinstance(day_str, str) else None,
        game_id=int(game_id) if isinstance(game_id, int) else None,
        is_finalized=bool(contest.get("isFinalized")),
        entrants=contest.get("numBrawlers")
        if isinstance(contest.get("numBrawlers"), int)
        else None,
    )
    if not fetch_sub_routes:
        return sample

    routes: dict[str, dict[str, Any]] = {"meta": meta}
    persisted: list[str] = []
    unavailable: list[str] = []
    for route in CONTEST_ROUTES:
        if route == "meta":
            continue
        try:
            route_payload = await fetch_contest_route(
                client, contest_id, route, headers, refresh_headers=capture_live_headers
            )
            _verify_contest_identity(route_payload, contest_id=contest_id)
            routes[route] = route_payload
            persisted.append(route)
        except Exception as error:  # noqa: BLE001 - a stale archived contest may 500 per-route
            unavailable.append(f"{route}:{type(error).__name__}")
        await asyncio.sleep(0.05)

    if store is not None and game_id is not None and day_str is not None:
        try:
            captured_day = datetime.fromisoformat(day_str).replace(tzinfo=UTC)
        except ValueError:
            captured_day = datetime.now(UTC)
        season = season_label_for_date(captured_day.date())
        bundle = {"contest_id": contest_id, "routes": routes}
        store.persist_endpoint(
            game_id=int(game_id),
            season=season,
            endpoint="contest",
            payload=bundle,
            source_url=f"contests/playerratingcontest/{contest_id}",
            captured_at=datetime.now(UTC).isoformat(),
            event_time=day_str,
        )

    return ContestSample(
        contest_id=sample.contest_id,
        kind=sample.kind,
        sport=sample.sport,
        day=sample.day,
        game_id=sample.game_id,
        is_finalized=sample.is_finalized,
        entrants=sample.entrants,
        routes_persisted=tuple(persisted),
        routes_unavailable=tuple(unavailable),
    )


@dataclass(frozen=True)
class RangeCoverage:
    """Denominator-carrying coverage report for a contest-ID range scan."""

    ids_scanned: int
    nhl_found: int
    other_sport_found: int
    absent: int
    failed: int
    nhl_contests: tuple[ContestSample, ...] = field(default_factory=tuple)

    def to_json_obj(self) -> dict[str, Any]:
        return {
            "ids_scanned": self.ids_scanned,
            "nhl_found": self.nhl_found,
            "other_sport_found": self.other_sport_found,
            "absent": self.absent,
            "failed": self.failed,
            "nhl_contests": [
                {
                    "contest_id": c.contest_id,
                    "day": c.day,
                    "game_id": c.game_id,
                    "is_finalized": c.is_finalized,
                    "entrants": c.entrants,
                    "routes_persisted": list(c.routes_persisted),
                    "routes_unavailable": list(c.routes_unavailable),
                }
                for c in self.nhl_contests
            ],
        }


async def scan_contest_range(
    client: httpx.AsyncClient,
    headers: RequestHeaders,
    contest_ids: Sequence[int],
    *,
    store: NhlCorpusStore | None = None,
    fetch_sub_routes: bool = True,
    request_pause_s: float = 0.1,
) -> RangeCoverage:
    """Scan a caller-supplied sequence of contest IDs, honestly reporting the
    outcome of every one (found/other-sport/absent/failed), never silently
    dropping an ID from the denominator.
    """

    counts = {"nhl": 0, "other_sport": 0, "absent": 0, "failed": 0}
    nhl_contests: list[ContestSample] = []
    for contest_id in contest_ids:
        sample = await sample_contest(
            client, headers, contest_id, store=store, fetch_sub_routes=fetch_sub_routes
        )
        counts[sample.kind] += 1
        if sample.kind == "nhl":
            nhl_contests.append(sample)
        await asyncio.sleep(request_pause_s)
    return RangeCoverage(
        ids_scanned=len(contest_ids),
        nhl_found=counts["nhl"],
        other_sport_found=counts["other_sport"],
        absent=counts["absent"],
        failed=counts["failed"],
        nhl_contests=tuple(nhl_contests),
    )
