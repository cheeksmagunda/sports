from __future__ import annotations

import inspect
import json
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from nfl_oracle.calendar.schedule import ScheduledGame
from nfl_oracle.contests.store import ContestStore
from nfl_oracle.recommendations import cli, weekclose
from nfl_oracle.recommendations.store import RecommendationStore, migrate
from tests.unit.test_recommendation_contracts import NOW, sample_slate

DAY = NOW.date()
NO_FREEZE_DAY = date(2026, 9, 8)
SEASON = 2026
WEEK = 1


def _week_games() -> list[ScheduledGame]:
    return [
        ScheduledGame(
            season=SEASON,
            week=WEEK,
            game_id="2026_01_AAA_BBB",
            gameday=NO_FREEZE_DAY,
            home_team="AAA",
            away_team="BBB",
        ),
        ScheduledGame(
            season=SEASON,
            week=WEEK,
            game_id="2026_01_CCC_DDD",
            gameday=DAY,
            home_team="CCC",
            away_team="DDD",
        ),
    ]


def _setup_store(tmp_path: Path) -> RecommendationStore:
    engine = create_engine(f"sqlite:///{tmp_path / 'decisions.db'}")
    migrate(engine)
    return RecommendationStore(engine, writable=True, clock=lambda: NOW)


def _freeze_five(store: RecommendationStore) -> None:
    store.freeze(
        sample_slate(),
        {"picks": [{"player_id": i} for i in range(1, 6)]},
        model_fingerprint="model-v1",
        input_fingerprint="inputs-v1",
        decision_at=NOW,
    )


def _write_replayable_contest(project: Path) -> ContestStore:
    """A finalized 5-player-pool contest with one winning entry.

    Pool: five distinct players via draftStats (values 5.0..3.0), plus the
    winner's own single-card entry re-using the top value. Zero boost
    throughout, so hindsight_best_lineup's DP reduces to sorting by value.
    """
    contest_store = ContestStore(project=project)
    contest_store.write_route(
        2141,
        "meta",
        {
            "info": {
                "isLocked": True,
                "contest": {
                    "id": 2141,
                    "sport": "nfl",
                    "day": DAY.isoformat(),
                    "endDay": DAY.isoformat(),
                    "season": SEASON,
                    "numBrawlers": 500,
                    "isFinalized": True,
                    "additionalInfo": {"lineupSize": 5},
                },
            }
        },
        source_url="test",
        http_status=200,
        captured_at=NOW,
    )
    contest_store.write_route(
        2141,
        "entries",
        {
            "entries": [
                {
                    "id": 1,
                    "rank": 1,
                    "score": "10.0",
                    "payout": 0,
                    "wager": 0,
                    "type": "general",
                    "additionalInfo": {
                        "lineup": [
                            {
                                "playerId": 101,
                                "id": 101,
                                "order": 0,
                                "multiplier": 2.0,
                                "multiplierBonus": 0.0,
                                "value": "5.0",
                                "score": "10.0",
                            }
                        ]
                    },
                }
            ]
        },
        source_url="test",
        http_status=200,
        captured_at=NOW,
    )
    players = {101: 5.0, 102: 4.5, 103: 4.0, 104: 3.5, 105: 3.0}
    contest_store.write_route(
        2141,
        "stats",
        {
            "draftStats": [
                {
                    "sectionName": "mostDrafted",
                    "players": [
                        {
                            "playerId": pid,
                            "multiplierBonus": 0.0,
                            "value": str(value),
                            "count": 10,
                        }
                        for pid, value in players.items()
                    ],
                }
            ]
        },
        source_url="test",
        http_status=200,
        captured_at=NOW,
    )
    return contest_store


def test_unresolved_week_returns_empty_punch_list(tmp_path: Path) -> None:
    result = weekclose.build_week_punch_list(_setup_store(tmp_path), [], season=SEASON, week=99)
    assert result["resolved"] is False
    assert result["punch_list"] == []
    assert result["gamedays"] == []


