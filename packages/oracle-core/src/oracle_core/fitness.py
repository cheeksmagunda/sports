"""Domain-free WIN/CLOSE fitness helpers for the portfolio backtest race.

A sport application owns what "winner" and "rank-20" mean for its contest
(the top score on a slate's leaderboard, and the score at the 20th-place
cutoff). This module owns only the band math that turns those two numbers
plus a fresh variant score into the WIN/CLOSE booleans the race engine
feeds on. It is deliberately standalone so both ``wnba-oracle`` and
``nfl-oracle`` can use it before ``oracle_core.race`` lands; when the race
engine is extracted, these predicates fold into it unchanged.

Definitions (issues #332 / #339)::

    WIN   = score >= winner
    CLOSE = score >= (1 - b) * winner
    b     = median(rank20 / winner) across historical slates

``b`` is the median of the per-slate ratio of the rank-20 score to the
winner score over the corpus of historical slates the application supplies.
``win_close_band`` reduces that corpus to one band; ``is_win`` and
``is_close`` apply it to a fresh score; ``win_close`` returns both flags.

Worked example. Suppose two slates produced (winner, rank20) pairs
``(100, 80)`` and ``(120, 90)``. The ratios are ``0.80`` and ``0.75``, so
``b = median(0.80, 0.75) = 0.775``. For a new slate with ``winner = 100``:

* WIN threshold  = ``100``            (score >= 100 wins)
* CLOSE threshold = ``(1 - 0.775) * 100 = 22.5``  (score >= 22.5 closes)

Edge cases: a non-positive winner yields no WIN and no CLOSE (the band is
undefined for a slate nobody scored on). ``win_close_band`` ignores slates
with a non-positive winner and requires at least one usable ratio.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "WinCloseBand",
    "win_close_band",
    "is_win",
    "is_close",
    "win_close",
]


@dataclass(frozen=True)
class WinCloseBand:
    """The CLOSE band parameter ``b`` and the corpus it was derived from.

    ``b`` is the median ``rank20 / winner`` ratio. ``slate_count`` is the
    number of usable slates that went into the median, for provenance and
    logging (an app can report how much history a band was built from).
    """

    b: float
    slate_count: int

    def close_threshold(self, winner: float) -> float:
        """Return the CLOSE threshold ``(1 - b) * winner`` for a slate.

        Returns ``0.0`` for a non-positive winner; callers should treat that
        as "no close band on this slate" (``is_close`` returns ``False``).
        """

        if winner <= 0:
            return 0.0
        return (1.0 - self.b) * winner


def win_close_band(winners: Sequence[float], rank20s: Sequence[float]) -> WinCloseBand:
    """Reduce a corpus of per-slate (winner, rank20) scores to one band ``b``.

    ``b`` is the median of ``rank20 / winner`` over every slate with a
    positive winner. Slates with a non-positive winner are skipped (the
    ratio is undefined), and the median is taken over the surviving ratios,
    so a single anomalous zero-winner slate cannot poison the band. At least
    one usable slate is required.
    """

    if len(winners) != len(rank20s):
        raise ValueError(f"winners and rank20s must align: {len(winners)} != {len(rank20s)}")
    ratios = [r20 / w for w, r20 in zip(winners, rank20s, strict=True) if w > 0]
    if not ratios:
        raise ValueError("win_close_band requires at least one slate with winner > 0")
    return WinCloseBand(b=statistics.median(ratios), slate_count=len(ratios))


def is_win(score: float, winner: float) -> bool:
    """WIN: ``score`` reached or exceeded the slate ``winner``.

    A non-positive winner means nobody won the slate, so no score wins.
    """

    return winner > 0 and score >= winner


def is_close(score: float, winner: float, band: float | WinCloseBand) -> bool:
    """CLOSE: ``score`` reached ``(1 - b) * winner``.

    ``band`` is either a ``WinCloseBand`` (from :func:`win_close_band`) or a
    plain ``float`` ``b``. A non-positive winner yields no CLOSE (the band
    is undefined for a slate nobody scored on).
    """

    b = band.b if isinstance(band, WinCloseBand) else float(band)
    if winner <= 0:
        return False
    return score >= (1.0 - b) * winner


def win_close(score: float, winner: float, band: float | WinCloseBand) -> tuple[bool, bool]:
    """Return ``(won, close)`` for ``score`` on a slate with ``winner``."""

    return is_win(score, winner), is_close(score, winner, band)
