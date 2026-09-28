"""Keep only HV/TDV leaderboard rows as the NFL train target.

Issue #597, operator lock from audit #599. ``nfl-pipeline train`` calls the
#185 ladder (``high_tv_board_from_draft_stats``, ``select_label_kind``,
``build_high_potential_labels``) and keeps a Corpus G row only when
``(player_id, game_id)`` is on ``draftStats.highestBoostedValuePlayers``.
The label is that board's ``value`` (``label_kind=hv_tdv_leaderboard``).

Corpus G box ``value`` is not y. Draft counts, popularity sections, winning
drafts, and reconstructed boards (``nfl_draft_stats_reconstructed``, including
a boosts-present fallback) are excluded. A board with no game id is skipped
so a player id cannot retarget every other game.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from oracle_core.contest_max import hv_objective_flags
from oracle_core.high_tv import (
    HighPotentialLabelKind,
    build_high_potential_labels,
    select_label_kind,
)

from nfl_oracle.contests.hv_export import HV_SECTION, extract_matchup_links
from nfl_oracle.contests.parse import ContestParseError, load_contest
from nfl_oracle.contests.store import ContestStore
from nfl_oracle.recommendations.high_tv import (
    high_tv_board_from_draft_stats,
    nfl_season_for_day,
)
from nfl_oracle.recommendations.model import HistoricalPerformance

# Source string high_tv_board_from_draft_stats uses only for the HV section.
_HV_SECTION_SOURCE = "nfl_highestBoostedValuePlayers"

_VALUE_TOLERANCE = 1e-6


@dataclass(frozen=True)
class HvOverlayAudit:
    """What the train-time overlay did. Counts only; no payloads."""

    boards: int
    rows_overlaid: int
    rows_raw: int
    conflicts: int
    skipped_unscoped: int
    skipped_boards: int
    corpus_c_root: str
    export_root: str
    hv_corpus_root: str
    rows_excluded: int = 0
    training_target: str = "hv_tdv_leaderboards"
    label_section: str = "highestBoostedValuePlayers"
    operator_lock: str = "hv_tdv_only"
    ladder: str = "oracle_core.high_tv.select_label_kind"
    raw_box_used_as_target: bool = False
    fit_seasons: tuple[int, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "boards": self.boards,
            "rows_overlaid": self.rows_overlaid,
            "rows_raw": self.rows_raw,
            "rows_excluded": self.rows_excluded,
            "conflicts": self.conflicts,
            "skipped_unscoped": self.skipped_unscoped,
            "skipped_boards": self.skipped_boards,
            "corpus_c_root": self.corpus_c_root,
            "export_root": self.export_root,
            "hv_corpus_root": self.hv_corpus_root,
            "training_target": self.training_target,
            "label_section": self.label_section,
            "operator_lock": self.operator_lock,
            "ladder": self.ladder,
            "raw_box_used_as_target": self.raw_box_used_as_target,
            "fit_seasons": list(self.fit_seasons),
            "draft_count_is_label": False,
            "contest_entry": False,
            **hv_objective_flags(),
        }


def _finite(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
    elif isinstance(value, str):
        try:
            number = float(value)
        except ValueError:
            return None
    else:
        return None
    if not math.isfinite(number):
        return None
    return number


def _game_id(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value if value > 0 else None
    if isinstance(value, str) and value.isdigit():
        parsed = int(value)
        return parsed if parsed > 0 else None
    return None


def _is_hv_section_board(section: str, source: str) -> bool:
    """True only for boards taken from the HV section, not reconstructions."""

    if section != HV_SECTION:
        return False
    lowered = source.lower()
    if "reconstruct" in lowered or "draft_count" in lowered or "mostdrafted" in lowered:
        return False
    if not source:
        return True
    return "highestboostedvalueplayers" in lowered


class _LabelIndex:
    """(player_id, game_id) -> HV value. Disagreeing boards drop the key."""

    def __init__(self) -> None:
        self.values: dict[tuple[int, int], float] = {}
        self._conflicts: set[tuple[int, int]] = set()
        self.boards = 0
        self.skipped_unscoped = 0
        self.skipped_boards = 0

    def add_board(
        self,
        *,
        game_ids: Iterable[int],
        players: Iterable[tuple[int, float]],
    ) -> None:
        scoped = {int(game_id) for game_id in game_ids if int(game_id) > 0}
        usable = [(int(player_id), value) for player_id, value in players if value is not None]
        if not usable:
            self.skipped_boards += 1
            return
        if not scoped:
            self.skipped_unscoped += 1
            self.skipped_boards += 1
            return
        self.boards += 1
        for game_id in scoped:
            for player_id, value in usable:
                key = (player_id, game_id)
                if key in self._conflicts:
                    continue
                prior = self.values.get(key)
                if prior is None:
                    self.values[key] = value
                elif abs(prior - value) > _VALUE_TOLERANCE:
                    self.values.pop(key, None)
                    self._conflicts.add(key)

    @property
    def conflicts(self) -> int:
        return len(self._conflicts)


def _fit_seasons(rows: Sequence[HistoricalPerformance]) -> tuple[int, ...]:
    return tuple(sorted({nfl_season_for_day(row.kickoff_at.date()) for row in rows}))


def _ladder_scores(values: Mapping[int, float], game_ids: Iterable[int]) -> list[tuple[int, float]]:
    """#185 rung 1 only: HV/TDV scores for each scoped game."""

    kind = select_label_kind(has_total_value_board=True)
    if kind is not HighPotentialLabelKind.HIGH_TOTAL_VALUE_BOARD:
        return []
    accepted: dict[int, float] = {}
    for game_id in game_ids:
        slate_id = int(game_id)
        if slate_id <= 0 or not values:
            continue
        labels = build_high_potential_labels(
            dict(values),
            slate_id=slate_id,
            has_total_value_board=True,
        )
        for label in labels:
            if label.kind != HighPotentialLabelKind.HIGH_TOTAL_VALUE_BOARD:
                continue
            accepted[int(label.player_id)] = float(label.score)
    return list(accepted.items())


