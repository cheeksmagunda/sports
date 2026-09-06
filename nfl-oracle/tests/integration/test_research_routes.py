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
        "/research/provider/rules-offline",
        "/research/gates/entry",
        "/research/catalog/seasons",
        "/research/coverage/summary",
        "/research/schedule/summary",
        "/research/identity/density",
        "/research/health/readiness-score",
        "/research/shadow/contest-dry-run",
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
    assert body["identity"]["n_identities"] >= 100
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
    assert body["n_identities"] >= 100
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
    assert status["identity"]["n_identities"] >= 100
    assert "note" in status["auth"]
    draft = status["draft_readiness"]
    assert draft["contest_entry"] is False
    assert draft["submit_hard_denied"] is True
    assert draft["railway_deploy_ready"] is False
    assert draft["policy"] == "deny_by_default_entry_gates"
    assert draft["coverage_seed_game_count"] == 70
    assert draft["identity_n"] >= 100

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


def test_schedule_summary_offline_census() -> None:
    client = _client()
    body = client.get("/research/schedule/summary").json()
    assert body["contest_entry"] is False
    assert body["density"]["season_count"] >= 8
    assert body["density"]["game_count"] >= 1000
    assert body["continuous_regular_season_count"] >= 3
    cov = client.get("/research/coverage/summary").json()
    assert cov["schedule"]["density"]["season_count"] >= 8
    assert cov["schedule"]["continuous_regular_season_count"] >= 3
    assert "coverage_census" in cov["schedule"]


def _synthetic_train_labels() -> list[dict]:
    """Offline-safe inline labels for feature_ridge shadow path."""

    rows: list[dict] = []
    roster = [(101, "QB"), (102, "RB"), (103, "WR"), (104, "TE"), (105, "K")]
    for season, bump in ((2022, 0.0), (2023, 1.0)):
        for pid, pos in roster:
            rows.append(
                {
                    "player_id": pid,
                    "game_id": season * 1000 + pid,
                    "season": season,
                    "position": pos,
                    "value": float(pid % 100) + bump,
                    "team_id": 1,
                }
            )
    return rows


def test_e2e_schedule_shadow_rank_rules_offline() -> None:
    """End-to-end research path: schedule + shadow rank + provider rules-offline."""

    client = _client()

    schedule = client.get("/research/schedule/summary").json()
    assert schedule["contest_entry"] is False
    assert schedule["density"]["season_count"] >= 8
    assert schedule["density"]["game_count"] >= 1000

    rules = client.get("/research/provider/rules-offline").json()
    assert rules["contest_entry"] is False
    assert rules["observation_only"] is True
    assert rules["provider_contract_verified"] is False
    assert rules["submit_enabled"] is False
    assert len(rules["unknown_rules"]) >= 1
    assert len(rules["offline_rule_notes"]) == len(rules["unknown_rules"])

    # Default path remains offline-safe (explicit values; flag off).
    ranked_default = client.post(
        "/research/shadow/rank-orderings",
        json={
            "player_ids": [101, 102, 103, 104, 105],
            "values_by_player": {"101": 9.0, "102": 7.0, "103": 5.0, "104": 3.0, "105": 1.0},
            "top_k": 5,
        },
    )
    assert ranked_default.status_code == 200
    dbody = ranked_default.json()
    assert dbody["contest_entry"] is False
    assert dbody["use_feature_value_model"] is False
    assert dbody["value_model"]["value_source"] == "explicit"
    assert dbody["value_model"]["default_offline_safe"] is True
    assert dbody["returned"] == 5

    # Opt-in feature_ridge path via clear flag.
    ranked_model = client.post(
        "/research/shadow/rank-orderings",
        json={
            "player_ids": [101, 102, 103, 104, 105],
            "use_feature_value_model": True,
            "decision_season": 2024,
            "player_positions": {
                "101": "QB",
                "102": "RB",
                "103": "WR",
                "104": "TE",
                "105": "K",
            },
            "train_labels": _synthetic_train_labels(),
            "top_k": 5,
        },
    )
    assert ranked_model.status_code == 200, ranked_model.text
    mbody = ranked_model.json()
    assert mbody["contest_entry"] is False
    assert mbody["use_feature_value_model"] is True
    assert mbody["value_model"]["value_source"] == "feature_ridge"
    assert mbody["value_model"]["method"] == "feature_ridge"
    assert mbody["value_model"]["n_train_labels"] == 10
    assert len(mbody["values_by_player"]) == 5
    assert mbody["rankings"][0]["total"] >= mbody["rankings"][-1]["total"]

    preview = client.post(
        "/research/shadow/preview",
        json={
            "player_ids": [101, 102, 103, 104, 105],
            "use_feature_value_model": True,
            "decision_season": 2024,
            "player_positions": {
                "101": "QB",
                "102": "RB",
                "103": "WR",
                "104": "TE",
                "105": "K",
            },
            "train_labels": _synthetic_train_labels(),
            "include_best_ordering": True,
        },
    )
    assert preview.status_code == 200, preview.text
    pbody = preview.json()
    assert pbody["contest_entry"] is False
    assert pbody["value_model"]["value_source"] == "feature_ridge"
    assert "contest_shadow_score" in pbody or "shadow_score" in pbody


