"""Highest Total Value board as the NHL train + backtest target (#535 / #453).

Operator rule: fit and grade against Real Sports ``highestBoostedValuePlayers``
(Highest value / Total Value), never winning drafts. When contest
``draftStats`` for that section exist, they are the label path. When they do
not, report an explicit corpus gap rather than inventing labels.

Under the hard zero-boost gate (#501 / #517), card boosts stay 0 until every
franchise has 1 GP; HV ranking still uses the section rows' realized
``value`` fields when present.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from oracle_core.high_tv import (
    HighPotentialLabelKind,
    HighTvBoard,
    build_high_tv_board,
)

from nhl_oracle.labels.schema import TRAINING_LABEL_SECTION, ValueLabel

HV_SECTION_ALIASES: frozenset[str] = frozenset(
    {
        TRAINING_LABEL_SECTION,
        "HighestBoostedValuePlayers",
        "highest_value",
        "Highest value",
        "Highest Value",
        "Total Value",
        "totalValue",
    }
)

HvIngestStatus = Literal[
    "hv_section_present",
    "draft_stats_without_hv_section",
    "contest_stats_missing",
    "empty_hv_section",
]


@dataclass(frozen=True)
class HvBoardRow:
    """One Highest Total Value board player with required realized value."""

    player_id: int
    value: float
    card_boost: float
    position: str
    rank: int
    approx_total_value: float
    display_name: str = ""
    team_key: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "player_id": self.player_id,
            "value": self.value,
            "card_boost": self.card_boost,
            "position": self.position,
            "rank": self.rank,
            "approx_total_value": self.approx_total_value,
            "display_name": self.display_name,
            "team_key": self.team_key,
        }


@dataclass(frozen=True)
class HvBoardExtract:
    """Parsed HV board plus ingest honesty for one contest ``/stats`` payload."""

    contest_id: int
    status: HvIngestStatus
    rows: tuple[HvBoardRow, ...]
    section_name: str | None
    skipped_missing_value: int
    notes: tuple[str, ...]

    @property
    def has_train_labels(self) -> bool:
        return self.status == "hv_section_present" and bool(self.rows)

    def to_dict(self) -> dict[str, Any]:
        return {
            "contest_id": self.contest_id,
            "status": self.status,
            "section_name": self.section_name,
            "n_rows": len(self.rows),
            "skipped_missing_value": self.skipped_missing_value,
            "notes": list(self.notes),
            "rows": [row.to_dict() for row in self.rows],
            "train_label_section": TRAINING_LABEL_SECTION,
            "observation_only": True,
            "contest_entry": False,
        }


@dataclass(frozen=True)
class HvCorpusGap:
    """Explicit gap when durable RS contest HV ingest is missing (#535 / #526)."""

    corpus_root: str
    contests_scanned: int
    contests_with_stats: int
    contests_with_hv_section: int
    detail: str

    @property
    def hv_ingest_ready(self) -> bool:
        return self.contests_with_hv_section > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "corpus_root": self.corpus_root,
            "contests_scanned": self.contests_scanned,
            "contests_with_stats": self.contests_with_stats,
            "contests_with_hv_section": self.contests_with_hv_section,
            "hv_ingest_ready": self.hv_ingest_ready,
            "detail": self.detail,
            "train_label_section": TRAINING_LABEL_SECTION,
        }


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _section_name(section: Mapping[str, Any]) -> str | None:
    for key in ("sectionName", "section", "name", "title"):
        raw = section.get(key)
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _is_hv_section(name: str | None) -> bool:
    if name is None:
        return False
    if name in HV_SECTION_ALIASES:
        return True
    folded = name.casefold().replace(" ", "").replace("_", "")
    return folded in {
        "highestboostedvalueplayers",
        "highestvalue",
        "totalvalue",
    }


def _player_id(row: Mapping[str, Any]) -> int | None:
    pid = row.get("playerId")
    if isinstance(pid, int) and pid > 0:
        return pid
    if isinstance(pid, str) and pid.isdigit() and int(pid) > 0:
        return int(pid)
    nested = _as_dict(row.get("player"))
    nested_id = nested.get("id")
    if isinstance(nested_id, int) and nested_id > 0:
        return nested_id
    return None


