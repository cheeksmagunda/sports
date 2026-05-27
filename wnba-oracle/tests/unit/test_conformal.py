"""MondrianCQR sanity tests."""

from __future__ import annotations

import numpy as np

from wnba_oracle.eval.conformal import MondrianCQR


def test_mondrian_cqr_per_cell_bands_widen_when_residuals_are_larger() -> None:
    rng = np.random.default_rng(0)
    y = rng.normal(0, 1, 500)
    q_lo = y - 0.5
    q_hi = y + 0.5
    cells = [("G",) if i < 250 else ("F",) for i in range(500)]
    # Inject big residuals into the F cell
    y[250:] = y[250:] + rng.normal(0, 2.0, 250)
    cqr = MondrianCQR(target_coverage=0.8)
    cqr.fit(y, q_lo, q_hi, cells)
    # F should have a larger correction than G
    assert cqr.cell_q[("F",)] > cqr.cell_q[("G",)]


def test_mondrian_cqr_adjust_widens_bands_when_residuals_exceed() -> None:
    """When the calibration residuals are LARGER than the model bands, the
    correction widens; when they are smaller (band over-covers), it shrinks.
    The CQR `adjust` should always be symmetric on both sides."""
    rng = np.random.default_rng(0)
    n = 200
    y = rng.normal(0, 1, n)
    q_lo = y - 0.1  # model is over-confident: band 0.2 wide but truth varies more
    q_hi = y + 0.1
    # Make q_lo/q_hi the same band but mis-positioned so residuals stack up
    q_lo = np.full(n, -0.1)
    q_hi = np.full(n, 0.1)
    cells = [("G",)] * n
    cqr = MondrianCQR(target_coverage=0.9)
    cqr.fit(y, q_lo, q_hi, cells)
    new_lo, new_hi = cqr.adjust(q_lo, q_hi, cells)
    # New band is wider than the original
    assert (new_hi - new_lo).mean() > (q_hi - q_lo).mean()


def test_mondrian_cqr_adjust_shrinks_when_overcovered() -> None:
    """When the band over-covers (truth always inside), the correction is
    negative and the band shrinks. This is the dual of widening."""
    y = np.zeros(50)
    q_lo = y - 0.5
    q_hi = y + 0.5
    cells = [("G",)] * 50
    cqr = MondrianCQR(target_coverage=0.9)
    cqr.fit(y, q_lo, q_hi, cells)
    new_lo, new_hi = cqr.adjust(q_lo, q_hi, cells)
    assert (new_hi - new_lo).mean() < (q_hi - q_lo).mean()
