"""Load Highest-value boards into NFL train and replay sample weights (#185, #620).

``fit_model`` predicts raw box ``value`` so live scoring can still apply
``value * (slot + boost)`` once. The #185 ladder changes *which rows are
emphasized*:

1. When a finalized contest has ``highestBoostedValuePlayers`` and a game id
   that joins to Corpus G, the top-k players on that board get the high
   sample weight. Other players in that game stay at the base weight. Raw
   box-score leaders who missed the board are not up-weighted.
2. Games with no linked board keep the per-game top-k box-value weights.

Reconstructed rankings and winning drafts are not rung 1. A board that does
not name its games is counted and skipped; it cannot be joined without
inventing a game id.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nfl_oracle.contests.hv_export import (
    HV_SECTION,
    TOTAL_VALUE_FILENAME,
    extract_matchup_links,
    resolve_corpus_c_root,
    resolve_export_root,
)
from nfl_oracle.contests.parse import ContestParseError, iter_contests
from nfl_oracle.contests.store import ContestStore

HIGH_WEIGHT = 4.0
TOP_K = 5


@dataclass(frozen=True)
class HvTrainOverlay:
    """Sample-weight overlay for one train or replay fit."""

    weights: dict[tuple[int, int], float]
    covered_game_ids: tuple[int, ...]
    contest_ids: tuple[int, ...]
    skipped_no_game_link: int = 0
    skipped_not_hv: int = 0
    export_files: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": "hv_board_top5_weight_else_box_value_top5",
            "label_ladder": [
                "high_total_value_board",
                "raw_highest_score_pre_boost",
            ],
            "contests": len(self.contest_ids),
            "covered_games": len(self.covered_game_ids),
            "weighted_player_games": len(self.weights),
            "skipped_no_game_link": self.skipped_no_game_link,
            "skipped_not_hv": self.skipped_not_hv,
            "export_files": self.export_files,
            "contest_entry": False,
        }


def overlay_for_replay(
    history_root: Path,
    *,
    corpus_c_root: Path | None = None,
    export_root: Path | None = None,
) -> HvTrainOverlay:
    """Overlay for a walk-forward replay next to a Corpus G history root.

    An explicit root is used as given. Otherwise a sibling ``corpus_c`` /
    ``data/export/hv_boards`` directory is used when it exists. A missing
    sibling falls through to ``load_hv_train_overlay`` defaults (env, then
    the package data dir).
    """

    history = Path(history_root).expanduser().resolve()
    corpus = corpus_c_root
    if corpus is None:
        sibling = history.parent / "corpus_c"
        corpus = sibling if sibling.is_dir() else None
    export = export_root
    if export is None:
        sibling_export = history.parent.parent / "export" / "hv_boards"
        export = sibling_export if sibling_export.is_dir() else None
    return load_hv_train_overlay(corpus_c_root=corpus, export_root=export)


def load_hv_train_overlay(
    project: Path | None = None,
    *,
    corpus_c_root: Path | None = None,
    export_root: Path | None = None,
    top_k: int = TOP_K,
    high_weight: float = HIGH_WEIGHT,
) -> HvTrainOverlay:
    """Read Corpus C first, then export files for contests not already loaded.

    Explicit roots win over the process environment so tests stay hermetic.
    Missing directories yield an empty overlay (rung 2 for every game).
    """

    corpus_root = (
        Path(corpus_c_root) if corpus_c_root is not None else resolve_corpus_c_root(project)
    )
    export = Path(export_root) if export_root is not None else resolve_export_root(project=project)
    weights: dict[tuple[int, int], float] = {}
    covered: set[int] = set()
    contests: set[int] = set()
    skipped_link = 0
    skipped_hv = 0
    export_files = 0

    if corpus_root.is_dir():
        store = ContestStore(corpus_root)
        for parsed in iter_contests(store, finalized_only=True):
            contest_id = int(parsed.contest.contest_id)
            hv_rows = [
                row
                for row in parsed.draft_stats
                if row.section == HV_SECTION and row.value is not None
            ]
            if not hv_rows:
                skipped_hv += 1
                continue
            try:
                links = extract_matchup_links(
                    parsed=parsed,
                    draftinfo=store.read_route(contest_id, "draftinfo"),
                    stats=store.read_route(contest_id, "stats"),
                )
            except (ContestParseError, OSError, ValueError, KeyError, TypeError):
                skipped_link += 1
                continue
            game_ids = [int(game_id) for game_id in links.get("game_ids") or []]
            if not game_ids:
                skipped_link += 1
                continue
            _merge_weights(
                weights,
                covered,
                players=[{"player_id": row.player_id, "value": row.value} for row in hv_rows],
                game_ids=game_ids,
                top_k=top_k,
                high_weight=high_weight,
            )
            contests.add(contest_id)

    if export.is_dir():
        for path in sorted(export.rglob(TOTAL_VALUE_FILENAME)):
            export_files += 1
            added = _overlay_from_export_file(
                path,
                weights=weights,
                covered=covered,
                seen_contests=contests,
                top_k=top_k,
                high_weight=high_weight,
            )
            if added == "not_hv":
                skipped_hv += 1
            elif added == "no_link":
                skipped_link += 1

    return HvTrainOverlay(
        weights=weights,
        covered_game_ids=tuple(sorted(covered)),
        contest_ids=tuple(sorted(contests)),
        skipped_no_game_link=skipped_link,
        skipped_not_hv=skipped_hv,
        export_files=export_files,
    )


def _overlay_from_export_file(
    path: Path,
    *,
    weights: dict[tuple[int, int], float],
    covered: set[int],
    seen_contests: set[int],
    top_k: int,
    high_weight: float,
) -> str | None:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return "not_hv"
    if not isinstance(doc, dict):
        return "not_hv"
    source = str(doc.get("source") or "")
    section = str(doc.get("section") or "")
    if HV_SECTION not in source and section != HV_SECTION:
        return "not_hv"
    # Reconstructed boards reuse the HV section name. Only the explicit
    # Highest-value section source is rung 1.
    if HV_SECTION not in source:
        return "not_hv"
    try:
        contest_id = int(doc["contest_id"])
    except (KeyError, TypeError, ValueError):
        return "not_hv"
    if contest_id in seen_contests:
        return None
    matchups_path = path.parent / "matchups.json"
    game_ids = _game_ids_from_matchups(matchups_path)
    players = doc.get("players")
    if not isinstance(players, list) or not game_ids:
        return "no_link"
    usable = []
    for row in players:
        if not isinstance(row, Mapping):
            continue
        try:
            usable.append({"player_id": int(row["player_id"]), "value": float(row["value"])})
        except (KeyError, TypeError, ValueError):
            continue
    if not usable:
        return "not_hv"
    _merge_weights(
        weights,
        covered,
        players=usable,
        game_ids=game_ids,
        top_k=top_k,
        high_weight=high_weight,
    )
    seen_contests.add(contest_id)
    return None


def _game_ids_from_matchups(path: Path) -> list[int]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    raw = payload.get("game_ids") or []
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for item in raw:
        try:
            out.append(int(item))
        except (TypeError, ValueError):
            continue
    return out


def _merge_weights(
    weights: dict[tuple[int, int], float],
    covered: set[int],
    *,
    players: Iterable[Mapping[str, Any]],
    game_ids: Iterable[int],
    top_k: int,
    high_weight: float,
) -> None:
    ranked = sorted(
        (
            (int(row["player_id"]), float(row["value"]))
            for row in players
            if row.get("value") is not None
        ),
        key=lambda item: (-item[1], item[0]),
    )
    games = [int(game_id) for game_id in game_ids]
    if not ranked or not games:
        return
    covered.update(games)
    for player_id, _value in ranked[: max(1, top_k)]:
        for game_id in games:
            key = (player_id, game_id)
            weights[key] = max(weights.get(key, 0.0), float(high_weight))
