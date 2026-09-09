from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import polars as pl
import pytest

from nfl_oracle.recommendations.context import (
    HistoricalContext,
    build_context,
    crosswalk_external_ids,
    enrich_historical_rows,
    resolve_identity,
)
from nfl_oracle.recommendations.schema import Candidate, Contest, EvidenceClock, Game, Slate
from nfl_oracle.recommendations.sources import (
    ContextSnapshot,
    Venue,
    capture_rows,
    collect_nflverse,
    collect_nws,
    forecast_features,
    load_venues,
)

NOW = datetime(2026, 9, 9, 15, tzinfo=UTC)


def _rows() -> dict[str, list[dict[str, object]]]:
    return {
        "schedules": [
            {
                "game_id": "2026_01_NE_SEA",
                "season": 2026,
                "week": 1,
                "gameday": "2026-09-06",
                "gametime": "13:00",
                "home_team": "SEA",
                "away_team": "NE",
            },
            {
                "game_id": "2026_02_NE_BUF",
                "season": 2026,
                "week": 2,
                "gameday": "2026-09-13",
                "gametime": "13:00",
                "home_team": "BUF",
                "away_team": "NE",
            },
            # This later row must never contribute to a week-two context.
            {
                "game_id": "2026_03_NE_MIA",
                "season": 2026,
                "week": 3,
                "gameday": "2026-09-20",
                "gametime": "13:00",
                "home_team": "MIA",
                "away_team": "NE",
            },
        ],
        "rosters": [
            {
                "season": 2026,
                "week": 2,
                "team": "NE",
                "position": "WR",
                "full_name": "José Smith",
                "gsis_id": "00-0000001",
            }
        ],
        "player_stats": [
            {
                "player_id": "00-0000001",
                "game_id": "2026_01_NE_SEA",
                "attempts": 0,
                "targets": 8,
                "receptions": 6,
                "receiving_yards": 88,
                "season": 2026,
                "week": 1,
            },
            {
                "player_id": "00-0000001",
                "game_id": "2026_03_NE_MIA",
                "attempts": 0,
                "targets": 99,
                "receptions": 99,
                "receiving_yards": 999,
                "season": 2026,
                "week": 3,
            },
        ],
        "team_stats": [
            {
                "team": "NE",
                "opponent_team": "SEA",
                "game_id": "2026_01_NE_SEA",
                "attempts": 30,
                "carries": 24,
                "sacks_suffered": 2,
                "passing_yards": 250,
                "rushing_yards": 110,
                "season": 2026,
                "week": 1,
            }
        ],
        "depth_charts": [
            {
                "dt": "2026-09-08T12:00:00Z",
                "team": "NE",
                "gsis_id": "00-0000001",
                "pos_rank": 1,
                "pos_slot": 1,
            }
        ],
    }


def _snapshot(*, captured_at: datetime = NOW) -> ContextSnapshot:
    return ContextSnapshot(
        sources={
            name: capture_rows(name, rows, captured_at=captured_at)
            for name, rows in _rows().items()
        }
    )


def _slate() -> Slate:
    clock = EvidenceClock(source_available_at=NOW, captured_at=NOW)
    kickoff = datetime(2026, 9, 13, 17, tzinfo=UTC)
    return Slate(
        contest=Contest(
            contest_id=2141,
            day=kickoff.date(),
            end_day=kickoff.date(),
            slot_multipliers=(2, 1.8, 1.6, 1.4, 1.2),
            is_locked=False,
            is_finalized=False,
            clock=clock,
            evidence_sha256="a" * 64,
        ),
        games=(
            Game(
                game_id=19457,
                season=2026,
                kickoff_at=kickoff,
                home_team_id=2,
                away_team_id=1,
                home_team="BUF",
                away_team="NE",
                status="scheduled",
            ),
        ),
        candidates=tuple(
            Candidate(
                player_id=i,
                game_id=19457,
                team_id=1,
                name="José Smith" if i == 1 else f"Player {i}",
                position="WR",
                team="NE",
                opponent="BUF",
                injury_status="Active" if i == 1 else "Questionable",
                card_boost=0,
                clock=clock,
            )
            for i in range(1, 6)
        ),
        captured_at=NOW,
        source_hashes=("b" * 64,),
        pool_roster_count=5,
        pool_search_matched_count=5,
    )


def test_nflverse_capture_uses_all_requested_seasons_and_hashes_immutable_rows() -> None:
    calls: list[tuple[str, object]] = []

    def frame(name: str, rows: list[dict[str, object]]) -> object:
        calls.append((name, [2025, 2026]))
        return pl.DataFrame(rows)

    loader = SimpleNamespace(
        load_schedules=lambda seasons: frame(
            "schedule", [{"game_id": "g", "season": 2025, "extra": "drop"}]
        ),
        load_rosters_weekly=lambda seasons: frame(
            "roster", [{"season": 2025, "week": 1, "gsis_id": "p"}]
        ),
        load_player_stats=lambda seasons: frame("player", [{"player_id": "p", "season": 2025}]),
        load_team_stats=lambda seasons: frame("team", [{"team": "NE", "season": 2025}]),
        load_depth_charts=lambda seasons: frame("depth", [{"gsis_id": "p", "dt": "2026-09-01"}]),
    )
    snapshot = collect_nflverse([2025, 2026], loader=loader, clock=lambda: NOW)

    assert {name for name, _ in calls} == {"schedule", "roster", "player", "team", "depth"}
    assert all(seasons == [2025, 2026] for _, seasons in calls)
    assert "extra" not in snapshot.sources["schedules"].rows[0]
    assert snapshot.sources["schedules"].clock.captured_at == NOW
    assert snapshot.sources["schedules"].sha256


