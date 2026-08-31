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
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import TypeVar

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
from wnba_oracle.picker.stacking import (
    POLICY_VERSION,
    LineupShape,
    StackingDecision,
    StackPreference,
    describe_lineup,
    meets_full_preference,
    meets_game_preference,
    preference_for_slate,
    resolve_game_keys,
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

_PlayerSpecT = TypeVar("_PlayerSpecT", PlayerSamplingSpec, FieldPlayerSpec)


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


def _smallest_feasible_team_cap(teams: list[str], requested: int) -> int:
    """Relax only as far as needed to produce one five-player lineup."""
    for candidate in range(max(1, requested), 6):
        if _cap_is_feasible(teams, candidate):
            return candidate
    return 5


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
    stacking_decision: StackingDecision | None = None


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
    # Contextual stacking is a soft, projections-first balance policy. The
    # optimizer keeps unrestricted and balanced winners from the same scan.
    # It selects the balanced candidate when its objective is within
    # contextual_stack_ev_margin of the unrestricted winner. Concentration is
    # still allowed when its advantage is larger, or when balance is
    # infeasible. The legacy fixed game-stack bonus is ignored while this is
    # enabled because correlation is already represented in the joint samples
    # and field simulation. False restores the previous objective exactly.
    contextual_stacking_enabled: bool = False
    contextual_stack_ev_margin: float = 0.01
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
    # False keeps the loop byte-identical.
    #
    # MEASURED 2026-08-19 over the 50 slates with recorded serving knobs:
    # mean +1.040, sd 5.410, t=1.36, 95% CI [-0.459, +2.540]. NOT shipped -- the
    # interval includes zero. It does survive dropping the best slate (+0.733)
    # and both minutes regimes lean positive (+1.417 / +0.664), and per-slate
    # swings are large (-13.98 to +16.12), so the change genuinely reshuffles
    # selection; the NET is just not separable from noise at this corpus size.
    # An n=20 preview read +1.76 and shrank as slates were added, which is
    # regression to the mean -- do not re-ship on a partial run. Re-measure when
    # the corpus grows:
    # `scripts/lab.py variant --set committed_order_objective=True --last 0`
    committed_order_objective: bool = False


@dataclass
class _ScanInputs:
    """Precomputed optimizer state shared by constraint-relaxation scans."""

    cfg: OptimizeConfig
    filtered_count: int
    effective_max_per_team: int
    effective_boost_sum_cap: float
    effective_max_single_boost: float
    keep_teams: list[str]
    keep_opponents: list[str]
    keep_game_keys: list[str]
    keep_is_anchor: list[bool]
    keep_boosts: np.ndarray
    keep_log_own: np.ndarray
    real_score_samples: np.ndarray
    field_scores: np.ndarray
    ownership: np.ndarray
    slot_multipliers: np.ndarray
    curve: PayoutCurve
    field_size_total: int
    field_lineup_counter: Counter[frozenset[int]] | None
    stack_preference: StackPreference | None
    required_game_count: int | None
    unrestricted_indices: frozenset[int]
    balance_indices: frozenset[int]


@dataclass(frozen=True)
class _Candidate:
    objective: float
    indices: tuple[int, ...]
    samples: np.ndarray
    shape: LineupShape


@dataclass(frozen=True)
class _ScanResult:
    best_unrestricted: _Candidate | None
    best_game_balanced: _Candidate | None
    best_fully_balanced: _Candidate | None
    n_evaluated: int
    n_skipped_team: int
    n_skipped_anchor: int
    n_skipped_boost: int
    n_skipped_game_coverage: int


def _candidate_pool_combinations(
    unrestricted_indices: frozenset[int],
    balance_indices: frozenset[int],
) -> Iterator[tuple[tuple[int, ...], bool, bool]]:
    """Enumerate each top-N universe directly and deduplicate their overlap."""
    unrestricted = tuple(sorted(unrestricted_indices))
    balance = tuple(sorted(balance_indices))
    for combo in itertools.combinations(unrestricted, 5):
        yield combo, True, all(index in balance_indices for index in combo)
    if balance_indices == unrestricted_indices:
        return
    for combo in itertools.combinations(balance, 5):
        if all(index in unrestricted_indices for index in combo):
            continue
        yield combo, False, True


def _scan_lineups(
    inputs: _ScanInputs,
    min_anchors_req: int,
) -> _ScanResult:
    """Enumerate once and retain unrestricted and balanced winners."""
    cfg = inputs.cfg
    best_unrestricted: _Candidate | None = None
    best_game_balanced: _Candidate | None = None
    best_fully_balanced: _Candidate | None = None
    n_evaluated = n_skipped_team = n_skipped_anchor = n_skipped_boost = 0
    n_skipped_game_coverage = 0
    boost_cap_on = inputs.effective_boost_sum_cap > 0.0 or inputs.effective_max_single_boost > 0.0
    leverage_on = cfg.leverage_weight > 0.0
    ceiling_on = cfg.ceiling_weight > 0.0
    duplication_penalty_on = cfg.duplication_weight > 0.0

    for combo, eligible_unrestricted, eligible_balance_pool in _candidate_pool_combinations(
        inputs.unrestricted_indices,
        inputs.balance_indices,
    ):
        if inputs.effective_max_per_team < 5 and _exceeds_team_cap(
            combo, inputs.keep_teams, inputs.effective_max_per_team
        ):
            n_skipped_team += 1
            continue
        if min_anchors_req > 0 and _anchor_count(combo, inputs.keep_is_anchor) < min_anchors_req:
            n_skipped_anchor += 1
            continue
        if boost_cap_on and _exceeds_boost_cap(
            combo,
            inputs.keep_boosts,
            inputs.effective_boost_sum_cap,
            inputs.effective_max_single_boost,
        ):
            n_skipped_boost += 1
            continue

        shape = describe_lineup(combo, inputs.keep_teams, inputs.keep_game_keys)
        if (
            inputs.required_game_count is not None
            and shape.game_count != inputs.required_game_count
        ):
            n_skipped_game_coverage += 1
            continue

        own_samples = lineup_score_samples(
            inputs.real_score_samples,
            inputs.keep_boosts,
            list(combo),
            inputs.slot_multipliers,
            committed_order=cfg.committed_order_objective,
        )
        objective = expected_payout(
            own_samples,
            inputs.field_scores,
            inputs.curve,
            field_size=inputs.field_size_total,
        )
        if inputs.field_lineup_counter is not None:
            clones = inputs.field_lineup_counter.get(frozenset(combo), 0)
            if clones > 0:
                objective /= float(1 + clones)
        if not cfg.contextual_stacking_enabled and cfg.game_stack_bonus > 0.0:
            pairs = _game_stack_pairs(combo, inputs.keep_teams, inputs.keep_opponents)
            if pairs > 0:
                objective += cfg.game_stack_bonus * pairs
        if leverage_on:
            leverage = float(-inputs.keep_log_own[list(combo)].mean())
            objective += cfg.leverage_weight * leverage
        if ceiling_on:
            p50, p90 = np.quantile(own_samples, [0.5, 0.9])
            denominator = max(abs(float(p50)), 1.0)
            objective += cfg.ceiling_weight * float((p90 - p50) / denominator)
        if duplication_penalty_on:
            duplication_probability = float(np.prod(inputs.ownership[list(combo)]))
            objective -= (
                cfg.duplication_weight * duplication_probability * float(inputs.field_size_total)
            )
        n_evaluated += 1
        candidate = _Candidate(
            objective=float(objective),
            indices=combo,
            samples=own_samples,
            shape=shape,
        )
        if (eligible_unrestricted or eligible_balance_pool) and (
            best_unrestricted is None or candidate.objective > best_unrestricted.objective
        ):
            best_unrestricted = candidate
        preference = inputs.stack_preference
        if (
            preference is not None
            and (eligible_unrestricted or eligible_balance_pool)
            and meets_game_preference(shape, preference)
        ):
            if best_game_balanced is None or candidate.objective > best_game_balanced.objective:
                best_game_balanced = candidate
            if meets_full_preference(shape, preference) and (
                best_fully_balanced is None or candidate.objective > best_fully_balanced.objective
            ):
                best_fully_balanced = candidate

    return _ScanResult(
        best_unrestricted=best_unrestricted,
        best_game_balanced=best_game_balanced,
        best_fully_balanced=best_fully_balanced,
        n_evaluated=n_evaluated,
        n_skipped_team=n_skipped_team,
        n_skipped_anchor=n_skipped_anchor,
        n_skipped_boost=n_skipped_boost,
        n_skipped_game_coverage=n_skipped_game_coverage,
    )


@dataclass(frozen=True)
class _FilteredPool:
    sampling: list[PlayerSamplingSpec]
    field: list[FieldPlayerSpec]
    player_ids: list[int]
    boosts: np.ndarray
    unrestricted_player_ids: frozenset[int]
    balance_player_ids: frozenset[int]


@dataclass(frozen=True)
class _StackContext:
    game_key_by_player: dict[int, str]
    metadata_quality: str
    slate_game_count: int | None
    slate_team_count: int
    preference: StackPreference | None


@dataclass
class _ConstraintState:
    n_games: int
    max_per_team: int
    min_anchors: int
    boost_sum_cap: float
    max_single_boost: float
    teams: list[str]
    opponents: list[str]
    is_anchor: list[bool]
    team_cap_reason: str


def _align_player_specs(
    sampling_specs: list[PlayerSamplingSpec],
    field_specs: list[FieldPlayerSpec],
) -> tuple[list[PlayerSamplingSpec], list[FieldPlayerSpec]]:
    """Validate and align the optimizer's parallel player contracts.

    List position is an adapter detail, not model meaning.  The optimizer
    consumes two views of each player, so it joins those views by the stable
    Real Sports player id before any filtering, sampling, or constraint work.
    The sampling order remains unchanged in this phase to preserve incumbent
    scoring; canonical model ordering is a separate, measured change.
    """
    if len(sampling_specs) != len(field_specs):
        raise ValueError(
            f"sampling/field spec length mismatch: {len(sampling_specs)} != {len(field_specs)}"
        )

    def _index_unique(specs: Sequence[_PlayerSpecT], label: str) -> dict[int, _PlayerSpecT]:
        indexed: dict[int, _PlayerSpecT] = {}
        duplicates: set[int] = set()
        for spec in specs:
            player_id = int(spec.player_id)
            if player_id in indexed:
                duplicates.add(player_id)
            indexed[player_id] = spec
        if duplicates:
            values = ", ".join(str(value) for value in sorted(duplicates))
            raise ValueError(f"duplicate {label} player_id values: {values}")
        return indexed

    sampling_by_id = _index_unique(sampling_specs, "sampling")
    field_by_id = _index_unique(field_specs, "field")
    sampling_ids = set(sampling_by_id)
    field_ids = set(field_by_id)
    if sampling_ids != field_ids:
        missing_field = sorted(sampling_ids - field_ids)
        missing_sampling = sorted(field_ids - sampling_ids)
        raise ValueError(
            "sampling/field player_id mismatch: "
            f"missing_field={missing_field}, missing_sampling={missing_sampling}"
        )

    aligned_field: list[FieldPlayerSpec] = []
    for sampling in sampling_specs:
        field = field_by_id[int(sampling.player_id)]
        if not np.isclose(float(sampling.boost), float(field.card_boost), rtol=0.0, atol=1e-12):
            raise ValueError(
                f"player {sampling.player_id} boost mismatch: "
                f"sampling={sampling.boost}, field={field.card_boost}"
            )
        aligned_field.append(field)
    return list(sampling_specs), aligned_field


def _stack_context(sampling_specs: list[PlayerSamplingSpec]) -> _StackContext:
    game_key_by_player, metadata_quality, slate_game_count = resolve_game_keys(sampling_specs)
    slate_team_count = len({spec.team.strip().upper() for spec in sampling_specs if spec.team})
    preference = (
        preference_for_slate(slate_game_count, slate_team_count)
        if slate_game_count is not None
        else None
    )
    return _StackContext(
        game_key_by_player=game_key_by_player,
        metadata_quality=metadata_quality,
        slate_game_count=slate_game_count,
        slate_team_count=slate_team_count,
        preference=preference,
    )


def _required_game_coverage(
    sampling_specs: list[PlayerSamplingSpec],
    stack_context: _StackContext,
) -> int | None:
    """Require one player per game when five reliable games fill five slots."""
    provider_ids = {str(spec.game_id or "").strip() for spec in sampling_specs}
    provider_ids.discard("")
    provider_ids_complete = all(str(spec.game_id or "").strip() for spec in sampling_specs)
    provider_claims_five_games = provider_ids_complete and len(provider_ids) == 5
    validated_five_games = stack_context.slate_game_count == 5
    if provider_claims_five_games and not validated_five_games:
        raise ValueError(
            "five-game coverage metadata is inconsistent; refusing to optimize an uncovered lineup"
        )
    return 5 if validated_five_games else None


def _slate_limits(
    sampling_specs: list[PlayerSamplingSpec],
    cfg: OptimizeConfig,
    resolved_n_games: int | None = None,
) -> tuple[int, int]:
    """Return slate game count and the small-slate-aware team cap."""
    n_teams = len({spec.team for spec in sampling_specs if spec.team})
    n_games = resolved_n_games if resolved_n_games is not None else max(n_teams // 2, 1)
    max_per_team = cfg.max_per_team
    if cfg.dynamic_team_cap and 0 < n_teams <= 2:
        max_per_team = 5
    elif cfg.dynamic_team_cap and 2 < n_teams <= 4:
        max_per_team = max(cfg.max_per_team, 3)
    return n_games, max_per_team


def _filter_pool(
    sampling_specs: list[PlayerSamplingSpec],
    field_specs: list[FieldPlayerSpec],
    top_n: int,
    max_slot_multiplier: float,
    stack_context: _StackContext,
    coverage_aware: bool,
) -> _FilteredPool:
    """Keep top value while retaining balance-feasible slate coverage."""
    visible_value = np.array(
        [
            (
                spec.rank_pred_override
                if spec.rank_pred_override is not None
                else spec.pred_real_score
            )
            * (max_slot_multiplier + spec.card_boost)
            for spec in field_specs
        ],
        dtype=float,
    )
    if coverage_aware:
        player_ids = np.array([int(spec.player_id) for spec in sampling_specs], dtype=np.int64)
        order = np.lexsort((player_ids, -visible_value))
    else:
        # Exact legacy ordering, including reverse-stable tie behavior. This
        # preserves the disabled policy as a byte-reversible rollback path.
        order = np.argsort(visible_value, kind="stable")[::-1]
    limit = min(top_n, len(sampling_specs))
    legacy_keep = [int(index) for index in order[:limit]]
    balance_keep = list(legacy_keep)
    if coverage_aware and stack_context.preference is not None:
        required: list[int] = []

        def add_first_by_group(values: list[str], occurrence: int = 0) -> None:
            seen: dict[str, int] = {}
            for raw_index in order:
                index = int(raw_index)
                value = values[index]
                if not value:
                    continue
                depth = seen.get(value, 0)
                seen[value] = depth + 1
                if depth == occurrence and index not in required and len(required) < limit:
                    required.append(index)

        all_game_keys = [
            stack_context.game_key_by_player.get(int(spec.player_id), "") for spec in sampling_specs
        ]
        all_teams = [str(spec.team or "").strip().upper() for spec in sampling_specs]
        add_first_by_group(all_game_keys)
        add_first_by_group(all_teams)
        for occurrence in range(1, stack_context.preference.max_players_per_game):
            add_first_by_group(all_game_keys, occurrence)
        keep_priority = required + [int(index) for index in order if int(index) not in required]
        balance_keep = keep_priority[:limit]
    selected = set(legacy_keep) | set(balance_keep)
    keep = np.array([int(index) for index in order if int(index) in selected], dtype=int)
    sampling = [sampling_specs[index] for index in keep]
    field = [field_specs[index] for index in keep]
    return _FilteredPool(
        sampling=sampling,
        field=field,
        player_ids=[spec.player_id for spec in sampling],
        boosts=np.array([spec.boost for spec in sampling], dtype=float),
        unrestricted_player_ids=frozenset(
            int(sampling_specs[index].player_id) for index in legacy_keep
        ),
        balance_player_ids=frozenset(
            int(sampling_specs[index].player_id) for index in balance_keep
        ),
    )


def _sample_filtered_scores(
    pool: _FilteredPool,
    cfg: OptimizeConfig,
    mixture_variance_enabled: bool,
) -> np.ndarray:
    availability_probs: np.ndarray | None = None
    if mixture_variance_enabled:
        probabilities = np.array([spec.p_active for spec in pool.sampling], dtype=float)
        availability_probs = probabilities if np.any(probabilities < 1.0) else None
    return sample_joint_real_scores(
        pool.sampling,
        cfg.n_samples,
        CopulaConfig(seed=cfg.seed, score_offset=cfg.score_offset),
        availability_probs=availability_probs,
    )


def _simulate_field_scores(
    pool: _FilteredPool,
    real_score_samples: np.ndarray,
    slot_multipliers: np.ndarray,
    cfg: OptimizeConfig,
    stack_context: _StackContext,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ownership = project_ownership(pool.field)
    teams = [spec.team or "" for spec in pool.sampling]
    if cfg.contextual_stacking_enabled:
        game_keys = [
            stack_context.game_key_by_player.get(int(spec.player_id), "") for spec in pool.sampling
        ]
    else:
        # Keep the policy-disabled field simulation identical to the legacy
        # team/opponent implementation. Provider identity remains available
        # to the contextual path without changing rollback behavior.
        opponents = [spec.opponent or "" for spec in pool.sampling]
        game_keys = [
            "|".join(sorted([team, opponent])) if team and opponent else ""
            for team, opponent in zip(teams, opponents)
        ]
    field_lineups = simulate_field_lineups_correlated(
        ownership,
        game_keys=game_keys,
        team_keys=teams,
        same_game_boost=cfg.field_same_game_boost,
        same_team_boost=cfg.field_same_team_boost,
        n_lineups=cfg.n_field_lineups,
        lineup_size=5,
        seed=cfg.seed + 1,
    )
    field_scores = np.zeros((cfg.n_field_lineups, cfg.n_samples))
    for row in range(cfg.n_field_lineups):
        field_scores[row] = lineup_score_samples(
            real_score_samples,
            pool.boosts,
            list(field_lineups[row]),
            slot_multipliers,
            committed_order=cfg.committed_order_objective,
        )
    return ownership, field_lineups, field_scores


def _prepare_constraints(
    pool: _FilteredPool,
    cfg: OptimizeConfig,
    n_games: int,
    max_per_team: int,
) -> _ConstraintState:
    teams = [spec.team for spec in pool.sampling]
    opponents = [spec.opponent for spec in pool.sampling]
    is_anchor = [bool(spec.is_anchor) for spec in pool.sampling]
    team_cap_reason = "dynamic_small_slate" if max_per_team != cfg.max_per_team else "configured"
    if max_per_team < 5 and not _cap_is_feasible(teams, max_per_team):
        relaxed_cap = (
            _smallest_feasible_team_cap(teams, max_per_team + 1)
            if cfg.contextual_stacking_enabled
            else 5
        )
        log.warning(
            "optimizer_cap_infeasible",
            effective_max_per_team=max_per_team,
            n_games=n_games,
            relaxed_max_per_team=relaxed_cap,
            note=(
                "relaxing to the smallest feasible cap"
                if cfg.contextual_stacking_enabled
                else "restoring the legacy uncapped fallback"
            ),
        )
        max_per_team = relaxed_cap
        team_cap_reason = "feasibility_relaxed"

    available_anchors = sum(is_anchor)
    min_anchors = min(cfg.min_anchors, available_anchors)
    if min_anchors < cfg.min_anchors:
        log.warning(
            "optimizer_anchor_floor_clamped",
            requested=cfg.min_anchors,
            available=available_anchors,
        )

    boost_sum_cap = cfg.boost_sum_cap
    max_single_boost = cfg.max_single_boost
    if (boost_sum_cap > 0.0 or max_single_boost > 0.0) and not _boost_cap_is_feasible(
        pool.boosts, boost_sum_cap, max_single_boost
    ):
        log.warning(
            "optimizer_boost_cap_infeasible_at_pool",
            boost_sum_cap=cfg.boost_sum_cap,
            max_single_boost=cfg.max_single_boost,
            note="relaxing both caps to 0 (cannot starve the slate)",
        )
        boost_sum_cap = 0.0
        max_single_boost = 0.0

    return _ConstraintState(
        n_games=n_games,
        max_per_team=max_per_team,
        min_anchors=min_anchors,
        boost_sum_cap=boost_sum_cap,
        max_single_boost=max_single_boost,
        teams=teams,
        opponents=opponents,
        is_anchor=is_anchor,
        team_cap_reason=team_cap_reason,
    )


def _run_constraint_scans(
    inputs: _ScanInputs,
    constraints: _ConstraintState,
) -> _ScanResult:
    result = _scan_lineups(inputs, constraints.min_anchors)
    if result.n_evaluated == 0 and constraints.min_anchors > 0:
        log.warning("optimizer_anchor_floor_infeasible", note="relaxing anchor floor to 0")
        result = _scan_lineups(inputs, 0)
    if result.n_evaluated == 0 and (
        constraints.boost_sum_cap > 0.0 or constraints.max_single_boost > 0.0
    ):
        log.warning(
            "optimizer_boost_cap_infeasible_post_scan",
            boost_sum_cap=constraints.boost_sum_cap,
            max_single_boost=constraints.max_single_boost,
            note="relaxing both boost caps to 0",
        )
        constraints.boost_sum_cap = 0.0
        constraints.max_single_boost = 0.0
        inputs.effective_boost_sum_cap = 0.0
        inputs.effective_max_single_boost = 0.0
        result = _scan_lineups(inputs, constraints.min_anchors)

    log.info(
        "optimizer_stage2",
        evaluated=result.n_evaluated,
        skipped_team_cap=result.n_skipped_team,
        skipped_anchor_floor=result.n_skipped_anchor,
        skipped_boost_cap=result.n_skipped_boost,
        skipped_game_coverage=result.n_skipped_game_coverage,
        max_per_team=inputs.cfg.max_per_team,
        effective_max_per_team=constraints.max_per_team,
        effective_min_anchors=constraints.min_anchors,
        effective_boost_sum_cap=constraints.boost_sum_cap,
        effective_max_single_boost=constraints.max_single_boost,
        n_games=constraints.n_games,
    )
    return result


def _select_contextual_candidate(
    result: _ScanResult,
    cfg: OptimizeConfig,
    stack_context: _StackContext,
    *,
    effective_max_per_team: int = 5,
    team_cap_reason: str = "not_recorded",
) -> tuple[_Candidate | None, StackingDecision]:
    best = result.best_unrestricted
    preference = stack_context.preference
    selected = best
    reason = "no_feasible_lineup"
    if best is not None and not cfg.contextual_stacking_enabled:
        reason = "policy_disabled"
    elif best is not None and preference is None:
        reason = "metadata_incomplete"
    elif best is not None and preference is not None:
        full = result.best_fully_balanced
        game = result.best_game_balanced
        margin = cfg.contextual_stack_ev_margin
        if full is not None and full.indices == best.indices:
            reason = "best_projected_balanced"
        elif full is not None and best.objective - full.objective <= margin + 1e-12:
            selected = full
            reason = "team_balance_within_margin"
        elif game is not None and game.indices == best.indices:
            reason = "best_projected_game_balanced"
        elif game is not None and best.objective - game.objective <= margin + 1e-12:
            selected = game
            reason = "game_balance_within_margin"
        elif game is not None or full is not None:
            reason = "contextual_ev_override"
        else:
            reason = "balance_infeasible"

    empty_shape = LineupShape(None, 0, None, 0, (), ())
    selected_shape = selected.shape if selected is not None else empty_shape
    selected_objective = selected.objective if selected is not None else 0.0
    best_objective = best.objective if best is not None else 0.0
    decision = StackingDecision(
        policy_version=POLICY_VERSION,
        enabled=cfg.contextual_stacking_enabled,
        reason=reason,
        metadata_quality=stack_context.metadata_quality,
        slate_game_count=stack_context.slate_game_count,
        slate_team_count=stack_context.slate_team_count,
        preferred_min_games=preference.min_games if preference is not None else None,
        preferred_max_players_per_game=(
            preference.max_players_per_game if preference is not None else None
        ),
        preferred_team_count=preference.target_team_count if preference is not None else 0,
        effective_max_players_per_team=effective_max_per_team,
        team_cap_reason=team_cap_reason,
        selected_game_count=selected_shape.game_count,
        selected_team_count=selected_shape.team_count,
        selected_max_players_per_game=selected_shape.max_players_per_game,
        selected_max_players_per_team=selected_shape.max_players_per_team,
        selected_game_counts=selected_shape.game_counts,
        selected_team_counts=selected_shape.team_counts,
        selected_objective=float(selected_objective),
        best_unrestricted_objective=float(best_objective),
        best_game_balanced_objective=(
            float(result.best_game_balanced.objective)
            if result.best_game_balanced is not None
            else None
        ),
        best_fully_balanced_objective=(
            float(result.best_fully_balanced.objective)
            if result.best_fully_balanced is not None
            else None
        ),
        objective_sacrifice=float(max(0.0, best_objective - selected_objective)),
        override_margin=float(cfg.contextual_stack_ev_margin),
        legacy_stack_bonus_ignored=(cfg.contextual_stacking_enabled and cfg.game_stack_bonus > 0.0),
    )
    log.info(
        "optimizer_stacking_decision",
        policy_version=decision.policy_version,
        enabled=decision.enabled,
        reason=decision.reason,
        metadata_quality=decision.metadata_quality,
        slate_game_count=decision.slate_game_count,
        selected_game_count=decision.selected_game_count,
        selected_team_count=decision.selected_team_count,
        selected_max_players_per_game=decision.selected_max_players_per_game,
        objective_sacrifice=decision.objective_sacrifice,
        override_margin=decision.override_margin,
    )
    return selected, decision


def _assemble_recommendation(
    result: _ScanResult,
    pool: _FilteredPool,
    real_score_samples: np.ndarray,
    slot_multipliers: np.ndarray,
    cfg: OptimizeConfig,
    n_games: int,
    stack_context: _StackContext,
    constraints: _ConstraintState,
) -> LineupRecommendation:
    selected, stacking_decision = _select_contextual_candidate(
        result,
        cfg,
        stack_context,
        effective_max_per_team=constraints.max_per_team,
        team_cap_reason=constraints.team_cap_reason,
    )
    if selected is None or not np.isfinite(selected.objective):
        log.error(
            "optimizer_no_feasible_lineup",
            n_filtered=len(pool.sampling),
            n_games=n_games,
            best_ev=float(selected.objective) if selected is not None else float("-inf"),
            note="no feasible 5-combo after all relaxations; EV clamped to 0.0",
        )
        return LineupRecommendation(
            player_ids=(),
            slot_multipliers=tuple(float(value) for value in slot_multipliers),
            expected_payout=0.0,
            lineup_score_p10=0.0,
            lineup_score_p50=0.0,
            lineup_score_p90=0.0,
            entry_flag="enter_with_caveat" if cfg.never_skip else "skip",
            stacking_decision=stacking_decision,
        )

    best_ev = selected.objective
    best_indices = selected.indices
    best_samples = selected.samples

    if cfg.ceiling_tilt_slots:
        sort_key = np.quantile(real_score_samples[:, list(best_indices)], 0.9, axis=0)
        sort_method = "p90 (ceiling-tilted)"
    else:
        sort_key = np.median(real_score_samples[:, list(best_indices)], axis=0)
        sort_method = "p50 (rearrangement)"
    order = np.argsort(sort_key, kind="stable")[::-1]
    ordered_player_ids = tuple(pool.player_ids[best_indices[index]] for index in order)
    p10, p50, p90 = np.quantile(best_samples, [0.1, 0.5, 0.9])

    if best_ev < cfg.skip_if_expected_payout_below:
        entry_flag = "skip"
    elif best_ev < cfg.caveat_if_expected_payout_below:
        entry_flag = "skip" if cfg.caveat_is_skip else "enter_with_caveat"
    else:
        entry_flag = "enter"
    if cfg.never_skip and entry_flag == "skip":
        entry_flag = "enter_with_caveat"
    log.debug("optimizer_slot_assignment", method=sort_method)

    return LineupRecommendation(
        player_ids=ordered_player_ids,
        slot_multipliers=tuple(float(value) for value in slot_multipliers),
        expected_payout=float(best_ev),
        lineup_score_p10=float(p10),
        lineup_score_p50=float(p50),
        lineup_score_p90=float(p90),
        entry_flag=entry_flag,
        stacking_decision=stacking_decision,
    )


def optimize_lineup(
    sampling_specs: list[PlayerSamplingSpec],
    field_specs: list[FieldPlayerSpec],
    curve: PayoutCurve,
    *,
    slot_multipliers: np.ndarray = DEFAULT_SLOT_MULTIPLIERS,
    cfg: OptimizeConfig = OptimizeConfig(),
    mixture_variance_enabled: bool = True,
) -> LineupRecommendation:
    sampling_specs, field_specs = _align_player_specs(sampling_specs, field_specs)
    n_all = len(sampling_specs)
    if n_all < 5:
        raise ValueError(f"pool too small ({n_all}) - need >= 5 players")

    stack_context = _stack_context(sampling_specs)
    required_game_count = _required_game_coverage(sampling_specs, stack_context)
    n_games, max_per_team = _slate_limits(
        sampling_specs,
        cfg,
        (stack_context.slate_game_count if cfg.contextual_stacking_enabled else None),
    )
    pool = _filter_pool(
        sampling_specs,
        field_specs,
        cfg.top_n_filter,
        float(np.max(slot_multipliers)),
        stack_context,
        cfg.contextual_stacking_enabled or required_game_count is not None,
    )
    log.info("optimizer_stage1", n_all=n_all, n_filtered=len(pool.sampling))

    real_score_samples = _sample_filtered_scores(pool, cfg, mixture_variance_enabled)
    ownership, field_lineups, field_scores = _simulate_field_scores(
        pool,
        real_score_samples,
        slot_multipliers,
        cfg,
        stack_context,
    )
    constraints = _prepare_constraints(pool, cfg, n_games, max_per_team)
    field_lineup_counter = (
        Counter(frozenset(int(index) for index in row) for row in field_lineups)
        if cfg.duplication_aware_payout
        else None
    )
    scan_inputs = _ScanInputs(
        cfg=cfg,
        filtered_count=len(pool.sampling),
        effective_max_per_team=constraints.max_per_team,
        effective_boost_sum_cap=constraints.boost_sum_cap,
        effective_max_single_boost=constraints.max_single_boost,
        keep_teams=constraints.teams,
        keep_opponents=constraints.opponents,
        keep_game_keys=[
            stack_context.game_key_by_player.get(int(spec.player_id), "") for spec in pool.sampling
        ],
        keep_is_anchor=constraints.is_anchor,
        keep_boosts=pool.boosts,
        keep_log_own=np.log(np.clip(ownership, 1e-4, 1.0)),
        real_score_samples=real_score_samples,
        field_scores=field_scores,
        ownership=ownership,
        slot_multipliers=slot_multipliers,
        curve=curve,
        field_size_total=cfg.n_field_lineups + 1,
        field_lineup_counter=field_lineup_counter,
        stack_preference=(stack_context.preference if cfg.contextual_stacking_enabled else None),
        required_game_count=required_game_count,
        unrestricted_indices=frozenset(
            index
            for index, player_id in enumerate(pool.player_ids)
            if int(player_id) in pool.unrestricted_player_ids
        ),
        balance_indices=frozenset(
            index
            for index, player_id in enumerate(pool.player_ids)
            if int(player_id) in pool.balance_player_ids
        ),
    )
    result = _run_constraint_scans(scan_inputs, constraints)
    return _assemble_recommendation(
        result,
        pool,
        real_score_samples,
        slot_multipliers,
        cfg,
        n_games,
        stack_context,
        constraints,
    )
