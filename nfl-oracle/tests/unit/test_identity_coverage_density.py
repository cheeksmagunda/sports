"""Offline identity + coverage density fixtures and helpers."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nfl_oracle.data.catalog import load_season_game_catalog
from nfl_oracle.data.coverage_matrix import load_coverage_matrix_doc
from nfl_oracle.data.density import summarize_coverage_density
from nfl_oracle.data.summary import research_data_summary
from nfl_oracle.identity import (
    IdentityMap,
    load_identity_map_from_players_file,
    research_identity_summary,
    summarize_identity_density,
    upsert_from_players_payload,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def test_dense_players_fixture_identity_density() -> None:
    payload = json.loads((FIXTURES / "identity" / "dense_players.json").read_text(encoding="utf-8"))
    ident = IdentityMap()
    n = upsert_from_players_payload(ident, payload)
    assert n >= 100
    density = summarize_identity_density(ident)
    assert density.n_identities == n
    assert density.n_complete >= 70
    assert density.complete_ratio > 0.8
    assert density.n_with_external_alias >= 50
    assert density.alias_ratio > 0.5
    assert density.n_with_display_name >= 36
    assert "QB" in density.position_counts
    assert "DEF" in density.position_counts
    dumped = density.to_dict()
    assert dumped["n_complete"] == density.n_complete
    assert "complete_ratio" in dumped


def test_first_last_name_compose_for_density() -> None:
    ident = IdentityMap()
    n = upsert_from_players_payload(
        ident,
        {
            "players": [
                {
                    "id": 1,
                    "firstName": "Ada",
                    "lastName": "QB",
                    "position": "QB",
                    "teamId": 7,
                }
            ]
        },
    )
    assert n == 1
    record = ident.get(1)
    assert record is not None
    assert record.display_name == "Ada QB"
    dens = summarize_identity_density(ident)
    assert dens.n_complete == 1


def test_dense_coverage_fixture_density() -> None:
    catalog = load_season_game_catalog(FIXTURES / "coverage" / "dense_catalog.json")
    matrix = load_coverage_matrix_doc(FIXTURES / "coverage" / "dense_matrix.json")
    dens = summarize_coverage_density(catalog=catalog, matrix=matrix)
    assert dens.catalog_season_count == 14
    assert dens.catalog_seed_game_count == 70
    assert dens.mean_seeds_per_season == pytest.approx(70 / 14)
    assert dens.min_seeds_per_season == 4
    assert dens.max_seeds_per_season == 6
    assert dens.status_counts["known"] == 12
    assert dens.status_counts["unknown"] == 1
    assert dens.status_counts["blocked"] == 1
    assert dens.known_ratio == pytest.approx(12 / 14)
    assert dens.matrix_game_id_count == 40
    assert dens.seasons_with_zero_matrix_games == 2


def test_research_summary_includes_density_and_identity_from_offline_root() -> None:
    root = FIXTURES / "offline_research"
    summary = research_data_summary(project_root=root)
    assert summary["contest_entry"] is False
    assert summary["density"]["catalog_season_count"] == 14
    assert summary["density"]["catalog_seed_game_count"] == 70
    assert summary["density"]["status_counts"]["known"] == 12
    assert summary["coverage_matrix"]["path_exists"] is True
    assert summary["identity"]["path_exists"] is True
    assert summary["identity"]["n_identities"] >= 100
    assert summary["identity"]["density"]["n_complete"] >= 70
    assert summary["schedule"]["density"]["season_count"] >= 8
    assert "coverage_census" in summary["schedule"]


def test_load_identity_map_from_offline_players_file() -> None:
    path = FIXTURES / "offline_research" / "data" / "identity" / "players.json"
    ident = load_identity_map_from_players_file(path)
    assert len(ident) >= 100
    summary = research_identity_summary(players_path=path)
    assert summary["contest_entry"] is False
    assert summary["error"] is None
    assert summary["density"]["complete_ratio"] > 0.8
    assert summary["density"]["n_with_external_alias"] >= 50
    assert summary["aliases"]["n_with_external_alias"] >= 50