def test_mixed_freeze_and_no_freeze_flags_no_freeze_day(tmp_path: Path) -> None:
    store = _setup_store(tmp_path)
    _freeze_five(store)

    result = weekclose.build_week_punch_list(store, _week_games(), season=SEASON, week=WEEK)

    assert result["resolved"] is True
    assert result["gamedays"] == [NO_FREEZE_DAY.isoformat(), DAY.isoformat()]
    rows_by_day = {row["day"]: row for row in result["rows"]}
    assert rows_by_day[NO_FREEZE_DAY.isoformat()]["freeze_status"] == "no_freeze"
    assert rows_by_day[DAY.isoformat()]["freeze_status"] == "frozen"

    infra_findings = [
        item
        for item in result["punch_list"]
        if item["category"] == "infra" and item["evidence"].get("day") == NO_FREEZE_DAY.isoformat()
    ]
    assert len(infra_findings) == 1
    assert "No freeze recorded" in infra_findings[0]["title"]


def test_frozen_day_with_on_disk_contest_reports_capture_ratio(tmp_path: Path) -> None:
    store = _setup_store(tmp_path)
    _freeze_five(store)
    contest_store = _write_replayable_contest(tmp_path / "nfl-oracle")

    result = weekclose.build_week_punch_list(
        store, _week_games(), season=SEASON, week=WEEK, contest_store=contest_store
    )

    rows_by_day = {row["day"]: row for row in result["rows"]}
    replay = rows_by_day[DAY.isoformat()]["replay"]
    assert replay is not None
    assert replay["winner_capture_ratio"] == pytest.approx(10.0 / 33.0)
    assert replay["entries_scored"] == 1


def test_missing_contest_on_disk_degrades_to_no_replay(tmp_path: Path) -> None:
    store = _setup_store(tmp_path)
    _freeze_five(store)
    contest_store = ContestStore(project=tmp_path / "nfl-oracle")

    result = weekclose.build_week_punch_list(
        store, _week_games(), season=SEASON, week=WEEK, contest_store=contest_store
    )

    rows_by_day = {row["day"]: row for row in result["rows"]}
    assert rows_by_day[DAY.isoformat()]["replay"] is None


def test_persist_writes_artifact_once(tmp_path: Path) -> None:
    store = _setup_store(tmp_path)
    _freeze_five(store)

    result = weekclose.build_and_persist_week_punch_list(
        store, _week_games(), season=SEASON, week=WEEK
    )

    artifact = store.latest_artifact(weekclose.weekclose_punchlist_kind(SEASON, WEEK))
    assert artifact is not None
    assert artifact["payload"]["season"] == result["season"]
    assert artifact["payload"]["week"] == result["week"]


def test_producer_never_imports_training_or_pipeline_modules() -> None:
    source = inspect.getsource(weekclose)
    for forbidden in ("fit_model", "RecommendationPipeline", "activate_model", "ModelBundle"):
        assert forbidden not in source


def test_no_em_dash_in_producer_or_cli_additions() -> None:
    for module in (weekclose, cli):
        source = inspect.getsource(module)
        assert "\u2014" not in source


def test_cli_weekclose_prints_punch_list_json(tmp_path: Path, monkeypatch, capsys) -> None:
    project = tmp_path / "nfl-oracle"
    (project / "data" / "schedule").mkdir(parents=True)
    csv_text = (
        "season,week,game_id,gameday,home_team,away_team,game_type\n"
        f"{SEASON},{WEEK},2026_01_AAA_BBB,{NO_FREEZE_DAY.isoformat()},AAA,BBB,REG\n"
        f"{SEASON},{WEEK},2026_01_CCC_DDD,{DAY.isoformat()},CCC,DDD,REG\n"
    )
    (project / "data" / "schedule" / "schedules.csv").write_text(csv_text, encoding="utf-8")

    engine = create_engine(f"sqlite:///{tmp_path / 'decisions.db'}")
    migrate(engine)
    store = RecommendationStore(engine, writable=True, clock=lambda: NOW)
    _freeze_five(store)

    monkeypatch.setattr(cli, "_engine", lambda: engine)
    monkeypatch.setattr(cli, "_project_root", lambda: project)

    exit_code = cli.main(
        [
            "weekclose",
            "--season",
            str(SEASON),
            "--week",
            str(WEEK),
        ]
    )

    assert exit_code == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["resolved"] is True
    assert printed["season"] == SEASON
    assert printed["week"] == WEEK
    assert isinstance(printed["punch_list"], list)
    assert printed["gamedays"] == [NO_FREEZE_DAY.isoformat(), DAY.isoformat()]
