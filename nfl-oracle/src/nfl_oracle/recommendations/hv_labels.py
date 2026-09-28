"""Overlay Highest-value / Total Value board labels onto Corpus G history.

Issue #597. ``nfl-pipeline train`` fits ridge on these labels:

* rung 1: ``draftStats.highestBoostedValuePlayers`` ``value`` (and exported
  HV/TDV boards that came from that section);
* rung 2: the raw postgame box ``playerBoxScores[].value`` when no board
  scopes that player-game.

Draft counts, popularity sections, and reconstructed boards are never the
label. A board with no game id is skipped so a player id cannot retarget
every other game in the archive.
"""

from __future__ import annotations

import json
import math
import os
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nfl_oracle.contests.hv_export import HV_SECTION, extract_matchup_links
from nfl_oracle.contests.parse import ContestParseError, load_contest
from nfl_oracle.contests.store import ContestStore
from nfl_oracle.recommendations.model import HistoricalPerformance

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
    training_target: str = "hv_tdv_board_value_else_raw_box_not_draft_count"

    def to_dict(self) -> dict[str, Any]:
        return {
            "boards": self.boards,
            "rows_overlaid": self.rows_overlaid,
            "rows_raw": self.rows_raw,
            "conflicts": self.conflicts,
            "skipped_unscoped": self.skipped_unscoped,
            "skipped_boards": self.skipped_boards,
            "corpus_c_root": self.corpus_c_root,
            "export_root": self.export_root,
            "hv_corpus_root": self.hv_corpus_root,
            "training_target": self.training_target,
            "draft_count_is_label": False,
            "contest_entry": False,
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
            continue
        hv_rows = [
            {
                "player_id": row.player_id,
                "value": row.value,
            }
            for row in parsed.draft_stats
            if row.section == HV_SECTION and row.value is not None
        ]
        if not hv_rows:
            continue
        draftinfo = store.read_route(contest_id, "draftinfo")
        stats = store.read_route(contest_id, "stats")
        links = extract_matchup_links(parsed=parsed, draftinfo=draftinfo, stats=stats)
        index.add_board(
            game_ids=links.get("game_ids") or (),
            players=_players_from_hv_rows(hv_rows),
        )


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
    index.add_board(
        game_ids=_matchup_game_ids(path, payload),
        players=_players_from_hv_rows([row for row in players if isinstance(row, dict)]),
    )


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
    """Replace box values with HV-section values where a board scopes the game.

    Rows with no board, a conflicting board, or only a popularity section keep
    their raw box value.
    """

    default_c, default_export, default_hv = resolve_label_roots(project)
    corpus_c = corpus_c_root or default_c
    export = export_root or default_export
    hv_corpus = hv_corpus_root or default_hv
    index = _LabelIndex()
    _index_corpus_c(index, corpus_c)
    _index_tree(index, export, "total_value_leaderboard.json")
    _index_tree(index, hv_corpus, "hv_board.json")

    overlaid = 0
    updated: list[HistoricalPerformance] = []
    for row in rows:
        value = index.values.get((row.player_id, row.game_id))
        if value is None:
            updated.append(row)
            continue
        overlaid += 1
        if abs(row.value - value) <= _VALUE_TOLERANCE:
            updated.append(row)
        else:
            updated.append(row.model_copy(update={"value": value}))
    audit = HvOverlayAudit(
        boards=index.boards,
        rows_overlaid=overlaid,
        rows_raw=len(updated) - overlaid,
        conflicts=index.conflicts,
        skipped_unscoped=index.skipped_unscoped,
        skipped_boards=index.skipped_boards,
        corpus_c_root=str(corpus_c),
        export_root=str(export),
        hv_corpus_root=str(hv_corpus),
    )
    return updated, audit
