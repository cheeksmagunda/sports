"""Sweep OPTIMIZER_MAX_SINGLE_BOOST against the corpus counterfactual.

Winner lineups on 2026-06-22 and other slates used boost-3.0 lottery cards
(Madina Okot, Zia Cooke), which the live picker excludes at
MAX_SINGLE_BOOST=2.5. This script re-runs the loss_ledger counterfactual
selection at multiple caps to measure whether relaxing the ceiling would
close the gap. Uses the same guardrails as the live picker (anchor floor,
team cap, boost_sum_cap) so the delta is knob-specific.

Usage:
    uv run --extra dev python scripts/sweep_max_boost.py
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT))

from scripts.loss_ledger import _OFF_OVERLAY, _run_counterfactual, build_ledger  # noqa: E402

CAPS = [2.5, 3.0, 0.0]  # 0.0 = disabled (uncapped)


def main() -> int:
    ledger = build_ledger(limit=30)
    print(f"loaded {len(ledger)} slates from the ledger\n")

    baseline = _run_counterfactual(ledger, overlay=_OFF_OVERLAY, max_single_boost=CAPS[0])
    baseline_by_slate = {r["slate"]: r for r in baseline}

    print(
        f"{'cap':>6}{'overlay':>14}{'n':>6}{'up_vs_base':>12}"
        f"{'down_vs_base':>14}{'total_delta':>13}{'beat_median':>13}"
    )
    for cap in CAPS:
        for overlay in (_OFF_OVERLAY, "starter-fade"):
            rows = _run_counterfactual(ledger, overlay=overlay, max_single_boost=cap)
            n_up = n_down = n_beat = 0
            total = 0.0
            for r in rows:
                base = baseline_by_slate.get(r["slate"])
                if base is None:
                    continue
                delta = r["new"] - base["new"]
                if delta > 0.1:
                    n_up += 1
                elif delta < -0.1:
                    n_down += 1
                total += delta
                if r["gap_after"] is not None and r["gap_after"] <= 0:
                    n_beat += 1
            label = f"{cap:g}" if cap > 0 else "off"
            print(
                f"{label:>6}{overlay:>14}{len(rows):>6}{n_up:>12}{n_down:>14}"
                f"{total:>+13.1f}{n_beat:>13}"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
