"""Real Sports real_score reconstructed from the box line (D55).

real_score is a deterministic fantasy formula. Fitting it on the 3,375-row
corpus-vs-nba_api join recovers it at R^2 = 0.957, MAE 0.218 (the ~4% residual
is rounding / a small normalization term we don't need for rate estimation).

Locking the formula lets the minutes pipeline run SELF-CONTAINED on nba_api
game logs: one source gives both minutes and real_score, so the per-minute
rate needs no dependency on slate_labels (which is not reliably maintained on
prod). These are the platform's scoring weights, a fixed constant, not a
predictive model -- so fitting on all data just recovers the function.
"""

from __future__ import annotations

from collections.abc import Mapping

# Fitted weights (scripts/backfill_minutes.py refit, 2026-06-01).
REAL_SCORE_WEIGHTS: dict[str, float] = {
    "pts": 0.15137,
    "reb": 0.08027,
    "oreb": 0.07928,
    "dreb": 0.00099,
    "ast": 0.20396,
    "stl": 0.22278,
    "blk": 0.21969,
    "tov": -0.22861,
    "fgm": 0.05849,
    "fga": -0.05430,
    "fg3m": 0.06453,
    "ftm": -0.03013,
    "fta": -0.00007,
}
REAL_SCORE_INTERCEPT = -0.03557


def box_to_real_score(box: Mapping[str, float]) -> float:
    """Reconstruct real_score from a per-game box line.

    `box` keys are the lowercase stat names in REAL_SCORE_WEIGHTS (missing
    keys treated as 0). Floored at 0.0 (real_score is rarely negative; corpus
    min -0.39, p1 = 0.00).
    """
    total = REAL_SCORE_INTERCEPT
    for stat, w in REAL_SCORE_WEIGHTS.items():
        v = box.get(stat)
        if v is not None:
            total += w * float(v)
    return max(0.0, total)
