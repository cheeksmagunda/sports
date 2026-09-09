"""Card boosts: what they are, when they appear, and how to recover them.

A card boost (``multiplierBonus``) is assigned by the provider, not chosen by
the entrant. The effective multiplier on a committed card is
``slot_multiplier + card_boost``, so a boost is pure leverage on a player's
Real value and is the single largest source of spread between lineups.

Two facts drive everything downstream:

* The provider's own draft copy says "Lower-ranked players get bigger boosts",
  so the boost is a function of the player's pre-game Real ranking. Recovering
  that function from finalized contests lets the model reason about leverage
  before the live boost table is published.
* The live boost table can read all-zero well before lock. An all-zero table is
  indistinguishable in shape from a real one, and an optimizer fed zeros
  silently degenerates into "pick the five highest projected values", throwing
  away the entire leverage dimension. Zero-boost slates must therefore be
  detected and gated, never quietly optimized.
"""

from __future__ import annotations

import statistics
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from nfl_oracle.contests.schema import MAX_OBSERVED_BOOST, OBSERVED_SLOT_MULTIPLIERS

# Boosts are published in tenths. Snapping removes float noise introduced by the
# provider's own arithmetic (``1.4000000000000001``) without inventing values.
BOOST_QUANTUM = 0.1


def snap_boost(value: float) -> float:
    """Round an observed boost to the provider's published tenth."""
    return round(round(float(value) / BOOST_QUANTUM) * BOOST_QUANTUM, 1)


def boost_from_multiplier(effective_multiplier: float, slot_multiplier: float) -> float:
    """Recover the card boost from a saved entry's effective multiplier."""
    boost = snap_boost(float(effective_multiplier) - float(slot_multiplier))
    if boost < -1e-9 or boost > MAX_OBSERVED_BOOST + 1e-9:
        raise ValueError("recovered_boost_out_of_range")
    return max(boost, 0.0)


def slot_multiplier_for(slot: int, multipliers: Sequence[float] | None = None) -> float:
    """Return the committed multiplier for a 1-indexed slot."""
    table = tuple(multipliers or OBSERVED_SLOT_MULTIPLIERS)
    if not 1 <= slot <= len(table):
        raise ValueError("slot_out_of_range")
    return float(table[slot - 1])


@dataclass(frozen=True)
class BoostObservation:
    """One capture of the live pre-lock boost table."""

    contest_id: int
    captured_at: str
    n_players: int
    n_nonzero: int
    max_boost: float
    distinct_boosts: tuple[float, ...]
    # True when the table is published and usable for optimization.
    published: bool
    source: str = "prelock_rating_search"

    @property
    def all_zero(self) -> bool:
        return self.n_players > 0 and self.n_nonzero == 0


def observe_boosts(
    contest_id: int, players: Iterable[Mapping[str, Any]], *, captured_at: str
) -> BoostObservation:
    """Summarize a live boost table capture without storing player identity."""
    boosts: list[float] = []
    for player in players:
        raw = player.get("multiplierBonus")
        if raw is None:
            continue
        boosts.append(snap_boost(float(raw)))
    nonzero = [b for b in boosts if b > 0]
    return BoostObservation(
        contest_id=contest_id,
        captured_at=captured_at,
        n_players=len(boosts),
        n_nonzero=len(nonzero),
        max_boost=max(boosts) if boosts else 0.0,
        distinct_boosts=tuple(sorted(set(boosts))),
        published=bool(nonzero),
    )


@dataclass(frozen=True)
class BoostRankCurve:
    """Empirical map from pre-game Real ranking to card boost.

    Fitted from finalized contests where both the ranking and the boost are
    observed. Monotone non-increasing in rank quality by construction of the
    provider's rule, but the fit does not assume it; a violation is reported so
    a rule-era change shows up instead of being smoothed away.
    """

    # rank bucket upper bound -> median boost observed in that bucket
    buckets: tuple[tuple[int, float], ...]
    n_observations: int
    n_contests: int
    monotone: bool
    unranked_boost: float | None

    def predict(self, primary_ranking: int | None) -> float | None:
        """Return the expected boost for a ranking, or None when unlearnable."""
        if primary_ranking is None:
            return self.unranked_boost
        for upper, boost in self.buckets:
            if primary_ranking <= upper:
                return boost
        return self.buckets[-1][1] if self.buckets else None


def fit_boost_rank_curve(
    observations: Sequence[tuple[int | None, float, int]],
    *,
    bucket_edges: Sequence[int] = (10, 25, 50, 75, 100, 150, 200, 300, 500, 1000, 10_000),
) -> BoostRankCurve:
    """Fit rank -> boost from ``(primary_ranking, boost, contest_id)`` triples."""
    ranked = [(r, b) for r, b, _ in observations if r is not None]
    unranked = [b for r, b, _ in observations if r is None]
    buckets: list[tuple[int, float]] = []
    for upper in bucket_edges:
        lower = 0 if not buckets else buckets[-1][0]
        inside = [b for r, b in ranked if lower < r <= upper]
        if inside:
            buckets.append((upper, snap_boost(statistics.median(inside))))
    monotone = all(a[1] <= b[1] + 1e-9 for a, b in zip(buckets, buckets[1:], strict=False))
    return BoostRankCurve(
        buckets=tuple(buckets),
        n_observations=len(observations),
        n_contests=len({c for _, _, c in observations}),
        monotone=monotone,
        unranked_boost=snap_boost(statistics.median(unranked)) if unranked else None,
    )


def boost_leverage_table(boosts: Iterable[float]) -> dict[str, float]:
    """Describe the leverage spread a boost table creates across the five slots.

    ``value_ratio_to_match`` answers the question that decides every lineup: how
    much of a top card's Real value does a max-boost card need to produce in
    order to tie it. A small ratio means the boosted card is cheap leverage.
    """
    table = sorted({snap_boost(b) for b in boosts})
    if not table:
        return {}
    best_slot = float(OBSERVED_SLOT_MULTIPLIERS[0])
    worst_slot = float(OBSERVED_SLOT_MULTIPLIERS[-1])
    top = table[-1]
    return {
        "n_distinct_boosts": float(len(table)),
        "max_boost": top,
        "min_boost": table[0],
        "max_effective_multiplier": best_slot + top,
        "min_effective_multiplier": worst_slot + table[0],
        # A max-boost card in the worst slot vs a zero-boost card in the best.
        "value_ratio_to_match": (
            best_slot / (worst_slot + top) if (worst_slot + top) > 0 else float("inf")
        ),
        "leverage_span": (best_slot + top) / best_slot,
    }


def boost_histogram(boosts: Iterable[float]) -> dict[str, int]:
    return {f"{k:.1f}": v for k, v in sorted(Counter(snap_boost(b) for b in boosts).items())}
