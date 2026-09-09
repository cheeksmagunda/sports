"""Flat supervised dataset mapping Corpus G box statistics to the Real ``value`` label.

One row per ``(game_id, player_id)`` for every finalized player-game on disk under
``data/raw/corpus_g/<season>/<game_id>/``. Every ``statValues`` entry becomes a
``stat_<type>`` column and every ``advancedStatValues`` entry becomes an ``adv_<type>``
column, so provider label collisions (four different stat types all labelled ``lng``)
cannot merge distinct measurements.

Absent columns are emitted as ``null``, never as ``0``. The provider renders a stat
line conditionally by position and by whether the player recorded the category at all,
so "column not present" means "not rendered", not "zero". Imputation is the modeller's
decision, not this module's.

The module is disk-only. It performs no provider calls and writes only under the
requested output directory.
"""

from __future__ import annotations

import json
import math
import os
from collections import Counter, defaultdict
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from nfl_oracle.baselines.ridge import RidgeRegressor

__all__ = [
    "ADV_PREFIX",
    "COMPOUND_STAT_COMPONENTS",
    "IDENTITY_COLUMNS",
    "POSITION_FAMILIES",
    "STAT_PREFIX",
    "BoxStatRow",
    "BuildResult",
    "ColumnRegistry",
    "ColumnSpec",
    "GameMeta",
    "build_dataset",
    "column_name",
    "game_meta_from_payloads",
    "iter_game_dirs",
    "main",
    "parse_numeric",
    "position_family",
    "rows_from_stats_payload",
    "scan_columns",
    "split_compound",
]

STAT_PREFIX: Final[str] = "stat_"
ADV_PREFIX: Final[str] = "adv_"

#: Stat types whose provider value is a compound ``"made/attempted"`` string.
#: Each becomes two float columns, e.g. ``stat_44_cmp`` and ``stat_44_att``.
COMPOUND_STAT_COMPONENTS: Final[Mapping[int, tuple[str, str]]] = {
    44: ("cmp", "att"),
    162: ("made", "att"),
    171: ("made", "att"),
}

POSITION_FAMILIES: Final[Mapping[str, str]] = {
    "QB": "passer",
    "RB": "rusher",
    "WR": "receiver",
    "TE": "receiver",
    "OL": "line",
    "DB": "defense",
    "DL": "defense",
    "LB": "defense",
    "K": "special",
    "P": "special",
    "LS": "special",
}
UNKNOWN_FAMILY: Final[str] = "other"

IDENTITY_COLUMNS: Final[tuple[tuple[str, str, str], ...]] = (
    ("season", "int", "Corpus G season directory name."),
    ("game_id", "int", "Real game id (Corpus G game directory name)."),
    ("season_type", "str", "preseason / regularseason / postseason, from feed.json game."),
    ("week", "int", "League week from feed.json game."),
    ("kickoff", "str", "ISO8601 kickoff instant (feed game.dateTime, else manifest clocks)."),
    ("game_date", "str", "Local game day YYYY-MM-DD (feed game.day, else kickoff prefix)."),
    ("player_id", "int", "Real player id, stable across seasons."),
    ("display_name", "str", "Provider short display name, e.g. 'J. Hurts'."),
    ("position", "str", "Provider position bucket."),
    ("position_family", "str", "Coarse family: passer/rusher/receiver/line/defense/special."),
    ("team_id", "int", "Real team id the player is credited to."),
    ("opponent_team_id", "int", "The other team id in gameBoxScore.teamBoxScores."),
    ("is_home", "bool", "True when team_id equals feed game.homeTeamId."),
    ("did_not_play", "bool", "Provider didNotPlay flag."),
    ("game_status", "str", "Provider gameStatus; only 'final' rows are emitted."),
    ("box_value", "float", "LABEL: playerBoxScores[].value parsed at full precision."),
    ("fantasy_points_fanduel", "float", "Provider FanDuel fantasy points for the same game."),
    ("performance_tag_count", "int", "Number of entries in performanceTags."),
)

#: Column names that identify the row rather than describe the performance.
_LABEL_COLUMN: Final[str] = "box_value"

BoxStatRow = dict[str, Any]


# --------------------------------------------------------------------------------------
# Parsing primitives
# --------------------------------------------------------------------------------------


def parse_numeric(raw: object) -> float | None:
    """Parse a provider stat value into a float, or ``None`` when it is not numeric."""

    if raw is None or isinstance(raw, bool):
        return None
    if isinstance(raw, (int, float)):
        value = float(raw)
        return value if math.isfinite(value) else None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        try:
            value = float(text)
        except ValueError:
            return None
        return value if math.isfinite(value) else None
    return None


