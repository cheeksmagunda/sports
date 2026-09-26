"""Offline tests for the WNBA race corpus builder stub (#337)."""

from __future__ import annotations

import importlib.util
import json
import pathlib
import sys
from types import ModuleType

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts"


def _load_script() -> ModuleType:
    # Ensure corpus_backup_common is importable the same way the script does.
    sys.path.insert(0, str(SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location(
        "build_race_corpus", SCRIPTS_DIR / "build_race_corpus.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_seasons_all_and_list() -> None:
    mod = _load_script()
    assert mod.parse_seasons("all") is None
    assert mod.parse_seasons("2024,2026") == frozenset({"2024", "2026"})
    with pytest.raises(ValueError, match="YYYY"):
        mod.parse_seasons("26")


def test_in_seasons_filters_by_year() -> None:
    mod = _load_script()
    assert mod.in_seasons("2026-09-25", None) is True
    assert mod.in_seasons("2026-09-25", frozenset({"2026"})) is True
    assert mod.in_seasons("2025-07-01", frozenset({"2026"})) is False


def test_stub_build_and_verify_round_trip(tmp_path: pathlib.Path) -> None:
    mod = _load_script()
    out = tmp_path / "wnba"
    assert mod.main(["--stub", "--seasons", "2026", "--out", str(out)]) == 0
    manifest_path = out / "manifest.json"
    decoded = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert decoded["kind"] == "wnba_race_corpus"
    assert decoded["stub"] is True
    assert decoded["seasons"] == ["2026"]
    assert (out / "season=2026" / "finishers.parquet").is_file()
    assert (out / "season=2026" / "shark_priors.parquet").is_file()
    assert mod.main(["--verify-only", "--out", str(out)]) == 0


def test_verify_rejects_tampered_hash(tmp_path: pathlib.Path) -> None:
    mod = _load_script()
    out = tmp_path / "wnba"
    assert mod.main(["--stub", "--stub-seasons", "2025", "--out", str(out)]) == 0
    payload = out / "season=2025" / "field.parquet"
    payload.write_bytes(payload.read_bytes() + b"x")
    with pytest.raises(mod.RaceCorpusValidationError, match="hash"):
        mod.verify_race_corpus(out)
