"""Two-stage lineup optimizer.

Stage 1: filter to top-N players by `pred_real_score * (2.0 + card_boost)`.
Stage 2: enumerate C(N, 5) lineups, score each by E[payout(lineup_score)],
         pick argmax. For N=30, C(30,5)=142506. Budget ~30s per slate.

Slot assignment is by rearrangement inequality: highest real_score median
gets the highest slot multiplier (handled in sample.lineup_score_samples).

Output is a frozen Lineup with the 5 player_ids in slot order, the
predicted EV, the predicted lineup-score percentile distribution, and
the entry recommendation flag (enter / skip / enter_with_caveat).

Slot scheme: verified 2026-05-27 against the 320-entry leaderboard corpus
(every single top-20 entry across 16 slates used the same 5 base slot
multipliers). The platform fixes 5 descending slot multipliers and the
user only chooses which player goes in which slot. The CARD BOOST is
additive on top of the slot multiplier (effective_mult = slot + boost).
See D42.
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

# Verified against the 2026 WNBA leaderboards corpus: every single top-20
# entry across all 16 finalized slates used exactly these 5 slot
# multipliers (the platform fixes them; user only picks which player goes
# in which slot). Effective per-slot multiplier = slot_mult + card_boost.
DEFAULT_SLOT_MULTIPLIERS = np.array([2.0, 1.8, 1.6, 1.4, 1.2])

# The max-slot effective multiplier estimate used by the stage-1 filter to
# rank players for the top-N pool. Equals the highest slot any player
# could land in (2.0) plus their card_boost. This is the player's
# "ceiling contribution" to a lineup, which is the right quantity to
# rank by since rearrangement-inequality slot assignment will hand the
# highest-pred player slot 2.0.
MAX_SLOT_MULT = float(DEFAULT_SLOT_MULTIPLIERS.max())


def _exceeds_team_cap(combo: tuple[int, ...], teams: list[str], max_per_team: int) -> bool:
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


def _cap_is_feasible(teams: list[str], max_per_team: int) -> bool:
    """True if at least one 5-player lineup respects max_per_team.

    The most players we can field under the cap is sum over teams of
    min(team_size, max_per_team) (plus any team-less players, which are
    uncapped). If that total is < 5, no valid lineup exists -- the classic
    case being a 1-game slate (2 teams) with max_per_team=2, where the
    ceiling is 2+2=4 < 5.
    """
    sizes: dict[str, int] = {}
    n_teamless = 0
    for t in teams:
        if not t:
            n_teamless += 1
        else:
            sizes[t] = sizes.get(t, 0) + 1
    capacity = n_teamless + sum(min(sz, max_per_team) for sz in sizes.values())
    return capacity >= 5


def _anchor_count(combo: tuple[int, ...], is_anchor: list[bool]) -> int:
    """How many players in combo are confirmed-minutes anchors."""
    return sum(1 for idx in combo if is_anchor[idx])


def _exceeds_boost_cap(
    combo: tuple[int, ...],
    boosts: np.ndarray,
    sum_cap: float,
    max_single: float,
) -> bool:
    """True if combo violates either the per-pick max or the sum-of-boost cap.

    D70 (R2). Either threshold at 0.0 means that constraint is disabled.
    Boost values are added to the slot multiplier in lineup_score; capping
    them caps the lineup-wide multiplier load on high-variance lottery cards.
    """
    if max_single > 0.0:
        for idx in combo:
            if boosts[idx] > max_single:
                return True
    if sum_cap > 0.0:
        total = 0.0
        for idx in combo:
            total += boosts[idx]
            if total > sum_cap:
                return True
    return False


def _boost_cap_is_feasible(
    boosts: np.ndarray, sum_cap: float, max_single: float
) -> bool:
    """True if at least one 5-player lineup respects the boost caps.

    Greedy lower bound: take the five smallest-boost players (after the
    per-pick max filter) and check their sum. If even that fails, no
    feasible lineup exists; the optimizer relaxes (with a warning).
    """
    eligible = boosts if max_single <= 0.0 else boosts[boosts <= max_single]
    if len(eligible) < 5:
        return False
    if sum_cap <= 0.0:
        return True
    return float(np.sort(eligible)[:5].sum()) <= sum_cap


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
    # correlation). Set to 5 to disable. This is the cap for LARGE slates
    # (3+ games); small-slate behavior is governed by dynamic_team_cap.
    max_per_team: int = 2
    # dynamic_team_cap: relax max_per_team on small slates, where the few
    # available teams make a hard cap of 2 either harmful or infeasible.
    # Verified against the 2026 corpus (D50): on 1-game slates, 100% of
    # top-20 finishers AND 100% of winners stack 3+ from one team -- and a
    # hard cap of 2 is literally INFEASIBLE there (5 players over 2 teams
    # forces a 3-2 split by pigeonhole, so the optimizer evaluates zero
    # lineups and ships nothing, e.g. 2026-05-19 scored 0.0). On 2-game
    # slates ~32% of top-20 finishers stack 3+. On 3+ game slates only 13%
    # do and the realized-oracle cap-cost is 0.00, so the diversification
    # cap stays at max_per_team there. Effective cap by slate size:
    #   1 game  -> 5 (uncapped; copula's rho_same_team still discourages)
    #   2 games -> max(max_per_team, 3)
    #   3+ games-> max_per_team
    dynamic_team_cap: bool = True
    # caveat_is_skip: when True, demote 'enter_with_caveat' to 'skip'.
    # Off by default to preserve current behavior; flip via the
    # CAVEAT_IS_SKIP env var on services that should refuse marginal-EV
    # contests until live-field calibration data is in.
    caveat_is_skip: bool = False
    # never_skip: when True, the optimizer never emits 'skip'. Any lineup
    # that would otherwise be flagged 'skip' (below the skip-EV floor, or
    # demoted by caveat_is_skip) is surfaced as 'enter_with_caveat'
    # instead. The product runs every slate and always presents the best
    # available lineup, so it should never tell the operator to sit out;
    # the marginal-EV signal is preserved via the caveat flag and the
    # expected_payout value rather than via suppression. Library default
    # is False so the bare OptimizeConfig() keeps the legacy three-state
    # behavior; production wires this on through Settings.never_skip.
    never_skip: bool = False
    # score_offset (K): passed through to the copula sampler. MUST equal the K
    # the caller used to build each spec's mu (job2 reads both from settings).
    # D52 default 2.0 (was 10.0).
    score_offset: float = 2.0
    # min_anchors (D57, Tier 1 seatbelt): require at least this many
    # confirmed-minutes "anchor" players (PlayerSamplingSpec.is_anchor) in the
    # lineup, so it can't be all cold-start darts -- the 2026-06-01 failure mode
    # (4 of 5 picks were high-boost players who logged ~0 minutes). 0 disables
    # (default, current behavior). The floor is clamped to the anchors present
    # in the filtered pool and relaxed if jointly infeasible with the team cap,
    # so it NEVER forfeits a slate (the D50 lesson). Set via LINEUP_ANCHOR_FLOOR.
    min_anchors: int = 0
    # D70 (R2): boost caps from research/internal/04_boost_economics.md.
    # boost_sum_cap is the lineup-wide ceiling on sum of card_boost for the 5
    # picks; max_single_boost is the per-pick ceiling. 0.0 disables either,
    # which is the library default so a bare OptimizeConfig() is unchanged
    # from pre-D70 behaviour. The optimizer's _scan loop skips any combo
    # that violates either cap; if no combo is jointly feasible with the
    # team cap, both caps relax to 0.0 (with a warning) so we never forfeit.
    # Set via Settings.optimizer_boost_sum_cap / optimizer_max_single_boost.
    boost_sum_cap: float = 0.0
    max_single_boost: float = 0.0


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

    # Slate size from the full pool (not the filtered top-N, which can drop
    # an entire team). Keyed on distinct-team count rather than games so odd
    # counts degrade gracefully. 2 teams = 1 game, 3-4 teams = 2 games,
    # 5+ teams = 3+ games. Drives the dynamic team cap below.
    n_teams = len({s.team for s in sampling_specs if s.team})
    n_games = max(n_teams // 2, 1)
    effective_max_per_team = cfg.max_per_team
    if cfg.dynamic_team_cap and n_teams > 0:
        if n_teams <= 2:  # 1-game slate: cap of 2 is infeasible (forfeit)
            effective_max_per_team = 5  # uncapped: 5 players / 2 teams forces 3+
        elif n_teams <= 4:  # 2-game slate: ~32% of top-20 finishers stack 3+
            effective_max_per_team = max(cfg.max_per_team, 3)

    # Stage 1: filter to top-N by visible value.
    # The (MAX_SLOT_MULT + card_boost) factor is the player's max possible
    # effective multiplier (when assigned to slot 2.0 by rearrangement).
    # Prior bug used (1.0 + card_boost) which under-weighted low-boost
    # players relative to high-boost ones, biasing the pool toward chalk.
    visible_value = np.array(
        [s.pred_real_score * (MAX_SLOT_MULT + s.card_boost) for s in field_specs],
        dtype=float,
    )
    # kind='stable' so ties resolve in input order (the build-specs caller
    # already orders by EB-tier confidence + player_id), removing
    # quicksort's implementation-defined nondeterminism on tied
    # visible_value scores.
    order = np.argsort(visible_value, kind="stable")[::-1]
    keep = order[: min(cfg.top_n_filter, n_all)]
    filtered_sampling = [sampling_specs[i] for i in keep]
    filtered_field = [field_specs[i] for i in keep]
    keep_ids = [s.player_id for s in filtered_sampling]
    keep_boosts = np.array([s.boost for s in filtered_sampling], dtype=float)
    log.info("optimizer_stage1", n_all=n_all, n_filtered=len(filtered_sampling))

    # Joint sample once for the filtered pool.
    real_score_samples = sample_joint_real_scores(
        filtered_sampling,
        cfg.n_samples,
        CopulaConfig(seed=cfg.seed, score_offset=cfg.score_offset),
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
    keep_is_anchor = [bool(s.is_anchor) for s in filtered_sampling]
    # If the cap admits no valid 5-combo from the filtered pool (e.g. a
    # 1-game slate with dynamic_team_cap disabled), relax to uncapped so we
    # never ship an empty lineup. n_evaluated==0 below would otherwise leave
    # best_indices=() and freeze a no-player recommendation.
    if effective_max_per_team < 5 and not _cap_is_feasible(keep_teams, effective_max_per_team):
        log.warning(
            "optimizer_cap_infeasible",
            effective_max_per_team=effective_max_per_team,
            n_games=n_games,
            note="relaxing to uncapped",
        )
        effective_max_per_team = 5

    # Anchor floor (D57, Tier 1 seatbelt): clamp the requested floor to the
    # anchors actually present in the filtered pool so it can never demand more
    # than exist (the relaxation below is the second safety net).
    n_anchors_pool = sum(keep_is_anchor)
    effective_min_anchors = min(cfg.min_anchors, n_anchors_pool)
    if effective_min_anchors < cfg.min_anchors:
        log.warning(
            "optimizer_anchor_floor_clamped",
            requested=cfg.min_anchors,
            available=n_anchors_pool,
        )

    # D70 (R2): clamp the boost caps to the filtered pool's reality. If even
    # the five smallest-boost players in the pool would violate the requested
    # caps, disable them (with a warning) up front rather than relying on the
    # post-scan relax. The relax below still catches the cap+team-cap joint
    # infeasibility.
    effective_boost_sum_cap = cfg.boost_sum_cap
    effective_max_single_boost = cfg.max_single_boost
    if (effective_boost_sum_cap > 0.0 or effective_max_single_boost > 0.0) and not (
        _boost_cap_is_feasible(keep_boosts, effective_boost_sum_cap, effective_max_single_boost)
    ):
        log.warning(
            "optimizer_boost_cap_infeasible_at_pool",
            boost_sum_cap=cfg.boost_sum_cap,
            max_single_boost=cfg.max_single_boost,
            note="relaxing both caps to 0 (cannot starve the slate)",
        )
        effective_boost_sum_cap = 0.0
        effective_max_single_boost = 0.0

    def _scan(min_anchors_req: int) -> tuple[float, tuple[int, ...], np.ndarray, int, int, int, int]:
        """Enumerate C(n,5) under team cap + anchor floor + boost cap; return the best."""
        b_ev = -np.inf
        b_idx: tuple[int, ...] = ()
        b_samp: np.ndarray = np.zeros(cfg.n_samples)
        n_eval = n_skip_team = n_skip_anchor = n_skip_boost = 0
        boost_cap_on = effective_boost_sum_cap > 0.0 or effective_max_single_boost > 0.0
        for combo in itertools.combinations(range(len(filtered_sampling)), 5):
            if effective_max_per_team < 5 and _exceeds_team_cap(
                combo, keep_teams, effective_max_per_team
            ):
                n_skip_team += 1
                continue
            if min_anchors_req > 0 and _anchor_count(combo, keep_is_anchor) < min_anchors_req:
                n_skip_anchor += 1
                continue
            if boost_cap_on and _exceeds_boost_cap(
                combo, keep_boosts, effective_boost_sum_cap, effective_max_single_boost
            ):
                n_skip_boost += 1
                continue
            own_samples = lineup_score_samples(
                real_score_samples, keep_boosts, list(combo), slot_multipliers
            )
            ev = expected_payout(
                own_samples, field_scores, curve, field_size=cfg.n_field_lineups + 1
            )
            n_eval += 1
            if ev > b_ev:
                b_ev, b_idx, b_samp = ev, combo, own_samples
        return b_ev, b_idx, b_samp, n_eval, n_skip_team, n_skip_anchor, n_skip_boost

    (
        best_ev,
        best_indices,
        best_samples,
        n_evaluated,
        n_skipped_team_cap,
        n_skipped_anchor,
        n_skipped_boost,
    ) = _scan(effective_min_anchors)
    if n_evaluated == 0 and effective_min_anchors > 0:
        # Anchor floor + team cap were jointly infeasible on the filtered pool.
        # Relax the floor and re-scan so we never freeze an empty lineup.
        log.warning("optimizer_anchor_floor_infeasible", note="relaxing anchor floor to 0")
        (
            best_ev,
            best_indices,
            best_samples,
            n_evaluated,
            n_skipped_team_cap,
            n_skipped_anchor,
            n_skipped_boost,
        ) = _scan(0)
    if n_evaluated == 0 and (effective_boost_sum_cap > 0.0 or effective_max_single_boost > 0.0):
        # D70: boost caps were jointly infeasible with the team cap on the
        # filtered pool. Drop the boost caps and re-scan; never forfeit.
        log.warning(
            "optimizer_boost_cap_infeasible_post_scan",
            boost_sum_cap=effective_boost_sum_cap,
            max_single_boost=effective_max_single_boost,
            note="relaxing both boost caps to 0",
        )
        effective_boost_sum_cap = 0.0
        effective_max_single_boost = 0.0
        (
            best_ev,
            best_indices,
            best_samples,
            n_evaluated,
            n_skipped_team_cap,
            n_skipped_anchor,
            n_skipped_boost,
        ) = _scan(effective_min_anchors)
    log.info(
        "optimizer_stage2",
        evaluated=n_evaluated,
        skipped_team_cap=n_skipped_team_cap,
        skipped_anchor_floor=n_skipped_anchor,
        skipped_boost_cap=n_skipped_boost,
        max_per_team=cfg.max_per_team,
        effective_max_per_team=effective_max_per_team,
        effective_min_anchors=effective_min_anchors,
        effective_boost_sum_cap=effective_boost_sum_cap,
        effective_max_single_boost=effective_max_single_boost,
        n_games=n_games,
    )

    # Lineup assembly: assign slots by rearrangement inequality on median
    rs_median = np.median(real_score_samples[:, list(best_indices)], axis=0)
    # kind='stable' so tied medians (e.g. two boost-3 rookies with the
    # same EB shrinkage pull, as on 2026-05-28's R.Johnson/G.VanSlooten
    # tie at 1.71) resolve deterministically by input order, not by
    # quicksort implementation detail.
    order = np.argsort(rs_median, kind="stable")[::-1]
    ordered_pids = tuple(keep_ids[best_indices[i]] for i in order)

    p10, p50, p90 = np.quantile(best_samples, [0.1, 0.5, 0.9])

    if best_ev < cfg.skip_if_expected_payout_below:
        flag = "skip"
    elif best_ev < cfg.caveat_if_expected_payout_below:
        flag = "skip" if cfg.caveat_is_skip else "enter_with_caveat"
    else:
        flag = "enter"
    # never_skip: the product surfaces a playable lineup every slate and
    # never tells the operator to sit out. Promote any 'skip' to
    # 'enter_with_caveat' so the marginal-EV signal survives (via the
    # caveat flag + expected_payout) without suppressing the slate.
    if cfg.never_skip and flag == "skip":
        flag = "enter_with_caveat"

    return LineupRecommendation(
        player_ids=ordered_pids,
        slot_multipliers=tuple(float(x) for x in slot_multipliers),
        expected_payout=float(best_ev),
        lineup_score_p10=float(p10),
        lineup_score_p50=float(p50),
        lineup_score_p90=float(p90),
        entry_flag=flag,
    )
