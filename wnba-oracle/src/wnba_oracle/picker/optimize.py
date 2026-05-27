"""Two-stage lineup optimizer.

Stage 1: filter to top-N players by `pred_real_score * (1 + card_boost)`.
Stage 2: enumerate C(N, 5) lineups, score each by E[payout(lineup_score)],
         pick argmax. For N=30, C(30,5)=142506. Budget ~30s per slate.

Slot assignment is by rearrangement inequality: highest real_score median
gets the highest slot multiplier (handled in sample.lineup_score_samples).

Output is a frozen Lineup with the 5 player_ids in slot order, the
predicted EV, the predicted lineup-score percentile distribution, and
the entry recommendation flag (enter / skip / enter_with_caveat).
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np

from wnba_oracle.common.logging import get_logger
from wnba_oracle.picker.field import FieldPlayerSpec, project_ownership, simulate_field_lineups
from wnba_oracle.picker.payout import PayoutCurve, expected_payout
from wnba_oracle.picker.sample import (
    CopulaConfig,
    PlayerSamplingSpec,
    lineup_score_samples,
    sample_joint_real_scores,
)

log = get_logger("oracle.picker.optimize")

DEFAULT_SLOT_MULTIPLIERS = np.array([3.0, 2.5, 2.0, 1.5, 1.0])


def _exceeds_team_cap(
    combo: tuple[int, ...], teams: list[str], max_per_team: int
) -> bool:
    """True if any team appears more than max_per_team times in combo."""
    counts: dict[str, int] = {}
    for idx in combo:
        t = teams[idx]
        if not t:
            continue
        counts[t] = counts.get(t, 0) + 1
        if counts[t] > max_per_team:
            return True
    return False


@dataclass(frozen=True)
class LineupRecommendation:
    player_ids: tuple[int, ...]
    slot_multipliers: tuple[float, ...]
    expected_payout: float
    lineup_score_p10: float
    lineup_score_p50: float
    lineup_score_p90: float
    entry_flag: str  # 'enter' | 'skip' | 'enter_with_caveat'


@dataclass(frozen=True)
class OptimizeConfig:
    top_n_filter: int = 30
    n_samples: int = 5000
    n_field_lineups: int = 1000
    skip_if_expected_payout_below: float = 0.95
    caveat_if_expected_payout_below: float = 1.10
    seed: int = 1729
    # Ported from basketball-main. Caps how many players from one team
    # appear in a lineup. Default 2 (one back-to-back stack is fine; three
    # players courts the negative same-team minutes-cannibalization
    # correlation). Set to 5 to disable.
    max_per_team: int = 2


def optimize_lineup(
    sampling_specs: list[PlayerSamplingSpec],
    field_specs: list[FieldPlayerSpec],
    curve: PayoutCurve,
    *,
    slot_multipliers: np.ndarray = DEFAULT_SLOT_MULTIPLIERS,
    cfg: OptimizeConfig = OptimizeConfig(),
) -> LineupRecommendation:
    n_all = len(sampling_specs)
    if n_all < 5:
        raise ValueError(f"pool too small ({n_all}) - need >= 5 players")

    # Stage 1: filter to top-N by visible value.
    visible_value = np.array(
        [s.pred_real_score * (1.0 + s.card_boost) for s in field_specs], dtype=float
    )
    order = np.argsort(visible_value)[::-1]
    keep = order[: min(cfg.top_n_filter, n_all)]
    filtered_sampling = [sampling_specs[i] for i in keep]
    filtered_field = [field_specs[i] for i in keep]
    keep_ids = [s.player_id for s in filtered_sampling]
    keep_boosts = np.array([s.boost for s in filtered_sampling], dtype=float)
    log.info("optimizer_stage1", n_all=n_all, n_filtered=len(filtered_sampling))

    # Joint sample once for the filtered pool.
    real_score_samples = sample_joint_real_scores(
        filtered_sampling, cfg.n_samples, CopulaConfig(seed=cfg.seed)
    )
    # Project field ownership + sample opponent lineups.
    ownership = project_ownership(filtered_field)
    field_lineup_idx = simulate_field_lineups(
        ownership,
        n_lineups=cfg.n_field_lineups,
        lineup_size=5,
        seed=cfg.seed + 1,
    )
    # Pre-compute field-lineup score samples
    field_scores = np.zeros((cfg.n_field_lineups, cfg.n_samples))
    for r in range(cfg.n_field_lineups):
        field_scores[r] = lineup_score_samples(
            real_score_samples,
            keep_boosts,
            list(field_lineup_idx[r]),
            slot_multipliers,
        )

    # Stage 2: enumerate C(n_filtered, 5) lineups. Skip any that violate
    # max_per_team early - counting same-team membership is much cheaper
    # than scoring then rejecting.
    keep_teams = [s.team for s in filtered_sampling]
    best_ev = -np.inf
    best_indices: tuple[int, ...] = ()
    best_samples: np.ndarray = np.zeros(cfg.n_samples)
    n_evaluated = 0
    n_skipped_team_cap = 0
    for combo in itertools.combinations(range(len(filtered_sampling)), 5):
        if cfg.max_per_team < 5 and _exceeds_team_cap(combo, keep_teams, cfg.max_per_team):
            n_skipped_team_cap += 1
            continue
        own_samples = lineup_score_samples(
            real_score_samples, keep_boosts, list(combo), slot_multipliers
        )
        ev = expected_payout(own_samples, field_scores, curve, field_size=cfg.n_field_lineups + 1)
        n_evaluated += 1
        if ev > best_ev:
            best_ev = ev
            best_indices = combo
            best_samples = own_samples
    log.info(
        "optimizer_stage2",
        evaluated=n_evaluated,
        skipped_team_cap=n_skipped_team_cap,
        max_per_team=cfg.max_per_team,
    )

    # Lineup assembly: assign slots by rearrangement inequality on median
    rs_median = np.median(real_score_samples[:, list(best_indices)], axis=0)
    order = np.argsort(rs_median)[::-1]
    ordered_pids = tuple(keep_ids[best_indices[i]] for i in order)

    p10, p50, p90 = np.quantile(best_samples, [0.1, 0.5, 0.9])

    if best_ev < cfg.skip_if_expected_payout_below:
        flag = "skip"
    elif best_ev < cfg.caveat_if_expected_payout_below:
        flag = "enter_with_caveat"
    else:
        flag = "enter"

    return LineupRecommendation(
        player_ids=ordered_pids,
        slot_multipliers=tuple(float(x) for x in slot_multipliers),
        expected_payout=float(best_ev),
        lineup_score_p10=float(p10),
        lineup_score_p50=float(p50),
        lineup_score_p90=float(p90),
        entry_flag=flag,
    )