def test_feature_value_model_flag_default_offline_safe_422() -> None:
    client = _client()
    # Flag on without train labels / season → 422 (does not silently invent values).
    resp = client.post(
        "/research/shadow/rank-orderings",
        json={
            "player_ids": [1, 2, 3, 4, 5],
            "use_feature_value_model": True,
            "player_positions": {"1": "QB", "2": "RB", "3": "WR", "4": "TE", "5": "K"},
        },
    )
    assert resp.status_code == 422


def test_openapi_research_tags_are_split() -> None:
    client = _client()
    schema = client.get("/openapi.json").json()
    path_tags: set[str] = set()
    for path_item in schema["paths"].values():
        for op in path_item.values():
            if isinstance(op, dict):
                path_tags.update(op.get("tags") or [])
    expected = {
        "research-schemas",
        "research-provider",
        "research-shadow",
        "research-data",
        "research-status",
    }
    assert expected <= path_tags
    assert "research" not in path_tags  # legacy single-tag bucket removed
    assert "research-schemas" in schema["paths"]["/research/schemas/labels"]["get"]["tags"]
    assert "research-shadow" in schema["paths"]["/research/shadow/preview"]["post"]["tags"]
    assert (
        "research-status"
        in schema["paths"]["/research/health/readiness-score"]["get"]["tags"]
    )


def test_health_readiness_score_endpoint_offline() -> None:
    client = _client()
    resp = client.get("/research/health/readiness-score")
    assert resp.status_code == 200
    body = resp.json()
    assert body["contest_entry"] is False
    assert body["observation_only"] is True
    assert body["entry_authorized"] is False
    assert body["name"] == "nfl_research_readiness_score"
    assert 0.0 <= body["score"] <= 100.0
    assert body["band"] in {
        "thin",
        "usable_offline",
        "dense_offline",
        "research_strong",
    }
    keys = {c["key"] for c in body["components"]}
    assert "catalog_seeds" in keys
    assert "schedule_density" in keys
    assert "realsports_auth" in keys
    # Dense offline fixtures should clear usable band even without auth.
    assert body["score"] >= 40.0

    status = client.get("/research/status").json()
    assert "readiness_score" in status
    assert status["readiness_score"]["contest_entry"] is False
    assert status["draft_readiness"]["readiness_band"] == status["readiness_score"]["band"]
    omitted = client.get("/research/status?include_readiness_score=false").json()
    assert "readiness_score" not in omitted


def test_contest_dry_run_route_offline() -> None:
    client = _client()
    resp = client.get("/research/shadow/contest-dry-run")
    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is True
    assert body["observation_only"] is True
    assert body["mode"] == "dry_run"
    assert body["contest_entry"] is False
    assert body["submit_enabled"] is False
    assert body["submit_proof"]["submit_denied"] is True
    assert len(body["five_card_set"]) == 5
    assert body["best_ordering"]["contest_entry"] is False

    ridge = client.get(
        "/research/shadow/contest-dry-run",
        params={"use_feature_ridge": True, "top_k": 2},
    )
    assert ridge.status_code == 200
    rbody = ridge.json()
    assert rbody["value_source"] == "feature_ridge"
    assert rbody["dry_run"] is True
    assert rbody["observation_only"] is True
    assert rbody["contest_entry"] is False


def test_schedule_slate_route_season_week_and_date() -> None:
    client = _client()
    missing = client.get("/research/schedule/slate")
    assert missing.status_code == 422
    by_week = client.get("/research/schedule/slate", params={"season": 2024, "week": 1})
    assert by_week.status_code == 200
    body = by_week.json()
    assert body["contest_entry"] is False
    assert body["resolved"] is True
    assert body["week"] == 1
    assert body["game_count"] >= 14
    assert "KC" in body["opponents"]
    by_date = client.get(
        "/research/schedule/slate",
        params={"date": "2024-09-05", "team": "KC"},
    )
    assert by_date.status_code == 200
    dbody = by_date.json()
    assert dbody["resolve_mode"] == "date_exact_gameday"
    assert dbody["team_opponent"] == "BAL"
    assert dbody["contest_entry"] is False


def test_contest_dry_run_optional_schedule_slate() -> None:
    client = _client()
    resp = client.get(
        "/research/shadow/contest-dry-run",
        params={
            "include_schedule_slate": True,
            "schedule_week": 1,
            "decision_season": 2025,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is True
    assert body["contest_entry"] is False
    slate = body["schedule_slate"]
    assert slate is not None
    assert slate["contest_entry"] is False
    assert slate["resolved"] is True
    assert slate["week"] == 1
    assert slate["game_count"] >= 1
