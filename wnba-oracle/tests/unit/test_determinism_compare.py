"""Content-based artifact comparison for the determinism gate.

Pickle SHAs are not byte-stable for LightGBM Boosters even under
content-deterministic training. The gate compares trained-model CONTENT via
`artifact_content_equal`. These tests pin that an artifact equals itself and
differs from a distinct artifact.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pytest

from wnba_oracle.train.pipeline import artifact_content_equal

MODELS = Path(__file__).resolve().parents[2] / "models"


def _artifacts() -> list[Path]:
    """Glob whatever picker artifacts are committed, rather than pinning two
    specific SHAs. Model rotation replaces the filenames; pinning them made the
    determinism safety-net silently `skip` (go dark) after a promotion."""
    return sorted(MODELS.glob("picker_*.pkl"))


def _load(path: Path):
    with open(path, "rb") as fh:
        return pickle.load(fh)


def test_artifact_equals_itself() -> None:
    arts = _artifacts()
    if not arts:
        pytest.skip("no picker artifacts present")
    art = _load(arts[0])
    equal, reason = artifact_content_equal(art, art)
    assert equal is True
    assert reason == "content-identical"


def test_distinct_artifacts_differ() -> None:
    arts = _artifacts()
    if len(arts) < 2:
        pytest.skip("need >= 2 distinct artifacts")
    a, b = _load(arts[0]), _load(arts[1])
    equal, reason = artifact_content_equal(a, b)
    assert equal is False
    assert reason  # names the first divergence


def test_reload_of_same_pickle_is_equal() -> None:
    """A re-pickled / re-loaded copy is content-equal even though the pickle
    bytes can differ. This is exactly the case the old SHA check got wrong."""
    arts = _artifacts()
    if not arts:
        pytest.skip("no picker artifacts present")
    art = _load(arts[0])
    reloaded = pickle.loads(pickle.dumps(art))
    equal, reason = artifact_content_equal(art, reloaded)
    assert equal is True, reason
