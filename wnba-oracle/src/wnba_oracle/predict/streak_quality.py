"""Hot-streak quality assessment.

The MLB DFS analysis distinguishes between power-driven hot streaks
(sustainable, driven by extra-base hits) and BABIP-driven streaks
(regressive, driven by batted-ball luck). The WNBA analog is:

- A SUSTAINABLE streak is driven by high-leverage stats (stl/blk/ast)
  and good shooting efficiency (true shooting %). These reflect
  repeatable skill and matchup edges that carry game to game.

- A REGRESSIVE streak is driven by high volume scoring on poor
  efficiency (lots of points but low TS%). This often represents
  variance in shot-making that regresses within a few games.

The streak quality score feeds the archetype classifier and can inform
the optimizer's ceiling/floor assessment: a player on a sustainable
streak is a higher-confidence ceiling play than one on a lucky run.
"""

from __future__ import annotations

from dataclasses import dataclass

from wnba_oracle.predict.stat_leverage import stat_leverage_score


@dataclass(frozen=True)
class StreakProfile:
    is_hot: bool
    quality: float
    driver: str


def streak_quality(
    *,
    fantasy_pts_l5: float = 0.0,
    fantasy_pts_l10: float = 0.0,
    pts_per_min_l5: float = 0.0,
    pts_per_min_l10: float = 0.0,
    ast_per_min_l10: float = 0.0,
    stl_blk_per_min_l10: float = 0.0,
    reb_per_min_l10: float = 0.0,
    ts_pct_l10: float = 0.0,
    hot_threshold: float = 1.15,
    ts_floor: float = 0.48,
) -> StreakProfile:
    """Assess whether a player is on a hot streak and whether it is
    sustainable or regressive.

    hot_threshold: L5 fantasy must exceed L10 by this factor to qualify
    as a hot streak (default 1.15 = 15% above baseline).

    ts_floor: true shooting percentage below which the streak is
    flagged as efficiency-regressive (default 0.48, below WNBA average
    of ~0.52).

    Returns a StreakProfile with:
    - is_hot: whether the player qualifies as streaking
    - quality: 0.0 to 1.0 (higher = more sustainable)
    - driver: one of "high_leverage", "efficient_scoring", "volume",
      "regressive", or "none"
    """
    if fantasy_pts_l10 <= 0.0 or fantasy_pts_l5 <= 0.0:
        return StreakProfile(is_hot=False, quality=0.0, driver="none")

    ratio = fantasy_pts_l5 / fantasy_pts_l10
    is_hot = ratio >= hot_threshold

    if not is_hot:
        return StreakProfile(is_hot=False, quality=0.0, driver="none")

    leverage = stat_leverage_score(
        pts_per_min=pts_per_min_l10,
        ast_per_min=ast_per_min_l10,
        stl_blk_per_min=stl_blk_per_min_l10,
        reb_per_min=reb_per_min_l10,
    )

    if leverage >= 0.45:
        quality = min(1.0, 0.6 + leverage * 0.4)
        driver = "high_leverage"
    elif ts_pct_l10 >= 0.55:
        quality = min(1.0, 0.5 + (ts_pct_l10 - 0.45) * 2.0)
        driver = "efficient_scoring"
    elif ts_pct_l10 < ts_floor:
        quality = max(0.0, 0.3 * (ts_pct_l10 / max(ts_floor, 0.01)))
        driver = "regressive"
    else:
        quality = 0.4
        driver = "volume"

    streak_magnitude = min(2.0, ratio)
    quality *= min(1.0, (streak_magnitude - 1.0) / 0.5)

    return StreakProfile(is_hot=is_hot, quality=round(quality, 3), driver=driver)
