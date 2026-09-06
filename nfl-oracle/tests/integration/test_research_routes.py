"""Integration coverage for research FastAPI routes (offline fixtures)."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nfl_oracle.providers.five_card import FiveCardProviderStub, ProviderNotReady
from nfl_oracle.service.app import create_app
from nfl_oracle.strategy.schema import FiveCardAction

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
        "/research/identity/density",
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
    assert body["catalog"]["season_count"] == 14
    assert body["catalog"]["seed_game_count"] == 70
    assert body["coverage_matrix"]["status_counts"]["known"] == 12
    assert body["coverage_matrix"]["status_counts"]["blocked"] == 1
    assert body["density"]["known_ratio"] == pytest.approx(12 / 14)
    assert body["density"]["mean_seeds_per_season"] == pytest.approx(70 / 14)
    assert body["identity"]["n_identities"] >= 55
    assert body["contest_entry"] is False


def test_catalog_seasons_offline_dense() -> None:
    client = _client()
    body = client.get("/research/catalog/seasons").json()
    assert body["season_count"] == 14
    assert body["seasons"]["2024"] == [2401, 2402, 2403, 2404, 2405]
    assert body["seasons"]["2025"] == [2501, 2502, 2503, 2504, 2505]
    assert body["seasons"]["2012"] == [1201, 1202, 1203, 1204, 1205]
    assert body["seasons"]["2013"] == [1301, 1302, 1303, 1304, 1305]
    assert body["seasons"]["2014"] == [1401, 1402, 1403, 1404, 1405]
    assert body["seasons"]["2015"] == [1501, 1502, 1503, 1504, 1505]
    assert body["seasons"]["2016"] == [1601, 1602, 1603, 1604]
    assert body["seasons"]["2018"] == [1801, 1802, 1803, 1804, 1805]
    assert body["contest_entry"] is False


def test_identity_density_route_offline() -> None:
    client = _client()
    body = client.get("/research/identity/density").json()
    assert body["contest_entry"] is False
    assert body["path_exists"] is True
    assert body["n_identities"] >= 55
    assert body["density"]["n_complete"] >= 50
    assert body["density"]["complete_ratio"] > 0.8
    assert "QB" in body["density"]["position_counts"]


def test_status_railway_gates_and_draft_readiness_honesty() -> None:
    client = _client()
    status = client.get("/research/status").json()
    assert status["mode"] == "research_shadow"
    assert status["contest_entry"] is False
    assert status["railway"]["in_repo_config"] is False
    assert status["railway"]["dockerfile"] is False
    assert status["railway"]["deploy_source_connected"] is False
    assert status["entry_gates"]["contest_entry"] is False
    assert status["data"]["density"]["catalog_seed_game_count"] == 70
    assert status["identity"]["n_identities"] >= 55
    assert "note" in status["auth"]
    draft = status["draft_readiness"]
    assert draft["contest_entry"] is False
    assert draft["submit_hard_denied"] is True
    assert draft["railway_deploy_ready"] is False
    assert draft["policy"] == "deny_by_default_entry_gates"
    assert draft["coverage_seed_game_count"] == 70
    assert draft["identity_n"] >= 55

    omitted = client.get("/research/status?include_gates=false").json()
    assert "entry_gates" not in omitted
    assert omitted["draft_readiness"]["contest_entry"] is False


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
    assert gates["policy"] == "submit_hard_denied_until_explicit_authorization"
    deny = next(g for g in gates["gates"] if g["key"] == "package_submit_hard_deny")
    assert deny["ok"] is False
    assert "package_submit_hard_deny" in gates["blocked_reasons"]
    provider = client.get("/research/provider/status").json()
    assert provider["contest_entry"] is False
    assert "posture" in provider

    stub = FiveCardProviderStub()
    action = FiveCardAction(player_ids=(1, 2, 3, 4, 5))
    with pytest.raises(ProviderNotReady, match="contest_entry_forbidden"):
        stub.submit(action)
    with pytest.raises(ProviderNotReady, match="inventory_blocked"):
        stub.fetch_slate_inventory(slate_id="offline")


def test_scoring_and_live_ok_schemas() -> None:
    client = _client()
    scoring = client.get("/research/schemas/scoring").json()
    assert scoring["name"] == "nfl_contest_scoring_algebra"
    assert scoring["contest_entry"] is False
    live = client.get("/research/features/live-ok").json()
    assert "player_prior_mean" in live["live_ok"]
    assert "same_slate_final_value" not in live["live_ok"]
    assert live["contest_entry"] is False


def test_health_auth_degraded_ok_for_research() -> None:
    client = _client()
    health = client.get("/health").json()
    assert health["status"] in {"ok", "degraded"}
    # Auth missing is expected on box; research still serves.
    assert "contest_entry" not in health or health.get("contest_entry") is False
