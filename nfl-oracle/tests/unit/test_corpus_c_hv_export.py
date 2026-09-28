"""Corpus C offline Total Value / HV board export (issue #526)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nfl_oracle.contests.hv_export import (
    COVERAGE_MANIFEST_FILENAME,
    DRAFT_STATS_FILENAME,
    HV_SECTION,
    MATCHUPS_FILENAME,
    TOTAL_VALUE_FILENAME,
    export_corpus_c,
    resolve_corpus_c_root,
)
from nfl_oracle.contests.store import ContestStore

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "corpus_c_hv"
DRIVE_FIXTURES = Path(__file__).resolve().parents[3] / "drive" / "nfl_fixtures"


def test_resolve_corpus_c_root_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "volume" / "raw" / "corpus_c"
    target.mkdir(parents=True)
    monkeypatch.setenv("NFL_CORPUS_C_ROOT", str(target))
    assert resolve_corpus_c_root() == target.resolve()


def test_empty_volume_scaffolds_coverage_manifest(tmp_path: Path) -> None:
    missing = tmp_path / "no_such_corpus_c"
    export_root = tmp_path / "export"
    summary = export_corpus_c(corpus_root=missing, export_root=export_root)
    assert summary.volume_empty is True
    assert summary.contests_seen == 0
    manifest = export_root / COVERAGE_MANIFEST_FILENAME
    assert manifest.is_file()
    body = json.loads(manifest.read_text(encoding="utf-8"))
    assert body["volume_empty"] is True
    assert body["railway_volume_mount"] == "/app/nfl-oracle/data"
    assert any(g["kind"] == "corpus_c_missing" for g in body["gaps"])
    assert (export_root / "scaffold.json").is_file()


def test_export_fixture_contest_with_hv_section(tmp_path: Path) -> None:
    export_root = tmp_path / "export"
    summary = export_corpus_c(
        corpus_root=FIXTURES,
        export_root=export_root,
        contest_ids=[9001],
    )
    assert summary.volume_empty is False
    assert summary.contests_exported == 1
    contest_dir = export_root / "nfl" / "2025" / "2025-09-15" / "contest_9001"
    tv = json.loads((contest_dir / TOTAL_VALUE_FILENAME).read_text(encoding="utf-8"))
    assert tv["section"] == HV_SECTION
    assert tv["source"] == f"draft_stats.{HV_SECTION}"
    assert tv["player_count"] == 6
    # Display rank is value * (2 + boost), not raw base. Player 405
    # (3.4 base, 2.0 boost) outranks raw leader 401 (5.0 base, 0 boost).
    assert tv["players"][0]["player_id"] == 405
    assert tv["players"][0]["rank"] == 1
    assert tv["players"][0]["value"] == 3.4 or float(tv["players"][0]["value"]) == 3.4

    lines = (contest_dir / DRAFT_STATS_FILENAME).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 7  # 6 HV + 1 mostDrafted
    sections = {json.loads(line)["section"] for line in lines}
    assert HV_SECTION in sections
    assert "mostDraftedPlayers" in sections

    matchups = json.loads((contest_dir / MATCHUPS_FILENAME).read_text(encoding="utf-8"))
    assert matchups["present"] is True
    assert 19457 in matchups["game_ids"]
    assert any("19457" in p for p in matchups["corpus_g_paths"])

    # Drive fixture game id exists for coordination with Corpus G fixtures.
    assert (DRIVE_FIXTURES / "game_19457_stats.json").is_file()


def test_export_reconstructs_when_hv_section_missing(tmp_path: Path) -> None:
    export_root = tmp_path / "export"
    summary = export_corpus_c(
        corpus_root=FIXTURES,
        export_root=export_root,
        contest_ids=[9002],
    )
    result = summary.results[0]
    assert result.status in {"exported", "partial"}
    assert "missing_hv_section" in result.gaps
    contest_dir = export_root / "nfl" / "2025" / "2025-09-15" / "contest_9002"
    tv = json.loads((contest_dir / TOTAL_VALUE_FILENAME).read_text(encoding="utf-8"))
    assert tv["source"] == "nfl_draft_stats_reconstructed"
    assert tv["player_count"] >= 1
    assert "no_matchup_links" in result.gaps


def test_export_all_fixture_contests_writes_manifest(tmp_path: Path) -> None:
    export_root = tmp_path / "export"
    summary = export_corpus_c(corpus_root=FIXTURES, export_root=export_root)
    assert summary.contests_seen == 2
    manifest = json.loads((export_root / COVERAGE_MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert manifest["sport"] == "nfl"
    assert "Corpus G/C are not on the backups branch" in manifest["notes"]


def test_store_collected_ids_matches_fixtures() -> None:
    store = ContestStore(FIXTURES)
    assert store.collected_ids() == [9001, 9002]
