"""Draft-popularity estimator + anti-popularity contrarian adjustment.

Ported from basketball-main (NBA Real Sports). Their Finding 4:
draft popularity has -0.457 correlation with realized boost, and the
least-drafted 50% of pool produces ~24-26% more total value than the
most-drafted 50%. The contrarian adjustment penalizes high-popularity
players' projections, which (a) downweights chalk in the optimizer's
expected-payout calculation and (b) makes the lineup more leverageable
in top-20 / top-1 regimes where variance is asset.

Two consumers:
- `estimate_draft_popularity(...)` is the cheap heuristic used when
  measured drafts are not yet available (pregame, or for slates before
  slate_labels has finalized).
- `apply_contrarian_adjustment(...)` returns a modified predicted score
  per player after subtracting `pop_normalized * strength * max_boost`
  per the basketball-main formula.

Once `slate_labels.drafts` populates for a slate, prefer the measured
value over the estimator (see `slate_labels_to_popularity`).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

# WNBA big-market teams. Big-market multiplier increases the popularity
# baseline by 1.3x for players on these teams (basketball-main precedent
# for NBA uses LAL/GSW/BOS/NYK/CHI/PHI/MIA). WNBA equivalents are the
# teams with the largest media markets + national-TV slot frequency.
WNBA_BIG_MARKETS = {"NYL", "LVA", "LAS", "CHI", "PHO", "SEA", "IND"}


def estimate_draft_popularity(
    *,
    season_ppg: float,
    team: str = "",
    recent_ppg: float = 0.0,
    is_national_tv: bool = False,
    n_games_on_slate: int = 6,
) -> float:
    """Cheap popularity score in arbitrary units (not normalized).

    Calibration anchor (from basketball-main): a 20+ ppg star on a big-
    market team in a national-TV game on a 6-game slate produces a
    score around 5000-6000; a 12 ppg role player on a small market in a
    non-TV game produces ~1200-1400.

    `n_games_on_slate` matters because a 3-game slate concentrates
    public drafts on the few star options (multiplier 1.4); a 10-game
    slate diffuses popularity (multiplier 0.8).
    """
    base = float(season_ppg) * 100.0

    # Star name recognition
    if season_ppg >= 22:
        base *= 2.0
    elif season_ppg >= 17:
        base *= 1.5

    # Big-market multiplier
    if (team or "").upper() in WNBA_BIG_MARKETS:
        base *= 1.3

    # National TV
    if is_national_tv:
        base *= 1.2

    # Slate concentration
    if n_games_on_slate <= 3:
        base *= 1.4
    elif n_games_on_slate >= 8:
        base *= 0.8

    # Hot-streak amplifier: recent > 1.2x season -> +15%
    if season_ppg > 0 and recent_ppg > season_ppg * 1.2:
        base *= 1.15

    return base


def slate_labels_to_popularity(drafts: Mapping[int, int]) -> dict[int, float]:
    """Convert measured `drafts` counts (from slate_labels.drafts) into the
    same arbitrary-units scale the estimator uses, by rescaling against
    the median.

    `drafts` is {platform_player_id: int_draft_count}. Returns the same
    mapping with popularity scores comparable to the estimator output.
    """
    if not drafts:
        return {}
    counts = np.array(sorted(drafts.values()))
    if counts.sum() == 0:
        return dict.fromkeys(drafts, 0.0)
    median = float(np.median(counts))
    # Calibrate so median = 2500 (matches the estimator's mid-tier anchor)
    scale = 2500.0 / max(median, 1.0)
    return {int(pid): float(c) * scale for pid, c in drafts.items()}


@dataclass(frozen=True)
class ContrarianConfig:
    enabled: bool = True
    strength: float = 0.2  # basketball-main default; 0.0 disables contrarian tilt
    star_score_anchor: float = 2500.0  # popularity score above which penalty saturates
    max_penalty: float = 3.0  # caps subtraction in real_score units


def apply_contrarian_adjustment(
    pred_real_scores: dict[int, float],
    popularity_scores: dict[int, float],
    cfg: ContrarianConfig = ContrarianConfig(),
) -> dict[int, float]:
    """Subtract a popularity-scaled penalty from each player's predicted
    real_score.

    For a player whose popularity_score is 2500 (basketball-main star
    anchor), the penalty equals `strength * max_penalty` (default 0.6).
    Penalty grows linearly up to 1x the anchor, then caps. Unknown
    popularity (player not in `popularity_scores`) gets zero penalty -
    the cold-start prior should not be punished.
    """
    if not cfg.enabled or not popularity_scores:
        return dict(pred_real_scores)
    out: dict[int, float] = {}
    for pid, score in pred_real_scores.items():
        pop = popularity_scores.get(pid, 0.0)
        normalized = min(pop / max(cfg.star_score_anchor, 1.0), 1.0)
        penalty = normalized * cfg.strength * cfg.max_penalty
        out[pid] = float(score) - float(penalty)
    return out
