"""Research service edge cases for shadow/gates/status (observation only)."""

from __future__ import annotations

from fastapi.testclient import TestClient

from nfl_oracle.service.app import create_app


def test_import_providers_then_strategy_no_cycle() -> None:
    """Regression: strategy package exports must not circular-import providers."""

    from nfl_oracle.providers.auth_status import AuthProbeResult
    from nfl_oracle.strategy import OBSERVED_DEFAULT_SLOT_MULTIPLIERS, evaluate_entry_gates

    assert AuthProbeResult is not None
    assert OBSERVED_DEFAULT_SLOT_MULTIPLIERS[0] == 2.0
    report = evaluate_entry_gates()
    assert report.contest_entry is False


def test_status_can_omit_entry_gates() -> None:
    client = TestClient(create_app())
    with_gates = client.get("/research/status").json()
    assert "entry_gates" in with_gates
    assert with_gates["entry_gates"]["contest_entry"] is False
    without = client.get("/research/status", params={"include_gates": "false"}).json()
    assert "entry_gates" not in without
    assert without["contest_entry"] is False
    assert without["scoring"]["schema"] == "/research/schemas/scoring"


def test_shadow_preview_legacy_algebra_path() -> None:
    client = TestClient(create_app())
    resp = client.post(
        "/research/shadow/preview",
        json={
            "player_ids": [1, 2, 3, 4, 5],
            "slot_multipliers": [3, 2, 1, 1, 1],
            "values_by_player": {"1": 10, "2": 5, "3": 4, "4": 3, "5": 2},
            "use_contest_algebra": False,
            "include_best_ordering": False,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["contest_entry"] is False
    assert "contest_shadow_score" not in body
    assert body["shadow_score"]["total"] == 3 * 10 + 2 * 5 + 4 + 3 + 2
    assert "best_ordering" not in body


def test_rank_orderings_requires_values() -> None:
    client = TestClient(create_app())
    resp = client.post(
        "/research/shadow/rank-orderings",
        json={"player_ids": [1, 2, 3, 4, 5], "values_by_player": {}},
    )
    assert resp.status_code == 422


def test_gates_route_hard_denies_submit() -> None:
    client = TestClient(create_app())
    gates = client.get("/research/gates/entry").json()
    assert gates["contest_entry"] is False
    assert gates["observation_only"] is True
    keys = {g["key"] for g in gates["gates"]}
    assert "package_submit_hard_deny" in keys
    deny = next(g for g in gates["gates"] if g["key"] == "package_submit_hard_deny")
    assert deny["ok"] is False


def test_shadow_feature_value_model_flag_opt_in() -> None:
    client = TestClient(create_app())
    train = []
    for season in (2022, 2023):
        for pid, pos, val in (
            (1, "QB", 10.0),
            (2, "RB", 5.0),
            (3, "WR", 4.0),
            (4, "TE", 3.0),
            (5, "K", 2.0),
        ):
            train.append(
                {
                    "player_id": pid,
                    "game_id": season * 100 + pid,
                    "season": season,
                    "position": pos,
                    "value": val + (0.5 if season == 2023 else 0.0),
                }
            )
    resp = client.post(
        "/research/shadow/preview",
        json={
            "player_ids": [1, 2, 3, 4, 5],
            "use_feature_value_model": True,
            "decision_season": 2024,
            "player_positions": {"1": "QB", "2": "RB", "3": "WR", "4": "TE", "5": "K"},
            "train_labels": train,
            "include_best_ordering": False,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["contest_entry"] is False
    assert body["value_model"]["use_feature_value_model"] is True
    assert body["value_model"]["value_source"] == "feature_ridge"
    assert "shadow_score" in body


def test_status_exposes_value_model_flag_default() -> None:
    client = TestClient(create_app())
    status = client.get("/research/status").json()
    assert status["value_model"]["shadow_flag"] == "use_feature_value_model"
    assert status["value_model"]["shadow_flag_default"] is False
    assert status["value_model"]["default_offline_safe"] is True
    assert status["value_model"]["contest_entry"] is False
