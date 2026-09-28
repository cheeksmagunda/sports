"""Five-card contest maximization over a visible HV/TDV board.

The scoring law is provider-neutral and matches the verified non-negative
branch used by the sport apps:

    item_score = value * (slot_multiplier + card_boost)
    lineup_score = sum(item_score)

``value`` is the realized base (pre-boost Real score). ``card_boost`` is the
pre-lock card boost. Slot order for a fixed five is the rearrangement that
pairs descending base value with descending slot multipliers.

Three fives, never confused:

- **HV display rank.** Top five by ``value * (top_slot + card_boost)``, the
  top-slot contest value the Highest-value board is ranking. This is not
  draft count.
- **Raw-value rank.** Top five by base value alone. Kept so a caller can see
  the capture left on the table when boost is ignored.
- **Draft-count chalk.** Top five by ``draft_count``. The count chooses who
  is in the five. It is never a score and never a sample weight.

The hindsight ceiling is the exact five under the same law (dynamic program
over players sorted by descending base). It is an upper bound on the pool
that was supplied, not a claim about players the archive did not reveal.

Draft counts must not be passed into :func:`contest_display_rank_weights`.
"""

from __future__ import annotations

import csv
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SLOT_MULTIPLIERS: tuple[float, ...] = (2.0, 1.8, 1.6, 1.4, 1.2)
TOP_SLOT_MULTIPLIER: float = DEFAULT_SLOT_MULTIPLIERS[0]
LINEUP_SIZE: int = 5
# Train-audit encoding. The prose home is OVERVIEW.md (Win stack, #653).
HV_CAPTURE_OBJECTIVE = "5-player lineup maximizing capture of highestBoostedValuePlayers"
SHAPE_CONDITION_OBJECTIVE = (
    "Learn the shapes of every HV/TDV board appearance over history, "
    "learn the slate conditions that produced each shape, and at T-40 "
    "match shape and condition with the sport-owned model to commit the "
    "5-player lineup that maximizes capture of that slate's Highest value "
    "/ Total Value board, with Ollama on top as LLM-internal runs-on-shape."
)


def hv_objective_flags() -> dict[str, Any]:
    """Fields a fit writes for the product goal and the shape-and-condition campaign.

    Winning drafts are a reference bar. Cash and median construction are
    not the objective. Models stay in the sport app.
    """

    return {
        "objective": HV_CAPTURE_OBJECTIVE,
        "shape_condition_objective": SHAPE_CONDITION_OBJECTIVE,
        "lineup_size": LINEUP_SIZE,
        "winning_drafts_are_reference_bar": True,
        "winning_drafts_are_label": False,
        "cash_is_objective": False,
        "median_is_objective": False,
        "llm_internal": "runs-on-shape",
        "ollama_layer": "on_top_of_existing_schemas",
        "ollama_mode": "learn_and_tilt",
        "replaces_ridge": False,
        "replaces_valuelaw": False,
        "replaces_sport_model": False,
        "commit_path": "sport_owned_model_t40",
    }


_DEFENDER_CODES = frozenset(
    {
        "LB",
        "ILB",
        "OLB",
        "MLB",
        "DB",
        "CB",
        "S",
        "FS",
        "SS",
        "NB",
        "DL",
        "DE",
        "DT",
        "NT",
        "EDGE",
    }
)
_KICKER_CODES = frozenset({"K", "P", "PK"})
_SKILL_CODES = frozenset({"QB", "RB", "FB", "WR", "TE"})


@dataclass(frozen=True)
class ContestPlayer:
    """One visible-board row. ``draft_count`` selects chalk only."""

    player_id: int
    value: float
    card_boost: float = 0.0
    draft_count: float = 0.0
    position: str = ""
    team: str = ""
    game_id: str = ""
    on_hv_board: bool = True

    def display_value(self, top_slot: float = TOP_SLOT_MULTIPLIER) -> float:
        return display_contest_value(self.value, self.card_boost, top_slot=top_slot)


def display_contest_value(
    value: float,
    card_boost: float = 0.0,
    *,
    top_slot: float = TOP_SLOT_MULTIPLIER,
) -> float:
    """Top-slot contest value. Boost 0 keeps the same order as raw value."""

    return float(value) * (float(top_slot) + float(card_boost))


def position_family(position: str) -> str:
    """Coarse family for mix slices. Empty stays unknown."""

    code = position.strip().upper()
    if not code:
        return "unknown"
    if code in _KICKER_CODES:
        return "K"
    if code in _DEFENDER_CODES:
        return "DEF"
    if code in _SKILL_CODES:
        return code
    return "OTHER"


