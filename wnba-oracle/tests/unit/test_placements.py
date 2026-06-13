"""Placement / calibration tracking (D90, Phase 2).

Pure-function tests for the math layer of `scheduler/placements.py`. The DB
layer is exercised in integration tests; here we pin:

  - PIT computation correctness (and clipping at the upper tail).
  - PIT histogram + chi-square diagnostics behave sensibly on
    calibrated vs U-shape vs dome distributions.
  - Per-decile log-loss bucketing.
  - PlacementRow derived fields (finish_percentile, roi).
  - summarize-style aggregation respects display thresholds.
"""

from __future__ import annotations

import math

from wnba_oracle.scheduler.placements import (
    PlacementRow,
    chi2_uniformity_pvalue,
    compute_pit_value,
    ownership_log_loss_by_decile,
    pit_histogram,
    render_summary_markdown,
)


def test_pit_clips_to_top_of_cdf() -> None:
    cdf = {0.05: 0.10, 0.20: 0.30, 0.50: 0.60}
    # Finish at the 50th percentile -> top tail of the CDF; returns 0.60.
    assert compute_pit_value(0.50, cdf) == 0.60
    # Finish well below 50th -> first matching bin.
    assert compute_pit_value(0.04, cdf) == 0.10
    # Finish above 50% -> upper tail clip.
    assert compute_pit_value(0.85, cdf) == 0.60


def test_pit_value_handles_missing_cdf() -> None:
    assert compute_pit_value(0.5, None) is None
    assert compute_pit_value(0.5, {}) is None


def test_pit_histogram_counts_correctly() -> None:
    # 10 values, one in each bin -> flat (perfect calibration).
    flat = [0.05, 0.15, 0.25, 0.35, 0.45, 0.55, 0.65, 0.75, 0.85, 0.95]
    counts = pit_histogram(flat, n_bins=10)
    assert counts == [1] * 10
    # All values at the upper edge land in the top bin only when < 1.0.
    edge = pit_histogram([0.99, 1.0, 0.999], n_bins=10)
    assert edge[-1] == 3


def test_pit_histogram_drops_oob_values() -> None:
    counts = pit_histogram([-0.1, 0.5, 1.5, float("nan"), 0.0, 1.0], n_bins=4)
    # 0.0 -> bin 0, 0.5 -> bin 2, 1.0 -> bin 3 (clipped to last). -0.1/1.5/nan dropped.
    assert sum(counts) == 3
    assert counts[0] == 1
    assert counts[2] == 1
    assert counts[3] == 1


def test_chi2_returns_none_when_underpowered() -> None:
    """Fewer than 30 PIT values -> the chi-square test is underpowered."""
    counts = [2] * 10  # total 20 < 30 threshold
    assert chi2_uniformity_pvalue(counts) is None


def test_chi2_rejects_obvious_u_shape() -> None:
    """A U-shaped histogram on 100 PIT values (50 in bin 0, 50 in bin 9)
    should produce a tiny p-value, signalling the simulator is under-dispersed.
    """
    counts = [50, 0, 0, 0, 0, 0, 0, 0, 0, 50]
    p = chi2_uniformity_pvalue(counts)
    assert p is not None
    assert p < 0.05


def test_chi2_accepts_uniform_distribution() -> None:
    """A flat 100-PIT histogram should not be rejected by chi2."""
    counts = [10] * 10
    p = chi2_uniformity_pvalue(counts)
    assert p is not None
    assert p > 0.10


def test_ownership_log_loss_buckets_by_projected() -> None:
    """Players with projected 0.05 land in decile 0, projected 0.45 lands
    in decile 4, etc.
    """
    projected = {1: 0.05, 2: 0.45, 3: 0.85}
    actual = {1: 0.04, 2: 0.50, 3: 0.80}
    out = ownership_log_loss_by_decile(projected, actual)
    assert len(out) == 10
    # Decile 0 (0.0-0.1) has player 1.
    assert out[0][2] == 1
    assert out[4][2] == 1  # decile 4 (0.4-0.5) has player 2
    assert out[8][2] == 1  # decile 8 (0.8-0.9) has player 3


def test_ownership_log_loss_returns_empty_when_no_overlap() -> None:
    assert ownership_log_loss_by_decile({1: 0.5}, {2: 0.5}) == []
    assert ownership_log_loss_by_decile({}, {}) == []


def test_ownership_log_loss_finite_for_calibrated_inputs() -> None:
    """Perfectly calibrated p == y inputs should give log-loss == entropy(y),
    which is finite across populated buckets without crashing."""
    projected = {i: 0.05 + 0.01 * i for i in range(8)}
    actual = {i: 0.05 + 0.01 * i for i in range(8)}
    out = ownership_log_loss_by_decile(projected, actual)
    nonempty = [(bound, ll, n) for bound, ll, n in out if n > 0]
    assert len(nonempty) >= 1
    for _bound, ll, _n in nonempty:
        assert math.isfinite(ll)


def test_placement_row_finish_percentile() -> None:
    r = PlacementRow(
        slate_date="2026-06-12",
        contest_id=1,
        entry_rank=4253,
        entry_count=8300,
        entry_score=32.4,
        payout_cents=0,
        entry_fee_cents=100,
    )
    assert r.finish_percentile is not None
    assert abs(r.finish_percentile - 4253 / 8300) < 1e-9
    # ROI of -1.0 for a $0 payout / $1 entry fee.
    assert r.roi == -1.0


def test_placement_row_handles_missing_rank() -> None:
    r = PlacementRow(
        slate_date="2026-06-12",
        contest_id=1,
        entry_rank=None,
        entry_count=8300,
        entry_score=None,
        payout_cents=None,
        entry_fee_cents=None,
    )
    assert r.finish_percentile is None
    assert r.roi is None


def test_render_summary_markdown_includes_warning_below_threshold() -> None:
    """A summary with fewer than the tuning threshold should warn against
    knob-twisting from the small sample."""
    summary = {
        "n_placements": 10,
        "median_finish_percentile": 0.51,
        "cash_rate": 0.30,
        "top_10pct_rate": 0.05,
        "top_1pct_rate": 0.00,
        "tuning_warning": "do not tune objective weights below 100 slates (have 10; small-sample overfitting risk)",
    }
    md = render_summary_markdown(summary)
    assert "tune objective weights" in md
    assert "10 slates" in md
    assert "Top 10%" in md


def test_render_summary_markdown_empty() -> None:
    assert "No placements" in render_summary_markdown({"n_placements": 0})
