"""Real Sports corpus layout and durable-store export stubs (#526)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from realsports_corpus.coverage_manifest import (
    OllamaForbiddenError,
    assert_ollama_helper_forbidden,
    build_empty_manifest,
    is_historical_capture_complete,
    ollama_helper_allowed,
    record_family_status,
    write_coverage_manifest,
)
from realsports_corpus.export_stubs import (
    apply_export_results_to_manifest,
    export_nfl_corpus_c_contest,
    export_nfl_corpus_g_game,
    export_wnba_backup_csvs,
    scaffold_all_stub_families,
)
from realsports_corpus.layout import (
    REQUIRED_VARIABLE_FAMILIES,
    SlateKey,
    ensure_kind_roots,
    ensure_slate_layout,
    family_dir,
)

DURABLE = (
    Path(__file__).resolve().parents[1]
    / "realsports_corpus"
    / "fixtures"
    / "durable_stores"
)


def test_required_families_include_operator_kinds() -> None:
    required = set(REQUIRED_VARIABLE_FAMILIES)
    for name in (
        "players",
        "team_weights",
        "lineups",
        "slate_rosters",
        "averages",
        "combined_stats",
        "recorded_states",
        "total_value_leaderboards",
        "matchups",
    ):
        assert name in required


def test_ensure_slate_layout_is_kind_first(tmp_path: Path) -> None:
    key = SlateKey(sport="wnba", year=2025, slate_date="2025-07-01")
    ensure_kind_roots(tmp_path)
    created = ensure_slate_layout(tmp_path, key)
    assert set(created) == set(REQUIRED_VARIABLE_FAMILIES)
    tv = family_dir(tmp_path, key, "total_value_leaderboards")
    assert (
        tv
        == tmp_path / "total_value_leaderboards" / "wnba" / "2025" / "slate_2025-07-01"
    )
    assert tv.is_dir()


def test_ollama_helper_forbidden_until_complete() -> None:
    manifest = build_empty_manifest()
    assert not is_historical_capture_complete(manifest)
    assert not ollama_helper_allowed(manifest)
    with pytest.raises(OllamaForbiddenError, match="FORBIDDEN"):
        assert_ollama_helper_forbidden(manifest)


def test_ollama_allowed_only_when_every_sport_family_present() -> None:
    manifest = build_empty_manifest()
    for sport in ("wnba", "nfl", "nba", "nhl"):
        for family in REQUIRED_VARIABLE_FAMILIES:
            manifest = record_family_status(
                manifest,
                sport=sport,  # type: ignore[arg-type]
                family=family,
                status="present",
                artifact_count=1,
            )
    assert is_historical_capture_complete(manifest)
    assert ollama_helper_allowed(manifest)
    assert_ollama_helper_forbidden(manifest)


def test_wnba_backup_export_maps_hv_and_lineups(tmp_path: Path) -> None:
    key = SlateKey(sport="wnba", year=2025, slate_date="2025-07-01")
    results = export_wnba_backup_csvs(
        corpus_root=tmp_path,
        key=key,
        backup_dir=DURABLE / "wnba_backup",
    )
    families = {r.family for r in results}
    assert "total_value_leaderboards" in families
    assert "players" in families
    assert "lineups" in families
    assert "combined_stats" in families
    tv = (
        family_dir(tmp_path, key, "total_value_leaderboards")
        / "highestBoostedValuePlayers.json"
    )
    payload = json.loads(tv.read_text(encoding="utf-8"))
    assert len(payload["rows"]) == 2
    assert all(r["section"] == "highestBoostedValuePlayers" for r in payload["rows"])


def test_nfl_corpus_g_and_c_export_stubs(tmp_path: Path) -> None:
    key = SlateKey(sport="nfl", year=2025, slate_date="2025-09-07")
    g_results = export_nfl_corpus_g_game(
        corpus_root=tmp_path,
        key=key,
        game_dir=DURABLE / "nfl_corpus_g" / "game_1",
    )
    c_results = export_nfl_corpus_c_contest(
        corpus_root=tmp_path,
        key=key,
        contest_dir=DURABLE / "nfl_corpus_c" / "contest_1",
    )
    results = g_results + c_results
    by_family = {r.family: r for r in results}
    assert by_family["players"].rows == 1
    assert by_family["combined_stats"].rows == 1
    assert by_family["matchups"].rows == 1
    assert by_family["recorded_states"].rows == 1
    assert by_family["feeds"].rows == 1
    assert by_family["total_value_leaderboards"].rows == 1
    assert by_family["draft_stats_all_sections"].rows == 2
    assert by_family["lineups"].rows == 1
    assert by_family["slate_rosters"].rows == 1

    manifest = apply_export_results_to_manifest(
        None,
        sport="nfl",
        results=results,
        year=2025,
        slate_date="2025-09-07",
    )
    assert not ollama_helper_allowed(manifest)
    with pytest.raises(OllamaForbiddenError):
        assert_ollama_helper_forbidden(manifest)


def test_scaffold_stubs_cover_all_families(tmp_path: Path) -> None:
    key = SlateKey(sport="nba", year=2025, slate_date="2025-10-01")
    results = scaffold_all_stub_families(tmp_path, key)
    assert len(results) == len(REQUIRED_VARIABLE_FAMILIES)
    for family in REQUIRED_VARIABLE_FAMILIES:
        stub = family_dir(tmp_path, key, family) / "STUB.json"
        assert stub.is_file()

    out = tmp_path / "coverage_manifest.json"
    write_coverage_manifest(out, build_empty_manifest())
    assert out.is_file()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["historical_capture_complete"] is False
    assert payload["ollama_codespace_helper"]["allowed"] is False
