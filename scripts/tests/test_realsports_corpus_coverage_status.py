"""Offline coverage_manifest generate + Ollama gate handoff (#526)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from realsports_corpus.coverage_manifest import (
    is_historical_capture_complete,
    ollama_helper_allowed,
)
from realsports_corpus.generate_coverage_status import (
    build_status_report,
    main as generate_main,
    run_offline_fixture_export,
)


def test_offline_generate_forbids_ollama(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    manifest, results = run_offline_fixture_export(corpus)
    assert results
    assert (corpus / "coverage_manifest.json").is_file()
    assert not is_historical_capture_complete(manifest)
    assert not ollama_helper_allowed(manifest)
    report = build_status_report(manifest)
    assert report["ollama_gate"] == "FORBIDDEN"
    assert report["historical_capture_complete"] is False
    assert len(report["operator_unlock_checklist"]) >= 5
    assert report["family_status_rollup"]["nba"]["players"] == "stub"
    # NFL fixture should mark HV present via Corpus C.
    assert report["family_status_rollup"]["nfl"]["total_value_leaderboards"] in {
        "present",
        "partial",
    }


def test_cli_writes_status_files(tmp_path: Path) -> None:
    out = tmp_path / "out"
    assert generate_main(["--out-dir", str(out)]) == 0
    assert (out / "coverage_manifest.json").is_file()
    assert (out / "coverage_status.json").is_file()
    assert (out / "coverage_status.md").is_file()
    payload = json.loads((out / "coverage_status.json").read_text(encoding="utf-8"))
    assert payload["ollama"] is False
    assert payload["mode"] == "offline_fixture_dry_run"
