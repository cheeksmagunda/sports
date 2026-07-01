"""Injury-cascade minutes redistribution.

Ported from basketball-main `_cascade_minutes`. When a starter is ruled
OUT, their minutes get redistributed to teammates in the same position
group, weighted inversely by current minutes (bench players inherit
proportionally more), with a per-player cap.

Why this matters: the largest source of upside in a WNBA slate is a
backup who suddenly inherits 30 starter-level minutes because the
starter is OUT. RotoWire / Real Sports surface the injury an hour
before tip; the optimizer that incorporates the redistribution beats
the one that doesn't.

Cohort sharing (per basketball-main):
- G shares only with G.
- F shares with F (and partially with C - 0.30 share).
- C shares with F (and partially with C - 0.30 share back).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from wnba_oracle.features.spec import Cohort, cohort_for_position


@dataclass(frozen=True)
class CascadeConfig:
    redistribution_rate: float = 0.70  # fraction of OUT mins redistributed; rest is "lost"
    center_forward_share: float = 0.30  # OUT C minutes also share with F at this fraction
    per_player_cap_minutes: float = 8.0  # max bonus a single player can receive


@dataclass(frozen=True)
class CascadeInput:
    player_id: int
    team: str
    position: str
    minutes_l10: float
    is_out: bool


def redistribute_minutes(
    rows: Iterable[CascadeInput],
    cfg: CascadeConfig = CascadeConfig(),
) -> dict[int, float]:
    """Return {player_id: bonus_minutes} the cascade adds on top of mins_l10.

    Inputs that are not 'OUT' but have minutes_l10 > 0 are eligible
    recipients; OUT inputs with minutes_l10 > 0 are donors. The function
    is pure - it does not mutate the inputs.
    """
    by_team: dict[str, list[CascadeInput]] = {}
    for row in rows:
        if not row.team:
            continue
        by_team.setdefault(row.team, []).append(row)

    bonuses: dict[int, float] = {}
    for team_rows in by_team.values():
        donors = [r for r in team_rows if r.is_out and r.minutes_l10 > 0]
        recipients = [r for r in team_rows if not r.is_out and r.minutes_l10 > 0]
        if not donors or not recipients:
            continue

        # Minutes freed per cohort
        freed: dict[Cohort, float] = {}
        for d in donors:
            pg = cohort_for_position(d.position)
            freed[pg] = freed.get(pg, 0.0) + d.minutes_l10
            if pg == "C":
                freed["F"] = freed.get("F", 0.0) + d.minutes_l10 * cfg.center_forward_share
            elif pg == "F":
                freed["C"] = freed.get("C", 0.0) + d.minutes_l10 * cfg.center_forward_share

        for cohort, minutes_freed in freed.items():
            eligible = []
            for r in recipients:
                rcohort = cohort_for_position(r.position)
                if (
                    rcohort == cohort
                    or (rcohort == "C" and cohort == "F")
                    or (rcohort == "F" and cohort == "C")
                ):
                    eligible.append(r)
            if not eligible:
                continue

            # Inverse-minutes weights: bench players inherit more.
            inv_mins = [1.0 / max(r.minutes_l10, 1.0) for r in eligible]
            total = sum(inv_mins)
            if total <= 0:
                continue
            for r, w in zip(eligible, inv_mins, strict=True):
                share = (w / total) * minutes_freed * cfg.redistribution_rate
                capped = min(share, cfg.per_player_cap_minutes)
                bonuses[r.player_id] = bonuses.get(r.player_id, 0.0) + capped

    # Final per-player cap (catches accumulation across multiple cohorts)
    for pid in list(bonuses):
        bonuses[pid] = min(bonuses[pid], cfg.per_player_cap_minutes)
    return bonuses