def test_context_snapshot_is_content_addressed_and_venue_config_is_extensible(
    tmp_path: Path,
) -> None:
    snapshot = _snapshot()
    path = snapshot.save(tmp_path)
    assert path == snapshot.save(tmp_path)
    assert ContextSnapshot.load(path) == snapshot

    venue_path = tmp_path / "venues.json"
    venue_path.write_text(
        json.dumps(
            {
                "venues": {
                    "BUF00": {
                        "name": "Highmark Stadium",
                        "latitude": 42.7738,
                        "longitude": -78.7870,
                        "coordinate_source": "https://example.test/venues/buf",
                        "verified_at": "2026-09-01T00:00:00Z",
                    }
                }
            }
        )
    )
    venues = load_venues(venue_path)
    assert venues["BUF00"].name == "Highmark Stadium"


def test_identity_crosswalk_requires_one_effective_stable_id() -> None:
    rosters = tuple(_rows()["rosters"])
    assert resolve_identity("Jose Smith", "NE", "WR", 2026, 2, rosters) == "00-0000001"
    assert crosswalk_external_ids(
        [(19457, "José Smith", "NE", "WR")], season=2026, week=2, rosters=rosters
    ) == {19457: "00-0000001"}

    ambiguous = rosters + ({**rosters[0], "gsis_id": "00-0000002"},)
    with pytest.raises(ValueError, match="identity_ambiguous"):
        resolve_identity("Jose Smith", "NE", "WR", 2026, 2, ambiguous)


def test_historical_features_are_time_safe_and_include_role_pace_and_rest() -> None:
    context = HistoricalContext(_snapshot())
    features = context.features(
        "00-0000001",
        "NE",
        "BUF",
        before=datetime(2026, 9, 9, 15, tzinfo=UTC),
        kickoff=datetime(2026, 9, 13, 17, tzinfo=UTC),
        season=2026,
    )
    assert features["history_game_count"] == 1
    assert features["prior_receiving_yards"] == 88
    assert features["team_pace_prior"] == 56
    assert features["days_rest"] == 7

    bundle = build_context(_slate(), _snapshot(), NOW)
    player = bundle.features_by_player[1]
    assert bundle.external_ids[1] == "00-0000001"
    assert player["depth_rank"] == 1
    assert player["depth_first_team"] == 1
    assert player["injury_active"] == 1
    assert player["injury_questionable"] == 0


def test_retrospective_enrichment_keeps_actual_snapshot_clock() -> None:
    target = SimpleNamespace(
        player_id=11,
        game_id=9001,
        kickoff_at=datetime(2026, 9, 13, 17, tzinfo=UTC),
    )
    result = enrich_historical_rows(
        [target],
        _snapshot(captured_at=NOW + timedelta(days=5)),
        metadata={
            (11, 9001): {
                "name": "José Smith",
                "team": "NE",
                "opponent": "BUF",
                "position": "WR",
                "season": 2026,
                "week": 2,
            }
        },
    )
    assert len(result.rows) == 1
    enriched = result.rows[0]
    assert enriched.evidence_mode == "retrospective_reconstructed"
    assert enriched.clock.captured_at == NOW + timedelta(days=5)
    assert enriched.clock.captured_at > target.kickoff_at
    assert enriched.features["prior_receiving_yards"] == 88
    assert not result.excluded


def test_nws_forecast_is_predecision_and_venue_coordinates_are_verified() -> None:
    venue = Venue(
        stadium_id="BUF00",
        name="Highmark Stadium",
        latitude=42.7738,
        longitude=-78.7870,
        coordinate_source="https://example.test/venues/buf",
        verified_at=NOW - timedelta(days=1),
    )

    class Response:
        def __init__(self, payload: dict[str, object]) -> None:
            self.payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return self.payload

    class Client:
        def get(self, url: str) -> Response:
            if "/points/" in url:
                return Response(
                    {
                        "properties": {
                            "forecastHourly": "https://api.weather.gov/gridpoints/BUF/1,1/forecast/hourly"
                        }
                    }
                )
            return Response(
                {
                    "properties": {
                        "generatedAt": "2026-09-09T14:00:00Z",
                        "periods": [
                            {
                                "startTime": "2026-09-13T17:00:00Z",
                                "endTime": "2026-09-13T18:00:00Z",
                                "temperature": 72,
                                "temperatureUnit": "F",
                                "windSpeed": "10 mph",
                                "probabilityOfPrecipitation": {"value": 20},
                            }
                        ],
                    }
                }
            )

    source = collect_nws(venue, client=Client(), clock=lambda: NOW)
    features = forecast_features(source, datetime(2026, 9, 13, 17, tzinfo=UTC), NOW)
    assert features == {
        "weather_temp_f": 72.0,
        "weather_wind_mph": 10.0,
        "weather_precip_prob": 0.2,
    }

    with pytest.raises(ValueError, match="future_forecast"):
        future = source.model_copy(
            update={"rows": ({**source.rows[0], "forecast_generated_at": "2026-09-10T00:00:00Z"},)}
        )
        forecast_features(future, datetime(2026, 9, 13, 17, tzinfo=UTC), NOW)
