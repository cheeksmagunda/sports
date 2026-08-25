"""D109: scope the optimizer pool to games that have not tipped yet.

A WNBA slate spans several tip times. Once the early game starts its
players are no longer enterable, so an operator drafting late needs a
pool drawn from the games still ahead. POOL_EXCLUDE_STARTED_GAMES turns
the scope on; job1 supplies features_json["game_start_utc"].
"""

from __future__ import annotations

import datetime as dt
import json

from wnba_oracle.ingest.realsports import _parse_pool
from wnba_oracle.scheduler.job2 import _game_start_utc, scope_to_upcoming_games

NOW = dt.datetime(2026, 8, 20, 1, 30, tzinfo=dt.UTC)


def _row(pid: int, start: str | None, *, as_text: bool = False) -> dict:
    feats: dict[str, object] = {"is_out": 0}
    if start is not None:
        feats["game_start_utc"] = start
    return {
        "real_sports_player_id": str(pid),
        "features_json": json.dumps(feats) if as_text else feats,
    }


def test_keeps_only_games_still_ahead() -> None:
    rows = [
        _row(1, "2026-08-19T23:30:00.000Z"),  # tipped two hours ago
        _row(2, "2026-08-20T02:00:00.000Z"),  # ahead
        _row(3, "2026-08-20T02:00:00.000Z"),
    ]
    kept, earliest, n_started, n_unknown = scope_to_upcoming_games(rows, NOW)

    assert [r["real_sports_player_id"] for r in kept] == ["2", "3"]
    assert earliest == dt.datetime(2026, 8, 20, 2, 0, tzinfo=dt.UTC)
    assert (n_started, n_unknown) == (1, 0)


def test_unknown_start_is_dropped_not_assumed_upcoming() -> None:
    """Fails closed: "has not started" cannot be verified without a tip time."""
    kept, earliest, n_started, n_unknown = scope_to_upcoming_games(
        [_row(1, None), _row(2, "garbage"), _row(3, "2026-08-20T02:00:00.000Z")], NOW
    )

    assert [r["real_sports_player_id"] for r in kept] == ["3"]
    assert (n_started, n_unknown) == (0, 2)
    assert earliest == dt.datetime(2026, 8, 20, 2, 0, tzinfo=dt.UTC)


def test_every_game_started_yields_empty_pool() -> None:
    kept, earliest, n_started, n_unknown = scope_to_upcoming_games(
        [_row(1, "2026-08-19T23:30:00.000Z"), _row(2, "2026-08-20T01:00:00.000Z")], NOW
    )

    assert kept == []
    assert earliest is None
    assert (n_started, n_unknown) == (2, 0)


def test_start_parses_from_jsonb_and_from_text_column() -> None:
    expected = dt.datetime(2026, 8, 20, 2, 0, tzinfo=dt.UTC)
    assert _game_start_utc(_row(1, "2026-08-20T02:00:00.000Z")) == expected
    assert _game_start_utc(_row(1, "2026-08-20T02:00:00.000Z", as_text=True)) == expected
    # A tip time already stored without a zone is UTC (the platform's own frame).
    assert _game_start_utc(_row(1, "2026-08-20T02:00:00")) == expected
    assert _game_start_utc(_row(1, None)) is None


def test_pool_parser_carries_the_game_tip_time() -> None:
    players = _parse_pool(
        {
            "players": [
                {
                    "id": 657,
                    "firstName": "Cecilia",
                    "lastName": "Zandalasini",
                    "position": "F",
                    "team": {"key": "gsv"},
                    "multiplierBonus": 2.2,
                    "gameId": 987,
                    "gameStartUtc": "2026-08-20T02:00:00.000Z",
                },
                {
                    "id": 691,
                    "firstName": "Shakira",
                    "lastName": "Austin",
                    "position": "C",
                    "team": {"key": "was"},
                    "multiplierBonus": 0.4,
                },
            ]
        }
    )

    assert players[0].game_start_utc == "2026-08-20T02:00:00.000Z"
    assert players[0].game_id == "987"
    assert players[1].game_start_utc == ""
    assert players[1].game_id == ""
