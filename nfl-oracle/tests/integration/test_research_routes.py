"""Integration coverage for research FastAPI routes (offline fixtures)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from nfl_oracle.service.app import create_app

OFFLINE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "offline_research"


def _client() -> TestClient:
    return TestClient(create_app(project_root=OFFLINE_ROOT))


def test_research_route_surface_contest_entry_false() -> None:
    client = _client()
    get_routes = [
        "/",
        "/health",
        "/research/schemas/labels",
        "/research/schemas/strategy",
        "/research/schemas/features",
        "/research/schemas/scoring",
        "/research/features/live-ok",
        "/research/provider/status",
        "/research/gates/entry",
        "/research/catalog/seasons",
        "/research/coverage/summary",
        "/research/status",
        "/research/status?include_gates=false",
    ]
    for path in get_routes:
        resp = client.get(path)
        assert resp.status_code == 200, path
        body = resp.json()
        if "contest_entry" in body:
            assert body["contest_entry"] is False, path


def test_coverage_summary_uses_offline_dense_fixtures() -> None:
    client = _client()
    body = client.get("/research/coverage/summary").json()
    assert body["catalog"]["season_count"] == 4
    assert body["catalog"]["seed_game_count"] == 14
    assert body["coverage_matrix"]["status_counts"]["known"] == 2
    assert body["coverage_matrix"]["status_counts"]["blocked"] == 1
    assert body["density"]["known_ratio"] == 0.5
    assert body["density"]["mean_seeds_per_season"] == 3.5
    assert body["contest_entry"] is False


def test_catalog_seasons_offline_dense() -> None:
    client = _client()
    body = client.get("/research/catalog/seasons").json()
    assert body["season_count"] == 4
    assert body["seasons"]["2024"] == [2401, 2402, 2403, 2404, 2405]
    assert body["contest_entry"] is False


def test_status_railway_and_gates_honesty() -> None:
    client = _client()
    status = client.get("/research/status").json()
    assert status["mode"] == "research_shadow"
    assert status["railway"]["in_repo_config"] is False
    assert status["railway"]["dockerfile"] is False
    assert status["railway"]["deploy_source_connected"] is False
    assert status["entry_gates"]["contest_entry"] is False
    assert status["data"]["density"]["catalog_seed_game_count"] == 14
    assert "note" in status["auth"]


def test_shadow_preview_and_rank_orderings_integration() -> None:
    client = _client()
    preview = client.post(
        "/research/shadow/preview",
        json={
            "player_ids": [11, 22, 33, 44, 55],
            "values_by_player": {"11": 9.0, "22": 7.0, "33": 5.0, "44": 3.0, "55": 1.0},
            "boosts_by_player": {"22": 1.0},
            "use_contest_algebra": True,
            "include_best_ordering": True,
        },
    )
    assert preview.status_code == 200
    pbody = preview.json()
    assert pbody["contest_entry"] is False
    assert pbody["structurally_valid"] is True
    assert "contest_shadow_score" in pbody
    assert pbody["best_ordering"]["contest_entry"] is False
    assert pbody["best_ordering"]["player_ids"][0] == 11

    ranked = client.post(
        "/research/shadow/rank-orderings",
        json={
            "player_ids": [11, 22, 33, 44, 55],
            "values_by_player": {"11": 9.0, "22": 7.0, "33": 5.0, "44": 3.0, "55": 1.0},
            "top_k": 8,
        },
    )
    assert ranked.status_code == 200
    rbody = ranked.json()
    assert rbody["contest_entry"] is False
    assert rbody["observation_only"] is True
    assert rbody["orderings_evaluated"] == 120
    assert rbody["returned"] == 8
    assert rbody["rankings"][0]["total"] >= rbody["rankings"][-1]["total"]


def test_shadow_validation_edges() -> None:
    client = _client()
    missing_values = client.post(
        "/research/shadow/rank-orderings",
        json={"player_ids": [1, 2, 3, 4, 5], "values_by_player": {}},
    )
    assert missing_values.status_code == 422

    extra = client.post(
        "/research/shadow/preview",
        json={
            "player_ids": [1, 2, 3, 4, 5],
            "values_by_player": {"1": 1},
            "unexpected": True,
        },
    )
    assert extra.status_code == 422

    bad_len = client.post(
        "/research/shadow/preview",
        json={"player_ids": [1, 2, 3], "values_by_player": {"1": 1}},
    )
    assert bad_len.status_code == 422


def test_gates_and_provider_hard_deny() -> None:
    client = _client()
    gates = client.get("/research/gates/entry").json()
    assert gates["contest_entry"] is False
    assert gates["observation_only"] is True
    deny = next(g for g in gates["gates"] if g["key"] == "package_submit_hard_deny")
    assert deny["ok"] is False
    provider = client.get("/research/provider/status").json()
    assert provider["contest_entry"] is False
    assert "posture" in provider


def test_scoring_and_live_ok_schemas() -> None:
    client = _client()
    scoring = client.get("/research/schemas/scoring").json()
    assert scoring["name"] == "nfl_contest_scoring_algebra"
    assert scoring["contest_entry"] is False
    live = client.get("/research/features/live-ok").json()
    assert "player_prior_mean" in live["live_ok"]
    assert "same_slate_final_value" not in live["live_ok"]
    assert live["contest_entry"] is False
