"""Additional research API + fixture honesty edges for draft readiness."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nfl_oracle.calendar.schedule import load_schedules_csv, summarize_schedule_density
from nfl_oracle.data.catalog import load_season_game_catalog
from nfl_oracle.data.coverage_matrix import load_coverage_matrix_doc
from nfl_oracle.data.density import summarize_coverage_density
from nfl_oracle.providers.five_card import FiveCardProviderStub, ProviderNotReady
from nfl_oracle.service.app import create_app
from nfl_oracle.strategy.schema import FiveCardAction

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
OFFLINE = FIXTURES / "offline_research"


def _client() -> TestClient:
    return TestClient(create_app(project_root=OFFLINE))


def test_offline_research_mirrors_dense_coverage_and_identity() -> None:
    dense_cat = load_season_game_catalog(FIXTURES / "coverage" / "dense_catalog.json")
    off_cat = load_season_game_catalog(OFFLINE / "data" / "catalog" / "season_game_ids.json")
    assert dense_cat.to_json_obj() == off_cat.to_json_obj()
    dense_mat = load_coverage_matrix_doc(FIXTURES / "coverage" / "dense_matrix.json")
    off_mat = load_coverage_matrix_doc(OFFLINE / "data" / "catalog" / "coverage_matrix.json")
    dens = summarize_coverage_density(catalog=off_cat, matrix=off_mat)
    assert dens.catalog_season_count == 12
    assert dens.catalog_seed_game_count == 56
    assert dens.status_counts["known"] == 10
    assert dens.matrix_game_id_count == 32
    assert dense_mat.seasons.keys() == off_mat.seasons.keys()


def test_schedule_fixture_four_seasons_density() -> None:
    games = load_schedules_csv(FIXTURES / "schedule" / "dense_schedules.csv")
    dens = summarize_schedule_density(games)
    assert dens.season_count == 4
    assert dens.game_count >= 36
    assert dens.week_count >= 12
    assert set(dens.seasons) == {2022, 2023, 2024, 2025}
    assert dens.missing_gameday_count >= 1


def test_research_root_and_schema_documents_observation_only() -> None:
    client = _client()
    root = client.get("/").json()
    assert root["contest_entry"] is False
    assert root["mode"] == "research_shadow"
    labels = client.get("/research/schemas/labels").json()
    strategy = client.get("/research/schemas/strategy").json()
    features = client.get("/research/schemas/features").json()
    scoring = client.get("/research/schemas/scoring").json()
    assert isinstance(labels, dict) and labels
    assert isinstance(strategy, dict) and strategy
    assert strategy.get("contest_entry") is False
    assert isinstance(features, dict) and features
    assert scoring["contest_entry"] is False
    assert scoring["name"] == "nfl_contest_scoring_algebra"


def test_shadow_preview_without_values_still_denies_entry() -> None:
    client = _client()
    resp = client.post(
        "/research/shadow/preview",
        json={"player_ids": [1, 2, 3, 4, 5], "include_best_ordering": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["contest_entry"] is False
    assert "contest_shadow_score" not in body
    assert "best_ordering" not in body


def test_rank_orderings_top_k_and_non_algebra() -> None:
    client = _client()
    payload = {
        "player_ids": [11, 22, 33, 44, 55],
        "values_by_player": {"11": 8, "22": 6, "33": 4, "44": 2, "55": 1},
        "top_k": 3,
        "use_contest_algebra": False,
        "slot_multipliers": [5, 4, 3, 2, 1],
    }
    resp = client.post("/research/shadow/rank-orderings", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["contest_entry"] is False
    assert body["use_contest_algebra"] is False
    assert body["returned"] == 3
    assert body["orderings_evaluated"] == 120
    assert body["rankings"][0]["total"] >= body["rankings"][-1]["total"]


def test_rank_orderings_top_k_out_of_range_422() -> None:
    client = _client()
    too_high = client.post(
        "/research/shadow/rank-orderings",
        json={
            "player_ids": [1, 2, 3, 4, 5],
            "values_by_player": {"1": 1, "2": 1, "3": 1, "4": 1, "5": 1},
            "top_k": 121,
        },
    )
    assert too_high.status_code == 422
    too_low = client.post(
        "/research/shadow/rank-orderings",
        json={
            "player_ids": [1, 2, 3, 4, 5],
            "values_by_player": {"1": 1, "2": 1, "3": 1, "4": 1, "5": 1},
            "top_k": 0,
        },
    )
    assert too_low.status_code == 422


def test_status_auth_block_has_no_secret_values() -> None:
    client = _client()
    status = client.get("/research/status").json()
    auth = status["auth"]
    assert set(auth.keys()) <= {"usable", "status", "note"}
    assert "eyJ" not in str(status)  # no jwt-ish secret blobs
    assert auth["note"]
    assert status["draft_readiness"]["submit_hard_denied"] is True
    assert status["draft_readiness"]["railway_deploy_ready"] is False
    assert status["railway"]["in_repo_config"] is False


def test_provider_submit_remains_hard_denied_after_shadow() -> None:
    client = _client()
    preview = client.post(
        "/research/shadow/preview",
        json={
            "player_ids": [1, 2, 3, 4, 5],
            "values_by_player": {"1": 9, "2": 7, "3": 5, "4": 3, "5": 1},
            "use_contest_algebra": True,
        },
    )
    assert preview.status_code == 200
    assert preview.json()["contest_entry"] is False
    stub = FiveCardProviderStub()
    with pytest.raises(ProviderNotReady, match="contest_entry_forbidden"):
        stub.submit(FiveCardAction(player_ids=(1, 2, 3, 4, 5)))


def test_coverage_summary_reports_unknown_and_blocked() -> None:
    client = _client()
    body = client.get("/research/coverage/summary").json()
    counts = body["coverage_matrix"]["status_counts"]
    assert counts["unknown"] == 1
    assert counts["blocked"] == 1
    assert counts["known"] == 10
    assert body["density"]["seasons_with_zero_matrix_games"] == 2
    assert body["contest_entry"] is False