def split_compound(raw: object) -> tuple[float | None, float | None]:
    """Split a ``"19/23"`` style provider value into its two numeric components."""

    if not isinstance(raw, str):
        single = parse_numeric(raw)
        return (single, None)
    parts = raw.strip().split("/")
    if len(parts) != 2:
        return (parse_numeric(raw), None)
    return (parse_numeric(parts[0]), parse_numeric(parts[1]))


def position_family(position: str | None) -> str:
    """Map a provider position bucket to its coarse family."""

    if position is None:
        return UNKNOWN_FAMILY
    return POSITION_FAMILIES.get(position, UNKNOWN_FAMILY)


def column_name(source: str, stat_type: int, component: str | None = None) -> str:
    """Build the flat column name for a stat type and optional compound component."""

    prefix = STAT_PREFIX if source == "stat" else ADV_PREFIX
    if component is None:
        return f"{prefix}{stat_type}"
    return f"{prefix}{stat_type}_{component}"


# --------------------------------------------------------------------------------------
# Column registry
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ColumnSpec:
    """One column of the flat dataset."""

    name: str
    source: str
    dtype: str
    description: str
    stat_type: int | None = None
    provider_label: str | None = None
    component: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "source": self.source,
            "dtype": self.dtype,
            "stat_type": self.stat_type,
            "provider_label": self.provider_label,
            "compound_component": self.component,
            "description": self.description,
        }


@dataclass
class ColumnRegistry:
    """Deterministic ordered column set discovered from the corpus."""

    specs: list[ColumnSpec] = field(default_factory=list)
    label_conflicts: dict[str, list[str]] = field(default_factory=dict)

    @property
    def names(self) -> list[str]:
        return [spec.name for spec in self.specs]

    def stat_specs(self) -> list[ColumnSpec]:
        return [spec for spec in self.specs if spec.source in {"stat", "adv"}]


def _identity_specs() -> list[ColumnSpec]:
    return [
        ColumnSpec(
            name=name,
            source="label" if name == _LABEL_COLUMN else "identity",
            dtype=dtype,
            description=description,
        )
        for name, dtype, description in IDENTITY_COLUMNS
    ]


def _sorted_game_ids(season_dir: Path) -> list[int]:
    ids: list[int] = []
    for child in season_dir.iterdir():
        if child.is_dir() and child.name.isdigit():
            ids.append(int(child.name))
    return sorted(ids)


