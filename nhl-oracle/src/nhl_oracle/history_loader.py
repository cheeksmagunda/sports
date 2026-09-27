"""Load multi-year NHL public history into Postgres for NHL-only research.

The public NHL API requires a browser-like User-Agent on some routes. This
loader fetches season game lists plus final gamecenter boxscores, then writes a
minimal normalized store for future NHL baselines and feature work.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

import httpx
from oracle_core.http import HttpxAsyncTransport, RetryPolicy, async_request_with_retry
from oracle_core.storage import PoolOptions, create_postgres_engine
from sqlalchemy import JSON, Boolean, Column, Float, Integer, MetaData, String, Table, delete
from sqlalchemy.engine import Connection, Engine

PUBLIC_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
STATS_API_BASE = "https://api.nhle.com/stats/rest/en"
WEB_API_BASE = "https://api-web.nhle.com/v1"
DEFAULT_GAME_TYPES = (2, 3)
DEFAULT_START_SEASON = 2021
DEFAULT_END_SEASON = 2024

metadata = MetaData()
history_games = Table(
    "nhl_history_games",
    metadata,
    Column("game_id", Integer, primary_key=True),
    Column("season_code", Integer, nullable=False),
    Column("season_start_year", Integer, nullable=False),
    Column("game_type", Integer, nullable=False),
    Column("game_date", String(10), nullable=False),
    Column("start_time_utc", String(32), nullable=True),
    Column("game_state", String(16), nullable=False),
    Column("game_schedule_state", String(16), nullable=True),
    Column("venue_name", String(120), nullable=True),
    Column("home_team_id", Integer, nullable=False),
    Column("home_team_abbrev", String(8), nullable=True),
    Column("home_score", Integer, nullable=True),
    Column("away_team_id", Integer, nullable=False),
    Column("away_team_abbrev", String(8), nullable=True),
    Column("away_score", Integer, nullable=True),
    Column("outcome_last_period_type", String(16), nullable=True),
    Column("source_url", String(255), nullable=False),
    Column("fetched_at", String(32), nullable=False),
    Column("payload_json", JSON, nullable=False),
)
history_player_games = Table(
    "nhl_history_player_games",
    metadata,
    Column("game_id", Integer, primary_key=True),
    Column("player_id", Integer, primary_key=True),
    Column("season_code", Integer, nullable=False),
    Column("season_start_year", Integer, nullable=False),
    Column("game_type", Integer, nullable=False),
    Column("game_date", String(10), nullable=False),
    Column("team_id", Integer, nullable=False),
    Column("opponent_team_id", Integer, nullable=False),
    Column("is_home", Boolean, nullable=False),
    Column("position", String(4), nullable=False),
    Column("sweater_number", Integer, nullable=True),
    Column("player_name", String(120), nullable=False),
    Column("goals", Integer, nullable=True),
    Column("assists", Integer, nullable=True),
    Column("points", Integer, nullable=True),
    Column("shots_on_goal", Integer, nullable=True),
    Column("hits", Integer, nullable=True),
    Column("blocked_shots", Integer, nullable=True),
    Column("penalty_minutes", Integer, nullable=True),
    Column("plus_minus", Integer, nullable=True),
    Column("giveaways", Integer, nullable=True),
    Column("takeaways", Integer, nullable=True),
    Column("shifts", Integer, nullable=True),
    Column("time_on_ice", String(16), nullable=True),
    Column("power_play_goals", Integer, nullable=True),
    Column("faceoff_winning_pctg", Float, nullable=True),
    Column("save_pctg", Float, nullable=True),
    Column("shots_against", Integer, nullable=True),
    Column("saves", Integer, nullable=True),
    Column("goals_against", Integer, nullable=True),
    Column("starter", Boolean, nullable=True),
    Column("decision", String(4), nullable=True),
    Column("source_url", String(255), nullable=False),
    Column("fetched_at", String(32), nullable=False),
    Column("payload_json", JSON, nullable=False),
)
season_coverage = Table(
    "nhl_history_season_coverage",
    metadata,
    Column("season_start_year", Integer, primary_key=True),
    Column("season_code", Integer, nullable=False),
    Column("game_types", String(16), nullable=False),
    Column("scheduled_games", Integer, nullable=False),
    Column("loaded_games", Integer, nullable=False),
    Column("loaded_player_rows", Integer, nullable=False),
    Column("failed_games", Integer, nullable=False),
    Column("first_game_date", String(10), nullable=True),
    Column("last_game_date", String(10), nullable=True),
    Column("loaded_at", String(32), nullable=False),
    Column("status", String(16), nullable=False),
)


@dataclass(frozen=True)
class CoverageRow:
    season_start_year: int
    season_code: int
    game_types: str
    scheduled_games: int
    loaded_games: int
    loaded_player_rows: int
    failed_games: int
    first_game_date: str | None
    last_game_date: str | None
    loaded_at: str
    status: str


@dataclass(frozen=True)
class LoadSummary:
    seasons: tuple[CoverageRow, ...]
    total_games: int
    total_player_rows: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "seasons": [asdict(row) for row in self.seasons],
            "total_games": self.total_games,
            "total_player_rows": self.total_player_rows,
            "observation_only": True,
            "contest_entry": False,
        }


def season_code_for_start_year(start_year: int) -> int:
    return int(f"{start_year}{start_year + 1}")


def season_start_year_from_code(season_code: int) -> int:
    return int(str(season_code)[:4])


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _env_database_url() -> str:
    for key in ("NHL_DATABASE_URL", "DATABASE_URL"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    raise RuntimeError("NHL_DATABASE_URL or DATABASE_URL is required")


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    return int(str(value))


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return float(str(value))


def _name_text(value: Any) -> str:
    if isinstance(value, dict):
        default = value.get("default")
        if isinstance(default, str) and default.strip():
            return default.strip()
    if isinstance(value, str):
        return value.strip()
    return ""


def migrate(engine: Engine) -> None:
    """Explicit create/replace migration for the NHL history research store."""

    metadata.create_all(engine)


def _replace_game_batch(
    conn: Connection,
    *,
    game_rows: Sequence[dict[str, Any]],
    player_rows: Sequence[dict[str, Any]],
) -> None:
    if not game_rows:
        return
    game_ids = [row["game_id"] for row in game_rows]
    conn.execute(delete(history_player_games).where(history_player_games.c.game_id.in_(game_ids)))
    conn.execute(delete(history_games).where(history_games.c.game_id.in_(game_ids)))
    conn.execute(history_games.insert(), list(game_rows))
    if player_rows:
        conn.execute(history_player_games.insert(), list(player_rows))


def _replace_coverage(conn: Connection, row: CoverageRow) -> None:
    conn.execute(
        delete(season_coverage).where(season_coverage.c.season_start_year == row.season_start_year)
    )
    conn.execute(season_coverage.insert().values(**asdict(row)))


async def _get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    transport = HttpxAsyncTransport(client)
    policy = RetryPolicy(max_attempts=5, base_delay=0.5, max_delay=8.0)
    response = await async_request_with_retry(
        transport,
        "GET",
        url,
        policy=policy,
        params=params,
        headers={"accept": "application/json"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError(f"Expected object payload from {url}")
    return payload


async def fetch_season_games(
    client: httpx.AsyncClient,
    *,
    season_code: int,
    game_type: int,
) -> list[dict[str, Any]]:
    payload = await _get_json(
        client,
        f"{STATS_API_BASE}/game",
        params={
            "limit": 2000,
            "cayenneExp": f"season={season_code} and gameType={game_type}",
        },
    )
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise TypeError("stats game listing must contain a data array")
    completed_rows: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict) and _int_or_none(row.get("gameStateId")) == 7:
            completed_rows.append(row)
    return completed_rows


async def fetch_boxscore(client: httpx.AsyncClient, game_id: int) -> dict[str, Any]:
    return await _get_json(client, f"{WEB_API_BASE}/gamecenter/{game_id}/boxscore")


def _game_row(boxscore: dict[str, Any], *, fetched_at: str, source_url: str) -> dict[str, Any]:
    season_code = _int_or_none(boxscore.get("season"))
    if season_code is None:
        raise ValueError("boxscore season missing")
    away_team = boxscore.get("awayTeam")
    home_team = boxscore.get("homeTeam")
    if not isinstance(away_team, dict) or not isinstance(home_team, dict):
        raise ValueError("boxscore team payload missing")
    return {
        "game_id": _int_or_none(boxscore.get("id")),
        "season_code": season_code,
        "season_start_year": season_start_year_from_code(season_code),
        "game_type": _int_or_none(boxscore.get("gameType")),
        "game_date": str(boxscore.get("gameDate")),
        "start_time_utc": boxscore.get("startTimeUTC"),
        "game_state": str(boxscore.get("gameState")),
        "game_schedule_state": boxscore.get("gameScheduleState"),
        "venue_name": _name_text(boxscore.get("venue")),
        "home_team_id": _int_or_none(home_team.get("id")),
        "home_team_abbrev": home_team.get("abbrev"),
        "home_score": _int_or_none(home_team.get("score")),
        "away_team_id": _int_or_none(away_team.get("id")),
        "away_team_abbrev": away_team.get("abbrev"),
        "away_score": _int_or_none(away_team.get("score")),
        "outcome_last_period_type": (
            boxscore.get("gameOutcome", {}).get("lastPeriodType")
            if isinstance(boxscore.get("gameOutcome"), dict)
            else None
        ),
        "source_url": source_url,
        "fetched_at": fetched_at,
        "payload_json": boxscore,
    }


def flatten_boxscore_player_rows(
    boxscore: dict[str, Any],
    *,
    fetched_at: str,
    source_url: str,
) -> list[dict[str, Any]]:
    season_code = _int_or_none(boxscore.get("season"))
    if season_code is None:
        raise ValueError("boxscore season missing")
    pbgs = boxscore.get("playerByGameStats")
    away_team = boxscore.get("awayTeam")
    home_team = boxscore.get("homeTeam")
    if (
        not isinstance(pbgs, dict)
        or not isinstance(away_team, dict)
        or not isinstance(home_team, dict)
    ):
        raise ValueError("boxscore player stats missing")
    out: list[dict[str, Any]] = []
    for side_name, team_key, own_team, opp_team in (
        ("away", "awayTeam", away_team, home_team),
        ("home", "homeTeam", home_team, away_team),
    ):
        team_payload = pbgs.get(team_key)
        if not isinstance(team_payload, dict):
            continue
        for group in ("forwards", "defense", "goalies"):
            rows = team_payload.get(group)
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not isinstance(row, dict):
                    continue
                out.append(
                    {
                        "game_id": _int_or_none(boxscore.get("id")),
                        "player_id": _int_or_none(row.get("playerId")),
                        "season_code": season_code,
                        "season_start_year": season_start_year_from_code(season_code),
                        "game_type": _int_or_none(boxscore.get("gameType")),
                        "game_date": str(boxscore.get("gameDate")),
                        "team_id": _int_or_none(own_team.get("id")),
                        "opponent_team_id": _int_or_none(opp_team.get("id")),
                        "is_home": side_name == "home",
                        "position": str(row.get("position") or ""),
                        "sweater_number": _int_or_none(row.get("sweaterNumber")),
                        "player_name": _name_text(row.get("name")),
                        "goals": _int_or_none(row.get("goals")),
                        "assists": _int_or_none(row.get("assists")),
                        "points": _int_or_none(row.get("points")),
                        "shots_on_goal": _int_or_none(row.get("sog")),
                        "hits": _int_or_none(row.get("hits")),
                        "blocked_shots": _int_or_none(row.get("blockedShots")),
                        "penalty_minutes": _int_or_none(row.get("pim")),
                        "plus_minus": _int_or_none(row.get("plusMinus")),
                        "giveaways": _int_or_none(row.get("giveaways")),
                        "takeaways": _int_or_none(row.get("takeaways")),
                        "shifts": _int_or_none(row.get("shifts")),
                        "time_on_ice": row.get("toi"),
                        "power_play_goals": _int_or_none(row.get("powerPlayGoals")),
                        "faceoff_winning_pctg": _float_or_none(row.get("faceoffWinningPctg")),
                        "save_pctg": _float_or_none(row.get("savePctg")),
                        "shots_against": _int_or_none(row.get("shotsAgainst")),
                        "saves": _int_or_none(row.get("saves")),
                        "goals_against": _int_or_none(row.get("goalsAgainst")),
                        "starter": row.get("starter"),
                        "decision": row.get("decision"),
                        "source_url": source_url,
                        "fetched_at": fetched_at,
                        "payload_json": row,
                    }
                )
    return out


async def _load_one_game(
    client: httpx.AsyncClient,
    row: dict[str, Any],
    *,
    semaphore: asyncio.Semaphore,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    game_id = _int_or_none(row.get("id"))
    if game_id is None:
        raise ValueError("schedule row missing id")
    async with semaphore:
        boxscore = await fetch_boxscore(client, game_id)
    if str(boxscore.get("gameState")) != "OFF":
        raise ValueError(f"game {game_id} not final: {boxscore.get('gameState')}")
    source_url = f"{WEB_API_BASE}/gamecenter/{game_id}/boxscore"
    fetched_at = _now_iso()
    return (
        _game_row(boxscore, fetched_at=fetched_at, source_url=source_url),
        flatten_boxscore_player_rows(boxscore, fetched_at=fetched_at, source_url=source_url),
    )


def _batched(rows: Sequence[dict[str, Any]], size: int) -> Iterable[Sequence[dict[str, Any]]]:
    for offset in range(0, len(rows), size):
        yield rows[offset : offset + size]


def _season_rows(rows: Sequence[dict[str, Any]]) -> tuple[str | None, str | None]:
    dates = sorted(str(row.get("gameDate")) for row in rows if row.get("gameDate"))
    if not dates:
        return None, None
    return dates[0], dates[-1]


def _coverage_row(
    *,
    season_start_year: int,
    season_code: int,
    game_types: Sequence[int],
    scheduled_games: int,
    loaded_games: int,
    loaded_player_rows: int,
    failed_games: int,
    first_game_date: str | None,
    last_game_date: str | None,
) -> CoverageRow:
    status = "complete" if failed_games == 0 and loaded_games == scheduled_games else "partial"
    return CoverageRow(
        season_start_year=season_start_year,
        season_code=season_code,
        game_types=",".join(str(value) for value in game_types),
        scheduled_games=scheduled_games,
        loaded_games=loaded_games,
        loaded_player_rows=loaded_player_rows,
        failed_games=failed_games,
        first_game_date=first_game_date,
        last_game_date=last_game_date,
        loaded_at=_now_iso(),
        status=status,
    )


async def load_history(
    *,
    engine: Engine,
    start_season: int,
    end_season: int,
    game_types: Sequence[int],
    concurrency: int,
) -> LoadSummary:
    migrate(engine)
    timeout = httpx.Timeout(connect=10.0, read=30.0, write=30.0, pool=30.0)
    headers = {"user-agent": PUBLIC_BROWSER_USER_AGENT, "accept": "application/json"}
    semaphore = asyncio.Semaphore(concurrency)
    summaries: list[CoverageRow] = []
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        for start_year in range(start_season, end_season + 1):
            season_code = season_code_for_start_year(start_year)
            scheduled: list[dict[str, Any]] = []
            for game_type in game_types:
                scheduled.extend(
                    await fetch_season_games(client, season_code=season_code, game_type=game_type)
                )
            scheduled = sorted(
                {int(row["id"]): row for row in scheduled if "id" in row}.values(),
                key=lambda row: int(row["id"]),
            )
            loaded_games = 0
            loaded_player_rows = 0
            failed_games = 0
            first_game_date, last_game_date = _season_rows(scheduled)
            for batch in _batched(scheduled, max(concurrency * 4, concurrency)):
                results = await asyncio.gather(
                    *(_load_one_game(client, row, semaphore=semaphore) for row in batch),
                    return_exceptions=True,
                )
                game_rows: list[dict[str, Any]] = []
                player_rows: list[dict[str, Any]] = []
                for result in results:
                    if isinstance(result, BaseException):
                        failed_games += 1
                        continue
                    game_row, rows = result
                    game_rows.append(game_row)
                    player_rows.extend(rows)
                if game_rows:
                    with engine.begin() as conn:
                        _replace_game_batch(conn, game_rows=game_rows, player_rows=player_rows)
                    loaded_games += len(game_rows)
                    loaded_player_rows += len(player_rows)
            coverage = _coverage_row(
                season_start_year=start_year,
                season_code=season_code,
                game_types=game_types,
                scheduled_games=len(scheduled),
                loaded_games=loaded_games,
                loaded_player_rows=loaded_player_rows,
                failed_games=failed_games,
                first_game_date=first_game_date,
                last_game_date=last_game_date,
            )
            with engine.begin() as conn:
                _replace_coverage(conn, coverage)
            summaries.append(coverage)
    return LoadSummary(
        seasons=tuple(summaries),
        total_games=sum(row.loaded_games for row in summaries),
        total_player_rows=sum(row.loaded_player_rows for row in summaries),
    )


def _parse_game_types(value: str) -> tuple[int, ...]:
    values = tuple(int(part.strip()) for part in value.split(",") if part.strip())
    if not values:
        raise argparse.ArgumentTypeError("at least one game type is required")
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load public NHL history into Postgres")
    parser.add_argument("--start-season", type=int, default=DEFAULT_START_SEASON)
    parser.add_argument("--end-season", type=int, default=DEFAULT_END_SEASON)
    parser.add_argument(
        "--game-types",
        type=_parse_game_types,
        default=DEFAULT_GAME_TYPES,
        help="Comma-separated NHL gameType ids (default: 2,3 for regular season + playoffs).",
    )
    parser.add_argument("--concurrency", type=int, default=12)
    return parser


async def _async_main(args: argparse.Namespace) -> int:
    if args.end_season < args.start_season:
        raise RuntimeError("end season must be greater than or equal to start season")
    engine = create_postgres_engine(
        _env_database_url(),
        pool=PoolOptions(pool_size=3, max_overflow=2, pool_timeout=30.0, pool_recycle=900),
    )
    summary = await load_history(
        engine=engine,
        start_season=args.start_season,
        end_season=args.end_season,
        game_types=args.game_types,
        concurrency=args.concurrency,
    )
    print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))
    return 0 if all(row.failed_games == 0 for row in summary.seasons) else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
