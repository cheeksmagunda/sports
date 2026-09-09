"""Replay the saved Corpus C archive against the verified scoring law.

Turns three STATUS.md prose claims into executable, re-derivable facts:
optimal slot-order rate, mean slot regret, and the winner's capture ratio
against the legal hindsight-best five-card lineup. Everything here reads
:class:`~nfl_oracle.contests.parse.ParsedContest` records produced by
:func:`nfl_oracle.contests.parse.iter_contests`; it duplicates none of that
parsing or law verification.

Honesty boundary, load-bearing: ``/entries`` serves at most the top twenty
saved human lineups and ``draft_count`` has an unstated denominator (see
:class:`~nfl_oracle.contests.schema.DraftStatRow`). Every statistic here is
conditioned on the visible top twenty of a field that can run past 60,000.
This module answers "did our lineup beat the visible winner", never
"what percentile would our lineup have finished at" -- the field beyond the
top twenty is not observed and no function here estimates it.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from nfl_oracle.contests.boosts import slot_multiplier_for
from nfl_oracle.contests.parse import ParsedContest
from nfl_oracle.contests.schema import EntryRecord


@dataclass(frozen=True)
class HindsightLineup:
    """The legal five-card lineup that maximizes score under finalized values."""

    player_ids: tuple[int, ...]
    values: tuple[float, ...]
    total_score: float


@dataclass(frozen=True)
class ContestReplayResult:
    contest_id: int
    entrants: int
    is_zero_boost: bool
    hindsight_best: HindsightLineup | None
    winner_score: float | None
    winner_capture_ratio: float | None
    entries_optimally_ordered: int
    entries_scored: int
    mean_slot_regret: float | None


def eligible_pool_values(contest: ParsedContest) -> dict[int, float]:
    """Every player id this contest reveals a finalized value for.

    Draft-stats rows and entry picks can disagree by floating point noise on a
    shared player; entry picks win because they are the leaderboard's own
    scoring input.
    """
    values: dict[int, float] = {}
    for row in contest.draft_stats:
        if row.value is not None:
            values[row.player_id] = row.value
    for entry in contest.entries:
        for pick in entry.picks:
            if pick.value is not None:
                values[pick.player_id] = pick.value
    return values


def hindsight_best_lineup(
    contest: ParsedContest, *, k: int | None = None
) -> HindsightLineup | None:
    """The true optimal legal k-card lineup given finalized values and boosts.

    ``score = value * (slot + boost)`` splits into an order-invariant part
    ``sum(value * boost)`` and a rearrangement part ``sum(value * slot)``. For
    ANY fixed set of k players, the rearrangement part is maximized by
    descending-value slot assignment (rearrangement inequality), independent
    of boost. So once the pool is sorted by value descending, a chosen
    player's within-set rank -- and therefore its slot multiplier -- is just
    its position among the chosen players in that global order. Selecting the
    optimal SET is then a single left-to-right DP over the sorted pool:
    ``best[m][j]`` is the max achievable total using a prefix of length ``m``
    having filled ``j`` of the ``k`` slots (slots ``1..j`` in encounter order).
    This is the ceiling: no legal k-card commitment scores higher under the
    verified law given these finalized values. Selecting by raw value alone
    (ignoring boost) is only correct when every boost is equal, e.g. the
    zero-boost regime.
    """
    k = k or contest.contest.lineup_size
    pool = eligible_pool_values(contest)
    if len(pool) < k:
        return None
    boosts = contest.boost_table()
    multipliers = contest.contest.slot_multipliers
    slots = [slot_multiplier_for(s, multipliers) for s in range(1, k + 1)]
    ranked = sorted(pool.items(), key=lambda kv: -kv[1])
    n = len(ranked)

    neg_inf = float("-inf")
    # best[j] = (total, choice-path) achievable after processing a prefix,
    # having filled j of the k slots so far (slot j+1 is assigned next).
    best: list[float] = [0.0] + [neg_inf] * k
    choice: list[list[bool]] = [[False] * (k + 1) for _ in range(n)]
    for i, (_player_id, value) in enumerate(ranked):
        own_boost_total = value * boosts.get(ranked[i][0], 0.0)
        for j in range(min(i, k - 1), -1, -1):
            if best[j] == neg_inf:
                continue
            candidate = best[j] + own_boost_total + value * slots[j]
            if candidate > best[j + 1]:
                best[j + 1] = candidate
                choice[i][j + 1] = True

    total = best[k]
    if total == neg_inf:
        return None
    chosen: list[int] = []
    j = k
    for i in range(n - 1, -1, -1):
        if j > 0 and choice[i][j]:
            chosen.append(i)
            j -= 1
    chosen.reverse()
    return HindsightLineup(
        player_ids=tuple(ranked[i][0] for i in chosen),
        values=tuple(ranked[i][1] for i in chosen),
        total_score=total,
    )


def slot_regret(entry: EntryRecord) -> float | None:
    """Points left on the table versus sorting this entry's own five cards by
    descending finalized value. Zero means the entry already committed the
    optimal order for the five players it drafted; it says nothing about
    whether those five were the right five.
    """
    if any(p.value is None for p in entry.picks):
        return None
    actual = entry.total_from_picks()
    if actual is None:
        return None
    by_value = sorted(entry.picks, key=lambda p: -(p.value or 0.0))
    slots = sorted((p.slot_multiplier for p in entry.picks), reverse=True)
    pairs = zip(by_value, slots, strict=True)
    optimal = sum((pick.value or 0.0) * (slot + pick.card_boost) for pick, slot in pairs)
    return optimal - actual


def is_optimally_ordered(entry: EntryRecord, *, tol: float = 1e-6) -> bool | None:
    regret = slot_regret(entry)
    if regret is None:
        return None
    return regret <= tol


def replay_contest(contest: ParsedContest) -> ContestReplayResult:
    boosts = contest.boost_table()
    is_zero_boost = bool(boosts) and all(b == 0.0 for b in boosts.values())
    best = hindsight_best_lineup(contest)
    winner = next((e for e in contest.entries if e.rank == 1), None)
    winner_score = winner.total_from_picks() if winner else None
    has_best = bool(winner_score) and best is not None and best.total_score > 0
    ratio = (winner_score or 0.0) / best.total_score if (has_best and best is not None) else None

    regrets: list[float] = []
    optimal_count = 0
    scored = 0
    for entry in contest.entries:
        r = slot_regret(entry)
        if r is None:
            continue
        scored += 1
        regrets.append(r)
        if r <= 1e-6:
            optimal_count += 1

    return ContestReplayResult(
        contest_id=contest.contest.contest_id,
        entrants=contest.contest.entrants,
        is_zero_boost=is_zero_boost,
        hindsight_best=best,
        winner_score=winner_score,
        winner_capture_ratio=ratio,
        entries_optimally_ordered=optimal_count,
        entries_scored=scored,
        mean_slot_regret=(sum(regrets) / len(regrets)) if regrets else None,
    )


@dataclass(frozen=True)
class PooledReplaySummary:
    n_contests: int
    n_entries_scored: int
    optimal_order_rate: float | None
    mean_slot_regret: float | None
    mean_winner_capture_ratio: float | None
    n_capture_observed: int


def pooled_summary(results: Iterable[ContestReplayResult]) -> PooledReplaySummary:
    results = list(results)
    total_optimal = sum(r.entries_optimally_ordered for r in results)
    total_scored = sum(r.entries_scored for r in results)
    weighted = [
        r.mean_slot_regret * r.entries_scored for r in results if r.mean_slot_regret is not None
    ]
    weight = sum(r.entries_scored for r in results if r.mean_slot_regret is not None)
    captures = [r.winner_capture_ratio for r in results if r.winner_capture_ratio is not None]
    return PooledReplaySummary(
        n_contests=len(results),
        n_entries_scored=total_scored,
        optimal_order_rate=(total_optimal / total_scored) if total_scored else None,
        mean_slot_regret=(sum(weighted) / weight) if weight else None,
        mean_winner_capture_ratio=(sum(captures) / len(captures)) if captures else None,
        n_capture_observed=len(captures),
    )


def replay_all(contests: Sequence[ParsedContest]) -> list[ContestReplayResult]:
    return [replay_contest(c) for c in contests]