def iter_game_dirs(root: Path) -> Iterator[tuple[int, int, Path]]:
    """Yield ``(season, game_id, game_dir)`` in deterministic ascending order."""

    if not root.is_dir():
        return
    seasons = sorted(
        int(child.name) for child in root.iterdir() if child.is_dir() and child.name.isdigit()
    )
    for season in seasons:
        season_dir = root / str(season)
        for game_id in _sorted_game_ids(season_dir):
            yield season, game_id, season_dir / str(game_id)


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _final_box_scores(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    raw = payload.get("playerBoxScores")
    if not isinstance(raw, list):
        return []
    rows: list[Mapping[str, Any]] = []
    for entry in raw:
        if isinstance(entry, dict) and entry.get("gameStatus") == "final":
            rows.append(entry)
    return rows


def _entry_types(entry: Mapping[str, Any], key: str) -> list[tuple[int, str | None, Any]]:
    raw = entry.get(key)
    if not isinstance(raw, list):
        return []
    out: list[tuple[int, str | None, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        stat_type = item.get("type")
        if not isinstance(stat_type, int) or isinstance(stat_type, bool):
            continue
        label = item.get("label")
        out.append((stat_type, label if isinstance(label, str) else None, item.get("value")))
    return out


def scan_columns(root: Path) -> ColumnRegistry:
    """First pass: discover every stat and advanced stat type present in the corpus."""

    labels: dict[tuple[str, int], Counter[str]] = defaultdict(Counter)
    for _season, _game_id, game_dir in iter_game_dirs(root):
        stats_path = game_dir / "stats.json"
        if not stats_path.is_file():
            continue
        payload = _load_json(stats_path)
        if not isinstance(payload, dict):
            continue
        for entry in _final_box_scores(payload):
            for source, key in (("stat", "statValues"), ("adv", "advancedStatValues")):
                for stat_type, label, _value in _entry_types(entry, key):
                    labels[(source, stat_type)][label or ""] += 1
    return _registry_from_labels(labels)


def _registry_from_labels(labels: Mapping[tuple[str, int], Counter[str]]) -> ColumnRegistry:
    registry = ColumnRegistry(specs=_identity_specs())
    for source in ("stat", "adv"):
        for stat_type in sorted(key[1] for key in labels if key[0] == source):
            counter = labels[(source, stat_type)]
            observed = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
            primary = observed[0][0] if observed else ""
            if len(observed) > 1:
                registry.label_conflicts[column_name(source, stat_type)] = [
                    name for name, _count in observed
                ]
            components = COMPOUND_STAT_COMPONENTS.get(stat_type) if source == "stat" else None
            if components is None:
                registry.specs.append(
                    ColumnSpec(
                        name=column_name(source, stat_type),
                        source=source,
                        dtype="float",
                        description=(
                            f"Provider {'statValues' if source == 'stat' else 'advancedStatValues'}"
                            f" type {stat_type} (label {primary!r})."
                        ),
                        stat_type=stat_type,
                        provider_label=primary or None,
                    )
                )
                continue
            for component in components:
                registry.specs.append(
                    ColumnSpec(
                        name=column_name(source, stat_type, component),
                        source=source,
                        dtype="float",
                        description=(
                            f"Provider statValues type {stat_type} (label {primary!r}) is a"
                            f' compound "a/b" string; this column is the {component!r} side.'
                        ),
                        stat_type=stat_type,
                        provider_label=primary or None,
                        component=component,
                    )
                )
    return registry


# --------------------------------------------------------------------------------------
# Game metadata
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class GameMeta:
    """Per-game context attached to every player row of that game."""

    season: int
    game_id: int
    season_type: str | None = None
    week: int | None = None
    kickoff: str | None = None
    game_date: str | None = None
    home_team_id: int | None = None
    away_team_id: int | None = None
    team_ids: tuple[int, ...] = ()

    def opponent_of(self, team_id: int | None) -> int | None:
        if team_id is None:
            return None
        others = [other for other in self.team_ids if other != team_id]
        if len(others) == 1:
            return others[0]
        if self.home_team_id is not None and self.away_team_id is not None:
            if team_id == self.home_team_id:
                return self.away_team_id
            if team_id == self.away_team_id:
                return self.home_team_id
        return None

    def home_flag(self, team_id: int | None) -> bool | None:
        if team_id is None or self.home_team_id is None:
            return None
        return team_id == self.home_team_id


def _as_int(raw: object) -> int | None:
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float) and math.isfinite(raw) and float(raw).is_integer():
        return int(raw)
    if isinstance(raw, str):
        text = raw.strip()
        if text.lstrip("-").isdigit():
            return int(text)
    return None


def _as_str(raw: object) -> str | None:
    return raw if isinstance(raw, str) and raw else None


def _team_ids_from_stats(payload: Mapping[str, Any]) -> tuple[int, ...]:
    box = payload.get("gameBoxScore")
    if not isinstance(box, dict):
        return ()
    teams = box.get("teamBoxScores")
    if not isinstance(teams, list):
        return ()
    ids: list[int] = []
    for team in teams:
        if not isinstance(team, dict):
            continue
        team_id = _as_int(team.get("teamId"))
        if team_id is not None and team_id not in ids:
            ids.append(team_id)
    return tuple(ids)


def game_meta_from_payloads(
    *,
    season: int,
    game_id: int,
    stats_payload: Mapping[str, Any],
    feed_game: Mapping[str, Any] | None = None,
    manifest: Mapping[str, Any] | None = None,
) -> GameMeta:
    """Assemble per-game context, tolerating a missing feed.json or manifest.json."""

    feed_game = feed_game or {}
    kickoff = _as_str(feed_game.get("dateTime"))
    if kickoff is None and isinstance(manifest, dict):
        clocks = manifest.get("clocks")
        if isinstance(clocks, dict):
            kickoff = _as_str(clocks.get("event_time"))
    if kickoff is None:
        for entry in _final_box_scores(stats_payload):
            kickoff = _as_str(entry.get("dateTime"))
            if kickoff is not None:
                break
    game_date = _as_str(feed_game.get("day"))
    if game_date is None and kickoff is not None and len(kickoff) >= 10:
        game_date = kickoff[:10]
    return GameMeta(
        season=season,
        game_id=game_id,
        season_type=_as_str(feed_game.get("seasonType")),
        week=_as_int(feed_game.get("week")),
        kickoff=kickoff,
        game_date=game_date,
        home_team_id=_as_int(feed_game.get("homeTeamId")),
        away_team_id=_as_int(feed_game.get("awayTeamId")),
        team_ids=_team_ids_from_stats(stats_payload),
    )


def _read_feed_game(game_dir: Path) -> Mapping[str, Any] | None:
    feed_path = game_dir / "feed.json"
    if not feed_path.is_file():
        return None
    payload = _load_json(feed_path)
    if not isinstance(payload, dict):
        return None
    game = payload.get("game")
    return game if isinstance(game, dict) else None


def _read_manifest(game_dir: Path) -> Mapping[str, Any] | None:
    manifest_path = game_dir / "manifest.json"
    if not manifest_path.is_file():
        return None
    payload = _load_json(manifest_path)
    return payload if isinstance(payload, dict) else None


# --------------------------------------------------------------------------------------
# Row construction
# --------------------------------------------------------------------------------------


def _stat_cells(entry: Mapping[str, Any]) -> tuple[dict[str, float], int]:
    """Return ``{column_name: numeric_value}`` for one player plus a collision count."""

    cells: dict[str, float] = {}
    collisions = 0
    for source, key in (("stat", "statValues"), ("adv", "advancedStatValues")):
        for stat_type, _label, raw in _entry_types(entry, key):
            components = COMPOUND_STAT_COMPONENTS.get(stat_type) if source == "stat" else None
            if components is None:
                name = column_name(source, stat_type)
                value = parse_numeric(raw)
                if value is None:
                    continue
                if name in cells:
                    collisions += 1
                    continue
                cells[name] = value
                continue
            left, right = split_compound(raw)
            for component, value in zip(components, (left, right), strict=True):
                name = column_name(source, stat_type, component)
                if value is None:
                    continue
                if name in cells:
                    collisions += 1
                    continue
                cells[name] = value
    return cells, collisions


def rows_from_stats_payload(
    payload: Mapping[str, Any],
    meta: GameMeta,
    registry: ColumnRegistry,
) -> list[BoxStatRow]:
    """Build dense rows for every finalized player-game in one ``stats.json`` payload."""

    stat_names = [spec.name for spec in registry.stat_specs()]
    rows: list[BoxStatRow] = []
    for entry in _final_box_scores(payload):
        player = entry.get("player")
        player_block: Mapping[str, Any] = player if isinstance(player, dict) else {}
        team_id = _as_int(entry.get("teamId"))
        position = _as_str(entry.get("position"))
        tags = entry.get("performanceTags")
        cells, _collisions = _stat_cells(entry)
        row: BoxStatRow = {
            "season": meta.season,
            "game_id": meta.game_id,
            "season_type": meta.season_type,
            "week": meta.week,
            "kickoff": meta.kickoff,
            "game_date": meta.game_date,
            "player_id": _as_int(entry.get("playerId")),
            "display_name": _as_str(player_block.get("displayName")),
            "position": position,
            "position_family": position_family(position),
            "team_id": team_id,
            "opponent_team_id": meta.opponent_of(team_id),
            "is_home": meta.home_flag(team_id),
            "did_not_play": bool(entry.get("didNotPlay")),
            "game_status": _as_str(entry.get("gameStatus")),
            _LABEL_COLUMN: parse_numeric(entry.get("value")),
            "fantasy_points_fanduel": parse_numeric(entry.get("fantasyPointsFanduel")),
            "performance_tag_count": len(tags) if isinstance(tags, list) else 0,
        }
        for name in stat_names:
            row[name] = cells.get(name)
        rows.append(row)
    return rows


# --------------------------------------------------------------------------------------
# Streaming statistics
# --------------------------------------------------------------------------------------


@dataclass
class PairAccumulator:
    """Streaming Pearson correlation between one column and the label."""

    n: int = 0
    sx: float = 0.0
    sxx: float = 0.0
    sy: float = 0.0
    syy: float = 0.0
    sxy: float = 0.0
    x_min: float | None = None
    x_max: float | None = None

    def update(self, x: float, y: float) -> None:
        self.n += 1
        self.sx += x
        self.sxx += x * x
        self.sy += y
        self.syy += y * y
        self.sxy += x * y
        self.x_min = x if self.x_min is None else min(self.x_min, x)
        self.x_max = x if self.x_max is None else max(self.x_max, x)

    def mean_x(self) -> float | None:
        return self.sx / self.n if self.n else None

    def pearson(self) -> float | None:
        if self.n < 3:
            return None
        cov = self.sxy - self.sx * self.sy / self.n
        var_x = self.sxx - self.sx * self.sx / self.n
        var_y = self.syy - self.sy * self.sy / self.n
        if var_x <= 1e-12 or var_y <= 1e-12:
            return None
        return cov / math.sqrt(var_x * var_y)


def _percentile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("empty sequence")
    if len(sorted_values) == 1:
        return sorted_values[0]
    pos = q * (len(sorted_values) - 1)
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return sorted_values[low]
    frac = pos - low
    return sorted_values[low] * (1.0 - frac) + sorted_values[high] * frac


def _distribution(values: Sequence[float]) -> dict[str, Any]:
    if not values:
        return {"n": 0}
    ordered = sorted(values)
    n = len(ordered)
    mean = math.fsum(ordered) / n
    if n > 1:
        variance = math.fsum((v - mean) ** 2 for v in ordered) / (n - 1)
    else:
        variance = 0.0
    return {
        "n": n,
        "mean": round(mean, 6),
        "sd": round(math.sqrt(variance), 6),
        "min": round(ordered[0], 6),
        "p05": round(_percentile(ordered, 0.05), 6),
        "p25": round(_percentile(ordered, 0.25), 6),
        "p50": round(_percentile(ordered, 0.50), 6),
        "p75": round(_percentile(ordered, 0.75), 6),
        "p95": round(_percentile(ordered, 0.95), 6),
        "max": round(ordered[-1], 6),
        "share_exactly_zero": round(sum(1 for v in ordered if v == 0.0) / n, 6),
        "share_negative": round(sum(1 for v in ordered if v < 0.0) / n, 6),
    }


def _pearson(pairs: Sequence[tuple[float, float]]) -> float | None:
    acc = PairAccumulator()
    for x, y in pairs:
        acc.update(x, y)
    return acc.pearson()


# --------------------------------------------------------------------------------------
# Purity evidence
# --------------------------------------------------------------------------------------


def _line_key(row: BoxStatRow, names: Sequence[str]) -> tuple[Any, ...]:
    return (row.get("position"),) + tuple(row.get(name) for name in names)


@dataclass
class DuplicateLineEvidence:
    """Result of the identical-box-line test."""

    scope: str
    group_count: int
    multi_row_group_count: int
    rows_in_multi_row_groups: int
    varying_group_count: int
    rows_in_varying_groups: int
    within_group_variance: float
    subset_total_variance: float
    unexplained_variance_share: float
    examples: list[dict[str, Any]]

    def to_json(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "group_count": self.group_count,
            "multi_row_group_count": self.multi_row_group_count,
            "rows_in_multi_row_groups": self.rows_in_multi_row_groups,
            "varying_group_count": self.varying_group_count,
            "rows_in_varying_groups": self.rows_in_varying_groups,
            "within_group_variance": round(self.within_group_variance, 6),
            "subset_total_variance": round(self.subset_total_variance, 6),
            "unexplained_variance_share": round(self.unexplained_variance_share, 6),
            "examples": self.examples,
        }


def _duplicate_line_evidence(
    rows: Sequence[BoxStatRow],
    names: Sequence[str],
    scope: str,
    *,
    example_count: int = 5,
) -> DuplicateLineEvidence:
    groups: dict[tuple[Any, ...], list[float]] = defaultdict(list)
    for row in rows:
        label = row.get(_LABEL_COLUMN)
        if label is None:
            continue
        groups[_line_key(row, names)].append(float(label))
    multi = {key: values for key, values in groups.items() if len(values) > 1}
    varying = {key: values for key, values in multi.items() if max(values) - min(values) > 1e-9}
    subset: list[float] = [value for values in multi.values() for value in values]
    within_ss = 0.0
    for values in multi.values():
        mean = math.fsum(values) / len(values)
        within_ss += math.fsum((v - mean) ** 2 for v in values)
    if subset:
        grand = math.fsum(subset) / len(subset)
        total_ss = math.fsum((v - grand) ** 2 for v in subset)
    else:
        total_ss = 0.0
    share = within_ss / total_ss if total_ss > 1e-12 else 0.0
    ranked = sorted(
        varying.items(),
        key=lambda kv: (-(max(kv[1]) - min(kv[1])), -len(kv[1]), str(kv[0])),
    )
    examples: list[dict[str, Any]] = []
    for key, values in ranked[:example_count]:
        nonzero = {
            name: value
            for name, value in zip(names, key[1:], strict=True)
            if value is not None and value != 0.0
        }
        examples.append(
            {
                "position": key[0],
                "rows": len(values),
                "box_value_min": round(min(values), 6),
                "box_value_max": round(max(values), 6),
                "box_value_spread": round(max(values) - min(values), 6),
                "non_zero_columns": nonzero,
            }
        )
    largest = sorted(multi.items(), key=lambda kv: (-len(kv[1]), str(kv[0])))[:example_count]
    for key, values in largest:
        nonzero = {
            name: value
            for name, value in zip(names, key[1:], strict=True)
            if value is not None and value != 0.0
        }
        examples.append(
            {
                "position": key[0],
                "rows": len(values),
                "box_value_min": round(min(values), 6),
                "box_value_max": round(max(values), 6),
                "box_value_spread": round(max(values) - min(values), 6),
                "non_zero_columns": nonzero,
                "note": "largest identical-line group",
            }
        )
    return DuplicateLineEvidence(
        scope=scope,
        group_count=len(groups),
        multi_row_group_count=len(multi),
        rows_in_multi_row_groups=len(subset),
        varying_group_count=len(varying),
        rows_in_varying_groups=sum(len(values) for values in varying.values()),
        within_group_variance=within_ss / len(subset) if subset else 0.0,
        subset_total_variance=total_ss / len(subset) if subset else 0.0,
        unexplained_variance_share=share,
        examples=examples,
    )


def _ridge_r2(
    rows: Sequence[BoxStatRow],
    names: Sequence[str],
    *,
    alpha: float = 1.0,
    max_rows: int = 20000,
) -> dict[str, Any]:
    """In-sample ridge R^2 of the visible box score against the label (an upper bound)."""

    usable = [row for row in rows if row.get(_LABEL_COLUMN) is not None]
    if len(usable) > max_rows:
        stride = len(usable) // max_rows + 1
        usable = usable[::stride]
    if len(usable) < 50:
        return {"n": len(usable), "features": 0, "r2": None, "reason": "insufficient rows"}
    kept: list[str] = []
    means: list[float] = []
    scales: list[float] = []
    for name in names:
        present = [row[name] for row in usable if row.get(name) is not None]
        if len(present) < 0.5 * len(usable):
            continue
        values = [float(v) for v in present]
        mean = math.fsum(values) / len(values)
        variance = math.fsum((v - mean) ** 2 for v in values) / len(values)
        if variance <= 1e-12:
            continue
        kept.append(name)
        means.append(mean)
        scales.append(math.sqrt(variance))
    if not kept:
        return {"n": len(usable), "features": 0, "r2": None, "reason": "no usable columns"}
    design: list[list[float]] = []
    target: list[float] = []
    for row in usable:
        features = [1.0]
        for name, mean, scale in zip(kept, means, scales, strict=True):
            raw = row.get(name)
            features.append(0.0 if raw is None else (float(raw) - mean) / scale)
        design.append(features)
        target.append(float(row[_LABEL_COLUMN]))
    model = RidgeRegressor(alpha=alpha).fit(design, target)
    predictions = model.predict(design)
    mean_y = math.fsum(target) / len(target)
    ss_res = math.fsum((y - p) ** 2 for y, p in zip(target, predictions, strict=True))
    ss_tot = math.fsum((y - mean_y) ** 2 for y in target)
    return {
        "n": len(usable),
        "features": len(kept),
        "r2": round(1.0 - ss_res / ss_tot, 6) if ss_tot > 1e-12 else None,
        "alpha": alpha,
        "interpretation": "in-sample, standardized, missing-as-mean; an optimistic upper bound",
    }


# --------------------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------------------


@dataclass
class BuildResult:
    """Summary of one dataset build."""

    dataset_path: Path
    schema_path: Path
    report_path: Path
    row_count: int
    column_count: int
    game_count: int
    schema: dict[str, Any]
    report: dict[str, Any]


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=False, ensure_ascii=False)
        handle.write("\n")
    os.replace(tmp, path)


def _atomic_write_lines(path: Path, lines: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for line in lines:
            handle.write(line)
            handle.write("\n")
    os.replace(tmp, path)


def _collect_rows(root: Path, registry: ColumnRegistry) -> tuple[list[BoxStatRow], int, int]:
    rows: list[BoxStatRow] = []
    games = 0
    missing_feed = 0
    for season, game_id, game_dir in iter_game_dirs(root):
        stats_path = game_dir / "stats.json"
        if not stats_path.is_file():
            continue
        payload = _load_json(stats_path)
        if not isinstance(payload, dict):
            continue
        games += 1
        feed_game = _read_feed_game(game_dir)
        if feed_game is None:
            missing_feed += 1
        meta = game_meta_from_payloads(
            season=season,
            game_id=game_id,
            stats_payload=payload,
            feed_game=feed_game,
            manifest=_read_manifest(game_dir),
        )
        rows.extend(rows_from_stats_payload(payload, meta, registry))
    rows.sort(key=lambda row: (row["season"], row["game_id"], row["player_id"] or -1))
    return rows, games, missing_feed


def _schema_document(
    rows: Sequence[BoxStatRow],
    registry: ColumnRegistry,
    *,
    root: Path,
    dataset_path: Path,
    game_count: int,
    missing_feed: int,
) -> dict[str, Any]:
    total = len(rows)
    labelled = [row for row in rows if row.get(_LABEL_COLUMN) is not None]
    columns: list[dict[str, Any]] = []
    for spec in registry.specs:
        present = 0
        acc = PairAccumulator()
        for row in rows:
            value = row.get(spec.name)
            if value is None:
                continue
            present += 1
            if spec.dtype in {"float", "int"} and not isinstance(value, str):
                label = row.get(_LABEL_COLUMN)
                if label is not None and spec.name != _LABEL_COLUMN:
                    acc.update(float(value), float(label))
        entry = spec.to_json()
        entry["present_rows"] = present
        entry["coverage"] = round(present / total, 6) if total else 0.0
        entry["correlation_with_box_value"] = (
            None if acc.pearson() is None else round(acc.pearson() or 0.0, 6)
        )
        entry["correlation_rows"] = acc.n
        entry["observed_min"] = None if acc.x_min is None else round(acc.x_min, 6)
        entry["observed_max"] = None if acc.x_max is None else round(acc.x_max, 6)
        mean_x = acc.mean_x()
        entry["observed_mean"] = None if mean_x is None else round(mean_x, 6)
        columns.append(entry)
    season_types = Counter(str(row.get("season_type")) for row in rows)
    return {
        "dataset": dataset_path.name,
        "corpus_root": str(root),
        "row_grain": "one row per (game_id, player_id) finalized player-game",
        "row_count": total,
        "labelled_row_count": len(labelled),
        "column_count": len(registry.specs),
        "game_count": game_count,
        "games_missing_feed_json": missing_feed,
        "label_column": _LABEL_COLUMN,
        "rows_by_season_type": dict(sorted(season_types.items())),
        "missing_convention": (
            "Absent stat columns are null, never zero. The provider renders stat categories "
            "conditionally, so a null means 'not rendered for this player-game', not 'zero'. "
            "Imputation is the modeller's decision."
        ),
        "compound_parsing": {
            "rule": (
                'Provider values shaped "a/b" are split on "/" into two float columns named '
                "<prefix><type>_<component>. Both sides are parsed with float(); an unsplittable "
                "value yields the parsed whole in the first component and null in the second."
            ),
            "types": {
                str(stat_type): {
                    "components": list(components),
                    "columns": [
                        column_name("stat", stat_type, component) for component in components
                    ],
                }
                for stat_type, components in sorted(COMPOUND_STAT_COMPONENTS.items())
            },
        },
        "provider_label_collisions": {
            "note": (
                "Column names key on the numeric stat type, not the provider label string, "
                "because several distinct types share a label (four types are labelled 'lng')."
            ),
            "types_with_multiple_observed_labels": registry.label_conflicts,
        },
        "columns": columns,
    }


def _label_report(rows: Sequence[BoxStatRow], registry: ColumnRegistry) -> dict[str, Any]:
    stat_names = [spec.name for spec in registry.stat_specs()]
    labelled = [row for row in rows if row.get(_LABEL_COLUMN) is not None]
    values = [float(row[_LABEL_COLUMN]) for row in labelled]

    by_position: dict[str, list[float]] = defaultdict(list)
    by_family: dict[str, list[float]] = defaultdict(list)
    by_season_type: dict[str, list[float]] = defaultdict(list)
    fd_by_position: dict[str, list[tuple[float, float]]] = defaultdict(list)
    fd_overall: list[tuple[float, float]] = []
    for row in labelled:
        label = float(row[_LABEL_COLUMN])
        position = str(row.get("position"))
        family = str(row.get("position_family"))
        by_position[position].append(label)
        by_family[family].append(label)
        by_season_type[str(row.get("season_type"))].append(label)
        fantasy = row.get("fantasy_points_fanduel")
        if fantasy is not None:
            fd_by_position[position].append((float(fantasy), label))
            fd_overall.append((float(fantasy), label))

    family_rows: dict[str, list[BoxStatRow]] = defaultdict(list)
    for row in labelled:
        family_rows[str(row.get("position_family"))].append(row)

    top_by_family: dict[str, list[dict[str, Any]]] = {}
    ridge_by_family: dict[str, dict[str, Any]] = {}
    for family in sorted(family_rows):
        members = family_rows[family]
        ranked: list[dict[str, Any]] = []
        for name in stat_names:
            acc = PairAccumulator()
            for row in members:
                value = row.get(name)
                if value is None:
                    continue
                acc.update(float(value), float(row[_LABEL_COLUMN]))
            corr = acc.pearson()
            if corr is None:
                continue
            ranked.append(
                {
                    "column": name,
                    "correlation": round(corr, 6),
                    "abs_correlation": round(abs(corr), 6),
                    "rows": acc.n,
                    "coverage_in_family": round(acc.n / len(members), 6),
                }
            )
        ranked.sort(key=lambda item: (-float(item["abs_correlation"]), str(item["column"])))
        top_by_family[family] = ranked[:15]
        ridge_by_family[family] = _ridge_r2(members, stat_names)

    duplicate_visible = _duplicate_line_evidence(
        labelled,
        [name for name in stat_names if name.startswith(STAT_PREFIX)],
        "position + every statValues column",
    )
    duplicate_all = _duplicate_line_evidence(
        labelled,
        stat_names,
        "position + every statValues and advancedStatValues column",
    )

    return {
        "label_distribution": {
            "overall": _distribution(values),
            "by_position": {
                position: _distribution(by_position[position]) for position in sorted(by_position)
            },
            "by_position_family": {
                family: _distribution(by_family[family]) for family in sorted(by_family)
            },
            "by_season_type": {
                season_type: _distribution(by_season_type[season_type])
                for season_type in sorted(by_season_type)
            },
        },
        "fanduel_correlation": {
            "overall": (
                None if _pearson(fd_overall) is None else round(_pearson(fd_overall) or 0.0, 6)
            ),
            "overall_rows": len(fd_overall),
            "by_position": {
                position: {
                    "correlation": (
                        None
                        if _pearson(fd_by_position[position]) is None
                        else round(_pearson(fd_by_position[position]) or 0.0, 6)
                    ),
                    "rows": len(fd_by_position[position]),
                }
                for position in sorted(fd_by_position)
            },
        },
        "top_columns_by_abs_correlation": top_by_family,
        "purity": {
            "question": (
                "Is box_value a pure function of the visible box score, or is there residual "
                "structure the box score cannot explain?"
            ),
            "answer": "not a pure function",
            "method": (
                "Group labelled rows by the exact tuple (position, every stat column). Two rows "
                "in the same group have byte-identical visible box lines. If box_value were a "
                "pure function of the visible box score, every group would be constant."
            ),
            "identical_visible_box_line": duplicate_visible.to_json(),
            "identical_visible_and_advanced_box_line": duplicate_all.to_json(),
            "ridge_upper_bound_r2_by_family": ridge_by_family,
        },
    }


def build_dataset(
    root: Path,
    out_dir: Path,
    *,
    registry: ColumnRegistry | None = None,
) -> BuildResult:
    """Build the flat box-stats dataset, its schema, and the label characterisation."""

    registry = registry or scan_columns(root)
    rows, game_count, missing_feed = _collect_rows(root, registry)
    names = registry.names
    dataset_path = out_dir / "box_stats.jsonl"
    lines = [
        json.dumps({name: row.get(name) for name in names}, ensure_ascii=False, sort_keys=False)
        for row in rows
    ]
    _atomic_write_lines(dataset_path, lines)

    schema = _schema_document(
        rows,
        registry,
        root=root,
        dataset_path=dataset_path,
        game_count=game_count,
        missing_feed=missing_feed,
    )
    schema_path = out_dir / "box_stats_schema.json"
    _atomic_write_json(schema_path, schema)

    report = _label_report(rows, registry)
    report["row_count"] = len(rows)
    report["column_count"] = len(names)
    report["game_count"] = game_count
    report_path = out_dir / "box_stats_label_report.json"
    _atomic_write_json(report_path, report)

    return BuildResult(
        dataset_path=dataset_path,
        schema_path=schema_path,
        report_path=report_path,
        row_count=len(rows),
        column_count=len(names),
        game_count=game_count,
        schema=schema,
        report=report,
    )


DEFAULT_CORPUS_ROOT: Final[Path] = Path("data/raw/corpus_g")
DEFAULT_OUT_DIR: Final[Path] = Path("data/artifacts/valuelaw")


def main(argv: Sequence[str] | None = None) -> int:
    """Build the dataset from the default on-disk locations."""

    import argparse

    parser = argparse.ArgumentParser(description="Build the Corpus G box-stats dataset.")
    parser.add_argument("--corpus-root", type=Path, default=DEFAULT_CORPUS_ROOT)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = build_dataset(Path(args.corpus_root), Path(args.out_dir))
    print(
        f"rows={result.row_count} columns={result.column_count} games={result.game_count} "
        f"-> {result.dataset_path}"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