def slate_regime(players: Sequence[ContestPlayer]) -> str:
    """``one_game`` or ``multi_game`` from game ids, else visible team count.

    Team count is a proxy for boards that do not carry game ids: two or fewer
    teams read as one game. A multi-game slate whose visible HV rows happen
    to come from two teams is labeled ``one_game`` by this proxy. Callers
    that know the slate's game list should set ``game_id`` on each row.
    """

    games = {player.game_id for player in players if player.game_id}
    if len(games) == 1:
        return "one_game"
    if len(games) > 1:
        return "multi_game"
    teams = {player.team for player in players if player.team}
    if 1 <= len(teams) <= 2:
        return "one_game"
    if len(teams) >= 3:
        return "multi_game"
    return "unknown"


def score_optimal(
    players: Sequence[ContestPlayer],
    *,
    slot_multipliers: Sequence[float] = DEFAULT_SLOT_MULTIPLIERS,
) -> float:
    """Score these cards under the best slot order. Length must match slots."""

    slots = tuple(float(slot) for slot in slot_multipliers)
    if len(players) != len(slots):
        raise ValueError("lineup_slot_length_mismatch")
    ordered = sorted(players, key=lambda player: (-player.value, player.player_id))
    descending = tuple(sorted(slots, reverse=True))
    return sum(
        player.value * (slot + player.card_boost)
        for player, slot in zip(ordered, descending, strict=True)
    )


def hindsight_lineup(
    players: Sequence[ContestPlayer],
    *,
    slot_multipliers: Sequence[float] = DEFAULT_SLOT_MULTIPLIERS,
) -> tuple[float, tuple[int, ...]] | None:
    """Exact ceiling. Players are sorted by descending base, then filled."""

    slots = tuple(float(slot) for slot in slot_multipliers)
    k = len(slots)
    ranked = sorted(players, key=lambda player: (-player.value, player.player_id))
    if len(ranked) < k:
        return None
    neg = float("-inf")
    best = [0.0] + [neg] * k
    take = [[False] * (k + 1) for _ in range(len(ranked))]
    for index, player in enumerate(ranked):
        own_boost = player.value * player.card_boost
        for filled in range(min(index, k - 1), -1, -1):
            if best[filled] == neg:
                continue
            candidate = best[filled] + own_boost + player.value * slots[filled]
            if candidate > best[filled + 1]:
                best[filled + 1] = candidate
                take[index][filled + 1] = True
    if best[k] == neg:
        return None
    chosen: list[int] = []
    filled = k
    for index in range(len(ranked) - 1, -1, -1):
        if filled > 0 and take[index][filled]:
            chosen.append(ranked[index].player_id)
            filled -= 1
    chosen.reverse()
    return best[k], tuple(chosen)


def _top_ids(
    players: Sequence[ContestPlayer],
    key,
    *,
    n: int,
) -> tuple[int, ...]:
    ordered = sorted(players, key=lambda player: (-key(player), player.player_id))
    return tuple(player.player_id for player in ordered[:n])


def _score_ids(
    ids: Sequence[int],
    by_id: Mapping[int, ContestPlayer],
    *,
    slot_multipliers: Sequence[float],
) -> float | None:
    if len(ids) < len(slot_multipliers):
        return None
    chosen = [by_id[pid] for pid in ids[: len(slot_multipliers)] if pid in by_id]
    if len(chosen) < len(slot_multipliers):
        return None
    return score_optimal(chosen, slot_multipliers=slot_multipliers)


def position_mix_label(ids: Sequence[int], by_id: Mapping[int, ContestPlayer]) -> str:
    """Stable mix label for the hindsight five. All-unknown stays one bucket."""

    counts: Counter[str] = Counter()
    unknown = 0
    for pid in ids:
        family = position_family(by_id[pid].position)
        if family == "unknown":
            unknown += 1
        else:
            counts[family] += 1
    if unknown == len(ids):
        return "position_unknown"
    parts = [f"{name}:{counts[name]}" for name in sorted(counts)]
    if unknown:
        parts.append(f"unknown:{unknown}")
    return "+".join(parts) if parts else "position_unknown"


