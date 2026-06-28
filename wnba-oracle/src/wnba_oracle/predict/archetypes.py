"""DFS value archetype classification.

Maps the sport-agnostic DFS principles from the MLB "Highest Value"
analysis to WNBA player profiles. The three MLB archetypes translate to:

Archetype A -- Ceiling Anchor (MLB: top-of-order slugger on high-total team)
    Confirmed starter with high usage on a fast-paced or high-implied-total
    team. High minutes floor AND high per-minute rate. These are the
    slate-breakers: they won't bust on minutes, and their production rate
    is high enough that a big night wins tournaments.

Archetype B -- Efficient Producer (MLB: table-setter who scores runs)
    High per-minute production in the highest-leverage Real Sports stat
    categories (stl/blk/ast). Their real_score is more "capital efficient"
    per box-score event than volume scorers. Reliable floor with hidden
    upside because the scoring formula amplifies their best stat categories.

Archetype C -- Leverage Spike (MLB: cheap high-K pitcher)
    High card_boost (discounted price) with confirmed role or recent
    uptrend. Mirrors the "stars and scrubs" construction: a cheap player
    with role security lets the optimizer pay up for ceiling anchors in
    other slots.

Supplementary tag -- Streaking
    L5 production significantly above L10 baseline, driven by sustainable
    stat categories. Not exclusive with the primary archetype; it modifies
    the confidence level of any archetype.

The archetype labels are surfaced in frozen lineup metadata for analysis
and, once calibrated against placement data, can inform the optimizer's
ceiling/leverage weights.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from wnba_oracle.predict.stat_leverage import is_leverage_efficient, stat_leverage_score
from wnba_oracle.predict.streak_quality import StreakProfile, streak_quality

Archetype = Literal["ceiling_anchor", "efficient_producer", "leverage_spike", "baseline"]


@dataclass(frozen=True)
class ArchetypeLabel:
    primary: Archetype
    is_streaking: bool
    streak_quality: float
    streak_driver: str
    stat_leverage: float
    confidence: float


@dataclass(frozen=True)
class ArchetypeInput:
    player_id: int
    card_boost: float
    is_confirmed_starter: bool
    is_anchor: bool
    mins_l10: float
    pts_per_min_l10: float
    ast_per_min_l10: float
    stl_blk_per_min_l10: float
    reb_per_min_l10: float
    ts_pct_l10: float
    fantasy_pts_l5: float
    fantasy_pts_l10: float
    pts_per_min_l5: float
    implied_team_total: float
    vegas_total: float
    usg_pct_l10: float


def classify_archetype(inp: ArchetypeInput) -> ArchetypeLabel:
    """Classify a single player into a DFS value archetype.

    The classification uses a decision-tree approach grounded in the
    MLB DFS findings. No ML model is needed: the archetypes are
    defined by observable feature thresholds that map directly to the
    principles in the analysis document.
    """
    leverage = stat_leverage_score(
        pts_per_min=inp.pts_per_min_l10,
        ast_per_min=inp.ast_per_min_l10,
        stl_blk_per_min=inp.stl_blk_per_min_l10,
        reb_per_min=inp.reb_per_min_l10,
    )
    streak = streak_quality(
        fantasy_pts_l5=inp.fantasy_pts_l5,
        fantasy_pts_l10=inp.fantasy_pts_l10,
        pts_per_min_l5=inp.pts_per_min_l5,
        pts_per_min_l10=inp.pts_per_min_l10,
        ast_per_min_l10=inp.ast_per_min_l10,
        stl_blk_per_min_l10=inp.stl_blk_per_min_l10,
        reb_per_min_l10=inp.reb_per_min_l10,
        ts_pct_l10=inp.ts_pct_l10,
    )

    primary = _classify_primary(inp, leverage)
    confidence = _compute_confidence(inp, primary, streak, leverage)

    return ArchetypeLabel(
        primary=primary,
        is_streaking=streak.is_hot,
        streak_quality=streak.quality,
        streak_driver=streak.driver,
        stat_leverage=round(leverage, 3),
        confidence=round(confidence, 3),
    )


def _classify_primary(inp: ArchetypeInput, leverage: float) -> Archetype:
    """Decision tree for the primary archetype label."""
    is_starter = inp.is_confirmed_starter or inp.is_anchor
    high_minutes = inp.mins_l10 >= 24.0
    high_total = inp.implied_team_total >= 42.0 or inp.vegas_total >= 155.0
    high_usage = inp.usg_pct_l10 >= 0.20

    if is_starter and high_minutes and (high_total or high_usage):
        return "ceiling_anchor"

    if is_leverage_efficient(
        pts_per_min=inp.pts_per_min_l10,
        ast_per_min=inp.ast_per_min_l10,
        stl_blk_per_min=inp.stl_blk_per_min_l10,
        reb_per_min=inp.reb_per_min_l10,
    ):
        return "efficient_producer"

    if inp.card_boost >= 2.0 and is_starter:
        return "leverage_spike"

    return "baseline"


def _compute_confidence(
    inp: ArchetypeInput,
    primary: Archetype,
    streak: StreakProfile,
    leverage: float,
) -> float:
    """Confidence score for the archetype assignment.

    Higher confidence when multiple signals align (minutes history +
    confirmed role + favorable matchup + sustainable streak). Lower
    when the classification rests on a single thin signal.
    """
    base = 0.4
    if primary == "ceiling_anchor":
        if inp.is_confirmed_starter:
            base += 0.15
        if inp.mins_l10 >= 30.0:
            base += 0.10
        if inp.implied_team_total >= 44.0:
            base += 0.10
        if inp.usg_pct_l10 >= 0.25:
            base += 0.10
    elif primary == "efficient_producer":
        base += min(0.3, leverage * 0.5)
        if inp.ts_pct_l10 >= 0.55:
            base += 0.10
    elif primary == "leverage_spike":
        if inp.card_boost >= 2.5:
            base += 0.10
        if inp.is_confirmed_starter:
            base += 0.15
        if inp.mins_l10 >= 20.0:
            base += 0.10

    if streak.is_hot and streak.quality >= 0.5:
        base += 0.10
    elif streak.is_hot and streak.driver == "regressive":
        base -= 0.05

    return max(0.0, min(1.0, base))


def classify_pool(pool: list[ArchetypeInput]) -> dict[int, ArchetypeLabel]:
    """Classify all players in a pool. Returns {player_id: ArchetypeLabel}."""
    return {inp.player_id: classify_archetype(inp) for inp in pool}
