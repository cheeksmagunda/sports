"""Ollama candidate scoring sits on the classic optimizer (#595)."""

from __future__ import annotations

import json
from datetime import timedelta
from typing import Any

import pytest

from nfl_oracle.recommendations.ollama_engine import (
    MIN_SIMULATIONS,
    candidate_client_paths,
    ollama_engine_from_env,
    utilities_from_payload,
)
from nfl_oracle.recommendations.optimizer import OptimizerConfig, ScoringPolicy, optimize
from tests.unit.test_recommendation_model_optimizer import BASE, projections, slate


def _ids(result: Any) -> list[int]:
    return [pick.player_id for pick in result.picks]


def _classic(target: Any) -> Any:
    return optimize(
        target,
        projections(target),
        decision_at=BASE + timedelta(days=8),
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(ollama_engine=False, simulations=100),
    )


def test_repo_client_path_is_the_watcher_http_client() -> None:
    path = candidate_client_paths()[0]
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "def generate_json" in text
    assert "nfl_oracle" not in text


def test_kill_switch_zero_restores_classic_and_does_not_call() -> None:
    assert ollama_engine_from_env({}) is True
    assert ollama_engine_from_env({"NFL_OLLAMA_ENGINE": "0"}) is False
    assert ollama_engine_from_env({"NFL_OLLAMA_ENGINE": "off"}) is False
    with pytest.raises(ValueError, match="NFL_OLLAMA_ENGINE_invalid"):
        ollama_engine_from_env({"NFL_OLLAMA_ENGINE": "maybe"})

    target = slate()

    def explode(prompt: str, *, timeout_s: float) -> dict[str, Any]:
        raise AssertionError(prompt)

    classic = _classic(target)
    killed = optimize(
        target,
        projections(target),
        decision_at=BASE + timedelta(days=8),
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(ollama_engine=False, simulations=100),
        ollama_client=explode,
    )
    assert _ids(killed) == _ids(classic)
    assert "ollama_engine_selected_by_json_utility" not in killed.assumptions
    assert "ollama_engine_fallback_classic_utility" not in killed.assumptions


def test_json_utility_can_select_a_different_candidate() -> None:
    target = slate()
    classic_ids = _ids(_classic(target))
    seen: dict[str, Any] = {}

    def client(prompt: str, *, timeout_s: float) -> dict[str, Any]:
        document = json.loads(prompt)
        assert document["simulations"] >= MIN_SIMULATIONS
        classic_set = set(classic_ids)
        alternatives = [
            row["players"] for row in document["lineups"] if set(row["players"]) != classic_set
        ]
        assert alternatives
        chosen = alternatives[0]
        seen["chosen"] = chosen
        seen["simulations"] = document["simulations"]
        return {
            "utilities": [
                {
                    "lineup_id": row["lineup_id"],
                    "players": row["players"],
                    "utility": 100.0 if row["players"] == chosen else 0.0,
                }
                for row in document["lineups"]
            ]
        }

    result = optimize(
        target,
        projections(target),
        decision_at=BASE + timedelta(days=8),
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(ollama_engine=True, simulations=100),
        ollama_client=client,
    )
    # The engine chooses the five. Slot-by-mean then commits descending
    # projected mean, so the frozen order can differ from the beam order.
    means = {row.player_id: row.mean for row in projections(target)}
    assert set(_ids(result)) == set(seen["chosen"])
    assert list(_ids(result)) == sorted(_ids(result), key=lambda pid: (-means[pid], pid))
    assert _ids(result) != classic_ids
    assert "ollama_engine_selected_by_json_utility" in result.assumptions
    assert seen["simulations"] >= MIN_SIMULATIONS


def test_timeout_falls_back_to_classic_utility() -> None:
    target = slate()

    def client(prompt: str, *, timeout_s: float) -> dict[str, Any]:
        raise TimeoutError("ollama_timeout")

    result = optimize(
        target,
        projections(target),
        decision_at=BASE + timedelta(days=8),
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(ollama_engine=True, simulations=100),
        ollama_client=client,
    )
    classic = _classic(target)
    assert _ids(result) == _ids(classic)
    assert result.simulated_p90 == classic.simulated_p90
    assert "ollama_engine_fallback_classic_utility" in result.assumptions


def test_invented_player_falls_back_to_classic_utility() -> None:
    target = slate()

    def client(prompt: str, *, timeout_s: float) -> dict[str, Any]:
        document = json.loads(prompt)
        utilities = []
        for row in document["lineups"]:
            players = list(row["players"])
            players[0] = 999_999
            utilities.append({"lineup_id": row["lineup_id"], "players": players, "utility": 5.0})
        return {"utilities": utilities}

    result = optimize(
        target,
        projections(target),
        decision_at=BASE + timedelta(days=8),
        scoring_policy=ScoringPolicy(),
        config=OptimizerConfig(ollama_engine=True, simulations=100),
        ollama_client=client,
    )
    assert _ids(result) == _ids(_classic(target))
    assert 999_999 not in _ids(result)
    assert "ollama_engine_fallback_classic_utility" in result.assumptions


def test_utilities_reject_partial_and_reordered_players() -> None:
    lineups = [(1.0, (1, 2, 3, 4, 5)), (0.5, (1, 2, 3, 4, 6))]
    valid = {
        "utilities": [
            {"lineup_id": 0, "players": [1, 2, 3, 4, 5], "utility": 1},
            {"lineup_id": 1, "players": [1, 2, 3, 4, 6], "utility": 2},
        ]
    }
    assert utilities_from_payload(valid, lineups) == {0: 1.0, 1: 2.0}
    reordered = {
        "utilities": [
            {"lineup_id": 0, "players": [5, 4, 3, 2, 1], "utility": 1},
            {"lineup_id": 1, "players": [1, 2, 3, 4, 6], "utility": 2},
        ]
    }
    assert utilities_from_payload(reordered, lineups) is None
    partial = {"utilities": [valid["utilities"][0]]}
    assert utilities_from_payload(partial, lineups) is None