def _required_float(row: Mapping[str, Any], *keys: str) -> float | None:
    for key in keys:
        raw = row.get(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return None


def approx_total_value(*, real_value: float, card_boost: float) -> float:
    """Match Real Sports HV Value column: ``value * (2 + card_boost)``.

    Under zero-boost, ``card_boost`` is 0 so this collapses to ``2 * value``.
    """

    if card_boost < 0:
        raise ValueError("card_boost_must_be_non_negative")
    return float(real_value) * (2.0 + float(card_boost))


def extract_hv_board(
    contest_stats: Mapping[str, Any] | None,
    *,
    contest_id: int,
    force_zero_boost: bool = True,
) -> HvBoardExtract:
    """Parse ``highestBoostedValuePlayers`` from a contest ``/stats`` payload.

    Missing ``value`` rows are skipped and counted (never coerced to 0.0).
    When ``force_zero_boost`` is true (default during the all-teams-played
    gap), ``card_boost`` is forced to 0.0 for ranking math even if draftStats
    still carry historical ``multiplierBonus``.
    """

    if contest_id <= 0:
        raise ValueError("contest_id_must_be_positive")
    if contest_stats is None:
        return HvBoardExtract(
            contest_id=contest_id,
            status="contest_stats_missing",
            rows=(),
            section_name=None,
            skipped_missing_value=0,
            notes=("contest_stats_missing: no RS /stats payload for HV labels",),
        )

    sections = _as_list(contest_stats.get("draftStats"))
    if not sections:
        return HvBoardExtract(
            contest_id=contest_id,
            status="contest_stats_missing",
            rows=(),
            section_name=None,
            skipped_missing_value=0,
            notes=("draftStats_absent_or_empty",),
        )

    hv_section: dict[str, Any] | None = None
    hv_name: str | None = None
    unnamed_fallback: dict[str, Any] | None = None
    for raw_section in sections:
        section = _as_dict(raw_section)
        if not section:
            continue
        name = _section_name(section)
        if _is_hv_section(name):
            hv_section = section
            hv_name = name
            break
        if name is None and unnamed_fallback is None:
            unnamed_fallback = section

    # Historical NHL audit fixtures omit sectionName; a single draftStats
    # block is treated as the scored pool only when no named HV section exists.
    if hv_section is None and unnamed_fallback is not None and len(sections) == 1:
        hv_section = unnamed_fallback
        hv_name = TRAINING_LABEL_SECTION
        unnamed_note = (
            "single_unnamed_draftStats_treated_as_hv_pool "
            f"(canonical section={TRAINING_LABEL_SECTION})"
        )
    else:
        unnamed_note = ""

    if hv_section is None:
        return HvBoardExtract(
            contest_id=contest_id,
            status="draft_stats_without_hv_section",
            rows=(),
            section_name=None,
            skipped_missing_value=0,
            notes=(
                "draftStats present but no highestBoostedValuePlayers section; "
                "HV train path blocked (do not use winning drafts)",
            ),
        )

    skipped = 0
    scored: list[tuple[float, HvBoardRow]] = []
    for raw_row in _as_list(hv_section.get("players")):
        row = _as_dict(raw_row)
        if not row:
            continue
        pid = _player_id(row)
        if pid is None:
            skipped += 1
            continue
        value = _required_float(row, "value", "real_score", "fantasyPoints")
        if value is None:
            skipped += 1
            continue
        raw_boost = _required_float(row, "multiplierBonus", "cardBoost", "card_boost")
        card_boost = 0.0 if force_zero_boost or raw_boost is None else raw_boost
        position = str(row.get("position") or row.get("pos") or "UNK").strip() or "UNK"
        display = str(row.get("displayName") or row.get("name") or "")
        team = str(row.get("teamKey") or row.get("team") or "")
        approx = approx_total_value(real_value=value, card_boost=card_boost)
        provisional = HvBoardRow(
            player_id=pid,
            value=value,
            card_boost=card_boost,
            position=position,
            rank=0,
            approx_total_value=approx,
            display_name=display,
            team_key=team,
        )
        scored.append((approx, provisional))

    if not scored:
        notes = ["hv_section_empty_or_all_rows_missing_value"]
        if unnamed_note:
            notes.insert(0, unnamed_note)
        return HvBoardExtract(
            contest_id=contest_id,
            status="empty_hv_section",
            rows=(),
            section_name=hv_name,
            skipped_missing_value=skipped,
            notes=tuple(notes),
        )

    scored.sort(key=lambda item: (-item[0], item[1].player_id))
    ranked: list[HvBoardRow] = []
    for index, (_approx, player) in enumerate(scored, start=1):
        ranked.append(
            HvBoardRow(
                player_id=player.player_id,
                value=player.value,
                card_boost=player.card_boost,
                position=player.position,
                rank=index,
                approx_total_value=player.approx_total_value,
                display_name=player.display_name,
                team_key=player.team_key,
            )
        )

    notes = [
        f"hv_section={hv_name or TRAINING_LABEL_SECTION}",
        f"n_rows={len(ranked)}",
        f"skipped_missing_value={skipped}",
        "force_zero_boost=" + ("true" if force_zero_boost else "false"),
        "train_target=highestBoostedValuePlayers (never winning drafts)",
    ]
    if unnamed_note:
        notes.insert(0, unnamed_note)
    return HvBoardExtract(
        contest_id=contest_id,
        status="hv_section_present",
        rows=tuple(ranked),
        section_name=hv_name or TRAINING_LABEL_SECTION,
        skipped_missing_value=skipped,
        notes=tuple(notes),
    )


def hv_board_to_high_tv(extract: HvBoardExtract, *, top_n: int = 5) -> HighTvBoard | None:
    """Map a parsed HV extract onto the shared ``oracle_core.high_tv`` board."""

    if not extract.has_train_labels:
        return None
    # Prefer approx Total Value for ranking; fall back already applied in extract.
    values = {row.player_id: row.approx_total_value for row in extract.rows}
    return build_high_tv_board(
        contest_id=extract.contest_id,
        values=values,
        best_possible_player_ids=tuple(row.player_id for row in extract.rows[:top_n]),
        top_n=top_n,
        complete_pool=True,
        has_total_value_board=True,
        source="nhl_highestBoostedValuePlayers",
    )


def hv_rows_to_value_labels(
    extract: HvBoardExtract,
    *,
    season: int,
    game_id: int,
    captured_at: str | None = None,
    source_available_at: str | None = None,
) -> tuple[ValueLabel, ...]:
    """Build train ``ValueLabel`` rows from an HV board extract.

    Raises when the extract is not train-ready so callers cannot silently
    train on an empty or missing HV section.
    """

    if season <= 0:
        raise ValueError("season_must_be_positive")
    if game_id <= 0:
        raise ValueError("game_id_must_be_positive")
    if not extract.has_train_labels:
        raise ValueError(f"hv_labels_unavailable:{extract.status}")

    labels: list[ValueLabel] = []
    for row in extract.rows:
        labels.append(
            ValueLabel(
                player_id=row.player_id,
                game_id=game_id,
                season=season,
                position=row.position,
                value=row.value,
                captured_at=captured_at,
                source_available_at=source_available_at,
                label_role="train_label",
                source_endpoint="stats",
                section=TRAINING_LABEL_SECTION,
                contest_id=extract.contest_id,
                card_boost=row.card_boost,
                label_kind=HighPotentialLabelKind.HIGH_TOTAL_VALUE_BOARD.value,
            )
        )
    return tuple(labels)


def report_hv_corpus_gap(corpus_root: Path | None) -> HvCorpusGap:
    """Scan an NHL corpus root for durable contest HV ``stats.json`` artifacts.

    Observation only: reports readiness; does not invent labels when missing.
    """

    root = Path(corpus_root) if corpus_root is not None else Path("nhl-oracle")
    raw = root / "data" / "raw" / "corpus_nhl"
    if not raw.is_dir():
        return HvCorpusGap(
            corpus_root=str(root),
            contests_scanned=0,
            contests_with_stats=0,
            contests_with_hv_section=0,
            detail=(
                "RS contest HV ingest gap: corpus_nhl raw root absent; "
                "Week 2 audit writes stats under game dirs but no durable "
                f"{TRAINING_LABEL_SECTION} train corpus yet (#526 / #535)"
            ),
        )

    import json

    scanned = 0
    with_stats = 0
    with_hv = 0
    for stats_path in raw.rglob("stats.json"):
        scanned += 1
        try:
            payload = json.loads(stats_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        with_stats += 1
        # Contest id from parent dir when numeric; else hash-stable placeholder.
        parent = stats_path.parent.name
        contest_id = int(parent) if parent.isdigit() else scanned
        extract = extract_hv_board(payload, contest_id=max(1, contest_id))
        if extract.has_train_labels:
            with_hv += 1

    if with_hv == 0:
        detail = (
            "RS contest HV ingest gap: scanned corpus has no "
            f"{TRAINING_LABEL_SECTION} train-ready boards "
            f"(scanned={scanned}, with_stats={with_stats}). "
            "draftStats used for contract/boost audit only until durable "
            "HV contest ingest lands (#526)."
        )
    else:
        detail = f"HV train path ready for {with_hv} contest stats artifact(s) (scanned={scanned})."
    return HvCorpusGap(
        corpus_root=str(root),
        contests_scanned=scanned,
        contests_with_stats=with_stats,
        contests_with_hv_section=with_hv,
        detail=detail,
    )


def filter_train_labels_to_hv(labels: Sequence[ValueLabel]) -> tuple[ValueLabel, ...]:
    """Keep only rows tagged with the HV training section (no silent widen)."""

    return tuple(
        row
        for row in labels
        if row.section == TRAINING_LABEL_SECTION
        or row.label_kind == HighPotentialLabelKind.HIGH_TOTAL_VALUE_BOARD.value
    )

__all__ = [
    'TRAINING_LABEL_SECTION',
    '_as_dict',
    '_as_list',
    '_section_name',
    '_is_hv_section',
    '_player_id',
    '_required_float',
    'approx_total_value',
    'extract_hv_board',
    'hv_board_to_high_tv',
    'hv_rows_to_value_labels',
    'report_hv_corpus_gap',
    'filter_train_labels_to_hv',
]