def _players_from_hv_rows(rows: Sequence[Mapping[str, Any]]) -> list[tuple[int, float]]:
    out: list[tuple[int, float]] = []
    for row in rows:
        player_id = _game_id(row.get("player_id") or row.get("playerId"))
        value = _finite(row.get("value"))
        if player_id is None or value is None:
            continue
        out.append((player_id, value))
    return out


def _index_corpus_c(index: _LabelIndex, root: Path) -> None:
    if not root.is_dir():
        return
    store = ContestStore(root)
    for contest_id in store.collected_ids():
        try:
            parsed = load_contest(store, contest_id)
        except (ContestParseError, ValueError, KeyError, TypeError, OSError):
            index.skipped_boards += 1
            continue
        if parsed is None:
            index.skipped_boards += 1
            continue
        board = high_tv_board_from_draft_stats(parsed)
        kind = select_label_kind(has_total_value_board=True)
        if (
            board is None
            or board.source != _HV_SECTION_SOURCE
            or board.label_kind != kind
            or kind is not HighPotentialLabelKind.HIGH_TOTAL_VALUE_BOARD
        ):
            index.skipped_boards += 1
            continue
        values = {
            int(row.player_id): float(row.value)
            for row in parsed.draft_stats
            if row.section == HV_SECTION and row.value is not None
        }
        draftinfo = store.read_route(contest_id, "draftinfo")
        stats = store.read_route(contest_id, "stats")
        links = extract_matchup_links(parsed=parsed, draftinfo=draftinfo, stats=stats)
        game_ids = links.get("game_ids") or ()
        players = _ladder_scores(values, game_ids)
        if not players:
            index.skipped_boards += 1
            if not any(int(game_id) > 0 for game_id in game_ids):
                index.skipped_unscoped += 1
            continue
        index.add_board(game_ids=game_ids, players=players)


