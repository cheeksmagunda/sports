"""Read-only, audited NFL collection. Never exposes an entry mutation method."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import httpx
from oracle_core.artifacts import atomic_write_json

from nfl_oracle.ingest.realsports import (
    BASE,
    RequestHeaders,
    capture_live_headers,
    http_headers,
    real_sports_get,
)
from nfl_oracle.ingest.redact import assert_no_identity_leak, redact_corpus_payload
from nfl_oracle.recommendations.schema import (
    Candidate,
    Contest,
    EvidenceClock,
    Game,
    Slate,
    fingerprint,
)


class ProviderError(RuntimeError):
    """Value-free provider failure suitable for job records."""


class NoSlate(ProviderError):
    """The validated provider day explicitly contains no NFL games or contest."""


class ObservationStore:
    """Content-addressed observations retain each capture time, including repeats."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def record(
        self, path: str, params: dict[str, Any], payload: dict[str, Any], captured_at: datetime
    ) -> str:
        clean = redact_corpus_payload(payload)
        assert_no_identity_leak(clean)
        record = {
            "source": "real_sports",
            "method": "GET",
            "path": path,
            "params": params,
            "captured_at": captured_at.isoformat(),
            "source_available_at": captured_at.isoformat(),
            "availability_basis": "observed_at_capture_not_backdated",
            "parser_version": 1,
            "payload": clean,
        }
        digest = fingerprint(record)
        target = self.root / digest[:2] / f"{digest}.json"
        if not target.exists():
            atomic_write_json(target, record, mode=0o600)
        return digest


def parse_contest(
    meta: dict[str, Any],
    draft: dict[str, Any],
    *,
    contest_id: int,
    captured_at: datetime,
    hashes: tuple[str, ...],
) -> Contest:
    info = meta["info"]
    contest = info["contest"]
    rules = draft["info"]
    if contest.get("id") != contest_id or contest.get("sport") != "nfl":
        raise ProviderError("contest_identity_mismatch")
    if rules.get("sport") != "nfl" or rules.get("day") != contest.get("day"):
        raise ProviderError("draft_identity_mismatch")
    if contest.get("additionalInfo", {}).get("lineupSize") != 5:
        raise ProviderError("unsupported_lineup_size")
    if rules.get("lineupSize") != 5 or rules.get("endDay") != contest.get("endDay"):
        raise ProviderError("draft_contract_mismatch")
    if type(info.get("isLocked")) is not bool or type(contest.get("isFinalized")) is not bool:
        raise ProviderError("missing_lock_state")
    return Contest(
        contest_id=contest_id,
        day=contest["day"],
        end_day=contest["endDay"],
        slot_multipliers=tuple(rules["defaultMultipliers"]),
        is_locked=info["isLocked"],
        is_finalized=contest["isFinalized"],
        clock=EvidenceClock(source_available_at=captured_at, captured_at=captured_at),
        evidence_sha256=fingerprint(hashes),
    )


def parse_game(raw: dict[str, Any]) -> Game:
    if raw.get("sport") != "nfl":
        raise ProviderError("game_sport_mismatch")
    return Game(
        game_id=raw["id"],
        season=raw["season"],
        kickoff_at=raw["dateTime"],
        home_team_id=raw["homeTeamId"],
        away_team_id=raw["awayTeamId"],
        home_team=raw["homeTeamKey"],
        away_team=raw["awayTeamKey"],
        status=raw["status"],
    )


