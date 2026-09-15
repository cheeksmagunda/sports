"""Walk-forward Real-value-allowed priors for the opponent defense.

Corpus G box rows already carry everything this needs: finalized Real
``value``, the scoring player's ``team_id``, the ``opponent_team_id`` derived
from the game feed, and the kickoff clock. Grouping those rows by
``opponent_team_id`` is a genuine "value allowed by that defense" table, so
``opp_def_value_allowed_prior`` is a Real-value join and not a yards-derived
proxy.

Time safety mirrors ``recommendations.context.HistoricalContext.prior_rows``:
a game may only enter a prior when its kickoff is strictly before the cutoff
AND at least ``EVENT_BUFFER_HOURS`` before the decision clock. A row therefore
never sees its own game, and a live decision never sees a same-slate final.

Rows are duck-typed (``player_id``, ``value``, ``kickoff_at``,
``opponent_team_id``, ``position``, ``did_not_play``) so this module does not
import ``recommendations`` and the package boundary stays one-way.
"""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import fmean
from typing import Any, Final

EVENT_BUFFER_HOURS: Final = 24
# Factor clamp. A defense prior may only move a player prior within this band;
# thin or extreme samples must not manufacture a magnitude.
FACTOR_CLAMP: Final[tuple[float, float]] = (0.5, 1.5)
MIN_SUPPORT: Final = 3


@dataclass(frozen=True)
class ValueAllowedObservation:
    """One finalized Real value, attributed to the defense that allowed it."""

    player_id: int
    opponent_team_id: int
    kickoff_at: datetime
    value: float
    position: str | None = None


@dataclass(frozen=True)
class PriorEstimate:
    """A mean with its sample size, so callers can refuse thin support."""

    mean: float | None
    n: int

    @property
    def usable(self) -> bool:
        return self.mean is not None and self.n > 0


_EMPTY = PriorEstimate(mean=None, n=0)


def observations_from_history(rows: Iterable[Any]) -> tuple[ValueAllowedObservation, ...]:
    """Adapt finalized history rows into value-allowed observations.

    Rows missing an opponent, a value, or a kickoff are skipped rather than
    imputed. Did-not-play rows are skipped: a zero that never took the field is
    not evidence about the defense.
    """

    out: list[ValueAllowedObservation] = []
    for row in rows:
        opponent = getattr(row, "opponent_team_id", None)
        value = getattr(row, "value", None)
        kickoff = getattr(row, "kickoff_at", None)
        player_id = getattr(row, "player_id", None)
        if opponent is None or value is None or kickoff is None or player_id is None:
            continue
        if bool(getattr(row, "did_not_play", False)):
            continue
        position = getattr(row, "position", None)
        out.append(
            ValueAllowedObservation(
                player_id=int(player_id),
                opponent_team_id=int(opponent),
                kickoff_at=kickoff,
                value=float(value),
                position=str(position) if position else None,
            )
        )
    return tuple(out)


def _mean_before(
    series: Sequence[tuple[datetime, float]], before: datetime, until: datetime | None
) -> PriorEstimate:
    if not series:
        return _EMPTY
    buffer = timedelta(hours=EVENT_BUFFER_HOURS)
    cutoff = min(before, until) if until is not None else before
    ceiling = min(cutoff, before - buffer)
    times = [observed for observed, _ in series]
    index = bisect_right(times, ceiling)
    values = [value for _, value in series[:index]]
    if not values:
        return _EMPTY
    return PriorEstimate(mean=float(fmean(values)), n=len(values))


class RealValueHistoryIndex:
    """Opponent-defense, player, position and league Real-value priors."""

    def __init__(self, observations: Iterable[ValueAllowedObservation]) -> None:
        self._by_opponent: dict[int, list[tuple[datetime, float]]] = {}
        self._by_opponent_position: dict[tuple[int, str], list[tuple[datetime, float]]] = {}
        self._by_player: dict[int, list[tuple[datetime, float]]] = {}
        self._by_position: dict[str, list[tuple[datetime, float]]] = {}
        self._league: list[tuple[datetime, float]] = []
        for item in observations:
            point = (item.kickoff_at, item.value)
            self._by_opponent.setdefault(item.opponent_team_id, []).append(point)
            self._by_player.setdefault(item.player_id, []).append(point)
            self._league.append(point)
            if item.position:
                key = item.position.upper()
                self._by_position.setdefault(key, []).append(point)
                self._by_opponent_position.setdefault((item.opponent_team_id, key), []).append(
                    point
                )
        for bucket in (
            self._by_opponent,
            self._by_opponent_position,
            self._by_player,
            self._by_position,
        ):
            for series in bucket.values():
                series.sort(key=lambda item: item[0])
        self._league.sort(key=lambda item: item[0])

    def __bool__(self) -> bool:
        return bool(self._league)

    def opponent_allowed_prior(
        self,
        opponent_team_id: int | None,
        before: datetime,
        *,
        until: datetime | None = None,
        position: str | None = None,
    ) -> PriorEstimate:
        """Mean Real value this defense allowed before the cutoff.

        A position split is preferred when it carries at least ``MIN_SUPPORT``
        observations; otherwise the all-position mean for that defense is used.
        """

        if opponent_team_id is None:
            return _EMPTY
        if position:
            split = _mean_before(
                self._by_opponent_position.get((int(opponent_team_id), position.upper()), []),
                before,
                until,
            )
            if split.usable and split.n >= MIN_SUPPORT:
                return split
        return _mean_before(self._by_opponent.get(int(opponent_team_id), []), before, until)

    def league_allowed_prior(
        self, before: datetime, *, until: datetime | None = None, position: str | None = None
    ) -> PriorEstimate:
        """League-wide mean Real value before the cutoff (the factor baseline)."""

        if position:
            split = _mean_before(self._by_position.get(position.upper(), []), before, until)
            if split.usable and split.n >= MIN_SUPPORT:
                return split
        return _mean_before(self._league, before, until)

    def player_prior(
        self, player_id: int | None, before: datetime, *, until: datetime | None = None
    ) -> PriorEstimate:
        """Mean finalized Real value for one player before the cutoff."""

        if player_id is None:
            return _EMPTY
        return _mean_before(self._by_player.get(int(player_id), []), before, until)

    def position_prior(
        self, position: str | None, before: datetime, *, until: datetime | None = None
    ) -> PriorEstimate:
        if not position:
            return _EMPTY
        return _mean_before(self._by_position.get(position.upper(), []), before, until)


def opponent_defense_factor(
    allowed: PriorEstimate,
    league: PriorEstimate,
    *,
    clamp: tuple[float, float] = FACTOR_CLAMP,
) -> float | None:
    """Ratio of value allowed by this defense to the league baseline.

    Returns None when either side lacks support or the baseline is not
    positive. The result is clamped so a thin defense sample cannot dominate a
    player prior.
    """

    if not allowed.usable or not league.usable:
        return None
    baseline = league.mean
    if baseline is None or baseline <= 0:
        return None
    assert allowed.mean is not None
    low, high = clamp
    return max(low, min(high, allowed.mean / baseline))


def opponent_adjusted_prior(player: PriorEstimate, factor: float | None) -> float | None:
    """Player Real-value prior scaled by the opponent-defense factor."""

    if factor is None or not player.usable or player.mean is None:
        return None
    return player.mean * factor
