"""Score five-card lineups against Highest-value / Total Value boards (#597).

Draft-image law, the same one ``EntryLineupPick`` checks on saved contests::

    card_score = realized_value * (slot_multiplier + card_boost)
    lineup_score = sum(card_score)

Default slots are the observed NFL multipliers ``(2.0, 1.8, 1.6, 1.4, 1.2)``.

Three lineups are scored on each board:

- **HV rank**: the five highest Value-column numbers (stated Value, else
  ``realized * (observed slot + boost)``), not draft counts. Chosen players
  are then placed by descending realized value so the largest production
  takes the largest slot. That placement is optimal because the boost term
  does not depend on slot order.
- **Chalk**: the five highest draft counts (win-frequency), ordered the same
  way so the gap is selection, not slot mistakes.
- **Hindsight**: the exact best five under the draft law (boosts included).

Ollama's slate watcher ranks by ``displayed_value`` / ``highestScore`` when
the board states that Value column, otherwise by ``value``
(``scripts/ollama_hv_watcher``). It does not rank by draft count. Ridge
trains on realized production when the board joins a Corpus G row. Sample
weights and this HV rank use the Value column. The optimizer objective stays
``total_value``. This harness is the shared score for those candidates.

Read-only. No provider calls, no contest entry, no store writes.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean
from typing import Any

from nfl_oracle.contests.schema import OBSERVED_SLOT_MULTIPLIERS
from nfl_oracle.recommendations.hv_boards import (
    HvBoard,
    HvBoardPlayer,
    iter_training_boards,
    player_value_column,
)

LINEUP_SIZE = 5
Slots = tuple[float, float, float, float, float]


def card_score(realized_value: float, slot_multiplier: float, card_boost: float) -> float:
    """One draft-image card: realized value times slot multiplier plus card boost."""

    return float(realized_value) * (float(slot_multiplier) + float(card_boost))


@dataclass(frozen=True)
class ScoredCard:
    player_id: int
    slot: int
    slot_multiplier: float
    card_boost: float
    realized_value: float
    card_score: float
    drafts: int | None = None
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ScoredLineup:
    kind: str
    player_ids: tuple[int, ...]
    total: float
    cards: tuple[ScoredCard, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["cards"] = [card.to_dict() for card in self.cards]
        return payload


def _by_id(players: Sequence[HvBoardPlayer]) -> dict[int, HvBoardPlayer]:
    out: dict[int, HvBoardPlayer] = {}
    for player in players:
        prior = out.get(player.player_id)
        if prior is None or player.realized_value > prior.realized_value:
            out[player.player_id] = player
    return out


def order_by_realized(
    player_ids: Sequence[int], players: dict[int, HvBoardPlayer]
) -> tuple[int, ...]:
    return tuple(sorted(player_ids, key=lambda pid: (-players[pid].realized_value, pid)))


def score_ordered(
    player_ids: Sequence[int],
    players: dict[int, HvBoardPlayer],
    slots: Sequence[float],
    *,
    kind: str,
) -> ScoredLineup:
    """Score ``player_ids`` already in slot order (index 0 is slot 1)."""

    cards: list[ScoredCard] = []
    total = 0.0
    for index, player_id in enumerate(player_ids):
        player = players[player_id]
        slot_multiplier = float(slots[index])
        scored = card_score(player.realized_value, slot_multiplier, player.card_boost)
        total += scored
        cards.append(
            ScoredCard(
                player_id=player_id,
                slot=index + 1,
                slot_multiplier=slot_multiplier,
                card_boost=player.card_boost,
                realized_value=player.realized_value,
                card_score=round(scored, 6),
                drafts=player.drafts,
                name=player.name,
            )
        )
    return ScoredLineup(
        kind=kind,
        player_ids=tuple(player_ids),
        total=round(total, 6),
        cards=tuple(cards),
    )


def hv_rank_lineup(
    players: Sequence[HvBoardPlayer],
    slots: Sequence[float],
) -> ScoredLineup:
    """Top Value-column players, then best slot order. Draft counts are ignored."""

    pool = _by_id(players)
    ranked = sorted(
        pool.values(),
        key=lambda player: (-player_value_column(player, slots), player.player_id),
    )
    chosen = [player.player_id for player in ranked[: len(slots)]]
    ordered = order_by_realized(chosen, pool)
    return score_ordered(ordered, pool, slots, kind="hv_rank")


def chalk_lineup(
    players: Sequence[HvBoardPlayer],
    slots: Sequence[float],
) -> ScoredLineup | None:
    """Top draft counts. None when fewer than ``len(slots)`` players have a count."""

    pool = _by_id(players)
    ranked = [player for player in pool.values() if player.drafts is not None]
    if len(ranked) < len(slots):
        return None
    ranked.sort(
        key=lambda player: (-int(player.drafts or 0), -player.realized_value, player.player_id)
    )
    chosen = [player.player_id for player in ranked[: len(slots)]]
    ordered = order_by_realized(chosen, pool)
    return score_ordered(ordered, pool, slots, kind="win_frequency_chalk")


def hindsight_best(
    players: Sequence[HvBoardPlayer],
    slots: Sequence[float],
) -> ScoredLineup | None:
    """Exact best lineup. Boost term is order-invariant; slots go to descending value.

    Players are considered in descending realized value. The dynamic program
    chooses which ``len(slots)`` players to keep. Chosen players are then
    placed in descending realized-value order so the largest value takes the
    largest slot. That is optimal because ``sum(value * boost)`` does not
    depend on slot order.
    """

    pool = _by_id(players)
    ordered_players = sorted(
        pool.values(), key=lambda player: (-player.realized_value, player.player_id)
    )
    k = len(slots)
    if len(ordered_players) < k:
        return None
    best: list[tuple[float, tuple[int, ...]] | None] = [(0.0, ())] + [None] * k
    for player in ordered_players:
        for filled in range(k - 1, -1, -1):
            prior = best[filled]
            if prior is None:
                continue
            gain = card_score(player.realized_value, slots[filled], player.card_boost)
            candidate = (prior[0] + gain, (*prior[1], player.player_id))
            current = best[filled + 1]
            if (
                current is None
                or candidate[0] > current[0]
                or (candidate[0] == current[0] and candidate[1] < current[1])
            ):
                best[filled + 1] = candidate
    chosen = best[k]
    if chosen is None:
        return None
    ordered = order_by_realized(chosen[1], pool)
    return score_ordered(ordered, pool, slots, kind="hindsight")


def _capture(score: float, ceiling: float) -> float | None:
    if ceiling <= 0:
        return None
    return round(score / ceiling, 6)


@dataclass(frozen=True)
class BoardReplayResult:
    contest_id: int | None
    slate_date: str | None
    game_id: int | None
    source: str
    path: str
    n_players: int
    slot_multipliers: tuple[float, ...]
    hindsight_total: float
    hindsight_player_ids: tuple[int, ...]
    hv_rank_total: float
    hv_rank_player_ids: tuple[int, ...]
    hv_rank_capture: float | None
    chalk_total: float | None
    chalk_player_ids: tuple[int, ...]
    chalk_capture: float | None
    hv_beats_chalk: bool | None
    hv_cards: tuple[ScoredCard, ...]
    chalk_cards: tuple[ScoredCard, ...]
    hindsight_cards: tuple[ScoredCard, ...]

    def to_dict(self, *, include_cards: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "contest_id": self.contest_id,
            "slate_date": self.slate_date,
            "game_id": self.game_id,
            "source": self.source,
            "path": self.path,
            "n_players": self.n_players,
            "slot_multipliers": list(self.slot_multipliers),
            "hindsight_total": self.hindsight_total,
            "hindsight_player_ids": list(self.hindsight_player_ids),
            "hv_rank_total": self.hv_rank_total,
            "hv_rank_player_ids": list(self.hv_rank_player_ids),
            "hv_rank_capture": self.hv_rank_capture,
            "chalk_total": self.chalk_total,
            "chalk_player_ids": list(self.chalk_player_ids),
            "chalk_capture": self.chalk_capture,
            "hv_beats_chalk": self.hv_beats_chalk,
        }
        if include_cards:
            payload["hv_cards"] = [card.to_dict() for card in self.hv_cards]
            payload["chalk_cards"] = [card.to_dict() for card in self.chalk_cards]
            payload["hindsight_cards"] = [card.to_dict() for card in self.hindsight_cards]
        return payload


def _slots_of(raw: Sequence[float] | None) -> Slots | None:
    if raw is None:
        return OBSERVED_SLOT_MULTIPLIERS
    if len(raw) != LINEUP_SIZE:
        return None
    return (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]), float(raw[4]))


def replay_board(
    board: HvBoard,
    *,
    slots: Sequence[float] | None = None,
) -> BoardReplayResult | None:
    """Score one HV board. None when the pool cannot fill five cards."""

    resolved = _slots_of(slots)
    if resolved is None:
        return None
    players = board.players
    if len({player.player_id for player in players}) < LINEUP_SIZE:
        return None
    ceiling = hindsight_best(players, resolved)
    hv = hv_rank_lineup(players, resolved)
    chalk = chalk_lineup(players, resolved)
    if ceiling is None:
        return None
    hv_capture = _capture(hv.total, ceiling.total)
    chalk_capture = None if chalk is None else _capture(chalk.total, ceiling.total)
    beats: bool | None
    if chalk is None or abs(hv.total - chalk.total) <= 1e-6:
        beats = None
    else:
        beats = hv.total > chalk.total
    return BoardReplayResult(
        contest_id=board.contest_id,
        slate_date=None if board.slate_date is None else board.slate_date.isoformat(),
        game_id=board.game_id,
        source=board.source,
        path=board.path,
        n_players=len({player.player_id for player in players}),
        slot_multipliers=resolved,
        hindsight_total=ceiling.total,
        hindsight_player_ids=ceiling.player_ids,
        hv_rank_total=hv.total,
        hv_rank_player_ids=hv.player_ids,
        hv_rank_capture=hv_capture,
        chalk_total=None if chalk is None else chalk.total,
        chalk_player_ids=() if chalk is None else chalk.player_ids,
        chalk_capture=chalk_capture,
        hv_beats_chalk=beats,
        hv_cards=hv.cards,
        chalk_cards=() if chalk is None else chalk.cards,
        hindsight_cards=ceiling.cards,
    )


@dataclass
class ReplaySummary:
    n_boards: int
    n_scored: int
    n_hv_beats_chalk: int
    n_chalk_beats_hv: int
    n_ties: int
    mean_hv_rank_capture: float | None
    mean_chalk_capture: float | None
    mean_hv_rank_total: float | None
    mean_hindsight_total: float | None
    excluded: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_boards": self.n_boards,
            "n_scored": self.n_scored,
            "n_hv_beats_chalk": self.n_hv_beats_chalk,
            "n_chalk_beats_hv": self.n_chalk_beats_hv,
            "n_ties": self.n_ties,
            "mean_hv_rank_capture": self.mean_hv_rank_capture,
            "mean_chalk_capture": self.mean_chalk_capture,
            "mean_hv_rank_total": self.mean_hv_rank_total,
            "mean_hindsight_total": self.mean_hindsight_total,
            "excluded": dict(self.excluded),
        }


def summarize(
    results: Sequence[BoardReplayResult], *, excluded: dict[str, int] | None = None
) -> ReplaySummary:
    hv_caps = [row.hv_rank_capture for row in results if row.hv_rank_capture is not None]
    chalk_caps = [row.chalk_capture for row in results if row.chalk_capture is not None]
    beats = 0
    losses = 0
    ties = 0
    for row in results:
        if row.chalk_total is None:
            continue
        if abs(row.hv_rank_total - row.chalk_total) <= 1e-6:
            ties += 1
        elif row.hv_rank_total > row.chalk_total:
            beats += 1
        else:
            losses += 1
    return ReplaySummary(
        n_boards=len(results) + sum((excluded or {}).values()),
        n_scored=len(results),
        n_hv_beats_chalk=beats,
        n_chalk_beats_hv=losses,
        n_ties=ties,
        mean_hv_rank_capture=None if not hv_caps else round(mean(hv_caps), 6),
        mean_chalk_capture=None if not chalk_caps else round(mean(chalk_caps), 6),
        mean_hv_rank_total=None
        if not results
        else round(mean(row.hv_rank_total for row in results), 6),
        mean_hindsight_total=None
        if not results
        else round(mean(row.hindsight_total for row in results), 6),
        excluded=dict(excluded or {}),
    )


def replay_roots(
    *,
    contest_root: Path | None,
    export_root: Path | None,
    board_root: Path | None = None,
    slots: Sequence[float] | None = None,
) -> tuple[tuple[BoardReplayResult, ...], ReplaySummary]:
    """Replay every on-disk HV board. Reconstructed exports are excluded."""

    boards, audit = iter_training_boards(
        contest_root=contest_root,
        export_root=export_root,
        board_root=board_root,
    )
    excluded: dict[str, int] = {}
    if audit.export_files_skipped_reconstructed:
        excluded["reconstructed_or_unreadable"] = audit.export_files_skipped_reconstructed
    contests_without_board = audit.contests_indexed - sum(
        1 for board in boards if board.source.startswith("corpus_c.")
    )
    if contests_without_board > 0:
        excluded["missing_hv_section"] = contests_without_board
    results: list[BoardReplayResult] = []
    for board in boards:
        scored = replay_board(board, slots=slots)
        if scored is None:
            excluded["lineup_too_small"] = excluded.get("lineup_too_small", 0) + 1
            continue
        results.append(scored)
    return tuple(results), summarize(results, excluded=excluded)


def synthetic_boards(n: int, *, seed: int) -> tuple[HvBoard, ...]:
    """Deterministic boards where high draft counts are low realized value.

    Used to exercise the harness at depth when the full-year corpus is not
    mounted. These are not Real Sports rows and must stay labeled synthetic.
    """

    if n < 0:
        raise ValueError("synthetic_board_count")
    rng = random.Random(seed)
    boards: list[HvBoard] = []
    for index in range(n):
        players: list[HvBoardPlayer] = []
        for slot in range(8):
            if slot < 4:
                realized = rng.uniform(0.4, 2.5)
                drafts = 300 + slot * 10 + (index % 7)
                boost = rng.choice((0.0, 0.0, 0.5))
            elif slot == 7:
                realized = rng.uniform(8.0, 14.0)
                drafts = 1 + (index % 3)
                boost = rng.choice((0.0, 0.5, 1.0))
            else:
                realized = rng.uniform(2.5, 7.0)
                drafts = rng.randint(5, 80)
                boost = rng.choice((0.0, 0.5, 1.0, 1.5))
            players.append(
                HvBoardPlayer(
                    player_id=1000 + slot,
                    realized_value=round(realized, 4),
                    card_boost=boost,
                    drafts=drafts,
                    name=f"synthetic-{index}-{slot}",
                )
            )
        boards.append(
            HvBoard(
                players=tuple(players),
                source="synthetic.hv_tdv_depth",
                contest_id=None,
                slate_date=None,
                path=f"synthetic:{index}",
            )
        )
    return tuple(boards)


def replay_synthetic(n: int, *, seed: int) -> tuple[tuple[BoardReplayResult, ...], ReplaySummary]:
    boards = synthetic_boards(n, seed=seed)
    results: list[BoardReplayResult] = []
    excluded: dict[str, int] = {}
    for board in boards:
        scored = replay_board(board)
        if scored is None:
            excluded["lineup_too_small"] = excluded.get("lineup_too_small", 0) + 1
            continue
        results.append(scored)
    summary = summarize(results, excluded=excluded)
    summary.n_boards = n
    return tuple(results), summary
