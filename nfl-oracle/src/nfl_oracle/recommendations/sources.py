"""Public NFL context captures with immutable, honest observation clocks.

nflreadpy: https://nflreadpy.nflverse.com/api/load_functions/
NWS: https://www.weather.gov/documentation/services-web-api
Historical downloads are revised data captured now, not historical prelock evidence.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from oracle_core.artifacts import atomic_write_json
from pydantic import Field, field_validator, model_validator

from nfl_oracle.recommendations.schema import EvidenceClock, Record, fingerprint, utc

Row = dict[str, Any]


class SourceSnapshot(Record):
    source: str
    clock: EvidenceClock
    rows: tuple[Row, ...]
    sha256: str
    status: str = "available"
    revision_policy: str = "captured_now_not_point_in_time_archive"
    effective_season: int | None = None
    effective_week: int | None = None
    effective_from: datetime | None = None
    effective_to: datetime | None = None
    availability_basis: str = "captured_at"

    @field_validator("effective_from", "effective_to", mode="before")
    @classmethod
    def optional_aware(cls, value: datetime | str | None) -> datetime | None:
        if value is None:
            return None
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else value
        return utc(parsed)

    @model_validator(mode="after")
    def integrity(self) -> SourceSnapshot:
        if fingerprint(self.rows) != self.sha256:
            raise ValueError("context_source_integrity")
        return self


class ContextSnapshot(Record):
    sources: dict[str, SourceSnapshot]

    def save(self, root: Path) -> Path:
        body = self.model_dump(mode="json")
        path = root / "context" / f"{fingerprint(body)}.json"
        if not path.exists():
            atomic_write_json(path, body, mode=0o600)
        return path

    @classmethod
    def load(cls, path: Path) -> ContextSnapshot:
        body = json.loads(path.read_text())
        if path.stem != fingerprint(body):
            raise ValueError("context_manifest_integrity")
        return cls.model_validate(body)


def _json_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {str(k): _json_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(v) for v in value]
    return value


def _canonical_rows(rows: list[Row]) -> tuple[Row, ...]:
    """Make a capture independent of the upstream frame's row ordering."""
    clean = [_json_value(row) for row in rows]
    return tuple(sorted(clean, key=lambda row: json.dumps(row, sort_keys=True)))


def capture_rows(
    source: str,
    rows: list[Row],
    *,
    captured_at: datetime,
    status: str = "available",
    effective_season: int | None = None,
    effective_week: int | None = None,
    effective_from: datetime | None = None,
    effective_to: datetime | None = None,
    revision_policy: str = "captured_now_not_point_in_time_archive",
    availability_basis: str = "captured_at",
) -> SourceSnapshot:
    captured_at = utc(captured_at)
    clean = _canonical_rows(rows)
    return SourceSnapshot(
        source=source,
        clock=EvidenceClock(source_available_at=captured_at, captured_at=captured_at),
        rows=clean,
        sha256=fingerprint(clean),
        status=status,
        effective_season=effective_season,
        effective_week=effective_week,
        effective_from=effective_from,
        effective_to=effective_to,
        revision_policy=revision_policy,
        availability_basis=availability_basis,
    )


# Only these historical performance fields are exposed. No current game finals,
# closing market values, retrospective weather or postgame starting-QB fields.
PLAYER_STATS = (
    "player_id",
    "player_display_name",
    "position",
    "season",
    "week",
    "season_type",
    "game_id",
    "team",
    "opponent_team",
    "attempts",
    "passing_yards",
    "carries",
    "rushing_yards",
    "targets",
    "receptions",
    "receiving_yards",
    "target_share",
    "air_yards_share",
    "passing_epa",
    "rushing_epa",
    "receiving_epa",
    "def_tackles_solo",
    "def_sacks",
    "def_interceptions",
    "fg_att",
    "fg_made",
    "pat_att",
    "pat_made",
)
TEAM_STATS = (
    "season",
    "week",
    "season_type",
    "game_id",
    "team",
    "opponent_team",
    "attempts",
    "carries",
    "sacks_suffered",
    "passing_yards",
    "rushing_yards",
)
SCHEDULE = (
    "game_id",
    "season",
    "week",
    "game_type",
    "gameday",
    "gametime",
    "home_team",
    "away_team",
    "stadium_id",
    "stadium",
    "roof",
    "surface",
    "location",
)
ROSTER = (
    "season",
    "week",
    "team",
    "position",
    "depth_chart_position",
    "full_name",
    "gsis_id",
    "espn_id",
    "status",
    "status_description_abbr",
)
DEPTH = ("dt", "team", "gsis_id", "player_name", "pos_abb", "pos_rank", "pos_slot")


