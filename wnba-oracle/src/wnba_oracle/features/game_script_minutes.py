"""Game-script minutes redistribution (Tier 3).

In a projected blowout, starters sit late and the freed minutes flow to the
bench. This is the symmetric, pace-aware sibling of :mod:`injury_cascade`:
instead of one OUT starter's minutes redistributing to teammates, a blowout
frees a *fraction* of every starter's minutes (on both teams) and pushes them
to the bench, inverse-minutes weighted so the deepest bench inherits the most.

Why this matters: the largest ceiling on a WNBA slate is often a bench player
who eats 20 garbage-time minutes in a 20-point game. A high card_boost on that
player, multiplied by real minutes, is how slates are won. The blunt team-wide
blowout penalty (``game_script.GameScriptConfig.blowout_penalty``) cannot
express this: it taxes starters and bench equally. This module makes the effect
role-aware, starters down and bench up.

Blowout probability is a smooth ramp in the projected margin (absolute point
spread): 0 below ``soft_margin``, rising linearly to ``max_blowout_prob`` at
``hard_margin``. The redistribution is pure and returns signed minute deltas
(negative for trimmed starters, positive for boosted bench). The deltas are a
prior to be tuned once the availability/minutes engine lands underneath; this
module sits on top of whatever produces ``minutes_l10`` and does not depend on
how that baseline was computed.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class GameScriptMinutesConfig:
    soft_margin: float = 8.0  # spread below this: no blowout effect
    hard_margin: float = 18.0  # spread at/above this: full blowout effect
    max_blowout_prob: float = 1.0
    starter_minutes_floor: float = 24.0  # minutes_l10 >= this is a "starter" (trim donor)
    starter_trim_fraction: float = 0.18  # fraction of a starter's minutes freed at full blowout
    redistribution_rate: float = 0.70  # fraction of freed minutes that lands on the bench
    per_player_cap_minutes: float = 8.0  # max bonus a single bench player can receive


@dataclass(frozen=True)
class GameScriptInput:
    player_id: int
    team: str
    minutes_l10: float
    projected_margin: float  # abs(point spread) for this player's game


def blowout_probability(
    projected_margin: float, cfg: GameScriptMinutesConfig = GameScriptMinutesConfig()
) -> float:
    """Linear ramp from 0 at ``soft_margin`` to ``max_blowout_prob`` at ``hard_margin``."""
    m = abs(projected_margin)
    if m <= cfg.soft_margin:
        return 0.0
    if m >= cfg.hard_margin:
        return cfg.max_blowout_prob
    span = cfg.hard_margin - cfg.soft_margin
    if span <= 0:
        return cfg.max_blowout_prob
    return cfg.max_blowout_prob * (m - cfg.soft_margin) / span


def redistribute_game_script_minutes(
    rows: Iterable[GameScriptInput],
    cfg: GameScriptMinutesConfig = GameScriptMinutesConfig(),
) -> dict[int, float]:
    """Return {player_id: minutes_delta} from projected blowouts.

    Starters (``minutes_l10 >= starter_minutes_floor``) on a team in a likely
    blowout are trimmed by ``minutes_l10 * starter_trim_fraction *
    blowout_prob``; the freed pool (times ``redistribution_rate``) is shared
    among that team's bench, inverse-minutes weighted and per-player capped.
    Teams with no bench recipients are skipped (no trim, no bump) so minutes
    are never trimmed into an unmodelled void. Pure; does not mutate inputs.

    Unlike :func:`injury_cascade.redistribute_minutes` this ignores position
    cohorts: a coach emptying the bench in garbage time gives run across the
    whole second unit, not within a position group.
    """
    by_team: dict[str, list[GameScriptInput]] = {}
    for row in rows:
        if not row.team:
            continue
        by_team.setdefault(row.team, []).append(row)

    deltas: dict[int, float] = {}
    for team_rows in by_team.values():
        margin = max((r.projected_margin for r in team_rows), default=0.0)
        p = blowout_probability(margin, cfg)
        if p <= 0.0:
            continue
        starters = [r for r in team_rows if r.minutes_l10 >= cfg.starter_minutes_floor]
        bench = [r for r in team_rows if 0.0 < r.minutes_l10 < cfg.starter_minutes_floor]
        if not starters or not bench:
            continue

        freed = 0.0
        for s in starters:
            trim = s.minutes_l10 * cfg.starter_trim_fraction * p
            deltas[s.player_id] = deltas.get(s.player_id, 0.0) - trim
            freed += trim

        inv_mins = [1.0 / max(b.minutes_l10, 1.0) for b in bench]
        total = sum(inv_mins)
        if total <= 0.0:
            continue
        pool = freed * cfg.redistribution_rate
        for b, w in zip(bench, inv_mins, strict=True):
            share = (w / total) * pool
            deltas[b.player_id] = deltas.get(b.player_id, 0.0) + min(
                share, cfg.per_player_cap_minutes
            )
    return deltas
