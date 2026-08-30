"""Canonical realized contest scoring for offline evaluation.

This module deliberately does NOT import from ``wnba_oracle.picker``. Evaluation
must not inherit the code-under-test's assumptions about how slots get assigned,
because that is exactly how a scoring bug hides from its own backtest.

The platform rule (D42, re-verified 2026-08-19 against the
``contest_leaderboards.lineup`` JSONB, where per-player ``score`` == ``value`` *
``multiplier`` and ``multiplier`` == slot base + ``multiplierBonus``):

    lineup_score = sum_i  value_i * (slot_base_i + card_boost_i)

``value_i`` is the player's realized ``real_score``; ``card_boost_i`` is fixed
per player per slate; ``slot_base_i`` comes from the 5 descending slot bases and
is chosen by the entrant BEFORE tip.

Because the total decomposes as::

    sum_i value_i * card_boost_i   +   sum_i value_i * slot_base_i

the first term is invariant to slot ORDER. Only the second term depends on the
pairing, so choosing a slot order is a pure rearrangement problem: the
EV-maximising ex-ante order pairs the highest EXPECTED value with the highest
slot base (``ev_optimal_order``).

Two scores, never to be confused:

- :func:`committed_order_score` is what an entrant actually gets. The slot order
  is fixed before tip, so realized values are applied to the order as committed.
  This is the ONLY correct measure of a past entry or of a backtested strategy.
- :func:`hindsight_max_score` re-sorts by realized value. That is an oracle
  upper bound, not an achievable result. It is useful for headroom analysis and
  nothing else.

Conflating the two inflates every result and, worse, makes a backtest unable to
detect a slot-assignment bug in the optimizer. ``scripts/loss_ledger.py``
carried exactly that conflation until 2026-08-19, when its ``score_lineup`` was
repointed here; knob numbers in git history that cite it predate the fix.

``tests/unit/test_contest_score.py`` checks the rule above against three real
top-20 entries captured from the leaderboard, so a platform change breaks a
test rather than quietly skewing every backtest.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

# The platform fixes 5 descending slot bases; the entrant only chooses which
# player occupies which slot. Verified across every top-20 entry in the
# leaderboard corpus (D42).
DEFAULT_SLOT_BASES: tuple[float, ...] = (2.0, 1.8, 1.6, 1.4, 1.2)


def _validate(
    values: Sequence[float],
    boosts: Sequence[float],
    slot_bases: Sequence[float],
) -> None:
    if len(values) != len(boosts):
        raise ValueError(f"values/boosts length mismatch: {len(values)} vs {len(boosts)}")
    if len(values) != len(slot_bases):
        raise ValueError(f"expected {len(slot_bases)} picks, got {len(values)}")


def committed_order_score(
    values: Sequence[float],
    boosts: Sequence[float],
    slot_bases: Sequence[float] = DEFAULT_SLOT_BASES,
) -> float:
    """Realized lineup score with the slot order AS COMMITTED.

    ``values[i]`` and ``boosts[i]`` describe the player the entrant placed in
    slot ``i`` (slot 0 = the 2.0x base). This is the achievable score and the
    default metric for every backtest.
    """
    _validate(values, boosts, slot_bases)
    return sum(float(v) * (float(sb) + float(b)) for v, b, sb in zip(values, boosts, slot_bases))


def committed_lineup_score(
    player_ids: Sequence[int],
    value_by_player: Mapping[int, float],
    boost_by_player: Mapping[int, float],
    slot_bases: Sequence[float] = DEFAULT_SLOT_BASES,
) -> float:
    """Score a lineup mapping in the player order the entrant committed."""
    values = [float(value_by_player.get(int(player_id), 0.0)) for player_id in player_ids]
    boosts = [float(boost_by_player.get(int(player_id), 0.0)) for player_id in player_ids]
    return committed_order_score(values, boosts, slot_bases)


def hindsight_max_score(
    values: Sequence[float],
    boosts: Sequence[float],
    slot_bases: Sequence[float] = DEFAULT_SLOT_BASES,
) -> float:
    """Upper bound: the best slot order given perfect foreknowledge of values.

    NOT achievable in play. Use only to measure headroom left on the table by
    slot assignment, never to score a strategy. See module docstring.
    """
    _validate(values, boosts, slot_bases)
    order = sorted(range(len(values)), key=lambda i: float(values[i]), reverse=True)
    bases = sorted((float(s) for s in slot_bases), reverse=True)
    return sum(float(values[i]) * (base + float(boosts[i])) for i, base in zip(order, bases))


def ev_optimal_order(predicted_values: Sequence[float]) -> tuple[int, ...]:
    """Indices sorted so index 0 takes the highest slot base.

    The EV-maximising ex-ante assignment under the additive rule: pair the
    highest EXPECTED value with the highest slot base (rearrangement
    inequality). Ties resolve by input order so the result is deterministic.
    """
    return tuple(
        sorted(range(len(predicted_values)), key=lambda i: (-float(predicted_values[i]), i))
    )


def slot_order_headroom(
    values: Sequence[float],
    boosts: Sequence[float],
    slot_bases: Sequence[float] = DEFAULT_SLOT_BASES,
) -> float:
    """Points left on the table by the committed order, versus perfect ordering.

    Always >= 0. Reports how much of a loss is attributable to slot assignment
    rather than to player selection.
    """
    return hindsight_max_score(values, boosts, slot_bases) - committed_order_score(
        values, boosts, slot_bases
    )