def _matchup_game_ids(board_path: Path, payload: Mapping[str, Any]) -> set[int]:
    ids: set[int] = set()
    for key in ("game_ids",):
        raw = payload.get(key)
        if isinstance(raw, list):
            for item in raw:
                game_id = _game_id(item)
                if game_id is not None:
                    ids.add(game_id)
    for key in ("contest_game_id", "game_id"):
        game_id = _game_id(payload.get(key))
        if game_id is not None:
            ids.add(game_id)
    slate_key = payload.get("slate_or_game_id") or payload.get("slate_key")
    game_id = _game_id(slate_key)
    if game_id is not None:
        ids.add(game_id)
    sibling = board_path.parent / "matchups.json"
    if sibling.is_file():
        try:
            matchups = json.loads(sibling.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            matchups = None
        if isinstance(matchups, dict):
            for item in matchups.get("game_ids") or []:
                game_id = _game_id(item)
                if game_id is not None:
                    ids.add(game_id)
            contest_game = _game_id(matchups.get("contest_game_id"))
            if contest_game is not None:
                ids.add(contest_game)
    return ids


def _index_board_file(index: _LabelIndex, path: Path) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        index.skipped_boards += 1
        return
    if not isinstance(payload, dict):
        index.skipped_boards += 1
        return
    section = str(payload.get("section") or "")
    source = str(payload.get("source") or "")
    if not _is_hv_section_board(section, source):
        index.skipped_boards += 1
        return
    players = payload.get("players")
    if not isinstance(players, list):
        index.skipped_boards += 1
        return
    game_ids = _matchup_game_ids(path, payload)
    scores = _ladder_scores(
        dict(_players_from_hv_rows([row for row in players if isinstance(row, dict)])),
        game_ids,
    )
    if not scores:
        index.skipped_boards += 1
        if not game_ids:
            index.skipped_unscoped += 1
        return
    index.add_board(game_ids=game_ids, players=scores)


def _index_tree(index: _LabelIndex, root: Path, filename: str) -> None:
    if not root.is_dir():
        return
    for path in sorted(root.rglob(filename)):
        if path.is_file():
            _index_board_file(index, path)


def resolve_label_roots(project: Path) -> tuple[Path, Path, Path]:
    """Corpus C, HV export, and durable HV corpus roots for this project."""

    corpus_env = os.environ.get("NFL_CORPUS_C_ROOT", "").strip()
    export_env = os.environ.get("NFL_HV_EXPORT_ROOT", "").strip()
    hv_env = os.environ.get("NFL_HV_CORPUS_ROOT", "").strip()
    corpus = Path(corpus_env).expanduser() if corpus_env else project / "data" / "raw" / "corpus_c"
    export = (
        Path(export_env).expanduser() if export_env else project / "data" / "export" / "hv_boards"
    )
    hv_corpus = (
        Path(hv_env).expanduser() if hv_env else project / "data" / "raw" / "realsports_corpus"
    )
    return corpus, export, hv_corpus


def apply_hv_tdv_labels(
    project: Path,
    rows: Sequence[HistoricalPerformance],
    *,
    corpus_c_root: Path | None = None,
    export_root: Path | None = None,
    hv_corpus_root: Path | None = None,
) -> tuple[list[HistoricalPerformance], HvOverlayAudit]:
    """Return only rows on an HV/TDV leaderboard.

    The label is the #185 rung-1 score from ``highestBoostedValuePlayers``.
    Rows with no board, a conflicting board, a popularity section, or a
    reconstructed board are excluded. Corpus G box value is not y.
    """

    default_c, default_export, default_hv = resolve_label_roots(project)
    corpus_c = corpus_c_root or default_c
    export = export_root or default_export
    hv_corpus = hv_corpus_root or default_hv
    index = _LabelIndex()
    _index_corpus_c(index, corpus_c)
    _index_tree(index, export, "total_value_leaderboard.json")
    _index_tree(index, hv_corpus, "hv_board.json")

    kept: list[HistoricalPerformance] = []
    excluded = 0
    for row in rows:
        value = index.values.get((row.player_id, row.game_id))
        if value is None:
            excluded += 1
            continue
        update: dict[str, Any] = {"label_kind": "hv_tdv_leaderboard"}
        if abs(row.value - value) > _VALUE_TOLERANCE:
            update["value"] = value
        kept.append(row.model_copy(update=update))
    audit = HvOverlayAudit(
        boards=index.boards,
        rows_overlaid=len(kept),
        rows_raw=0,
        rows_excluded=excluded,
        conflicts=index.conflicts,
        skipped_unscoped=index.skipped_unscoped,
        skipped_boards=index.skipped_boards,
        corpus_c_root=str(corpus_c),
        export_root=str(export),
        hv_corpus_root=str(hv_corpus),
        fit_seasons=_fit_seasons(kept),
        raw_box_used_as_target=False,
    )
    return kept, audit