class NFLReader:
    def __init__(
        self,
        client: httpx.AsyncClient,
        headers: RequestHeaders,
        store: ObservationStore,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        max_requests: int = 2500,
    ) -> None:
        self.client = client
        self.headers = http_headers(headers)
        self.store = store
        self.clock = clock
        self.hashes: list[str] = []
        self.requests = 0
        self.max_requests = max_requests
        self.last_captured_at = self.clock()

    async def get(self, path: str, **params: Any) -> dict[str, Any]:
        allowed = (
            path in {"/home/nfl/next", "/home/nfl/day/next"}
            or path == "/players/sport/nfl/search"
            or re.fullmatch(r"/games/[1-9][0-9]*/sport/nfl/(players|feed|stats)", path)
            or re.fullmatch(
                r"/games/playerratingcontest/[1-9][0-9]*(/(draftinfo|entries|stats))?", path
            )
        )
        if not allowed or "?" in path or ".." in path:
            raise ProviderError("read_path_not_allowed")
        if self.requests >= self.max_requests:
            raise ProviderError("request_budget_exhausted")
        self.requests += 1
        try:
            response = await real_sports_get(
                self.client,
                BASE + path,
                headers=self.headers,
                params=params,
                max_attempts=3,
                timeout_s=25,
                refresh_headers=capture_live_headers,
            )
            payload = response.json()
        except Exception as error:
            # Provider errors can include authentication or query values.
            raise ProviderError(f"provider_request_failed:{type(error).__name__}") from None
        if not isinstance(payload, dict):
            raise ProviderError("provider_object_required")
        self.last_captured_at = self.clock()
        self.hashes.append(self.store.record(path, params, payload, self.last_captured_at))
        return payload

    async def contest(self, contest_id: int) -> Contest:
        path = f"/games/playerratingcontest/{contest_id}"
        meta = await self.get(path, contestType="sport", source="home")
        # Stop before sub-route requests if the family/sport is wrong.
        if meta.get("info", {}).get("contest", {}).get("sport") != "nfl":
            raise ProviderError("contest_sport_mismatch")
        draft = await self.get(path + "/draftinfo", contestType="sport", source="home")
        return parse_contest(
            meta,
            draft,
            contest_id=contest_id,
            captured_at=self.clock(),
            hashes=tuple(self.hashes[-2:]),
        )

    async def next_day(self) -> date:
        """Resolve the provider's advertised NFL day without assuming local time."""
        home = await self.get("/home/nfl/next", cohort=0)
        raw_day = home.get("latestDayContent", {}).get("day")
        if not isinstance(raw_day, str):
            raise ProviderError("provider_next_day_missing")
        try:
            return date.fromisoformat(raw_day)
        except ValueError:
            raise ProviderError("provider_next_day_invalid") from None

    async def day_content(self, day: date) -> dict[str, Any]:
        home = await self.get("/home/nfl/day/next", day=day.isoformat(), cohort=0)
        content = home.get("content", {})
        if content.get("day") != day.isoformat():
            raise ProviderError("provider_day_identity_mismatch")
        if not isinstance(content.get("games"), list):
            raise ProviderError("provider_games_missing")
        return dict(content)

    async def collect(self, day: date, *, contest_id: int | None = None) -> Slate:
        self.hashes = []
        content = await self.day_content(day)
        ids = content.get("config", {}).get("dailyDraftInfo", {}).get("contests", [])
        available = [x["id"] for x in ids if isinstance(x, dict) and type(x.get("id")) is int]
        if not available and not content["games"]:
            raise NoSlate("no_slate")
        if contest_id is None:
            if len(available) != 1:
                raise ProviderError("ambiguous_or_missing_contest")
            contest_id = available[0]
        if contest_id not in available:
            raise ProviderError("contest_not_in_current_slate")
        contest = await self.contest(contest_id)
        if contest.day != day or contest.end_day != day:
            raise ProviderError("unsupported_multi_day_contest")
        games = tuple(parse_game(g) for g in content.get("games", []))
        roster: dict[int, tuple[dict[str, Any], Game]] = {}
        for game in games:
            payload = await self.get(f"/games/{game.game_id}/sport/nfl/players")
            players = payload.get("players")
            if not isinstance(players, list) or not players:
                raise ProviderError("empty_game_roster")
            for player in players:
                pid = player.get("id")
                if type(pid) is not int or player.get("sport") != "nfl":
                    raise ProviderError("invalid_roster_identity")
                if pid in roster:
                    raise ProviderError("duplicate_roster_identity")
                roster[pid] = (player, game)

        # A roster is finite, unlike a capped alphabet search. Query each missing
        # name and reconcile by exact Real ID, never by the name used for retrieval.
        rated: dict[int, dict[str, Any]] = {}
        observed_at: dict[int, datetime] = {}
        for query in [""] + [
            f"{p.get('firstName', '')} {p.get('lastName', '')}".strip() for p, _ in roster.values()
        ]:
            if query and all(
                pid in rated
                for pid, (p, _) in roster.items()
                if f"{p.get('firstName', '')} {p.get('lastName', '')}".strip() == query
            ):
                continue
            payload = await self.get(
                "/players/sport/nfl/search",
                query=query,
                searchType="ratingLineup",
                day=day.isoformat(),
                contestId=contest_id,
                includeNoOneOption="false",
            )
            if not isinstance(payload.get("players"), list):
                raise ProviderError("search_players_missing")
            for player in payload["players"]:
                pid = player.get("id")
                if pid not in roster:
                    continue
                original, game = roster[pid]
                if player.get("sport") != "nfl" or player.get("teamId") != original.get("teamId"):
                    raise ProviderError("search_roster_identity_mismatch")
                if player.get("multiplierBonus") is None:
                    raise ProviderError("missing_prelock_boost")
                rated[pid] = player
                observed_at[pid] = self.last_captured_at
            await asyncio.sleep(0.05)

        candidates: list[Candidate] = []
        for pid, player in sorted(rated.items()):
            _, game = roster[pid]
            home_player = player["teamId"] == game.home_team_id
            candidates.append(
                Candidate(
                    player_id=pid,
                    game_id=game.game_id,
                    team_id=player["teamId"],
                    name=f"{player['firstName']} {player['lastName']}",
                    position=player["position"],
                    team=game.home_team if home_player else game.away_team,
                    opponent=game.away_team if home_player else game.home_team,
                    injury_status=player.get("injuryStatus"),
                    card_boost=player["multiplierBonus"],
                    clock=EvidenceClock(
                        source_available_at=observed_at[pid], captured_at=observed_at[pid]
                    ),
                )
            )
        # Refresh lock after the sweep, preserving each player's actual capture.
        contest = await self.contest(contest_id)
        boosts = [candidate.card_boost for candidate in candidates]
        nonzero_boosts = sum(1 for boost in boosts if boost > 0)
        unmatched = tuple(sorted(set(roster) - set(rated)))
        return Slate(
            contest=contest,
            games=games,
            candidates=tuple(candidates),
            captured_at=self.clock(),
            source_hashes=tuple(self.hashes),
            pool_roster_count=len(roster),
            pool_search_matched_count=len(rated),
            pool_unmatched_ids=unmatched,
            pool_complete=len(roster) == len(rated) and not unmatched,
            boost_regime="zero_boost" if nonzero_boosts == 0 else "provider_boosts_present",
            boost_nonzero_count=nonzero_boosts,
            boost_max=max(boosts) if boosts else 0.0,
        )