def compare_board(
    players: Sequence[ContestPlayer],
    *,
    sport: str,
    slate_id: str,
    slate_date: str = "",
    slot_multipliers: Sequence[float] = DEFAULT_SLOT_MULTIPLIERS,
) -> dict[str, Any] | None:
    """Score one board. Returns None when the HV section has fewer than five."""

    slots = tuple(slot_multipliers)
    k = len(slots)
    by_id = {player.player_id: player for player in players}
    hv_rows = [player for player in players if player.on_hv_board]
    if len({player.player_id for player in hv_rows}) < k:
        return None
    ceiling = hindsight_lineup(list(by_id.values()), slot_multipliers=slots)
    if ceiling is None:
        return None
    ceiling_score, ceiling_ids = ceiling
    display_ids = _top_ids(hv_rows, lambda player: player.display_value(slots[0]), n=k)
    raw_ids = _top_ids(hv_rows, lambda player: player.value, n=k)
    chalk_ids = _top_ids(list(by_id.values()), lambda player: player.draft_count, n=k)
    scores = {
        "hv_display": _score_ids(display_ids, by_id, slot_multipliers=slots),
        "hv_raw": _score_ids(raw_ids, by_id, slot_multipliers=slots),
        "chalk": _score_ids(chalk_ids, by_id, slot_multipliers=slots),
    }
    hv_display_score = scores["hv_display"]
    hv_raw_score = scores["hv_raw"]
    chalk_score = scores["chalk"]
    if (
        hv_display_score is None
        or hv_raw_score is None
        or chalk_score is None
        or ceiling_score <= 0
    ):
        return None

    def _share(score: float) -> float:
        return round(score / ceiling_score, 6)

    def _overlap(ids: Sequence[int]) -> float:
        return round(len(set(ids) & set(ceiling_ids)) / k, 6)

    regime = slate_regime(list(by_id.values()))
    return {
        "sport": sport,
        "slate_id": slate_id,
        "slate_date": slate_date,
        "regime": regime,
        "regime_method": "game_id" if any(player.game_id for player in players) else "team_count",
        "pool_size": len(by_id),
        "hv_section_size": len({player.player_id for player in hv_rows}),
        "position_mix": position_mix_label(ceiling_ids, by_id),
        "ceiling_score": round(ceiling_score, 6),
        "ceiling_ids": list(ceiling_ids),
        "hv_display_ids": list(display_ids),
        "hv_raw_ids": list(raw_ids),
        "chalk_ids": list(chalk_ids),
        "hv_display_score": round(hv_display_score, 6),
        "hv_raw_score": round(hv_raw_score, 6),
        "chalk_score": round(chalk_score, 6),
        "hv_display_capture": _share(hv_display_score),
        "hv_raw_capture": _share(hv_raw_score),
        "chalk_capture": _share(chalk_score),
        "hv_display_overlap": _overlap(display_ids),
        "hv_raw_overlap": _overlap(raw_ids),
        "chalk_overlap": _overlap(chalk_ids),
        "draft_count_is_label": False,
    }


