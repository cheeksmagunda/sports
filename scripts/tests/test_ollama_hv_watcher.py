"""Offline tests for Ollama HV slate watcher timing + gate (#574)."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

from ollama_hv_watcher.boards import summarize_board_payload
from ollama_hv_watcher.discover import (
    discover_day_plan,
    load_fixture_calendars,
)
from ollama_hv_watcher.gate import (
    ensure_ollama_training_allowed,
    operator_unlock_enabled,
)
from ollama_hv_watcher.learn import (
    build_learn_prompt,
    write_learning_tick,
)
from ollama_hv_watcher.pick import (
    FIVE_PLAYER_LINEUP_SIZE,
    five_player_lineup,
)
from ollama_hv_watcher.windows import (
    DayWatchPlan,
    SlateWindow,
    build_day_plan,
)
from realsports_corpus.coverage_manifest import (
    OllamaForbiddenError,
    build_empty_manifest,
)


def _slate(
    sport: str,
    slate_id: str,
    kickoff: datetime,
    close: datetime,
    *,
    lead: int = 40,
) -> SlateWindow:
    return SlateWindow(
        sport=sport,
        slate_id=slate_id,
        freeze_or_kickoff_at=kickoff,
        close_at=close,
        lead_minutes=lead,
    )


def test_day_plan_arms_at_earliest_t40_and_releases_at_latest_close() -> None:
    kick_a = datetime(2026, 9, 27, 17, 0, tzinfo=UTC)
    kick_b = datetime(2026, 9, 27, 23, 0, tzinfo=UTC)
    plan = build_day_plan(
        [
            _slate("nfl", "sun", kick_a, datetime(2026, 9, 28, 4, 0, tzinfo=UTC)),
            _slate("wnba", "eve", kick_b, datetime(2026, 9, 28, 2, 30, tzinfo=UTC)),
        ]
    )
    assert plan.arm_at == kick_a - timedelta(minutes=40)
    assert plan.release_at == datetime(2026, 9, 28, 4, 0, tzinfo=UTC)
    assert plan.slates[0].session_id == "nfl:sun"
    assert plan.slates[1].session_id == "wnba:eve"

    before = plan.arm_at - timedelta(minutes=1)
    assert plan.should_run(before) is False
    assert plan.active_sessions(before) == ()

    at_arm = plan.arm_at
    assert plan.should_run(at_arm) is True
    assert [s.session_id for s in plan.active_sessions(at_arm)] == ["nfl:sun"]

    mid = datetime(2026, 9, 27, 22, 30, tzinfo=UTC)
    active = {s.session_id for s in plan.active_sessions(mid)}
    assert active == {"nfl:sun", "wnba:eve"}

    after = plan.release_at
    assert plan.should_run(after) is False


def test_duplicate_session_ids_rejected() -> None:
    kick = datetime(2026, 9, 27, 20, 0, tzinfo=UTC)
    close = datetime(2026, 9, 27, 23, 0, tzinfo=UTC)
    with pytest.raises(ValueError, match="duplicate_session_id"):
        DayWatchPlan(
            slates=(
                _slate("nhl", "2026-09-27", kick, close),
                _slate("nhl", "2026-09-27", kick + timedelta(hours=1), close),
            )
        )


def test_fixture_calendars_cover_all_sports() -> None:
    plan = load_fixture_calendars()
    assert plan is not None
    sports = {s.sport for s in plan.slates}
    assert sports == {"wnba", "nfl", "nhl", "nba"}
    # Earliest arm is NFL T-40 on the sample fixture day.
    assert plan.arm_at == datetime(2026, 9, 27, 16, 20, tzinfo=UTC)
    assert plan.release_at == datetime(2026, 9, 28, 4, 0, tzinfo=UTC)


def test_discover_prefers_explicit_windows_json(tmp_path: Path) -> None:
    path = tmp_path / "windows.json"
    path.write_text(
        json.dumps(
            {
                "slates": [
                    {
                        "sport": "nba",
                        "slate_id": "only",
                        "freeze_or_kickoff_at": "2026-10-01T00:40:00Z",
                        "close_at": "2026-10-01T03:00:00Z",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    plan = discover_day_plan(windows_json=path, include_fixtures=False)
    assert len(plan.slates) == 1
    assert plan.slates[0].session_id == "nba:only"
    assert plan.arm_at == datetime(2026, 10, 1, 0, 0, tzinfo=UTC)


def test_training_forbidden_until_unlock_or_coverage() -> None:
    empty = build_empty_manifest()
    with pytest.raises(OllamaForbiddenError):
        ensure_ollama_training_allowed(empty, environ={})
    assert ensure_ollama_training_allowed(
        empty, environ={"SPORTS_OLLAMA_UNLOCK": "1"}
    ) == ("operator_unlock")
    assert operator_unlock_enabled({"SPORTS_OLLAMA_UNLOCK": "1"}) is True
    assert operator_unlock_enabled({}) is False


def _five_players() -> list[dict[str, object]]:
    return [
        {"player_id": i, "name": f"P{i}", "value": float(60 - i), "team": "T"}
        for i in range(1, 7)
    ]


def test_board_summary_ranks_by_value() -> None:
    summary = summarize_board_payload(
        {
            "sport": "nfl",
            "slate_key": "x",
            "section": "highestBoostedValuePlayers",
            "players": _five_players(),
        }
    )
    assert summary.player_count == 6
    assert summary.top_players[0]["name"] == "P1"
    prompt = build_learn_prompt(summary)
    assert "Highest-value" in prompt or "HV" in prompt
    assert "exactly 5" in prompt or "exactly five" in prompt.lower()
    assert "P1" in prompt
    assert "DAILY CONTEST CARD" in prompt


def test_five_player_lineup_every_day() -> None:
    summary = summarize_board_payload(
        {
            "sport": "nfl",
            "slate_key": "sun",
            "players": _five_players(),
        }
    )
    card = five_player_lineup(summary)
    assert len(card) == FIVE_PLAYER_LINEUP_SIZE == 5
    assert [row["slot"] for row in card] == [1, 2, 3, 4, 5]
    assert [row["name"] for row in card] == ["P1", "P2", "P3", "P4", "P5"]


def test_five_player_lineup_fails_closed_when_short() -> None:
    summary = summarize_board_payload(
        {
            "sport": "wnba",
            "slate_key": "short",
            "players": [
                {"player_id": 1, "name": "A", "value": 3.0},
                {"player_id": 2, "name": "B", "value": 2.0},
            ],
        }
    )
    with pytest.raises(ValueError, match="need_five_players_every_day"):
        five_player_lineup(summary)


def test_write_learning_tick_dry_path(tmp_path: Path) -> None:
    summary = summarize_board_payload(
        {
            "sport": "wnba",
            "slate_key": "2026-09-27",
            "players": _five_players(),
        }
    )
    out = write_learning_tick(
        tmp_path,
        summary,
        notes="dry notes",
        model="llama3.2:3b",
        gate_reason="operator_unlock",
        dry_run=True,
    )
    assert out.is_file()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["dry_run"] is True
    assert payload["notes"] == "dry notes"
    assert payload["lineup_size"] == 5
    assert len(payload["five_player_lineup"]) == 5
    assert "wnba" in str(out)
