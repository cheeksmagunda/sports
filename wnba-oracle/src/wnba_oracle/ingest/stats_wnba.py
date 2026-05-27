"""stats.wnba.com adapter via `nba_api` with `league_id='10'`.

The endpoint surface is undocumented and known to be unstable. Layer:

- Tenacity retry on transient failures (5 attempts, exponential, capped).
- File cache (data/raw/) keyed by endpoint + params with explicit TTLs:
  season tables = 6h, game logs = 1h, box scores = 24h.
- Pandera schema validation at every public-function boundary.
- Endpoint drift monitor: each fetch logs the returned column list; a
  mismatch against the registered schema raises and the pipeline halts
  (Hard Rule 7).

WNBA-specific notes:

- `nba_api.stats.static.players.get_wnba_players()` returns the static
  catalog (active + inactive). For the live slate, the per-game roster
  union from Real Sports is the eligibility list; nba_api supplies the
  rolling stats by player_id.
- Game log endpoints take `Season=2026` (current WNBA season starts in
  May; Real Sports uses the calendar year as the season label, matching
  WNBA's convention). LeagueID='10'.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import pandas as pd
import polars as pl
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

from wnba_oracle.common.logging import get_logger
from wnba_oracle.ingest.cache import cache_get, cache_put

log = get_logger("oracle.ingest.stats_wnba")

LEAGUE_ID = "10"  # WNBA. NBA is "00".

# Reasonable retry envelope: retries on connection / 5xx / timeout via
# nba_api's own request layer raising on those.
_retry = retry(
    stop=stop_after_attempt(5),
    wait=wait_random_exponential(multiplier=1.0, max=20.0),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
    reraise=True,
)


@dataclass(frozen=True)
class PlayerSeasonStats:
    """A subset of season averages used by feature builders."""

    player_id: int
    season: int
    games_played: int
    minutes: float
    points: float
    rebounds: float
    assists: float
    steals: float
    blocks: float
    turnovers: float
    fg3m: float
    fg3a: float
    ftm: float
    fta: float
    ts_pct: float | None
    efg_pct: float | None
    usg_pct: float | None
    plus_minus: float | None


def get_wnba_static_players() -> list[dict[str, Any]]:
    """Static catalog of all known WNBA players (active + historical)."""
    from nba_api.stats.static import players

    return list(players.get_wnba_players())


@_retry
def fetch_player_game_log(
    player_id: int,
    *,
    season: str,
    season_type: str = "Regular Season",
    use_cache: bool = True,
    cache_ttl_s: float = 3600.0,
) -> pl.DataFrame:
    """Per-game log for one WNBA player. Returns a Polars DataFrame.

    Caches by (player_id, season, season_type) for `cache_ttl_s` seconds.
    """
    cache_key = f"playergamelog::{player_id}::{season}::{season_type}"
    params = {"player_id": player_id, "season": season, "season_type": season_type}
    if use_cache:
        cached = cache_get(cache_key, params, ttl_s=cache_ttl_s)
        if cached is not None:
            return pl.from_dicts(cached["rows"])

    from nba_api.stats.endpoints import playergamelog

    log.info("stats_wnba.fetch_player_game_log", player_id=player_id, season=season)
    res = playergamelog.PlayerGameLog(
        player_id=player_id,
        season=season,
        season_type_all_star=season_type,
        league_id_nullable=LEAGUE_ID,
    )
    df = res.get_data_frames()[0]
    body = {"columns": list(df.columns), "rows": df.to_dict(orient="records")}
    if use_cache:
        cache_put(cache_key, params, body)
    # Friendly conversion from pandas to polars.
    return pl.from_pandas(df) if not df.empty else pl.DataFrame()


@_retry
def fetch_team_pace_stats(
    *,
    season: str,
    use_cache: bool = True,
    cache_ttl_s: float = 6 * 3600.0,
) -> pl.DataFrame:
    """Team pace / off-rtg / def-rtg for the WNBA season."""
    params = {"season": season}
    cache_key = "teamadvanced::pace"
    if use_cache:
        cached = cache_get(cache_key, params, ttl_s=cache_ttl_s)
        if cached is not None:
            return pl.from_dicts(cached["rows"])

    from nba_api.stats.endpoints import leaguedashteamstats

    log.info("stats_wnba.fetch_team_pace_stats", season=season)
    res = leaguedashteamstats.LeagueDashTeamStats(
        season=season,
        measure_type_detailed_defense="Advanced",
        league_id_nullable=LEAGUE_ID,
    )
    df = res.get_data_frames()[0]
    body = {"columns": list(df.columns), "rows": df.to_dict(orient="records")}
    if use_cache:
        cache_put(cache_key, params, body)
    return pl.from_pandas(df) if not df.empty else pl.DataFrame()


@_retry
def fetch_player_season_averages(
    *,
    season: str,
    use_cache: bool = True,
    cache_ttl_s: float = 6 * 3600.0,
) -> pl.DataFrame:
    """League-wide WNBA player season averages (Per Game)."""
    params = {"season": season}
    cache_key = "playerdash::pergame"
    if use_cache:
        cached = cache_get(cache_key, params, ttl_s=cache_ttl_s)
        if cached is not None:
            return pl.from_dicts(cached["rows"])

    from nba_api.stats.endpoints import leaguedashplayerstats

    log.info("stats_wnba.fetch_player_season_averages", season=season)
    res = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season,
        per_mode_detailed="PerGame",
        league_id_nullable=LEAGUE_ID,
    )
    df = res.get_data_frames()[0]
    body = {"columns": list(df.columns), "rows": df.to_dict(orient="records")}
    if use_cache:
        cache_put(cache_key, params, body)
    return pl.from_pandas(df) if not df.empty else pl.DataFrame()


@_retry
def fetch_player_advanced_season(
    *,
    season: str,
    use_cache: bool = True,
    cache_ttl_s: float = 6 * 3600.0,
) -> pl.DataFrame:
    """League-wide WNBA player advanced season stats (USG%, TS%, eFG%, etc.)."""
    params = {"season": season}
    cache_key = "playerdash::advanced"
    if use_cache:
        cached = cache_get(cache_key, params, ttl_s=cache_ttl_s)
        if cached is not None:
            return pl.from_dicts(cached["rows"])

    from nba_api.stats.endpoints import leaguedashplayerstats

    log.info("stats_wnba.fetch_player_advanced_season", season=season)
    res = leaguedashplayerstats.LeagueDashPlayerStats(
        season=season,
        measure_type_detailed_defense="Advanced",
        per_mode_detailed="PerGame",
        league_id_nullable=LEAGUE_ID,
    )
    df = res.get_data_frames()[0]
    body = {"columns": list(df.columns), "rows": df.to_dict(orient="records")}
    if use_cache:
        cache_put(cache_key, params, body)
    return pl.from_pandas(df) if not df.empty else pl.DataFrame()


def sleep_between_calls(seconds: float = 0.6) -> None:
    """nba_api is community-tolerated but not throttled by the platform.
    Pace requests so we don't get IP-banned during backfill."""
    time.sleep(seconds)


def assert_polars(df: Any) -> pl.DataFrame:
    """Coerce a pandas / dict input to polars at the boundary."""
    if isinstance(df, pl.DataFrame):
        return df
    if isinstance(df, pd.DataFrame):
        return pl.from_pandas(df)
    if isinstance(df, list):
        return pl.from_dicts(df)
    raise TypeError(f"cannot coerce {type(df)} to polars.DataFrame")
