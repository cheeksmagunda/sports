"""Load multi-year NBA public history into Postgres for NBA-only research.

Fetches season schedules and final game details from the public data.nba.com
mobile JSON endpoints (no Real Sports auth), then writes a minimal normalized
store for future NBA baselines and feature work.
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
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import httpx
from oracle_core.http import HttpxAsyncTransport, RetryPolicy, async_request_with_retry
from oracle_core.storage import PoolOptions, create_postgres_engine
from sqlalchemy import JSON, Boolean, Column, Integer, MetaData, String, Table, delete
from sqlalchemy.engine import Connection, Engine

PUBLIC_BROWSER_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
DATA_NBA_BASE = "https://data.nba.com/data/10s/v2015/json/mobile_teams/nba"
DEFAULT_START_SEASON = 2021
DEFAULT_END_SEASON = 2024
# Regular season (002) + playoffs (004). Preseason (001) excluded.
DEFAULT_GAME_TYPE_PREFIXES = ("002", "004")

metadata = MetaData()
history_games = Table(
    "nba_history_games",
    metadata,
    Column("game_id", String(10), primary_key=True),
    Column("season_code", Integer, nullable=False),
    Column("season_start_year", Integer, nullable=False),
    Column("game_type_prefix", String(3), nullable=False),
    Column("game_date", String(10), nullable=False),
    Column("start_time_utc", String(32), nullable=True),
    Column("game_status", String(16), nullable=False),
    Column("venue_name", String(120), nullable=True),
    Column("home_team_id", Integer, nullable=False),
    Column("home_team_tricode", String(8), nullable=True),
    Column("home_score", Integer, nullable=True),
    Column("away_team_id", Integer, nullable=False),
    Column("away_team_tricode", String(8), nullable=True),
    Column("away_score", Integer, nullable=True),
    Column("source_url", String(255), nullable=False),
    Column("fetched_at", String(32), nullable=False),
    Column("payload_json", JSON, nullable=False),
)
history_player_games = Table(
    "nba_history_player_games",
    metadata,
    Column("game_id", String(10), primary_key=True),
    Column("player_id", Integer, primary_key=True),
    Column("season_code", Integer, nullable=False),
    Column("season_start_year", Integer, nullable=False),
    Column("game_type_prefix", String(3), nullable=False),
    Column("game_date", String(10), nullable=False),
    Column("team_id", Integer, nullable=False),
    Column("opponent_team_id", Integer, nullable=False),
    Column("is_home", Boolean, nullable=False),
    Column("position", String(8), nullable=True),
    Column("jersey_number", String(8), nullable=True),
    Column("player_name", String(120), nullable=False),
    Column("minutes", Integer, nullable=True),
    Column("seconds", Integer, nullable=True),
    Column("points", Integer, nullable=True),
    Column("rebounds", Integer, nullable=True),
    Column("assists", Integer, nullable=True),
    Column("steals", Integer, nullable=True),
    Column("blocks", Integer, nullable=True),
    Column("turnovers", Integer, nullable=True),
    Column("fgm", Integer, nullable=True),
    Column("fga", Integer, nullable=True),
    Column("fg3m", Integer, nullable=True),
    Column("fg3a", Integer, nullable=True),
    Column("ftm", Integer, nullable=True),
    Column("fta", Integer, nullable=True),
    Column("plus_minus", Integer, nullable=True),
    Column("source_url", String(255), nullable=False),
    Column("fetched_at", String(32), nullable=False),
    Column("payload_json", JSON, nullable=False),
)
season_coverage = Table(
    "nba_history_season_coverage",
    metadata,
    Column("season_start_year", Integer, primary_key=True),
    Column("season_code", Integer, nullable=False),
    Column("game_type_prefixes", String(32), nullable=False),
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
    game_type_prefixes: str
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


def ensure_public_ssl_database_url(url: str) -> str:
    """Reject railway.internal hosts and require sslmode=require on public TCP."""

    value = url.strip()
    if not value:
        raise RuntimeError("database URL is empty")
    if "railway.internal" in value:
        raise RuntimeError(
            "refusing railway.internal database URL; use public TCP "
            "(*.proxy.rlwy.net) with sslmode=require"
        )
    parsed = urlparse(value)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query["sslmode"] = "require"
    return urlunparse(parsed._replace(query=urlencode(query)))


def _env_database_url() -> str:
    for key in ("NBA_DATABASE_URL", "DATABASE_PUBLIC_URL", "DATABASE_URL"):
        value = os.environ.get(key, "").strip()
        if value:
            return ensure_public_ssl_database_url(value)
    raise RuntimeError("NBA_DATABASE_URL, DATABASE_PUBLIC_URL, or DATABASE_URL is required")


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


def _team_tricode(team: dict[str, Any]) -> str | None:
    for key in ("ta", "triCode", "abbreviation"):
        value = team.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def migrate(engine: Engine) -> None:
    """Explicit create migration for the NBA history research store."""

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


async def _get_json(client: httpx.AsyncClient, url: str) -> dict[str, Any]:
    transport = HttpxAsyncTransport(client)
    policy = RetryPolicy(max_attempts=8, base_delay=1.0, max_delay=20.0)
    response = await async_request_with_retry(
        transport,
        "GET",
        url,
        policy=policy,
        headers={
            "accept": "application/json",
            "origin": "https://www.nba.com",
            "referer": "https://www.nba.com/",
        },
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise TypeError(f"Expected object payload from {url}")
    return payload


def schedule_url(season_start_year: int) -> str:
    return f"{DATA_NBA_BASE}/{season_start_year}/league/00_full_schedule.json"


def gamedetail_url(season_start_year: int, game_id: str) -> str:
    return f"{DATA_NBA_BASE}/{season_start_year}/scores/gamedetail/{game_id}_gamedetail.json"


def _game_type_prefix(game_id: str) -> str:
    return game_id[:3]


def extract_schedule_games(
    payload: dict[str, Any],
    *,
    game_type_prefixes: Sequence[str],
) -> list[dict[str, Any]]:
    """Flatten data.nba.com full-schedule months into final eligible games."""

    months = payload.get("lscd")
    if not isinstance(months, list):
        raise TypeError("schedule payload missing lscd array")
    allowed = set(game_type_prefixes)
    out: list[dict[str, Any]] = []
    for month in months:
        if not isinstance(month, dict):
            continue
        mscd = month.get("mscd")
        if not isinstance(mscd, dict):
            continue
        games = mscd.get("g")
        if not isinstance(games, list):
            continue
        for game in games:
            if not isinstance(game, dict):
                continue
            game_id = str(game.get("gid") or "").strip()
            if len(game_id) != 10:
                continue
            if _game_type_prefix(game_id) not in allowed:
                continue
            status_text = str(game.get("stt") or "")
            status_code = str(game.get("st") or "")
            if status_text != "Final" and status_code != "3":
                continue
            out.append(game)
    # Deduplicate by game_id while preserving schedule order.
    deduped = {str(row["gid"]): row for row in out}
    return list(deduped.values())


async def fetch_season_games(
    client: httpx.AsyncClient,
    *,
    season_start_year: int,
    game_type_prefixes: Sequence[str],
) -> list[dict[str, Any]]:
    payload = await _get_json(client, schedule_url(season_start_year))
    return extract_schedule_games(payload, game_type_prefixes=game_type_prefixes)


async def fetch_gamedetail(
    client: httpx.AsyncClient,
    *,
    season_start_year: int,
    game_id: str,
) -> dict[str, Any]:
    payload = await _get_json(client, gamedetail_url(season_start_year, game_id))
    game = payload.get("g")
    if not isinstance(game, dict):
        raise TypeError(f"gamedetail missing g object for {game_id}")
    return game


def _game_row(
    detail: dict[str, Any],
    *,
    season_start_year: int,
    fetched_at: str,
    source_url: str,
) -> dict[str, Any]:
    game_id = str(detail.get("gid") or "").strip()
    if len(game_id) != 10:
        raise ValueError("gamedetail missing gid")
    home = detail.get("hls")
    away = detail.get("vls")
    if not isinstance(home, dict) or not isinstance(away, dict):
        raise ValueError(f"gamedetail teams missing for {game_id}")
    home_id = _int_or_none(home.get("tid"))
    away_id = _int_or_none(away.get("tid"))
    if home_id is None or away_id is None:
        raise ValueError(f"gamedetail team ids missing for {game_id}")
    start_utc = None
    gdtutc = detail.get("gdtutc")
    utctm = detail.get("utctm")
    if isinstance(gdtutc, str) and isinstance(utctm, str) and gdtutc and utctm:
        start_utc = f"{gdtutc}T{utctm}Z"
    return {
        "game_id": game_id,
        "season_code": season_code_for_start_year(season_start_year),
        "season_start_year": season_start_year,
        "game_type_prefix": _game_type_prefix(game_id),
        "game_date": str(detail.get("gdte") or ""),
        "start_time_utc": start_utc,
        "game_status": str(detail.get("stt") or detail.get("st") or ""),
        "venue_name": detail.get("an"),
        "home_team_id": home_id,
        "home_team_tricode": _team_tricode(home),
        "home_score": _int_or_none(home.get("s")),
        "away_team_id": away_id,
        "away_team_tricode": _team_tricode(away),
        "away_score": _int_or_none(away.get("s")),
        "source_url": source_url,
        "fetched_at": fetched_at,
        "payload_json": detail,
    }


def flatten_gamedetail_player_rows(
    detail: dict[str, Any],
    *,
    season_start_year: int,
    fetched_at: str,
    source_url: str,
) -> list[dict[str, Any]]:
    game_id = str(detail.get("gid") or "").strip()
    if len(game_id) != 10:
        raise ValueError("gamedetail missing gid")
    home = detail.get("hls")
    away = detail.get("vls")
    if not isinstance(home, dict) or not isinstance(away, dict):
        raise ValueError(f"gamedetail teams missing for {game_id}")
    home_id = _int_or_none(home.get("tid"))
    away_id = _int_or_none(away.get("tid"))
    if home_id is None or away_id is None:
        raise ValueError(f"gamedetail team ids missing for {game_id}")
    out: list[dict[str, Any]] = []
    for side_name, team, opp_id in (
        ("home", home, away_id),
        ("away", away, home_id),
    ):
        team_id = _int_or_none(team.get("tid"))
        if team_id is None:
            continue
        players = team.get("pstsg")
        if not isinstance(players, list):
            continue
        for row in players:
            if not isinstance(row, dict):
                continue
            player_id = _int_or_none(row.get("pid"))
            if player_id is None:
                continue
            first = str(row.get("fn") or "").strip()
            last = str(row.get("ln") or "").strip()
            name = f"{first} {last}".strip() or f"player-{player_id}"
            out.append(
                {
                    "game_id": game_id,
                    "player_id": player_id,
                    "season_code": season_code_for_start_year(season_start_year),
                    "season_start_year": season_start_year,
                    "game_type_prefix": _game_type_prefix(game_id),
                    "game_date": str(detail.get("gdte") or ""),
                    "team_id": team_id,
                    "opponent_team_id": opp_id,
                    "is_home": side_name == "home",
                    "position": row.get("pos"),
                    "jersey_number": str(row.get("num")) if row.get("num") is not None else None,
                    "player_name": name,
                    "minutes": _int_or_none(row.get("min")),
                    "seconds": _int_or_none(row.get("sec")),
                    "points": _int_or_none(row.get("pts")),
                    "rebounds": _int_or_none(row.get("reb")),
                    "assists": _int_or_none(row.get("ast")),
                    "steals": _int_or_none(row.get("stl")),
                    "blocks": _int_or_none(row.get("blk")),
                    "turnovers": _int_or_none(row.get("tov")),
                    "fgm": _int_or_none(row.get("fgm")),
                    "fga": _int_or_none(row.get("fga")),
                    "fg3m": _int_or_none(row.get("tpm")),
                    "fg3a": _int_or_none(row.get("tpa")),
                    "ftm": _int_or_none(row.get("ftm")),
                    "fta": _int_or_none(row.get("fta")),
                    "plus_minus": _int_or_none(row.get("pm")),
                    "source_url": source_url,
                    "fetched_at": fetched_at,
                    "payload_json": row,
                }
            )
    return out


async def _load_one_game(
    client: httpx.AsyncClient,
    schedule_row: dict[str, Any],
    *,
    season_start_year: int,
    semaphore: asyncio.Semaphore,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    game_id = str(schedule_row.get("gid") or "").strip()
    if len(game_id) != 10:
        raise ValueError("schedule row missing gid")
    async with semaphore:
        detail = await fetch_gamedetail(
            client, season_start_year=season_start_year, game_id=game_id
        )
    if str(detail.get("stt") or "") != "Final" and str(detail.get("st") or "") != "3":
        raise ValueError(f"game {game_id} not final: {detail.get('stt')}")
    source_url = gamedetail_url(season_start_year, game_id)
    fetched_at = _now_iso()
    return (
        _game_row(
            detail,
            season_start_year=season_start_year,
            fetched_at=fetched_at,
            source_url=source_url,
        ),
        flatten_gamedetail_player_rows(
            detail,
            season_start_year=season_start_year,
            fetched_at=fetched_at,
            source_url=source_url,
        ),
    )


def _batched(rows: Sequence[dict[str, Any]], size: int) -> Iterable[Sequence[dict[str, Any]]]:
    for offset in range(0, len(rows), size):
        yield rows[offset : offset + size]


def _season_rows(rows: Sequence[dict[str, Any]]) -> tuple[str | None, str | None]:
    dates = sorted(str(row.get("gdte")) for row in rows if row.get("gdte"))
    if not dates:
        return None, None
    return dates[0], dates[-1]


def _coverage_row(
    *,
    season_start_year: int,
    season_code: int,
    game_type_prefixes: Sequence[str],
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
        game_type_prefixes=",".join(game_type_prefixes),
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
    game_type_prefixes: Sequence[str],
    concurrency: int,
) -> LoadSummary:
    migrate(engine)
    timeout = httpx.Timeout(connect=10.0, read=60.0, write=30.0, pool=30.0)
    headers = {"user-agent": PUBLIC_BROWSER_USER_AGENT, "accept": "application/json"}
    semaphore = asyncio.Semaphore(concurrency)
    summaries: list[CoverageRow] = []
    async with httpx.AsyncClient(timeout=timeout, headers=headers) as client:
        for start_year in range(start_season, end_season + 1):
            season_code = season_code_for_start_year(start_year)
            scheduled = await fetch_season_games(
                client,
                season_start_year=start_year,
                game_type_prefixes=game_type_prefixes,
            )
            scheduled = sorted(scheduled, key=lambda row: str(row.get("gid") or ""))
            loaded_games = 0
            loaded_player_rows = 0
            failed_games = 0
            first_game_date, last_game_date = _season_rows(scheduled)
            for batch in _batched(scheduled, max(concurrency * 2, concurrency)):
                results = await asyncio.gather(
                    *(
                        _load_one_game(
                            client,
                            row,
                            season_start_year=start_year,
                            semaphore=semaphore,
                        )
                        for row in batch
                    ),
                    return_exceptions=True,
                )
                await asyncio.sleep(0.75)
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
                game_type_prefixes=game_type_prefixes,
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


def _parse_game_type_prefixes(value: str) -> tuple[str, ...]:
    values = tuple(part.strip() for part in value.split(",") if part.strip())
    if not values:
        raise argparse.ArgumentTypeError("at least one game type prefix is required")
    for part in values:
        if len(part) != 3 or not part.isdigit():
            raise argparse.ArgumentTypeError(f"game type prefix must be 3 digits (got {part!r})")
    return values


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Load public NBA history into Postgres")
    parser.add_argument("--start-season", type=int, default=DEFAULT_START_SEASON)
    parser.add_argument("--end-season", type=int, default=DEFAULT_END_SEASON)
    parser.add_argument(
        "--game-type-prefixes",
        type=_parse_game_type_prefixes,
        default=DEFAULT_GAME_TYPE_PREFIXES,
        help="Comma-separated NBA game-id prefixes (default: 002,004 regular+playoffs).",
    )
    parser.add_argument("--concurrency", type=int, default=6)
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
        game_type_prefixes=args.game_type_prefixes,
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
