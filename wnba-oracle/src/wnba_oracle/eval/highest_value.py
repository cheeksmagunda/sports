"""Highest-value board as the backtest / race reference (#453 / #505).

Operator rule: do **not** grade training or backtests on prior users'
winning drafts (``contest_leaderboards``). Grade against each slate's Real
Sports Highest value board (``highestBoostedValuePlayers``) — the Aubrey /
Copper / Flau'jae / Adams-style lists.

Winning drafts remain an optional observation-only bar; they are never the
fit target or the primary backtest reference.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import polars as pl

from wnba_oracle.eval.contest_score import (
    DEFAULT_SLOT_BASES,
    committed_lineup_score,
    hindsight_max_score,
)

HV_SECTION = "highestBoostedValuePlayers"


@dataclass(frozen=True)
class HighestValuePlayer:
    """One row of a slate's Highest value board."""

    player_id: int
    display_name: str
    team_key: str
    real_score: float
    card_boost: float
    drafts: int | None
    approx_total_value: float
    rank: int


@dataclass(frozen=True)
class HighestValueReference:
    """Per-slate backtest reference built only from the HV board."""

    slate_date: str
    players: tuple[HighestValuePlayer, ...]
    top5_player_ids: tuple[int, ...]
    top5_hindsight_score: float
    value_by_player: Mapping[int, float]
    boost_by_player: Mapping[int, float]

    @property
    def top10_player_ids(self) -> tuple[int, ...]:
        return tuple(p.player_id for p in self.players[:10])


def filter_highest_value_section(slate_labels: pl.DataFrame) -> pl.DataFrame:
    """Keep only Highest value board rows with a realized score."""

    if slate_labels.is_empty() or "section" not in slate_labels.columns:
        return slate_labels.head(0)
    return slate_labels.filter(
        (pl.col("section") == HV_SECTION) & pl.col("real_score").is_not_null()
    )


def _as_float(value: object) -> float:
    if isinstance(value, bool):
        raise TypeError("bool is not a numeric HV field")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        return float(value)
    raise TypeError(f"expected numeric HV field, got {type(value).__name__}")


def _as_int(value: object) -> int:
    if isinstance(value, bool):
        raise TypeError("bool is not an integer HV field")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"expected integer HV field, got {type(value).__name__}")


def rank_highest_value_players(rows: Sequence[Mapping[str, object]]) -> list[HighestValuePlayer]:
    """Rank HV rows by approx total value ``real_score * (2 + card_boost)``.

    Matches Real Sports Value column on operator screenshots (Copper 13.2,
    Flau'jae 17.9, Aubrey ~27.8, Adams ~42.4; zero-boost Henry 16.2 = 2×base).
    """

    scored: list[tuple[float, HighestValuePlayer]] = []
    for row in rows:
        rs = _as_float(row["real_score"])
        boost = _as_float(row.get("card_boost") or 0.0)
        drafts_raw = row.get("drafts")
        approx = rs * (2.0 + boost)
        player = HighestValuePlayer(
            player_id=_as_int(row["platform_player_id"]),
            display_name=str(row.get("display_name") or ""),
            team_key=str(row.get("team_key") or ""),
            real_score=rs,
            card_boost=boost,
            drafts=None if drafts_raw is None else _as_int(drafts_raw),
            approx_total_value=approx,
            rank=0,
        )
        scored.append((approx, player))
    scored.sort(key=lambda item: (-item[0], item[1].player_id))
    ranked: list[HighestValuePlayer] = []
    for i, (_tv, player) in enumerate(scored, start=1):
        ranked.append(
            HighestValuePlayer(
                player_id=player.player_id,
                display_name=player.display_name,
                team_key=player.team_key,
                real_score=player.real_score,
                card_boost=player.card_boost,
                drafts=player.drafts,
                approx_total_value=player.approx_total_value,
                rank=i,
            )
        )
    return ranked


def build_highest_value_reference(
    slate_labels: pl.DataFrame,
    slate_date: str,
    *,
    top_n: int = 5,
    slot_bases: Sequence[float] = DEFAULT_SLOT_BASES,
) -> HighestValueReference | None:
    """Build the HV backtest reference for one slate.

    ``top_n`` players (default 5) are the reference lineup set. Reference
    score is hindsight-optimal slotting of those players' realized values.
    """

    hv = filter_highest_value_section(slate_labels).filter(pl.col("slate_date") == slate_date)
    if hv.is_empty():
        return None
    players = rank_highest_value_players(list(hv.iter_rows(named=True)))
    if len(players) < top_n:
        return None
    top = players[:top_n]
    values = [p.real_score for p in top]
    boosts = [p.card_boost for p in top]
    value_by = {p.player_id: p.real_score for p in players}
    boost_by = {p.player_id: p.card_boost for p in players}
    return HighestValueReference(
        slate_date=str(slate_date),
        players=tuple(players),
        top5_player_ids=tuple(p.player_id for p in top),
        top5_hindsight_score=hindsight_max_score(values, boosts, slot_bases),
        value_by_player=value_by,
        boost_by_player=boost_by,
    )


def grade_lineup_vs_highest_value(
    player_ids: Sequence[int],
    reference: HighestValueReference,
    *,
    slot_bases: Sequence[float] = DEFAULT_SLOT_BASES,
    overlap_top_n: int = 10,
) -> dict[str, float | int]:
    """Grade a committed lineup against the slate's HV board."""

    our = tuple(int(pid) for pid in player_ids)
    hv_top = {
        reference.players[i].player_id for i in range(min(overlap_top_n, len(reference.players)))
    }
    hv_top5 = set(reference.top5_player_ids)
    our_score = committed_lineup_score(
        our,
        reference.value_by_player,
        reference.boost_by_player,
        slot_bases=slot_bases,
    )
    ref = reference.top5_hindsight_score
    capture = (our_score / ref) if ref > 0 else 0.0
    return {
        "our_score": our_score,
        "hv_top5_score": ref,
        "hv_capture_ratio": capture,
        "overlap_hv_top5": len(set(our) & hv_top5),
        "overlap_hv_top10": len(set(our) & hv_top),
    }