def collect_nflverse(
    seasons: list[int],
    *,
    clock: Callable[[], datetime] | None = None,
    loader: Any = None,
    current_week: Mapping[int, int] | None = None,
) -> ContextSnapshot:
    """Fetch all sources independently; unavailable sources remain explicit.

    The package HTTP client has a bounded timeout. Disable its opaque cache so
    each successful source's capture clock describes this request.
    """
    if not seasons:
        raise ValueError("seasons_required")
    now = clock or (lambda: datetime.now(UTC))
    module: Any = loader
    if loader is None:
        import nflreadpy as nflreadpy_package  # type: ignore[import-untyped]

        module = nflreadpy_package

        # nflreadpy 0.1.5 exposes configuration under ``nflreadpy.config``.
        # Keep the fallback for a compatible loader supplied by tests or a
        # later package version, while never silently accepting its cache.
        update_config = getattr(module, "update_config", None)
        if not callable(update_config):
            config = getattr(module, "config", None)
            update_config = getattr(config, "update_config", None)
        if not callable(update_config):
            raise RuntimeError("nflreadpy_configuration_unavailable")
        update_config(timeout=30, cache_mode="off", verbose=False)
    sources: dict[str, SourceSnapshot] = {}
    jobs = {
        "schedules": (module.load_schedules, seasons, SCHEDULE),
        "rosters": (module.load_rosters_weekly, seasons, ROSTER),
        "player_stats": (module.load_player_stats, seasons, PLAYER_STATS),
        "team_stats": (module.load_team_stats, seasons, TEAM_STATS),
        "depth_charts": (module.load_depth_charts, seasons, DEPTH),
    }
    for name, (function, years, columns) in jobs.items():
        if name == "rosters":
            schedule_snapshot = sources.get("schedules")
            sources[name] = _collect_rosters(
                module,
                years,
                columns,
                schedule_rows=schedule_snapshot.rows if schedule_snapshot is not None else (),
                current_week=current_week,
                captured_at=utc(now()),
            )
            continue
        # nflreadpy can combine compatible seasons for some endpoints but
        # raises on schema changes for others, especially depth charts. Fetch
        # each requested season independently so a successful 2024/2025
        # historical source is never discarded because an early 2026 release
        # is unavailable.
        if len(years) > 1 and name != "schedules":
            rows: list[Row] = []
            successful = 0
            for year in years:
                try:
                    rows.extend(_select_frame(function([year]), columns))
                    successful += 1
                except Exception:
                    continue
            sources[name] = capture_rows(
                f"nflreadpy.{function.__name__}",
                rows,
                captured_at=now(),
                status=(
                    "available"
                    if rows and successful == len(years)
                    else "partial"
                    if rows
                    else "unavailable"
                ),
            )
            continue
        try:
            frame = function(years)
            # Early-season current stats may not exist yet. Preserve completed
            # seasons independently instead of discarding their whole history.
            rows = frame.select([c for c in columns if c in frame.columns]).to_dicts()
            sources[name] = capture_rows(
                f"nflreadpy.{function.__name__}",
                rows,
                captured_at=now(),
                status="available" if rows else "empty",
            )
        except Exception:
            if len(years) > 1:
                rows = []
                successful = 0
                for year in years:
                    try:
                        frame = function([year])
                        rows.extend(
                            frame.select([c for c in columns if c in frame.columns]).to_dicts()
                        )
                        successful += 1
                    except Exception:
                        continue
                sources[name] = capture_rows(
                    f"nflreadpy.{function.__name__}",
                    rows,
                    captured_at=now(),
                    status=(
                        "available"
                        if rows and successful == len(years)
                        else "partial"
                        if rows
                        else "unavailable"
                    ),
                )
            else:
                sources[name] = capture_rows(
                    f"nflreadpy.{function.__name__}", [], captured_at=now(), status="unavailable"
                )
    return ContextSnapshot(sources=sources)


