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
from collections import Counter
from dataclasses import dataclass

import numpy as np

from wnba_oracle.common.logging import get_logger
from wnba_oracle.picker.field import (
    FieldPlayerSpec,
    project_ownership,
    simulate_field_lineups_correlated,
)
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


def _boost_cap_is_feasible(boosts: np.ndarray, sum_cap: float, max_single: float) -> bool:
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


def _game_stack_pairs(combo: tuple[int, ...], teams: list[str], opponents: list[str]) -> int:
    """Count "stack pairs" in combo. Two picks form a pair iff they are in
    the same game (unordered {team, opponent} match). A 2-stack contributes
    1 pair, a 3-stack contributes 2 (k-1 per group, summed).
    """
    counts: dict[frozenset[str], int] = {}
    for idx in combo:
        t = teams[idx]
        o = opponents[idx]
        if not t or not o:
            continue
        key = frozenset({t, o})
        counts[key] = counts.get(key, 0) + 1
    return sum(max(0, k - 1) for k in counts.values())


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
    # boost_sum_cap is the lineup-wide ceiling on sum of card_boost for the 5
    # picks; max_single_boost is the per-pick ceiling. 0.0 disables either,
    # which is the library default so a bare OptimizeConfig() is unchanged
    # from pre-D70 behaviour. The optimizer's _scan loop skips any combo
    # that violates either cap; if no combo is jointly feasible with the
    # team cap, both caps relax to 0.0 (with a warning) so we never forfeit.
    # Set via Settings.optimizer_boost_sum_cap / optimizer_max_single_boost.
    boost_sum_cap: float = 0.0
    max_single_boost: float = 0.0
    # D70 (R3): per-stack-pair additive bonus to expected_payout. A "stack
    # pair" is each pick beyond the first from the same game (so a 2-stack
    # contributes 1 pair, a 3-stack contributes 2). Same-game pairing uses
    # the unordered {team, opponent} key. Default 0.0 (off); a tiny value
    # like 0.005 mildly biases the optimizer toward stacked lineups at
    # near-equal EV. Historical top-20 lineups often stack 2+ from one game;
    # this offsets the independent-pick assumption.
    game_stack_bonus: float = 0.0
    # D87 (Phase 1 / objective shaping). Explicit additive terms on top of
    # E[payout]. The cleaner target is duplication-penalized E[payout]
    # alone, because leverage / ceiling / duplication are all emergent
    # properties of a correctly calibrated field sim (Phase 3) + per-player
    # ceiling marginals (Phase 4). Bolting additive correctives on top
    # double-counts signal already in the simulator, and the weights are
    # unpublished folklore unless calibrated against placement data.
    #
    # These knobs are kept as DORMANT calibration levers (default 0.0 -> the
    # bare OptimizeConfig() is byte-identical to pre-D87 behaviour) so the
    # operator can dial in a corrective during the period AFTER placement
    # data exists (D88) but BEFORE the simulator + marginals are recalibrated
    # to the live field. Once Phases 3 + 4 land and prove out, these are
    # expected to stay at 0.0.
    #
    #  - leverage_weight    : reward mean(-log own_i) over the 5 picks.
    #  - ceiling_weight     : reward (p90 - p50)/p50 of own lineup samples.
    #  - duplication_weight : penalise prod(own_i)*field_size (expected
    #                         mirror entries against our 5-stack).
    leverage_weight: float = 0.0
    ceiling_weight: float = 0.0
    duplication_weight: float = 0.0
    # D107 (Phase 4 / ceiling-tilted slots): sort players by p90 percentile
    # instead of p50 median when assigning to slot multipliers. Prioritizes
    # upside on high-multiplier slots so ceiling plays occupy the 2.0 slot
    # instead of the 1.2 slot. Default False maintains rearrangement-inequality
    # (p50-based) behavior; flip via OPTIMIZER_CEILING_TILT_SLOTS env var.
    ceiling_tilt_slots: bool = False
    # D88 (Phase 3 / stack-aware field). When either boost is != 1.0, the
    # field simulator generates correlated opponent lineups (same-game and
    # same-team affinity after each pick). Default 1.0 leaves the
    # independent-pick sampler in place byte-for-byte. Game / team keys are
    # derived from the filtered pool's `team` and `opponent` fields.
    field_same_game_boost: float = 1.0
    field_same_team_boost: float = 1.0
    # D88 (Phase 3, continued). When True, EV deducts an expected duplicate
    # penalty inside expected_payout itself (per-sample rank weighted by
    # 1/dup_count). This is the research-preferred way to price duplication,
    # equivalent to the synthesis prescription of E[payout(rank)/dup_count].
    # Default False so the math change is opt-in and byte-reversible.
    duplication_aware_payout: bool = False
    # committed_order_objective: score each candidate under a slot order fixed
    # ONCE from the per-player sample means, instead of re-slotting inside every
    # Monte-Carlo draw. The legacy objective is E[max over slot assignments],
    # which no entrant can realize and which flatters high-dispersion lineups
    # most, biasing selection toward volatility. Applied to the field lineups
    # too, so both sides of expected_payout describe the same world. Default
    # False keeps the loop byte-identical; measure with
    # `scripts/lab.py variant --set committed_order_objective=True`.
    committed_order_objective: bool = False


