"""Highest-value / Total Value boards as the NFL train label (#597).

Entrypoints this module serves:

- ``nfl-pipeline train`` (``recommendations.cli._model_bundle``) overlays these
  labels onto Corpus G rows before ``fit_model``.
- Corpus C contests (``data/raw/corpus_c``) and exported boards
  (``total_value_leaderboard.json``, ``hv_board.json``).
- Replay scoring lives in ``nfl_oracle.replay.hv_board_replay``. The older
  pool replay (``contest_pool_replay``) and ``sweep_picker_knobs`` stay the
  walk-forward production comparison; they are not the HV label source.

Two numbers, on purpose:

- Ridge ``y`` is realized production: the left-hand board number, or the
  Corpus G box score when no board joins. Training ``y`` on the Value column
  and then multiplying by ``(slot + boost)`` again would double-count.
- The Value column is ``realized * (slot_multiplier + card_boost)``, or the
  provider ``highestScore`` / transcribed ``displayed_value`` when that number
  is present. Sample weights and the replay HV rank use this column. Draft
  counts never enter either one.

``HV_T40_KNOBS`` is the env that makes the serving optimizer select that
Value column at T-40: ``max_value``, one team, one game, upside 0, field 0,
picker blend 0. Explicit env overrides still win.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from nfl_oracle.contests.parse import iter_contests
from nfl_oracle.contests.schema import OBSERVED_SLOT_MULTIPLIERS
from nfl_oracle.contests.store import ContestStore
from nfl_oracle.recommendations.model import HistoricalPerformance

HV_SECTION = "highestBoostedValuePlayers"
EASTERN = ZoneInfo("America/New_York")
BOARD_FILENAMES = ("total_value_leaderboard.json", "hv_board.json")

# Serving env that reproduces an HV lineup at T-40. Optimizer weights of 0
# keep selection on expected total value, so a popular high-value card
# (London, A'ja) stays and a popular lower-value card (Gibbs) does not.
# ``NFL_PICKER_BOOST_RANK_BLEND`` stays 0: the multiplier law is
# ``value * (slot + boost)``, not a swap of projected means into boost order.
# Live worker may still set that blend explicitly. This mapping does not
# mutate Railway.
HV_T40_KNOBS: dict[str, str] = {
    "NFL_OPTIMIZER_PROFILE": "max_value",
    "NFL_OPTIMIZER_MIN_DISTINCT_TEAMS": "1",
    "NFL_OPTIMIZER_MIN_DISTINCT_GAMES": "1",
    "NFL_OPTIMIZER_UPSIDE_WEIGHT": "0",
    "NFL_OPTIMIZER_FIELD_WEIGHT": "0",
    "NFL_PICKER_BOOST_RANK_BLEND": "0",
    "NFL_PICKER_POSITION_CALIBRATION": "0",
    "NFL_PICKER_PROFILE": "identity",
}


@dataclass(frozen=True)
class HvBoardPlayer:
    """One player on an HV/TDV board. ``drafts`` is recorded and never a label.

    ``realized_value`` is the left-hand number (ridge ``y``).
    ``displayed_value`` is the Value column when the provider or a transcript
    already states it. ``most_common_slot`` is the 1-indexed slot behind that
    column. Neither drafts nor the Value column replaces ``realized_value``.
    """

    player_id: int
    realized_value: float
    card_boost: float = 0.0
    drafts: int | None = None
    name: str | None = None
    most_common_slot: int | None = None
    displayed_value: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HvBoard:
    """One contest or slate Highest-value / Total Value board."""

    players: tuple[HvBoardPlayer, ...]
    source: str
    contest_id: int | None = None
    game_id: int | None = None
    slate_date: date | None = None
    path: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        if self.slate_date is not None:
            payload["slate_date"] = self.slate_date.isoformat()
        return payload


@dataclass
class HvLabelAudit:
    """How many training rows took a board label versus the raw box score."""

    boards_seen: int = 0
    hv_board_rows: int = 0
    hv_board_rows_relabeled: int = 0
    hv_board_rows_already_matched: int = 0
    raw_box_rows: int = 0
    label_collisions: int = 0
    contests_indexed: int = 0
    export_files_indexed: int = 0
    export_files_skipped_reconstructed: int = 0
    win_frequency_target_rows: int = 0
    value_column_rows: int = 0

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def player_value_column(
    player: HvBoardPlayer,
    slots: Sequence[float] = OBSERVED_SLOT_MULTIPLIERS,
) -> float:
    """Real Sports Value column for one board row.

    Prefer a stated Value (``displayed_value``, usually provider
    ``highestScore`` or a transcribed UI number). Otherwise
    ``realized * (slot_multiplier + card_boost)`` at ``most_common_slot``.
    A missing or out-of-range slot uses the best slot: at T-40 the lineup
    assigns slots, and the best slot is the one the optimizer can give.
    """

    if player.displayed_value is not None:
        return float(player.displayed_value)
    slot = player.most_common_slot
    if slot is not None and 1 <= int(slot) <= len(slots):
        multiplier = float(slots[int(slot) - 1])
    else:
        multiplier = float(slots[0])
    return float(player.realized_value) * (multiplier + float(player.card_boost))


@dataclass
class _Index:
    by_game: dict[tuple[int, int], HvBoardPlayer] = field(default_factory=dict)
    by_day: dict[tuple[int, date], HvBoardPlayer] = field(default_factory=dict)
    collisions: int = 0


def is_hv_board_document(payload: Mapping[str, Any]) -> bool:
    """True for a real HV/TDV board, false for reconstruction or chalk sections."""

    source = str(payload.get("source") or "")
    section = str(payload.get("section") or "")
    label = str(payload.get("label") or "")
    blob = f"{source} {section} {label}".casefold()
    if "reconstruct" in blob or "unreconstructable" in blob:
        return False
    if "mostdrafted" in blob or "winning_draft" in blob or "win_frequency" in blob:
        return False
    return (
        "highestboostedvalueplayers" in blob
        or section == HV_SECTION
        or label == "total_value_leaderboard"
    )


def _as_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if out != out or out in (float("inf"), float("-inf")):
        return None
    return out


def _as_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_date(value: Any) -> date | None:
    if not isinstance(value, str) or len(value) < 10:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _player_from_mapping(row: Mapping[str, Any]) -> HvBoardPlayer | None:
    player_id = _as_int(row.get("player_id") if "player_id" in row else row.get("playerId"))
    if player_id is None or player_id <= 0:
        return None
    realized = _as_float(row.get("value"))
    if realized is None:
        realized = _as_float(row.get("real_score"))
    if realized is None:
        return None
    boost = _as_float(row.get("card_boost"))
    if boost is None:
        boost = _as_float(row.get("multiplierBonus"))
    if boost is None:
        boost = 0.0
    drafts = _as_int(row.get("drafts") if "drafts" in row else row.get("count"))
    name = row.get("name") or row.get("display_name")
    displayed = _as_float(row.get("displayed_value"))
    if displayed is None:
        displayed = _as_float(row.get("highest_score"))
    if displayed is None:
        displayed = _as_float(row.get("highestScore"))
    slot = _as_int(row.get("most_common_slot"))
    if slot is None:
        slot = _as_int(row.get("mostCommonPosition"))
    return HvBoardPlayer(
        player_id=player_id,
        realized_value=realized,
        card_boost=float(boost),
        drafts=drafts,
        name=None if name is None else str(name),
        most_common_slot=slot,
        displayed_value=displayed,
    )


def board_from_document(payload: Mapping[str, Any], *, path: str = "") -> HvBoard | None:
    """Parse an exported HV/TDV JSON object. Returns None when it is not HV."""

    if not is_hv_board_document(payload):
        return None
    raw_players = payload.get("players")
    if not isinstance(raw_players, list):
        raw_players = payload.get("highestBoostedValuePlayers")
    if not isinstance(raw_players, list):
        return None
    players = []
    for row in raw_players:
        if isinstance(row, Mapping):
            parsed = _player_from_mapping(row)
            if parsed is not None:
                players.append(parsed)
    if not players:
        return None
    game_id = _as_int(payload.get("game_id") or payload.get("contest_game_id"))
    return HvBoard(
        players=tuple(players),
        source=str(payload.get("source") or payload.get("section") or HV_SECTION),
        contest_id=_as_int(payload.get("contest_id")),
        game_id=game_id,
        slate_date=_parse_date(payload.get("slate_date") or payload.get("slate_key")),
        path=path,
    )


def boards_from_contest_root(root: Path) -> tuple[list[HvBoard], int]:
    """Load HV-section boards from a Corpus C tree. Second value is contests seen."""

    if not root.is_dir():
        return [], 0
    store = ContestStore(root)
    boards: list[HvBoard] = []
    seen = 0
    for parsed in iter_contests(store):
        seen += 1
        hv_rows = [
            row for row in parsed.draft_stats if row.section == HV_SECTION and row.value is not None
        ]
        if not hv_rows:
            continue
        players = []
        for row in hv_rows:
            players.append(
                HvBoardPlayer(
                    player_id=int(row.player_id),
                    realized_value=float(row.value or 0.0),
                    card_boost=float(row.card_boost),
                    drafts=row.draft_count,
                    name=row.display_name,
                    most_common_slot=row.most_common_slot,
                    displayed_value=None if row.highest_score is None else float(row.highest_score),
                )
            )
        record = parsed.contest
        boards.append(
            HvBoard(
                players=tuple(players),
                source=f"corpus_c.{HV_SECTION}",
                contest_id=int(record.contest_id),
                game_id=None if record.game_id is None else int(record.game_id),
                slate_date=record.day,
                path=str(store.contest_dir(record.contest_id)),
            )
        )
    return boards, seen


def boards_from_export_root(
    root: Path, *, skip_contest_ids: set[int]
) -> tuple[list[HvBoard], int, int]:
    """Load exported HV JSON. Returns boards, files used, files skipped as reconstructed."""

    if not root.is_dir():
        return [], 0, 0
    boards: list[HvBoard] = []
    used = 0
    skipped = 0
    paths: list[Path] = []
    for name in BOARD_FILENAMES:
        paths.extend(sorted(root.rglob(name)))
    seen_paths: set[Path] = set()
    for path in paths:
        if path in seen_paths:
            continue
        seen_paths.add(path)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            skipped += 1
            continue
        if not isinstance(payload, dict):
            skipped += 1
            continue
        contest_id = _as_int(payload.get("contest_id"))
        if contest_id is not None and contest_id in skip_contest_ids:
            continue
        if not is_hv_board_document(payload):
            skipped += 1
            continue
        board = board_from_document(payload, path=str(path))
        if board is None:
            skipped += 1
            continue
        boards.append(board)
        used += 1
    return boards, used, skipped


def iter_training_boards(
    *,
    contest_root: Path | None = None,
    export_root: Path | None = None,
    board_root: Path | None = None,
) -> tuple[tuple[HvBoard, ...], HvLabelAudit]:
    """Corpus C HV sections first, then export files for contests not already indexed."""

    audit = HvLabelAudit()
    contest_boards: list[HvBoard] = []
    if contest_root is not None:
        contest_boards, seen = boards_from_contest_root(contest_root)
        audit.contests_indexed = seen
    skip = {board.contest_id for board in contest_boards if board.contest_id is not None}
    export_boards: list[HvBoard] = []
    for root in (export_root, board_root):
        if root is None:
            continue
        found, used, skipped = boards_from_export_root(root, skip_contest_ids=skip)
        export_boards.extend(found)
        audit.export_files_indexed += used
        audit.export_files_skipped_reconstructed += skipped
        for board in found:
            if board.contest_id is not None:
                skip.add(board.contest_id)
    boards = tuple(contest_boards + export_boards)
    audit.boards_seen = len(boards)
    return boards, audit


def _prefer(
    current: HvBoardPlayer, incoming: HvBoardPlayer, collisions: list[int]
) -> HvBoardPlayer:
    if current.player_id != incoming.player_id:
        raise ValueError("hv_label_player_mismatch")
    if abs(current.realized_value - incoming.realized_value) > 1e-9:
        collisions[0] += 1
    if incoming.realized_value > current.realized_value:
        return incoming
    return current


def _index_boards(boards: Sequence[HvBoard]) -> _Index:
    index = _Index()
    collision_box = [0]
    for board in boards:
        for player in board.players:
            if board.game_id is not None:
                key = (player.player_id, int(board.game_id))
                prior = index.by_game.get(key)
                index.by_game[key] = (
                    player if prior is None else _prefer(prior, player, collision_box)
                )
            elif board.slate_date is not None:
                key_day = (player.player_id, board.slate_date)
                prior_day = index.by_day.get(key_day)
                index.by_day[key_day] = (
                    player if prior_day is None else _prefer(prior_day, player, collision_box)
                )
    index.collisions = collision_box[0]
    return index


def _lookup(row: HistoricalPerformance, index: _Index) -> HvBoardPlayer | None:
    exact = index.by_game.get((row.player_id, row.game_id))
    if exact is not None:
        return exact
    day = row.kickoff_at.astimezone(EASTERN).date()
    return index.by_day.get((row.player_id, day))


def apply_hv_board_labels(
    rows: Sequence[HistoricalPerformance],
    boards: Sequence[HvBoard],
    *,
    audit: HvLabelAudit | None = None,
) -> tuple[list[HistoricalPerformance], HvLabelAudit]:
    """Replace box scores with HV/TDV realized values where a board joins.

    A join is ``(player_id, game_id)`` when the board names a game, otherwise
    ``(player_id, America/New_York slate date)`` for boards that have a date
    and no game id. Rows with no join keep their Corpus G value. Joined rows
    also receive ``value_column`` (the Value column) for sample weights.
    Ridge still trains on ``value``.
    """

    report = audit or HvLabelAudit(boards_seen=len(boards))
    report.boards_seen = len(boards)
    index = _index_boards(boards)
    report.label_collisions = index.collisions
    updated: list[HistoricalPerformance] = []
    for row in rows:
        label = _lookup(row, index)
        if label is None:
            report.raw_box_rows += 1
            updated.append(row)
            continue
        report.hv_board_rows += 1
        report.value_column_rows += 1
        column = player_value_column(label)
        # Ridge y stays realized production. value_column is excluded from the
        # training fingerprint and is only the sample-weight rank key.
        update: dict[str, Any] = {"value_column": column}
        if abs(float(row.value) - label.realized_value) <= 1e-6:
            report.hv_board_rows_already_matched += 1
        else:
            report.hv_board_rows_relabeled += 1
            update["value"] = label.realized_value
        updated.append(row.model_copy(update=update))
    report.win_frequency_target_rows = 0
    return updated, report


def discover_hv_label_roots(project: Path) -> tuple[Path, Path, Path | None]:
    """Contest root, export root, and optional extra board root from the environment."""

    contest = Path(os.environ.get("NFL_CORPUS_C_ROOT", str(project / "data" / "raw" / "corpus_c")))
    export = Path(
        os.environ.get("NFL_HV_EXPORT_ROOT", str(project / "data" / "export" / "hv_boards"))
    )
    extra = os.environ.get("NFL_HV_BOARD_ROOT", "").strip()
    return contest, export, Path(extra) if extra else None


def load_and_apply_hv_labels(
    rows: Sequence[HistoricalPerformance],
    project: Path,
) -> tuple[list[HistoricalPerformance], HvLabelAudit]:
    """Discover on-disk boards and overlay them. Missing roots leave raw labels."""

    contest_root, export_root, board_root = discover_hv_label_roots(project)
    try:
        boards, audit = iter_training_boards(
            contest_root=contest_root,
            export_root=export_root,
            board_root=board_root,
        )
    except (OSError, ValueError):
        return list(rows), HvLabelAudit()
    return apply_hv_board_labels(rows, boards, audit=audit)
