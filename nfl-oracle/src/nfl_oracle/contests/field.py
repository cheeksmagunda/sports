"""What winning lineups actually did, measured from the saved contest archive.

The provider serves only the top twenty entries of a field that can run past
twenty thousand. Every statistic in this module is therefore conditioned on
"made the visible top twenty" and is stated that way. Nothing here estimates the
median entry, because the median entry is never observed.

Three questions drive the whole study:

* **Leverage.** Winning lineups are built out of card boosts, not out of the
  highest-rated players. The measurements here quantify how much boost the
  visible winners carried relative to what was on the board.
* **Ordering.** The committed slot order is a free, deterministic lever: total
  score decomposes into a slot-invariant part and a rearrangement part, so the
  only correct ordering is by descending projected value. ``slot_regret``
  measures how much score real humans left on the table by getting that wrong.
* **Reachability.** ``counterfactual_best`` is the highest score any legal
  lineup could have produced with hindsight. The gap between it and the actual
  winner bounds how much of winning is selection skill versus variance.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from itertools import permutations

from nfl_oracle.contests.parse import ParsedContest
from nfl_oracle.contests.schema import ENTRIES_VISIBLE_LIMIT, EntryRecord


@dataclass(frozen=True)
class LineupProfile:
    """One saved human lineup, described in the terms the scoring law cares about."""

    contest_id: int
    rank: int
    score: float | None
    total_boost: float
    max_boost: float
    n_zero_boost: int
    mean_value: float | None
    best_real_rank: int | None
    worst_real_rank: int | None
    n_top10_real_rank: int
    distinct_teams: int
    # Score the same five players would have made under the best legal ordering.
    best_ordering_score: float | None
    slot_regret: float | None
    ordering_optimal: bool | None


def _best_ordering_score(entry: EntryRecord) -> float | None:
    """Maximum score the same five players could reach over all slot orders.

    The additive law makes this a rearrangement: pair the largest realized value
    with the largest slot multiplier. Computed by explicit enumeration so the
    result stands on arithmetic rather than on the inequality being quoted.
    """
    if not entry.picks or any(p.value is None for p in entry.picks):
        return None
    values = [float(p.value) for p in entry.picks if p.value is not None]
    slots = [float(p.slot_multiplier) for p in entry.picks]
    boosts = [float(p.card_boost) for p in entry.picks]
    invariant = sum(v * b for v, b in zip(values, boosts, strict=True))
    descending = sorted(slots, reverse=True)
    best = max(
        sum(values[i] * slot for i, slot in zip(order, descending, strict=True))
        for order in permutations(range(len(values)))
    )
    return invariant + best


def profile_entry(entry: EntryRecord) -> LineupProfile:
    boosts = [p.card_boost for p in entry.picks]
    values = [p.value for p in entry.picks if p.value is not None]
    ranks = [p.real_rank for p in entry.picks if p.real_rank is not None]
    best = _best_ordering_score(entry)
    actual = entry.total_from_picks()
    regret = None if best is None or actual is None else round(best - actual, 6)
    return LineupProfile(
        contest_id=entry.contest_id,
        rank=entry.rank,
        score=entry.score,
        total_boost=round(sum(boosts), 3),
        max_boost=max(boosts) if boosts else 0.0,
        n_zero_boost=sum(1 for b in boosts if b <= 0),
        mean_value=round(statistics.mean(values), 4) if values else None,
        best_real_rank=min(ranks) if ranks else None,
        worst_real_rank=max(ranks) if ranks else None,
        n_top10_real_rank=sum(1 for r in ranks if r <= 10),
        distinct_teams=len({p.team_id for p in entry.picks if p.team_id is not None}),
        best_ordering_score=None if best is None else round(best, 6),
        slot_regret=regret,
        ordering_optimal=None if regret is None else regret <= 1e-6,
    )


@dataclass(frozen=True)
class CounterfactualBest:
    """The best legal lineup with hindsight, over every player the contest revealed."""

    score: float
    player_ids: tuple[int, ...]
    slots: tuple[int, ...]
    n_players_considered: int
    # True when every considered player's boost and value were both observed.
    complete_pool: bool


def counterfactual_best(
    parsed: ParsedContest, *, slot_multipliers: Sequence[float] | None = None
) -> CounterfactualBest | None:
    """Solve the hindsight optimum exactly over the revealed player pool.

    With values and boosts fixed, the objective is
    ``sum(v_i * b_i) + sum(v_i * s_pi(i))``. The first term is order-invariant,
    so an exact solution comes from a small dynamic program over players sorted
    by descending value: the chosen five, in that order, take the slot
    multipliers in descending order.
    """
    slots = list(slot_multipliers or parsed.contest.slot_multipliers)
    values = parsed.observed_values()
    boosts = parsed.boost_table()
    pool = [(pid, values[pid], boosts[pid]) for pid in values if pid in boosts]
    if len(pool) < len(slots):
        return None
    pool.sort(key=lambda row: (-row[1], row[0]))
    k = len(slots)
    # best[j] maps "j slots already committed" to (score, chosen ids).
    best: list[tuple[float, tuple[int, ...]] | None] = [(0.0, ())] + [None] * k
    for pid, value, boost in pool:
        for j in range(min(k - 1, len(pool)), -1, -1):
            prior = best[j]
            if prior is None:
                continue
            gain = value * (slots[j] + boost)
            candidate = (prior[0] + gain, (*prior[1], pid))
            if best[j + 1] is None or candidate[0] > best[j + 1][0]:  # type: ignore[index]
                best[j + 1] = candidate
    top = best[k]
    if top is None:
        return None
    return CounterfactualBest(
        score=round(top[0], 6),
        player_ids=top[1],
        slots=tuple(range(1, k + 1)),
        n_players_considered=len(pool),
        complete_pool=set(values) == set(boosts),
    )


@dataclass
class ContestFieldStudy:
    """Everything the archive can honestly say about one finalized contest."""

    contest_id: int
    day: str
    entrants: int
    visible_entries: int
    censored: bool
    winner: LineupProfile | None
    profiles: list[LineupProfile] = field(default_factory=list)
    hindsight: CounterfactualBest | None = None
    # Consensus structure of the visible top twenty.
    core_player_ids: tuple[int, ...] = ()
    core_share: float = 0.0
    winner_score_gap_to_20th: float | None = None
    winner_share_of_hindsight: float | None = None
    mean_slot_regret: float | None = None
    share_ordering_optimal: float | None = None
    law_verified: bool = True

    def as_row(self) -> dict[str, object]:
        return {
            "contest_id": self.contest_id,
            "day": self.day,
            "entrants": self.entrants,
            "visible_entries": self.visible_entries,
            "censored": self.censored,
            "winner_score": self.winner.score if self.winner else None,
            "winner_total_boost": self.winner.total_boost if self.winner else None,
            "winner_max_boost": self.winner.max_boost if self.winner else None,
            "winner_n_zero_boost": self.winner.n_zero_boost if self.winner else None,
            "winner_n_top10_real_rank": self.winner.n_top10_real_rank if self.winner else None,
            "hindsight_best": self.hindsight.score if self.hindsight else None,
            "winner_share_of_hindsight": self.winner_share_of_hindsight,
            "winner_score_gap_to_20th": self.winner_score_gap_to_20th,
            "core_share": self.core_share,
            "mean_slot_regret": self.mean_slot_regret,
            "share_ordering_optimal": self.share_ordering_optimal,
            "law_verified": self.law_verified,
        }


def study_contest(parsed: ParsedContest) -> ContestFieldStudy | None:
    if not parsed.entries:
        return None
    profiles = [profile_entry(e) for e in sorted(parsed.entries, key=lambda e: e.rank)]
    winner = profiles[0] if profiles else None
    hindsight = counterfactual_best(parsed)
    counts: dict[int, int] = {}
    for entry in parsed.entries:
        for pick in entry.picks:
            counts[pick.player_id] = counts.get(pick.player_id, 0) + 1
    core = tuple(
        pid
        for pid, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        if n >= max(2, len(parsed.entries) // 2)
    )
    regrets = [p.slot_regret for p in profiles if p.slot_regret is not None]
    optimal = [p.ordering_optimal for p in profiles if p.ordering_optimal is not None]
    scores = [p.score for p in profiles if p.score is not None]
    return ContestFieldStudy(
        contest_id=parsed.contest.contest_id,
        day=parsed.contest.day.isoformat(),
        entrants=parsed.contest.entrants,
        visible_entries=len(parsed.entries),
        censored=parsed.contest.entrants > len(parsed.entries),
        winner=winner,
        profiles=profiles,
        hindsight=hindsight,
        core_player_ids=core,
        core_share=round(len(core) / 5, 3) if core else 0.0,
        winner_score_gap_to_20th=(round(scores[0] - scores[-1], 4) if len(scores) >= 2 else None),
        winner_share_of_hindsight=(
            round(scores[0] / hindsight.score, 4)
            if hindsight and hindsight.score > 0 and scores
            else None
        ),
        mean_slot_regret=round(statistics.mean(regrets), 4) if regrets else None,
        share_ordering_optimal=(
            round(sum(1 for o in optimal if o) / len(optimal), 4) if optimal else None
        ),
        law_verified=parsed.law_verified,
    )


def summarize_studies(studies: Iterable[ContestFieldStudy]) -> dict[str, object]:
    """Pool per-contest findings into the portfolio-level strategy summary."""
    rows = [s for s in studies if s.winner is not None]
    if not rows:
        return {"n_contests": 0}

    def pooled(values: list[float]) -> dict[str, float] | None:
        if not values:
            return None
        return {
            "mean": round(statistics.mean(values), 4),
            "median": round(statistics.median(values), 4),
            "min": round(min(values), 4),
            "max": round(max(values), 4),
        }

    winner_boost = [s.winner.total_boost for s in rows if s.winner]
    winner_max = [s.winner.max_boost for s in rows if s.winner]
    zero_boost = [float(s.winner.n_zero_boost) for s in rows if s.winner]
    top10 = [float(s.winner.n_top10_real_rank) for s in rows if s.winner]
    share = [s.winner_share_of_hindsight for s in rows if s.winner_share_of_hindsight is not None]
    regret = [s.mean_slot_regret for s in rows if s.mean_slot_regret is not None]
    optimal = [s.share_ordering_optimal for s in rows if s.share_ordering_optimal is not None]
    return {
        "n_contests": len(rows),
        "n_censored": sum(1 for s in rows if s.censored),
        "entrants": pooled([float(s.entrants) for s in rows]),
        "winner_total_boost": pooled(winner_boost),
        "winner_max_boost": pooled(winner_max),
        "winner_zero_boost_cards": pooled(zero_boost),
        "winner_top10_real_rank_cards": pooled(top10),
        "winner_share_of_hindsight_best": pooled([float(x) for x in share]),
        "visible_field_mean_slot_regret": pooled([float(x) for x in regret]),
        "visible_field_share_ordering_optimal": pooled([float(x) for x in optimal]),
        "visible_entry_limit": ENTRIES_VISIBLE_LIMIT,
        "caveat": "all_statistics_conditioned_on_reaching_the_visible_top_twenty",
    }
