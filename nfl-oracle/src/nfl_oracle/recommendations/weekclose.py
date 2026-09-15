"""Week-close punch-list producer: audit a full NFL week's freezes, grades,
and on-disk contests, then emit a prioritized list of model/infra findings.

Sibling to dayclose.py, but read-only over the same evidence: freezes and
dayclose_grade artifacts already in the RecommendationStore, plus any
finalized Corpus C contest already saved to disk. Session-free by
construction, so unit tests never need a live Real Sports session -- the
caller supplies an already-loaded schedule (offline CSV or fixture rows) and
an optional ContestStore.

This module never trains, retrains, or otherwise touches model.py,
optimizer.py, or pipeline.py. Findings are inputs to the issue/PR flow, not
automated corrections.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from nfl_oracle.calendar.schedule import ScheduledGame
from nfl_oracle.calendar.slate import SlateResolution, resolve_slate
from nfl_oracle.contests.parse import load_contest
from nfl_oracle.contests.store import ContestStore
from nfl_oracle.recommendations.dayclose import dayclose_grade_kind
from nfl_oracle.recommendations.store import RecommendationStore
from nfl_oracle.replay.harness import replay_contest

WEEKCLOSE_PUNCHLIST_KIND_PREFIX = "weekclose_punchlist"


def weekclose_punchlist_kind(season: int, week: int) -> str:
    return f"{WEEKCLOSE_PUNCHLIST_KIND_PREFIX}:{season}-W{week:02d}"


@dataclass(frozen=True)
class PunchItem:
    priority: int
    category: str  # "model" | "infra"
    title: str
    detail: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "priority": self.priority,
            "category": self.category,
            "title": self.title,
            "detail": self.detail,
            "evidence": self.evidence,
        }


def resolve_week_gamedays(
    games: Sequence[ScheduledGame],
    *,
    season: int | None = None,
    week: int | None = None,
    as_of: date | None = None,
) -> tuple[SlateResolution, list[date]]:
    """Resolve the target week from explicit season+week or an as-of date.

    Delegates entirely to calendar.slate.resolve_slate; never re-parses or
    re-derives schedule rows.
    """

    slate = resolve_slate(games, season=season, week=week, day=as_of)
    gamedays = sorted({g.gameday for g in slate.games if g.gameday is not None})
    return slate, gamedays


def _replay_metrics(contest_store: ContestStore | None, contest_id: Any) -> dict[str, Any] | None:
    if contest_store is None or not isinstance(contest_id, int):
        return None
    parsed = load_contest(contest_store, contest_id)
    if parsed is None:
        return None
    result = replay_contest(parsed)
    return {
        "contest_id": result.contest_id,
        "entrants": result.entrants,
        "winner_capture_ratio": result.winner_capture_ratio,
        "optimal_order_rate": (
            result.entries_optimally_ordered / result.entries_scored
            if result.entries_scored
            else None
        ),
        "entries_scored": result.entries_scored,
    }


def _gameday_row(
    store: RecommendationStore,
    contest_store: ContestStore | None,
    day: date,
) -> dict[str, Any]:
    frozen = store.latest(day)
    grade_artifact = store.latest_artifact(dayclose_grade_kind(day))
    grade_status = grade_artifact["payload"]["grade"]["status"] if grade_artifact else None

    row: dict[str, Any] = {
        "day": day.isoformat(),
        "freeze_status": "frozen" if frozen is not None else "no_freeze",
        "grade_status": grade_status,
        "model_fingerprint": frozen.get("model_fingerprint") if frozen else None,
        "decision_at": frozen.get("decision_at") if frozen else None,
        "replay": _replay_metrics(contest_store, frozen.get("contest_id")) if frozen else None,
    }
    return row


def _model_fingerprint_finding(rows: list[dict[str, Any]]) -> PunchItem | None:
    """Never retrains; only observes whether the week used one steady-state
    model or silently switched mid-week, which the operator should confirm
    was an intentional retrain rather than a worker-side accident.
    """

    fingerprints = sorted({row["model_fingerprint"] for row in rows if row["model_fingerprint"]})
    if len(fingerprints) <= 1:
        return None
    return PunchItem(
        priority=2,
        category="model",
        title="Model fingerprint changed within the week",
        detail=(
            "More than one model_fingerprint froze this week's slates. Confirm an "
            "intentional retrain occurred rather than an unplanned worker restart."
        ),
        evidence={"fingerprints": fingerprints},
    )


def _punch_list_for_rows(rows: list[dict[str, Any]]) -> list[PunchItem]:
    items: list[PunchItem] = []
    for row in rows:
        if row["freeze_status"] == "no_freeze":
            items.append(
                PunchItem(
                    priority=1,
                    category="infra",
                    title=f"No freeze recorded for {row['day']}",
                    detail=(
                        "The week's schedule has a slate on this gameday but no frozen "
                        "lineup was recorded by the worker."
                    ),
                    evidence={"day": row["day"]},
                )
            )
        elif row["grade_status"] == "incomplete":
            items.append(
                PunchItem(
                    priority=2,
                    category="infra",
                    title=f"Dayclose grade incomplete for {row['day']}",
                    detail=(
                        "A dayclose_grade artifact exists for this day but did not "
                        "finalize all five picks."
                    ),
                    evidence={"day": row["day"], "grade_status": row["grade_status"]},
                )
            )
    fingerprint_finding = _model_fingerprint_finding(rows)
    if fingerprint_finding is not None:
        items.append(fingerprint_finding)
    items.sort(key=lambda item: item.priority)
    return items


def build_week_punch_list(
    store: RecommendationStore,
    games: Sequence[ScheduledGame],
    *,
    season: int | None = None,
    week: int | None = None,
    as_of: date | None = None,
    contest_store: ContestStore | None = None,
) -> dict[str, Any]:
    """Audit one NFL week's gamedays and emit a prioritized punch list.

    Read-only: never freezes, grades, retrains, or submits a contest entry.
    """

    slate, gamedays = resolve_week_gamedays(games, season=season, week=week, as_of=as_of)
    if not slate.resolved:
        return {
            "contest_entry": False,
            "resolved": False,
            "season": slate.season,
            "week": slate.week,
            "note": slate.note,
            "gamedays": [],
            "rows": [],
            "punch_list": [],
        }

    rows = [_gameday_row(store, contest_store, day) for day in gamedays]
    punch_list = _punch_list_for_rows(rows)

    return {
        "contest_entry": False,
        "resolved": True,
        "season": slate.season,
        "week": slate.week,
        "gamedays": [day.isoformat() for day in gamedays],
        "rows": rows,
        "punch_list": [item.to_dict() for item in punch_list],
        "note": (
            "Findings are inputs to the issue/PR flow; this producer never trains, "
            "retrains, or otherwise changes models."
        ),
    }


def build_and_persist_week_punch_list(
    store: RecommendationStore,
    games: Sequence[ScheduledGame],
    *,
    season: int | None = None,
    week: int | None = None,
    as_of: date | None = None,
    contest_store: ContestStore | None = None,
) -> dict[str, Any]:
    """Same as build_week_punch_list, plus a best-effort artifact write.

    Mirrors dayclose's put_artifact pattern: content-addressed, written once.
    Silently skipped for a read-only store or an unresolved week.
    """

    result = build_week_punch_list(
        store, games, season=season, week=week, as_of=as_of, contest_store=contest_store
    )
    if result["resolved"] and store.writable:
        store.put_artifact(weekclose_punchlist_kind(result["season"], result["week"]), result)
    return result
