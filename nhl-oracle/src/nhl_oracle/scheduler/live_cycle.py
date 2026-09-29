"""Live IO for one T-40 runner cycle (#675).

Real Sports supplies the day, the contest, the games, and the pool. The public
NHL stats API supplies prior-season games played (Real player ids are NHL
ids) and current-season team GP for the zero-boost gate. Scoring lives in
``scheduler.runner``; this module only fetches.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, date, datetime
from typing import Any

import httpx

from nhl_oracle.ingest.realsports import (
    capture_live_headers,
    fetch_game_players,
    fetch_home_next,
    headers_or_capture,
)
from nhl_oracle.scheduler.runner import (
    CycleOutcome,
    SlateSnapshot,
    parse_game_players,
    parse_home_next,
    prior_games_played_from_summaries,
    score_cycle,
)
from nhl_oracle.scheduler.watchdog import season_id_for_date, team_games_played_from_summary

STATS_BASE = "https://api.nhle.com/stats/rest/en"
PUBLIC_HEADERS = {"User-Agent": "Mozilla/5.0 (nhl-oracle t40 runner)"}


def prior_season_id(day: date) -> str:
    """Season whose Real totals ``primaryValue`` carries. Override by env."""

    override = os.environ.get("NHL_PRIMARY_VALUE_SEASON_ID", "").strip()
    if override:
        return override
    current = season_id_for_date(day)
    start = int(current[:4]) - 1
    return f"{start}{start + 1}"


async def _public_json(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    response = await client.get(url, headers=PUBLIC_HEADERS)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError(f"public payload must be an object: {url}")
    return payload


async def _summary(client: httpx.AsyncClient, kind: str, season_id: str) -> dict[str, Any]:
    url = (
        f"{STATS_BASE}/{kind}/summary?limit=-1&cayenneExp=seasonId={season_id}%20and%20gameTypeId=2"
    )
    return await _public_json(client, url)


async def collect_snapshot(client: httpx.AsyncClient) -> SlateSnapshot | None:
    headers = await headers_or_capture()
    home = await fetch_home_next(client, headers, refresh_headers=capture_live_headers)
    parsed = parse_home_next(home)
    if parsed is None:
        return None
    day, contest_id, games = parsed
    payloads = await asyncio.gather(
        *(
            fetch_game_players(client, game.game_id, headers, refresh_headers=capture_live_headers)
            for game in games
        )
    )
    players = []
    seen: set[int] = set()
    with_players: set[int] = set()
    for game, payload in zip(games, payloads, strict=True):
        cards = parse_game_players(payload, game_id=game.game_id)
        if cards:
            with_players.add(game.game_id)
        for card in cards:
            if card.player_id not in seen:
                seen.add(card.player_id)
                players.append(card)
    return SlateSnapshot(
        day=day,
        contest_id=contest_id,
        games=games,
        players=tuple(players),
        captured_at=datetime.now(UTC),
        games_with_players=frozenset(with_players),
    )


async def run_cycle(now: datetime | None = None) -> CycleOutcome | None:
    """Collect and score one cycle. None when Real advertises no NHL draft."""

    async with httpx.AsyncClient(timeout=30.0) as client:
        snapshot = await collect_snapshot(client)
        if snapshot is None:
            return None
        prior = prior_season_id(snapshot.day)
        skaters, goalies, teams = await asyncio.gather(
            _summary(client, "skater", prior),
            _summary(client, "goalie", prior),
            _summary(client, "team", season_id_for_date(snapshot.day)),
        )
    decided_at = now or datetime.now(UTC)
    return score_cycle(
        snapshot,
        prior_games_played=prior_games_played_from_summaries(skaters, goalies),
        team_games_played=team_games_played_from_summary(teams),
        now=decided_at,
    )
