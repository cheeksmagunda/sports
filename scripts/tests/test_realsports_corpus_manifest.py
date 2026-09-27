"""Offline unit checks for Real Sports corpus staging and coverage (#526)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
FIXTURE = SCRIPTS / "realsports_corpus" / "fixtures" / "proof_slate"

sys.path.insert(0, str(SCRIPTS))

from realsports_corpus.coverage_manifest import (
    OllamaForbiddenError,
    assert_ollama_helper_forbidden,
    build_empty_manifest,
    ollama_helper_allowed,
)
from realsports_corpus.layout import (
    REQUIRED_VARIABLE_FAMILIES,
    ensure_kind_roots,
)
from realsports_corpus.stage_append import _stage_append


@pytest.fixture()
def corpus_root(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    ensure_kind_roots(root)
    empty = build_empty_manifest()
    (root / "coverage_manifest.json").write_text(
        json.dumps(empty.to_dict(), indent=2) + "\n",
        encoding="utf-8",
    )
    return root


def test_stage_fixture_soft_merges_coverage(corpus_root: Path) -> None:
    _stage_append(
        corpus_root,
        FIXTURE,
        sport="nfl",
        year="2026",
        slate_date="2026-01-01",
        kind="total_value_leaderboards",
        label="proof_slate",
    )
    payload = (
        corpus_root
        / "total_value_leaderboards"
        / "nfl"
        / "2026"
        / "slate_2026-01-01"
        / "payload.json"
    )
    assert payload.is_file()
    manifest = json.loads(
        (corpus_root / "coverage_manifest.json").read_text(encoding="utf-8")
    )
    slate = manifest["sports"]["nfl"]["years"]["2026"]["slates"]["2026-01-01"]
    assert slate["status"] == "partial"
    assert slate["kinds"]["total_value_leaderboards"]["status"] == "present"
    assert "proof_slate" in slate["labels"]
    assert manifest["updated_at"]


def test_stage_append_is_idempotent(corpus_root: Path) -> None:
    for _ in range(2):
        _stage_append(
            corpus_root,
            FIXTURE,
            sport="nfl",
            year="2026",
            slate_date="2026-01-01",
            kind="total_value_leaderboards",
            label="proof_slate",
        )
    manifest = json.loads(
        (corpus_root / "coverage_manifest.json").read_text(encoding="utf-8")
    )
    labels = manifest["sports"]["nfl"]["years"]["2026"]["slates"]["2026-01-01"][
        "labels"
    ]
    assert labels.count("proof_slate") == 1


def test_ollama_helper_forbidden_until_complete(corpus_root: Path) -> None:
    empty = build_empty_manifest()
    assert ollama_helper_allowed(empty) is False
    with pytest.raises(OllamaForbiddenError):
        assert_ollama_helper_forbidden(empty)
    assert len(REQUIRED_VARIABLE_FAMILIES) >= 9