def _mean(values: Sequence[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 6)


def _slice_means(boards: Sequence[Mapping[str, Any]], key: str) -> dict[str, Any]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for board in boards:
        grouped[str(board.get(key) or "unknown")].append(board)
    out: dict[str, Any] = {}
    for name in sorted(grouped):
        rows = grouped[name]
        out[name] = {
            "boards": len(rows),
            "hv_display_capture": _mean([float(row["hv_display_capture"]) for row in rows]),
            "hv_raw_capture": _mean([float(row["hv_raw_capture"]) for row in rows]),
            "chalk_capture": _mean([float(row["chalk_capture"]) for row in rows]),
        }
    return out


def summarize_boards(boards: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Means of capture ratios. Empty input stays an honest zero."""

    return {
        "boards_scored": len(boards),
        "hv_display_capture": _mean([float(row["hv_display_capture"]) for row in boards]),
        "hv_raw_capture": _mean([float(row["hv_raw_capture"]) for row in boards]),
        "chalk_capture": _mean([float(row["chalk_capture"]) for row in boards]),
        "hv_display_overlap": _mean([float(row["hv_display_overlap"]) for row in boards]),
        "hv_raw_overlap": _mean([float(row["hv_raw_overlap"]) for row in boards]),
        "chalk_overlap": _mean([float(row["chalk_overlap"]) for row in boards]),
        "by_sport": _slice_means(boards, "sport"),
        "by_regime": _slice_means(boards, "regime"),
        "by_position_mix": _slice_means(boards, "position_mix"),
        "draft_count_is_label": False,
        "score_law": "value * (slot_multiplier + card_boost)",
        "hv_rank_key": "value * (top_slot + card_boost)",
    }


def contest_display_rank_weights(
    values: Mapping[int, float],
    boosts: Mapping[int, float] | None = None,
    *,
    top_k: int = LINEUP_SIZE,
    high_weight: float = 4.0,
    base_weight: float = 1.0,
    top_slot: float = TOP_SLOT_MULTIPLIER,
) -> dict[int, float]:
    """Up-weight the top-k contest-display values. Draft count is not an input.

    ``boosts is None`` ranks by raw value, matching eras with no card boost.
    A supplied boost map, including an all-zero map, ranks by
    ``value * (top_slot + boost)``. All-zero boosts preserve raw order.
    """

    if not values:
        return {}
    if boosts is None:
        ranked = sorted(values, key=lambda pid: (-float(values[pid]), pid))
    else:
        ranked = sorted(
            values,
            key=lambda pid: (
                -display_contest_value(
                    float(values[pid]),
                    float(boosts.get(pid, 0.0)),
                    top_slot=top_slot,
                ),
                pid,
            ),
        )
    top = set(ranked[: max(1, top_k)])
    return {pid: (high_weight if pid in top else base_weight) for pid in ranked}


HV_SECTION_NAME = "highestBoostedValuePlayers"

# Submitted lineups are not a candidate pool. They stay out of the ceiling.
LINEUP_SECTIONS = frozenset({"leaderboard_lineup", "My draft"})


def _as_float(raw: object, default: float = 0.0) -> float:
    if raw is None or raw == "":
        return default
    return float(raw)  # type: ignore[arg-type]


def _section_is_hv(section: str) -> bool:
    return section == HV_SECTION_NAME


def players_from_mapping(rows: Sequence[Mapping[str, Any]]) -> tuple[ContestPlayer, ...]:
    """Normalize already-parsed rows. Missing value rows are dropped."""

    players: list[ContestPlayer] = []
    for row in rows:
        raw_value = row.get("value")
        if raw_value is None:
            raw_value = row.get("real_score")
        if raw_value is None:
            continue
        boost = row.get("card_boost", 0.0)
        drafts = row.get("draft_count", row.get("drafts", 0.0))
        players.append(
            ContestPlayer(
                player_id=int(row["player_id"]),
                value=float(raw_value),
                card_boost=0.0 if boost is None else float(boost),
                draft_count=0.0 if drafts is None else float(drafts),
                position=str(row.get("position") or ""),
                team=str(row.get("team") or ""),
                game_id=str(row.get("game_id") or ""),
                on_hv_board=bool(row.get("on_hv_board", True)),
            )
        )
    return tuple(players)


def _csv_player(row: Mapping[str, str]) -> dict[str, Any] | None:
    """One backup or export CSV row. Unknown headers return None."""

    if "platform_player_id" in row and "real_score" in row:
        player_id = row.get("platform_player_id") or ""
        value = row.get("real_score")
        slate_date = row.get("slate_date") or ""
        slate_id = row.get("contest_id") or slate_date
        team = row.get("team_key") or ""
        drafts = row.get("drafts")
        section = row.get("section") or HV_SECTION_NAME
    elif "player_id" in row and "value" in row:
        player_id = row.get("player_id") or ""
        value = row.get("value")
        slate_date = row.get("day") or row.get("slate_date") or ""
        slate_id = row.get("contest_id") or slate_date
        team = row.get("team") or row.get("team_id") or ""
        drafts = row.get("draft_count") or row.get("drafts")
        section = row.get("section") or HV_SECTION_NAME
    else:
        return None
    if not player_id or value in (None, ""):
        return None
    return {
        "slate_date": slate_date,
        "slate_id": str(slate_id),
        "player_id": int(player_id),
        "value": float(value),
        "card_boost": _as_float(row.get("card_boost"), 0.0),
        "draft_count": _as_float(drafts, 0.0),
        "position": row.get("position") or "",
        "team": team,
        "game_id": row.get("game_id") or "",
        "on_hv_board": _section_is_hv(section) if "section" in row else True,
    }


def _merge_player_rows(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """One row per player. HV membership sticks. Draft count takes the max.

    Value and boost stay on the HV row when that section is present, so a
    later popularity row cannot knock the player off the display board.
    """

    merged: dict[int, dict[str, Any]] = {}
    for raw in rows:
        row = dict(raw)
        player_id = int(row["player_id"])
        current = merged.get(player_id)
        if current is None:
            merged[player_id] = row
            continue
        drafts = max(float(current["draft_count"]), float(row["draft_count"]))
        if row["on_hv_board"] and not current["on_hv_board"]:
            row["draft_count"] = drafts
            row["on_hv_board"] = True
            merged[player_id] = row
            continue
        current["on_hv_board"] = bool(current["on_hv_board"] or row["on_hv_board"])
        current["draft_count"] = drafts
        if not current.get("position") and row.get("position"):
            current["position"] = row["position"]
        if not current.get("team") and row.get("team"):
            current["team"] = row["team"]
        if not current.get("game_id") and row.get("game_id"):
            current["game_id"] = row["game_id"]
    return list(merged.values())


def boards_from_csv(
    text: str,
    *,
    sport: str,
    positions: Mapping[tuple[str, int], str] | None = None,
) -> list[dict[str, Any]]:
    """Group a slate-label or player-results CSV into compare_board results.

    Chalk and the ceiling use board sections (HV, popular, 3x, most drafted).
    Submitted lineup sections are dropped. HV display rank and raw-value rank
    use ``highestBoostedValuePlayers`` only.
    """

    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    reader = csv.DictReader(text.splitlines())
    for raw in reader:
        section = raw.get("section") or ""
        if section in LINEUP_SECTIONS:
            continue
        parsed = _csv_player(raw)
        if parsed is None:
            continue
        if positions:
            position = positions.get((str(parsed["slate_date"]), int(parsed["player_id"])))
            if position:
                parsed["position"] = position
        key = (str(parsed["slate_date"]), str(parsed["slate_id"]))
        grouped[key].append(parsed)
    boards: list[dict[str, Any]] = []
    for (slate_date, slate_id), rows in sorted(grouped.items()):
        board = compare_board(
            players_from_mapping(_merge_player_rows(rows)),
            sport=sport,
            slate_id=slate_id,
            slate_date=slate_date,
        )
        if board is not None:
            boards.append(board)
    return boards


def _player_from_hv_json(row: Mapping[str, Any]) -> dict[str, Any] | None:
    player_id = row.get("player_id")
    if player_id is None:
        player_id = row.get("playerId")
    if player_id is None:
        return None
    value = row.get("real_score")
    if value is None:
        value = row.get("value")
    if value is None:
        value = row.get("base")
    if value is None:
        return None
    drafts = row.get("drafts")
    if drafts is None:
        drafts = row.get("draft_count")
    return {
        "player_id": int(player_id),
        "value": float(value),
        "card_boost": _as_float(row.get("card_boost"), 0.0),
        "draft_count": _as_float(drafts, 0.0),
        "position": str(row.get("position") or ""),
        "team": str(row.get("team") or row.get("team_key") or ""),
        "game_id": str(row.get("game_id") or ""),
        "on_hv_board": True,
    }


def board_from_hv_json(payload: Mapping[str, Any], *, sport: str = "") -> dict[str, Any] | None:
    """One ``hv_board.json`` or ``total_value_leaderboard.json`` document."""

    players_raw = payload.get("players")
    if not isinstance(players_raw, list):
        return None
    rows: list[dict[str, Any]] = []
    for item in players_raw:
        if not isinstance(item, Mapping):
            continue
        parsed = _player_from_hv_json(item)
        if parsed is not None:
            rows.append(parsed)
    resolved_sport = sport or str(payload.get("sport") or "")
    slate_date = str(payload.get("slate_date") or payload.get("day") or "")
    slate_id = str(payload.get("contest_id") or payload.get("slate_key") or slate_date)
    return compare_board(
        players_from_mapping(rows),
        sport=resolved_sport or "unknown",
        slate_id=slate_id,
        slate_date=slate_date,
    )


def iter_hv_json_files(root: Path) -> Iterable[Path]:
    """Yield leaderboard JSON files under a corpus or export root."""

    if not root.is_dir():
        return
    names = {"hv_board.json", "total_value_leaderboard.json", "highestBoostedValuePlayers.json"}
    for path in sorted(root.rglob("*.json")):
        if path.name in names:
            yield path


def apply_position_csv(
    boards_players: dict[tuple[str, int], str],
    text: str,
) -> dict[tuple[str, int], str]:
    """Merge ``slate_date,player_id,position`` rows into a lookup."""

    found = dict(boards_players)
    reader = csv.DictReader(text.splitlines())
    for row in reader:
        player_id = row.get("player_id") or ""
        slate_date = row.get("slate_date") or row.get("day") or ""
        position = row.get("position") or ""
        if player_id and slate_date and position:
            found[(slate_date, int(player_id))] = position
    return found
