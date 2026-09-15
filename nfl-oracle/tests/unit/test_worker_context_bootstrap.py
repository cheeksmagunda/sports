"""Worker context cold-start for Week-2 / TNF freezes (no baked-in artifacts)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from nfl_oracle.recommendations import cli as worker_cli
from nfl_oracle.recommendations.schema import Candidate, Contest, EvidenceClock, Game, Slate
from nfl_oracle.recommendations.sources import ContextSnapshot, capture_rows


NOW = datetime(2026, 9, 17, 20, tzinfo=UTC)


def _slate(*, kickoff: datetime = NOW + timedelta(hours=4)) -> Slate:
    clock = EvidenceClock(source_available_at=NOW, captured_at=NOW)
    game = Game(
        game_id=7001,
        season=2026,
        kickoff_at=kickoff,
        home_team_id=1,
        away_team_id=2,
        home_team="BUF",
        away_team="DET",
        status="scheduled",
    )
    candidate = Candidate(
        player_id=1,
        game_id=game.game_id,
        team_id=1,
        name="P1",
        position="WR",
        team="BUF",
        opponent="DET",
        injury_status="Active",
        card_boost=0.0,
        clock=clock,
    )
    return Slate(
        contest=Contest(
            contest_id=9001,
            day=kickoff.date(),
            end_day=kickoff.date(),
            slot_multipliers=(2.0, 1.8, 1.6, 1.4, 1.2),
            is_locked=False,
            is_finalized=False,
            clock=clock,
            evidence_sha256="a" * 64,
        ),
        games=(game,),
        candidates=(candidate,),
        captured_at=NOW,
        source_hashes=("b" * 64,),
        pool_roster_count=1,
        pool_search_matched_count=1,
    )


def _snapshot_with_schedule(*, include_tnf: bool) -> ContextSnapshot:
    rows = []
    if include_tnf:
        rows.append(
            {
                "game_id": "2026_02_DET_BUF",
                "season": 2026,
                "week": 2,
                "gameday": "2026-09-17",
                "home_team": "BUF",
                "away_team": "DET",
                "stadium_id": "BUF00",
                "stadium": "Highmark Stadium",
            }
        )
    else:
        rows.append(
            {
                "game_id": "2025_18_BUF_MIA",
                "season": 2025,
                "week": 18,
                "gameday": "2026-01-04",
                "home_team": "MIA",
                "away_team": "BUF",
                "stadium_id": "MIA00",
                "stadium": "Hard Rock Stadium",
            }
        )
    return ContextSnapshot(
        sources={
            "schedules": capture_rows("schedules", rows, captured_at=NOW, status="available"),
        }
    )


def test_latest_context_returns_none_when_absent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NFL_CONTEXT_SNAPSHOT", raising=False)
    assert worker_cli._latest_context(tmp_path) is None


def test_latest_context_explicit_missing_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NFL_CONTEXT_SNAPSHOT", str(tmp_path / "missing.json"))
    with pytest.raises(RuntimeError, match="NFL_CONTEXT_SNAPSHOT_missing"):
        worker_cli._latest_context(tmp_path)


def test_schedules_cover_slate_requires_exact_tnf_row() -> None:
    slate = _slate()
    assert worker_cli._schedules_cover_slate(_snapshot_with_schedule(include_tnf=True), slate)
    assert not worker_cli._schedules_cover_slate(_snapshot_with_schedule(include_tnf=False), slate)


def test_load_context_bootstraps_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("NFL_CONTEXT_SNAPSHOT", raising=False)
    project = tmp_path / "nfl-oracle"
    config = project / "config"
    config.mkdir(parents=True)
    # Minimal venue file so weather path can load venues.
    (config / "NFLconfigvenues.json").write_text(
        '[{"stadium_id":"BUF00","name":"Highmark Stadium","latitude":42.77,'
        '"longitude":-78.78,"coordinate_source":"https://example.com/x",'
        '"verified_at":"2026-09-08T00:00:00Z"}]'
    )
    calls: list[list[int]] = []

    def fake_collect(seasons: list[int], **kwargs: object) -> ContextSnapshot:
        calls.append(list(seasons))
        return _snapshot_with_schedule(include_tnf=True)

    monkeypatch.setattr(
        "nfl_oracle.recommendations.sources.collect_nflverse", fake_collect, raising=True
    )
    monkeypatch.setattr(
        worker_cli,
        "add_weather_for_slate",
        lambda snapshot, slate, venues, client, clock: snapshot,
    )

    loaded = worker_cli._load_context(project, _slate(), NOW)
    assert calls == [[2024, 2025, 2026]]
    assert worker_cli._schedules_cover_slate(loaded, _slate())
    saved = list((project / "data" / "artifacts" / "context").glob("*.json"))
    assert len(saved) == 1


def test_load_context_refreshes_when_schedules_miss_slate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("NFL_CONTEXT_SNAPSHOT", raising=False)
    project = tmp_path / "nfl-oracle"
    config = project / "config"
    config.mkdir(parents=True)
    (config / "NFLconfigvenues.json").write_text(
        '[{"stadium_id":"BUF00","name":"Highmark Stadium","latitude":42.77,'
        '"longitude":-78.78,"coordinate_source":"https://example.com/x",'
        '"verified_at":"2026-09-08T00:00:00Z"}]'
    )
    stale = _snapshot_with_schedule(include_tnf=False)
    stale.save(project / "data" / "artifacts")
    calls: list[str] = []

    def fake_collect(seasons: list[int], **kwargs: object) -> ContextSnapshot:
        calls.append("bootstrap")
        return _snapshot_with_schedule(include_tnf=True)

    monkeypatch.setattr(
        "nfl_oracle.recommendations.sources.collect_nflverse", fake_collect, raising=True
    )
    monkeypatch.setattr(
        worker_cli,
        "add_weather_for_slate",
        lambda snapshot, slate, venues, client, clock: snapshot,
    )

    loaded = worker_cli._load_context(project, _slate(), NOW)
    assert calls == ["bootstrap"]
    assert worker_cli._schedules_cover_slate(loaded, _slate())