def _schedule_effective_week(rows: Iterable[Row], season: int, at: datetime) -> int | None:
    target = utc(at).date().isoformat()
    upcoming: list[tuple[str, int]] = []
    prior: list[tuple[str, int]] = []
    for row in rows:
        if row.get("season") != season or row.get("game_type") not in {"REG", "POST"}:
            continue
        gameday = str(row.get("gameday", ""))
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", gameday):
            continue
        week = row.get("week")
        if not isinstance(week, int):
            try:
                week = int(cast(str | float, week))
            except (TypeError, ValueError):
                continue
        (upcoming if gameday >= target else prior).append((gameday, week))
    if upcoming:
        return min(upcoming)[1]
    return max(prior)[1] if prior else None


def _select_frame(frame: Any, columns: tuple[str, ...]) -> list[Row]:
    return cast(list[Row], frame.select([c for c in columns if c in frame.columns]).to_dicts())


def _collect_rosters(
    module: Any,
    years: list[int],
    columns: tuple[str, ...],
    *,
    schedule_rows: Iterable[Row],
    current_week: Mapping[int, int] | None,
    captured_at: datetime,
) -> SourceSnapshot:
    """Prefer weekly rosters, then use a current seasonal roster explicitly.

    A seasonal fallback is assigned only to the current requested season and
    effective schedule week. It is never presented as a historical weekly row.
    """
    function = module.load_rosters_weekly
    rows: list[Row] = []
    successful = 0
    seasonal_fallback = False
    for season in years:
        try:
            rows.extend(_select_frame(function([season]), columns))
            successful += 1
            continue
        except Exception:
            pass
        if season != max(years):
            continue
        seasonal = getattr(module, "load_rosters", None)
        if not callable(seasonal):
            continue
        try:
            fallback_rows = _select_frame(seasonal([season]), columns)
        except Exception:
            continue
        week = (current_week or {}).get(season) or _schedule_effective_week(
            schedule_rows, season, captured_at
        )
        if week is None:
            continue
        for row in fallback_rows:
            row["week"] = week
            row["week_source"] = "schedule_effective_current_week"
            row["effective_from"] = captured_at.isoformat()
            row["effective_to"] = None
        rows.extend(fallback_rows)
        seasonal_fallback = True
        successful += 1
    status = (
        "available"
        if rows and successful == len(years) and not seasonal_fallback
        else ("partial" if rows else "unavailable")
    )
    return capture_rows(
        f"nflreadpy.{function.__name__}",
        rows,
        captured_at=captured_at,
        status=status,
        effective_season=max(years) if seasonal_fallback else None,
        effective_week=(current_week or {}).get(max(years))
        or _schedule_effective_week(schedule_rows, max(years), captured_at)
        if seasonal_fallback
        else None,
        effective_from=captured_at if seasonal_fallback else None,
        revision_policy=(
            "seasonal_roster_effective_current_week_only"
            if seasonal_fallback
            else "captured_now_not_point_in_time_archive"
        ),
        availability_basis=(
            "verified_schedule_current_week" if seasonal_fallback else "captured_at"
        ),
    )


class Venue(Record):
    stadium_id: str
    name: str
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    coordinate_source: str
    verified_at: datetime
    indoor: bool = False

    _aware = field_validator("verified_at")(utc)

    @field_validator("coordinate_source")
    @classmethod
    def source_url(cls, value: str) -> str:
        if urlparse(value).scheme != "https":
            raise ValueError("venue_coordinate_source_required")
        return value


def load_venues(path: Path) -> dict[str, Venue]:
    payload = json.loads(path.read_text())
    if isinstance(payload, dict) and "venues" in payload:
        payload = payload["venues"]
    if isinstance(payload, dict):
        payload = [dict(value, stadium_id=key) for key, value in payload.items()]
    if not isinstance(payload, list):
        raise ValueError("venue_config_list_required")
    venues = [Venue.model_validate(v) for v in payload]
    result: dict[str, Venue] = {}
    for venue in venues:
        key = venue.stadium_id
        if key in result:
            key = f"{venue.stadium_id}|{venue.name}"
        if key in result:
            raise ValueError("duplicate_venue")
        result[key] = venue
    return result


