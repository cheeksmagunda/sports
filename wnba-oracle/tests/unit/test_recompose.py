"""predict_real_score recompose helpers + fallback (D63, Phase 2)."""

from __future__ import annotations

import numpy as np
import polars as pl

from wnba_oracle.train.pipeline import PickerArtifact, _sorted_quantiles


def test_sorted_quantiles_removes_crossing_and_floors() -> None:
    # Crossed quantiles (p10 > p50) and a sub-floor value.
    q = {
        0.1: np.array([5.0, 0.001]),
        0.5: np.array([3.0, 2.0]),
        0.9: np.array([8.0, 1.0]),
    }
    out = _sorted_quantiles(q, floor=0.5)
    # Row 0: sorted to (3,5,8) -> all >= floor.
    assert out[0.1][0] == 3.0 and out[0.5][0] == 5.0 and out[0.9][0] == 8.0
    # Row 1: sorted to (0.001,1,2) then floored at 0.5 -> (0.5,1,2).
    assert out[0.1][1] == 0.5 and out[0.5][1] == 1.0 and out[0.9][1] == 2.0
    for a in (out[0.1], out[0.5], out[0.9]):
        assert np.all(a >= 0.5)
    assert np.all(out[0.1] <= out[0.5]) and np.all(out[0.5] <= out[0.9])


def test_predict_real_score_none_without_heads() -> None:
    # An artifact with no trained heads cannot recompose -> caller falls back.
    art = PickerArtifact(feature_module_sha="x", config={})
    frame = pl.DataFrame({"position": ["F", "G"], "mins_l5": [20.0, 25.0]})
    assert art.predict_real_score(frame) is None


def test_predict_real_score_none_on_empty_frame() -> None:
    art = PickerArtifact(feature_module_sha="x", config={})
    assert art.predict_real_score(pl.DataFrame({"position": []})) is None
