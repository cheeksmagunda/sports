"""Hosted T-40 runner: pool parsing, projection, freeze decision (#675)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from nhl_oracle.scheduler import live_cycle
from nhl_oracle.scheduler.runner import (
    PoolPlayer,
    SlateGame,
    SlateSnapshot,
    parse_game_players,
    parse_home_next,
    prior_games_played_from_summaries,
    project_pool,
    score_cycle,
)
from nhl_oracle.service.cli import main

LOCK = datetime(2026, 9, 30, 23, 0, tzinfo=UTC)


def _player(
    pid: int, value: float | None, *, pos: str = "C", game: int = 1, inj: str = "Active"
) -> PoolPlayer:
    return PoolPlayer(
        player_id=pid,
        name=f"P{pid}",
        team="AAA" if game == 1 else "BBB",
        position=pos,
        game_id=game,
        injury_status=inj,
        primary_value=value,
    )


def _snapshot(players: tuple[PoolPlayer, ...], *, captured: datetime) -> SlateSnapshot:
    return SlateSnapshot(
        day=date(2026, 9, 30),
        contest_id=2211,
        games=(
            SlateGame(game_id=1, start_at=LOCK, status="scheduled"),
            SlateGame(game_id=2, start_at=LOCK + timedelta(hours=2), status="scheduled"),
        ),
        players=players,
        captured_at=captured,
        games_with_players=frozenset({1, 2}),
    )


def _pool() -> tuple[tuple[PoolPlayer, ...], dict[int, int]]:
    players = tuple(
        _player(100 + i, 30.0 * (10 - i), game=1 + i % 2, pos="D" if i % 3 == 0 else "C")
        for i in range(10)
    ) + (_player(200, 5.0, pos="G", game=2),)
    gp = {100 + i: 20 for i in range(10)} | {200: 10}
    return players, gp


def test_parse_home_next_and_players() -> None:
    home = {
        "latestDay": "2026-09-29",
        "latestDayContent": {
            "config": {"dailyDraftInfo": {"contests": [{"id": 2210, "source": "home"}]}},
            "games": [
                {"id": 2026020002, "dateTime": "2026-09-29T23:00:00.000Z", "status": "scheduled"},
                {"id": 2026020001, "dateTime": "2026-09-29T21:00:00.000Z", "status": "scheduled"},
            ],
        },
    }
    parsed = parse_home_next(home)
    assert parsed is not None
    day, contest_id, games = parsed
    assert (day, contest_id) == (date(2026, 9, 29), 2210)
    assert [g.game_id for g in games] == [2026020001, 2026020002]
    assert parse_home_next({"latestDay": "2026-09-29", "latestDayContent": {"config": {}}}) is None

    cards = parse_game_players(
        {
            "players": [
                {
                    "id": 8478427,
                    "firstName": "Sebastian",
                    "lastName": "Aho",
                    "position": "C",
                    "injuryStatus": "Active",
                    "team": {"key": "CAR"},
                    "rankings": {"primaryValue": 224.09},
                }
            ]
        },
        game_id=2026020001,
    )
    assert cards[0].name == "Sebastian Aho"
    assert cards[0].team == "CAR"
    assert cards[0].primary_value == pytest.approx(224.09)


def test_projection_covers_every_player_and_zeroes_out_status() -> None:
    players = (
        _player(1, 200.0),
        _player(2, 100.0),
        _player(3, None),  # rookie: no Real total
        _player(4, 212.0),  # Real total but 0 prior GP: must not divide by zero
        _player(5, 300.0, inj="Out"),
        _player(6, 20.0, pos="G"),
    )
    gp = prior_games_played_from_summaries(
        {"data": [{"playerId": 1, "gamesPlayed": 80}, {"playerId": 2, "gamesPlayed": 50}]},
        {"data": [{"playerId": 6, "gamesPlayed": 20}]},
    )
    projected = project_pool(players, gp)
    assert set(projected) == {1, 2, 3, 4, 5, 6}
    forward_mean = (200 / 80 + 100 / 50) / 2
    assert projected[3] == pytest.approx(forward_mean)
    assert projected[4] == pytest.approx(forward_mean)
    assert projected[5] == 0.0
    # Shrinkage pulls toward the bucket mean but keeps order.
    assert projected[2] < projected[1]
    assert projected[1] == pytest.approx((200 + forward_mean * 10) / 90)


def test_preview_before_window_frozen_inside_window() -> None:
    players, gp = _pool()
    before = LOCK - timedelta(hours=2)
    preview = score_cycle(
        _snapshot(players, captured=before),
        prior_games_played=gp,
        team_games_played=None,
        now=before,
    )
    assert preview.status == "preview"
    assert [p["player_id"] for p in preview.lineup] == [100, 101, 102, 103, 104]
    assert [p["multiplier"] for p in preview.lineup] == [2.0, 1.8, 1.6, 1.4, 1.2]
    assert "before_t40_window" in preview.readiness.blocked_reasons

    inside = LOCK - timedelta(minutes=39)
    frozen = score_cycle(
        _snapshot(players, captured=inside - timedelta(seconds=5)),
        prior_games_played=gp,
        team_games_played=None,
        now=inside,
    )
    assert frozen.status == "frozen"
    assert frozen.readiness.freeze_ready is True
    assert frozen.readiness.zero_boost_active is True
    payload = frozen.to_dict()
    assert payload["contest_entry"] is False
    assert payload["t40_open"] == (LOCK - timedelta(minutes=40)).isoformat()


def test_missing_game_pool_blocks_freeze() -> None:
    players, gp = _pool()
    inside = LOCK - timedelta(minutes=30)
    snap = _snapshot(players, captured=inside)
    partial = SlateSnapshot(
        day=snap.day,
        contest_id=snap.contest_id,
        games=snap.games,
        players=snap.players,
        captured_at=snap.captured_at,
        games_with_players=frozenset({1}),
    )
    outcome = score_cycle(partial, prior_games_played=gp, team_games_played=None, now=inside)
    assert outcome.status == "blocked"
    assert outcome.readiness.freeze_ready is False


def test_worker_runner_logs_cycle_without_database(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    players, gp = _pool()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("NHL_DATABASE_URL", raising=False)
    monkeypatch.setenv("NHL_T40_RUNNER", "1")

    async def fake_cycle() -> Any:
        return score_cycle(
            _snapshot(players, captured=LOCK - timedelta(hours=3)),
            prior_games_played=gp,
            team_games_played=None,
            now=LOCK - timedelta(hours=2),
        )

    monkeypatch.setattr(live_cycle, "run_cycle", fake_cycle)
    assert main(["worker", "--once"]) == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["status"] == "preview"
    assert payload["persisted"] is False
    assert "1:P100" in payload["message"]


def test_worker_cycle_error_does_not_crash(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("NHL_DATABASE_URL", raising=False)
    monkeypatch.setenv("NHL_T40_RUNNER", "1")

    async def broken() -> Any:
        raise RuntimeError("boom")

    monkeypatch.setattr(live_cycle, "run_cycle", broken)
    assert main(["worker", "--once"]) == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["status"] == "cycle_error"


def test_prior_season_id_defaults_to_previous_season(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NHL_PRIMARY_VALUE_SEASON_ID", raising=False)
    assert live_cycle.prior_season_id(date(2026, 9, 30)) == "20252026"
    monkeypatch.setenv("NHL_PRIMARY_VALUE_SEASON_ID", "20262027")
    assert live_cycle.prior_season_id(date(2026, 9, 30)) == "20262027"


def test_store_upsert_never_replaces_a_frozen_row() -> None:
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from nhl_oracle.service.lineup_store import lineups

    statement = pg_insert(lineups).values(
        slate_day="2026-09-30",
        contest_id=2211,
        status="preview",
        payload={},
        updated_at=LOCK,
    )
    statement = statement.on_conflict_do_update(
        index_elements=[lineups.c.slate_day, lineups.c.contest_id],
        set_={"status": statement.excluded.status},
        where=lineups.c.status != "frozen",
    )
    sql = str(statement.compile(dialect=postgresql.dialect()))
    assert "ON CONFLICT (slate_day, contest_id) DO UPDATE" in sql
    assert "WHERE nhl_t40_lineups.status != " in sql

    import inspect

    from nhl_oracle.service import lineup_store

    source = inspect.getsource(lineup_store.save_outcome)
    assert 'where=lineups.c.status != "frozen"' in source


async def test_run_cycle_reads_decision_clock_after_collect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The worker must never pass a pre-collect clock (#675 opening-night bug)."""

    players, gp = _pool()
    inside = LOCK - timedelta(minutes=30)
    ticks = iter([inside - timedelta(seconds=2), inside])

    class Clock(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
            return next(ticks)

    async def fake_collect(client: Any) -> SlateSnapshot:
        return _snapshot(players, captured=Clock.now(UTC))

    async def fake_summary(client: Any, kind: str, season_id: str) -> dict[str, Any]:
        if kind == "team":
            return {"data": []}
        rows = [{"playerId": pid, "gamesPlayed": games} for pid, games in gp.items()]
        return {"data": rows if kind == "skater" else []}

    monkeypatch.setattr(live_cycle, "datetime", Clock)
    monkeypatch.setattr(live_cycle, "collect_snapshot", fake_collect)
    monkeypatch.setattr(live_cycle, "_summary", fake_summary)
    outcome = await live_cycle.run_cycle()
    assert outcome is not None
    assert "clock_freshness" not in outcome.readiness.blocked_reasons
    assert outcome.status == "frozen"
