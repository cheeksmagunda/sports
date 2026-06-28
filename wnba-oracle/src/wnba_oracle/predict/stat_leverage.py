"""Stat-leverage concentration analysis.

The Real Sports scoring formula weights each stat differently. Under the
fitted REAL_SCORE_WEIGHTS (predict/scoring.py), defensive stats per event
are worth more than points per event:

    stl: 0.223, blk: 0.220, ast: 0.204  (high leverage)
    pts: 0.151, oreb: 0.079, reb: 0.080  (moderate leverage)

This is the WNBA analog of the MLB finding that strikeouts (2 pts each,
independent of game outcome) are the highest-leverage pitcher stat. A
player whose production concentrates in high-weight categories generates
more real_score per unit of box-score output than a volume scorer.

Two functions:
- stat_leverage_score: given a player's per-minute rates, compute a
  weighted leverage concentration score.
- is_leverage_efficient: whether a player's production profile tilts
  toward high-leverage stats.
"""

from __future__ import annotations

from wnba_oracle.predict.scoring import REAL_SCORE_WEIGHTS

HIGH_LEVERAGE_STATS = ("stl", "blk", "ast")
MODERATE_LEVERAGE_STATS = ("pts", "oreb", "reb")

HIGH_LEVERAGE_WEIGHT_SUM = sum(
    abs(REAL_SCORE_WEIGHTS[s]) for s in HIGH_LEVERAGE_STATS
)
ALL_POSITIVE_WEIGHT_SUM = sum(
    w for w in REAL_SCORE_WEIGHTS.values() if w > 0
)
HIGH_LEVERAGE_SHARE = HIGH_LEVERAGE_WEIGHT_SUM / ALL_POSITIVE_WEIGHT_SUM


def stat_leverage_score(
    *,
    pts_per_min: float = 0.0,
    ast_per_min: float = 0.0,
    stl_blk_per_min: float = 0.0,
    reb_per_min: float = 0.0,
) -> float:
    """Weighted leverage concentration: fraction of a player's per-minute
    real_score production attributable to high-leverage stats (stl/blk/ast).

    Returns a value in [0, 1]. Higher means more of the player's value
    comes from the efficient stat categories. A pure volume scorer with
    no defensive/playmaking contribution scores 0; a defense-first
    facilitator scores near 1.

    The per-minute rates are stat events per minute (not per game), matching
    the rolling features in features/rolling.py.
    """
    w_stl_blk = abs(REAL_SCORE_WEIGHTS["stl"]) + abs(REAL_SCORE_WEIGHTS["blk"])
    w_ast = abs(REAL_SCORE_WEIGHTS["ast"])
    w_pts = abs(REAL_SCORE_WEIGHTS["pts"])
    w_reb = abs(REAL_SCORE_WEIGHTS["reb"]) + abs(REAL_SCORE_WEIGHTS["oreb"])

    high_contrib = stl_blk_per_min * w_stl_blk + ast_per_min * w_ast
    total_contrib = (
        high_contrib
        + pts_per_min * w_pts
        + reb_per_min * w_reb
    )
    if total_contrib <= 0:
        return 0.0
    return min(1.0, high_contrib / total_contrib)


def is_leverage_efficient(
    *,
    pts_per_min: float = 0.0,
    ast_per_min: float = 0.0,
    stl_blk_per_min: float = 0.0,
    reb_per_min: float = 0.0,
    threshold: float = 0.45,
) -> bool:
    """True when a player's production tilts toward high-leverage stats
    above a threshold. Default 0.45 is calibrated to roughly the top
    tercile of WNBA per-minute profiles (guards with high assist rates
    and/or defensive specialists with steal/block rates).
    """
    return stat_leverage_score(
        pts_per_min=pts_per_min,
        ast_per_min=ast_per_min,
        stl_blk_per_min=stl_blk_per_min,
        reb_per_min=reb_per_min,
    ) >= threshold
