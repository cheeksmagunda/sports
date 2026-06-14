"""D-session: content-based artifact comparison for the determinism gate.

NEEDS_HUMAN #14: `make determinism-check` compared pickle SHAs, which are not
byte-stable for LightGBM Boosters even under content-deterministic training.
The fix compares trained-model CONTENT via `artifact_content_equal`. These
tests pin that an artifact equals itself and differs from a distinct artifact.
"""

from __future__ import annotations

import pickle
from pathlib import Path

import pytest

from wnba_oracle.train.pipeline import artifact_content_equal

MODELS = Path(__file__).resolve().parents[2] / "models"


def _load(name: str):
    path = MODELS / name
    if not path.exists():
        pytest.skip(f"artifact {name} not present")
    with open(path, "rb") as fh:
        return pickle.load(fh)


def test_artifact_equals_itself() -> None:
    art = _load("picker_e2ced9ec_1780873338.pkl")
    equal, reason = artifact_content_equal(art, art)
    assert equal is True
    assert reason == "content-identical"


def test_distinct_artifacts_differ() -> None:
    a = _load("picker_e2ced9ec_1780873338.pkl")
    b = _load("picker_bf3c8996_1780752059.pkl")
    equal, reason = artifact_content_equal(a, b)
    assert equal is False
    assert reason  # names the first divergence


def test_reload_of_same_pickle_is_equal() -> None:
    """A re-pickled / re-loaded copy is content-equal even though the pickle
    bytes can differ. This is exactly the case the old SHA check got wrong."""
    art = _load("picker_e2ced9ec_1780873338.pkl")
    reloaded = pickle.loads(pickle.dumps(art))
    equal, reason = artifact_content_equal(art, reloaded)
    assert equal is True, reason