def optimize_lineup(
    sampling_specs: list[PlayerSamplingSpec],
    field_specs: list[FieldPlayerSpec],
    curve: PayoutCurve,
    *,
    slot_multipliers: np.ndarray = DEFAULT_SLOT_MULTIPLIERS,
    cfg: OptimizeConfig = OptimizeConfig(),
    mixture_variance_enabled: bool = True,
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
    # rank_pred_override lets the caller nudge stage-1 ranking without
    # perturbing sampling. Used by the 2026-07-04 boost-tail lift: for
    # head-served players with card_boost >= threshold, the caller sets
    # this to pred_p90 * (mults) so the ranker prefers ceiling for the
    # tail; the sampler still sees pred_p50 via pred_real_score.
    visible_value = np.array(
        [
            (s.rank_pred_override if s.rank_pred_override is not None else s.pred_real_score)
            * (MAX_SLOT_MULT + s.card_boost)
            for s in field_specs
        ],
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
    # D107 (Tier 2): mixture-variance sampling. When enabled, pass availability probs
    # to gate each draw by Bernoulli(P(active)), creating spike-at-zero + tail instead
    # of just shifting the mean (expectation form). When disabled, sample without gating
    # (pure lognormal, no availability variance).
    avail_probs_arg = None
    if mixture_variance_enabled:
        avail_probs = np.array([s.p_active for s in filtered_sampling], dtype=float)
        # Only gate if any player has P(active) < 1.0
        avail_probs_arg = avail_probs if np.any(avail_probs < 1.0) else None
    real_score_samples = sample_joint_real_scores(
        filtered_sampling,
        cfg.n_samples,
        CopulaConfig(seed=cfg.seed, score_offset=cfg.score_offset),
        availability_probs=avail_probs_arg,
    )
    # Project field ownership + sample opponent lineups.
    ownership = project_ownership(filtered_field)
    # D88 (Phase 3): stack-aware field. When either boost is != 1.0 the
    # sampler conditions each draw on prior picks. The correlated helper
    # delegates back to the independent sampler when both boosts are 1.0, so
    # the default config is byte-identical to pre-D88.
    keep_teams_pre = [s.team or "" for s in filtered_sampling]
    keep_opponents_pre = [s.opponent or "" for s in filtered_sampling]
    keep_game_keys = [
        "|".join(sorted([t, o])) if t and o else ""
        for t, o in zip(keep_teams_pre, keep_opponents_pre)
    ]
    field_lineup_idx = simulate_field_lineups_correlated(
        ownership,
        game_keys=keep_game_keys,
        team_keys=keep_teams_pre,
        same_game_boost=cfg.field_same_game_boost,
        same_team_boost=cfg.field_same_team_boost,
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
            committed_order=cfg.committed_order_objective,
        )

    # Stage 2: enumerate C(n_filtered, 5) lineups. Skip any that violate
    # max_per_team early - counting same-team membership is much cheaper
    # than scoring then rejecting.
    keep_teams = [s.team for s in filtered_sampling]
    keep_opponents = [s.opponent for s in filtered_sampling]
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

    # D87 (Phase 1): pre-compute log-ownership over the filtered pool once so
    # the per-combo leverage term is a 5-element gather, not a per-call np call.
    # Clip at 1e-4 to bound the -log term (very-rare players don't earn
    # unbounded leverage credit). Identity vector when leverage_weight==0.
    keep_log_own = np.log(np.clip(ownership, 1e-4, 1.0))
    field_size_total = cfg.n_field_lineups + 1
    # D88 (Phase 3): pre-tabulate field lineup sets as a Counter so the
    # per-combo duplicate count is an O(1) dictionary hit instead of an O(n_field)
    # scan. With n_field=500 and C(30,5)~142k combos the scan path would burn
    # ~70M frozenset-equality checks per slate, breaching the 30s budget noted
    # in the module docstring. Only built when duplication_aware_payout is on
    # so the default path skips the allocation entirely.
    field_lineup_counter: Counter[frozenset[int]] | None = (
        Counter(frozenset(int(j) for j in row) for row in field_lineup_idx)
        if cfg.duplication_aware_payout
        else None
    )

    def _scan(
        min_anchors_req: int,
    ) -> tuple[float, tuple[int, ...], np.ndarray, int, int, int, int]:
        """Enumerate C(n,5) under team cap + anchor floor + boost cap; return the best."""
        b_ev = -np.inf
        b_idx: tuple[int, ...] = ()
        b_samp: np.ndarray = np.zeros(cfg.n_samples)
        n_eval = n_skip_team = n_skip_anchor = n_skip_boost = 0
        boost_cap_on = effective_boost_sum_cap > 0.0 or effective_max_single_boost > 0.0
        leverage_on = cfg.leverage_weight > 0.0
        ceiling_on = cfg.ceiling_weight > 0.0
        dup_on = cfg.duplication_weight > 0.0
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
                real_score_samples,
                keep_boosts,
                list(combo),
                slot_multipliers,
                committed_order=cfg.committed_order_objective,
            )
            ev = expected_payout(own_samples, field_scores, curve, field_size=field_size_total)
            # D88 (Phase 3): research-preferred duplication treatment.
            # `lineup_score_samples` reads the global `real_score_samples`
            # matrix by player index, so any field lineup with the SAME 5
            # players as `combo` produces an identical lineup_score per
            # sample. `expected_payout` uses strict > for rank, so these
            # clones tie us (do not beat us). The actual contest pays the
            # tied rank's prize split across (1 + n_clones) entries.
            # Dividing the post-MC EV by (1 + n_clones) is therefore the
            # correct, unbiased tie-share treatment -- E[payout(rank)] is
            # constant across the tied entries, so the divide is exact.
            if field_lineup_counter is not None:
                clones = field_lineup_counter.get(frozenset(combo), 0)
                if clones > 0:
                    ev /= float(1 + clones)
            # D70 (R3): game-stack bonus. Small additive EV bias per stack
            # pair so the optimizer mildly prefers stacked lineups when EVs
            # are near-equal. Bonus is in expected_payout units; tuned via
            # OPTIMIZER_GAME_STACK_BONUS (default 0.0 = no bias).
            if cfg.game_stack_bonus > 0.0:
                pairs = _game_stack_pairs(combo, keep_teams, keep_opponents)
                if pairs > 0:
                    ev += cfg.game_stack_bonus * pairs
            # D87 (Phase 1) objective-shaping terms. Each gated by a weight; all
            # default 0.0 so the loop is byte-identical to pre-D87 when off.
            if leverage_on:
                # Mean of -log(own_i) over the 5 chosen players. A 50% owned
                # chalk player contributes 0.69; a 5% contrarian play 3.0.
                leverage = float(-keep_log_own[list(combo)].mean())
                ev += cfg.leverage_weight * leverage
            if ceiling_on:
                # Upper-tail width on a stable denominator. Earlier draft used
                # (p90 - p50)/p50, but lineup_score_samples can sit at or below
                # zero on punt combos (D52 K=2 makes real_score - K naturally
                # negative for cold-starts), and dividing by a p50 near or
                # below zero either silently dropped the term or blew up to
                # +inf. Anchor on max(|p50|, 1.0) so the ratio stays in a
                # bounded, dimensionless band that is comparable across pools.
                p50, p90 = np.quantile(own_samples, [0.5, 0.9])
                denom = max(abs(float(p50)), 1.0)
                ev += cfg.ceiling_weight * float((p90 - p50) / denom)
            if dup_on:
                # Probability another single random opponent draws the SAME 5
                # players under independence = prod of ownerships. Multiply by
                # field size for expected mirror entries.
                dup_prob = float(np.prod(ownership[list(combo)]))
                ev -= cfg.duplication_weight * dup_prob * float(field_size_total)
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

    # Guard the -inf sentinel. If every candidate combo was skipped (the
    # filtered pool holds fewer than five draftable players, so C(n,5) is
    # empty even after the team-cap / anchor-floor / boost-cap relaxations
    # above), best_ev is still the -np.inf the scan initialised it to and
    # best_indices is (). Recording that float("-inf") is exactly how the
    # 2026-05-31 two-team slate froze an -inf expected_payout -- it pre-dated
    # the _cap_is_feasible relaxation, and the empty best_indices also feeds
    # np.median an empty slice (NaN + RuntimeWarning). Never persist -inf:
    # clamp the EV to 0.0 (a slate with no feasible lineup has zero expected
    # payout, not negative-infinite) and return the empty recommendation the
    # caller's slate_labels fallback can take over from.
    if n_evaluated == 0 or not np.isfinite(best_ev):
        log.error(
            "optimizer_no_feasible_lineup",
            n_filtered=len(filtered_sampling),
            n_games=n_games,
            best_ev=float(best_ev),
            note="no feasible 5-combo after all relaxations; EV clamped to 0.0",
        )
        flag = "enter_with_caveat" if cfg.never_skip else "skip"
        return LineupRecommendation(
            player_ids=tuple(int(keep_ids[i]) for i in best_indices),
            slot_multipliers=tuple(float(x) for x in slot_multipliers),
            expected_payout=0.0,
            lineup_score_p10=0.0,
            lineup_score_p50=0.0,
            lineup_score_p90=0.0,
            entry_flag=flag,
        )

    # Lineup assembly: assign slots by rearrangement inequality.
    # D107 (Phase 4): ceiling-tilted slots sort by p90 instead of p50 to
    # prioritize upside in high-multiplier slots. Default is p50 (rearrangement
    # inequality, which optimizes expected value). kind='stable' so tied values
    # (e.g. two boost-3 rookies with the same EB shrinkage, as on 2026-05-28's
    # R.Johnson/G.VanSlooten tie at 1.71) resolve deterministically by input
    # order, not by quicksort implementation detail.
    if cfg.ceiling_tilt_slots:
        rs_sort_key = np.quantile(real_score_samples[:, list(best_indices)], 0.9, axis=0)
        sort_method = "p90 (ceiling-tilted)"
    else:
        rs_sort_key = np.median(real_score_samples[:, list(best_indices)], axis=0)
        sort_method = "p50 (rearrangement)"
    order = np.argsort(rs_sort_key, kind="stable")[::-1]
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

    # D107: log which slot assignment method was used (p50 vs p90)
    log.debug("optimizer_slot_assignment", method=sort_method)

    return LineupRecommendation(
        player_ids=ordered_pids,
        slot_multipliers=tuple(float(x) for x in slot_multipliers),
        expected_payout=float(best_ev),
        lineup_score_p10=float(p10),
        lineup_score_p50=float(p50),
        lineup_score_p90=float(p90),
        entry_flag=flag,
    )