def collect_nws(
    venue: Venue, *, client: httpx.Client, clock: Callable[[], datetime] | None = None
) -> SourceSnapshot:
    """Capture the NWS hourly forecast. US only; international stays unavailable.

    Caller supplies a descriptive NWS User-Agent and bounded HTTP client timeout.
    API-discovered links are constrained to the NWS HTTPS origin.
    """
    now = clock or (lambda: datetime.now(UTC))
    if venue.verified_at > now():
        raise ValueError("future_venue_verification")
    if venue.indoor:
        return capture_rows("nws", [], captured_at=now(), status="indoor")
    point = client.get(f"https://api.weather.gov/points/{venue.latitude},{venue.longitude}")
    point.raise_for_status()
    url = point.json()["properties"]["forecastHourly"]
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != "api.weather.gov":
        raise ValueError("invalid_nws_forecast_origin")
    response = client.get(url)
    response.raise_for_status()
    properties = response.json()["properties"]
    rows = [
        {
            **period,
            "forecast_generated_at": properties.get("generatedAt"),
            "stadium_id": venue.stadium_id,
            "coordinate_source": venue.coordinate_source,
        }
        for period in properties["periods"]
    ]
    return capture_rows(url, rows, captured_at=now())


def resolve_venue(venues: Mapping[str, Venue], stadium_id: str, name: str) -> Venue | None:
    """Resolve a schedule venue, including reused IDs at neutral sites."""
    direct = venues.get(stadium_id)
    if direct is not None and direct.name == name:
        return direct
    for key, venue in venues.items():
        if venue.stadium_id == stadium_id and venue.name == name:
            return venue
        if key == stadium_id and direct is None and venue.stadium_id == stadium_id:
            return venue
    return direct


def add_weather_for_slate(
    snapshot: ContextSnapshot,
    slate: Any,
    venues: Mapping[str, Venue],
    *,
    client: httpx.Client,
    clock: Callable[[], datetime] | None = None,
) -> ContextSnapshot:
    """Capture one NWS source per scheduled stadium in a recommendation slate."""
    now = clock or (lambda: datetime.now(UTC))
    schedules = snapshot.sources.get("schedules")
    if schedules is None:
        return snapshot
    sources = dict(snapshot.sources)
    for game in slate.games:
        matches = [
            row
            for row in schedules.rows
            if _json_value(row.get("season")) == game.season
            and row.get("gameday")
            == game.kickoff_at.astimezone(ZoneInfo("America/New_York")).date().isoformat()
            and str(row.get("home_team")) == game.home_team
            and str(row.get("away_team")) == game.away_team
        ]
        if len(matches) != 1:
            continue
        schedule = matches[0]
        stadium_id = str(schedule.get("stadium_id", ""))
        venue = resolve_venue(venues, stadium_id, str(schedule.get("stadium", "")))
        key = f"weather:{stadium_id}"
        if venue is None:
            sources[key] = capture_rows("nws", [], captured_at=now(), status="venue_unverified")
            continue
        try:
            sources[key] = collect_nws(venue, client=client, clock=now)
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            sources[key] = capture_rows("nws", [], captured_at=now(), status="unavailable")
    return snapshot.model_copy(update={"sources": sources})


def forecast_features(
    snapshot: SourceSnapshot, kickoff: datetime, decision_at: datetime
) -> dict[str, float]:
    snapshot.clock.assert_available(decision_at)
    if (utc(decision_at) - snapshot.clock.captured_at).total_seconds() > 6 * 3600:
        return {}
    for row in snapshot.rows:
        start = utc(datetime.fromisoformat(str(row["startTime"])))
        end = utc(datetime.fromisoformat(str(row["endTime"])))
        if not start <= utc(kickoff) < end:
            continue
        generated = row.get("forecast_generated_at")
        if generated and utc(datetime.fromisoformat(str(generated))) > utc(decision_at):
            raise ValueError("future_forecast")
        features: dict[str, float] = {}
        temp = row.get("temperature")
        if isinstance(temp, (int, float)) and row.get("temperatureUnit") in {"F", "C"}:
            features["weather_temp_f"] = float(
                temp if row["temperatureUnit"] == "F" else temp * 9 / 5 + 32
            )
        wind = str(row.get("windSpeed", ""))
        if re.fullmatch(r"\d+(?: to \d+)? mph", wind):
            numbers = [float(v) for v in re.findall(r"\d+", wind)]
            features["weather_wind_mph"] = sum(numbers) / len(numbers)
        probability = row.get("probabilityOfPrecipitation")
        if isinstance(probability, Mapping) and isinstance(probability.get("value"), (int, float)):
            value = float(probability["value"])
            if 0 <= value <= 100:
                features["weather_precip_prob"] = value / 100
        return features
    return {}
