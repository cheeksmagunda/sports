"""Day-close grading: score a frozen NFL lineup against finalized real-world
results, and extend the historical corpus by one slate.

Never touches pipeline.py, model.py, optimizer.py, or the worker loop. Reads
an already-frozen lineup, force-refreshes the corresponding Corpus C contest
and Corpus G game(s), grades with the existing grading.grade_frozen_lineup,
and writes a new dayclose_grade artifact via the existing
RecommendationStore.put_artifact. Gracefully degrades (never raises for a
single day's incomplete data) so a bounded catch-up window can retry a
later-finalizing contest on a subsequent run.

The Corpus C scan cursor and the Corpus G backfill resume cursor both treat
"already fetched once" as permanently resolved, which is correct for a
historical sweep but wrong here: this job's entire purpose is to re-check a
contest and its games after they may have finalized since an earlier,
pregame capture. Both refreshes below call the underlying single-item fetch
directly (ContestScanner.collect, ingest_game) instead of the cursor-aware
wrappers, so a day-close run always sees current data.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from nfl_oracle.calendar.season import season_label_for_date
from nfl_oracle.common.paths import resolve_project_root
from nfl_oracle.contests.collector import ContestOutcome, ContestScanner
from nfl_oracle.contests.store import ContestStore
from nfl_oracle.ingest.corpus_g import CorpusGStore, ingest_game
from nfl_oracle.ingest.realsports import capture_live_headers, headers_or_capture
from nfl_oracle.recommendations.grading import grade_frozen_lineup
from nfl_oracle.recommendations.history import load_history
from nfl_oracle.recommendations.store import RecommendationStore

DAYCLOSE_GRADE_KIND_PREFIX = "dayclose_grade"
DEFAULT_CATCHUP_WINDOW_DAYS = 7
EASTERN = ZoneInfo("America/New_York")


def dayclose_grade_kind(day: date) -> str:
    return f"{DAYCLOSE_GRADE_KIND_PREFIX}:{day.isoformat()}"


def frozen_game_ids(frozen: dict[str, Any]) -> list[int]:
    lineup = frozen.get("lineup") if isinstance(frozen.get("lineup"), dict) else {}
    picks = lineup.get("picks") if isinstance(lineup, dict) else None
    if not isinstance(picks, list):
        return []
    ids: set[int] = set()
    for pick in picks:
        if isinstance(pick, dict) and "game_id" in pick:
            ids.add(int(pick["game_id"]))
    return sorted(ids)


@dataclass(frozen=True)
class DaycloseResult:
    day: date
    status: str
    detail: str = ""


class RealSportsRefresh:
    """Live, read-only refresh of one day's Corpus C contest and Corpus G games."""

    def __init__(self, *, project_root: Path, corpus_g_store: CorpusGStore | None = None) -> None:
        self.project_root = project_root
        self.corpus_g_store = corpus_g_store or CorpusGStore(project_root)

    async def refresh_contest(self, contest_id: int) -> ContestOutcome:
        headers = await headers_or_capture()
        store = ContestStore(project=self.project_root)
        async with httpx.AsyncClient(timeout=30) as client:
            scanner = ContestScanner(client, headers, store, refresh_headers=capture_live_headers)
            return await scanner.collect(contest_id)

    async def refresh_games(self, game_ids: Sequence[int], *, season: int) -> None:
        headers = await headers_or_capture()
        async with httpx.AsyncClient(timeout=60.0) as client:
            for game_id in game_ids:
                await ingest_game(
                    game_id=game_id,
                    store=self.corpus_g_store,
                    client=client,
                    headers=headers,
                    refresh_headers=capture_live_headers,
                    season_hint=season,
                )


def grade_day(
    store: RecommendationStore,
    refresh: RealSportsRefresh,
    day: date,
    *,
    season: int,
) -> DaycloseResult:
    """Grade one day's frozen lineup against finalized results, if ready."""

    if store.latest_artifact(dayclose_grade_kind(day)) is not None:
        return DaycloseResult(day, "already_graded")

    frozen = store.latest(day)
    if frozen is None:
        return DaycloseResult(day, "no_freeze")

    contest_id = int(frozen["contest_id"])
    outcome = asyncio.run(refresh.refresh_contest(contest_id))
    if outcome.kind != "nfl":
        return DaycloseResult(day, "contest_unresolved", detail=outcome.kind)
    if not outcome.is_finalized:
        return DaycloseResult(day, "not_finalized")

    game_ids = frozen_game_ids(frozen)
    if not game_ids:
        return DaycloseResult(day, "no_game_ids")

    asyncio.run(refresh.refresh_games(game_ids, season=season))

    rows, excluded = load_history(refresh.corpus_g_store.raw_root)
    wanted = set(game_ids)
    performances = [row for row in rows if row.game_id in wanted]
    if not performances:
        return DaycloseResult(day, "no_performances", detail=str(excluded))

    report = grade_frozen_lineup(frozen, performances)
    payload = {
        "schema_version": 1,
        "day": day.isoformat(),
        "contest_id": contest_id,
        "field_size": outcome.entrants,
        "grade": report.model_dump(mode="json"),
    }
    store.put_artifact(dayclose_grade_kind(day), payload)
    return DaycloseResult(day, "graded", detail=report.status)


def run(
    store: RecommendationStore,
    *,
    project_root: Path | None = None,
    target_day: date | None = None,
    catchup_window_days: int = DEFAULT_CATCHUP_WINDOW_DAYS,
    now: datetime | None = None,
    refresh: RealSportsRefresh | None = None,
) -> dict[str, Any]:
    """Grade `target_day` (default: yesterday in US/Eastern), then sweep a
    bounded catch-up window for recent days with a freeze but no grade yet.

    Never raises for an individual day's incomplete or unready data; a day
    that cannot be graded is reported in `outcomes`, not a failure of the
    whole run. Only an unexpected exception in a single day's grading is
    caught and reported as that day's "error" outcome, so one bad day cannot
    prevent the catch-up sweep from covering the rest of the window.
    """

    root = project_root or resolve_project_root(__file__)
    live = refresh or RealSportsRefresh(project_root=root)
    current = now or datetime.now(UTC)
    eastern_today = current.astimezone(EASTERN).date()
    day = target_day or (eastern_today - timedelta(days=1))

    outcomes: dict[str, str] = {}
    details: dict[str, str] = {}

    def attempt(target: date) -> None:
        try:
            result = grade_day(store, live, target, season=season_label_for_date(target))
        except Exception as error:  # noqa: BLE001 - degrade, never fail the whole run
            outcomes[target.isoformat()] = "error"
            details[target.isoformat()] = type(error).__name__
            return
        outcomes[target.isoformat()] = result.status
        if result.detail:
            details[target.isoformat()] = result.detail

    attempt(day)
    for offset in range(1, catchup_window_days):
        candidate = day - timedelta(days=offset)
        if candidate.isoformat() in outcomes:
            continue
        if store.latest(candidate) is None:
            continue
        if store.latest_artifact(dayclose_grade_kind(candidate)) is not None:
            continue
        attempt(candidate)

    settled = {"graded", "already_graded", "no_freeze", "no_game_ids"}
    failed_days = [d for d, s in outcomes.items() if s == "error"]
    if failed_days:
        status = "failed"
    elif any(s not in settled for s in outcomes.values()):
        status = "degraded"
    else:
        status = "success"
    return {
        "status": status,
        "processed_day": day.isoformat(),
        "outcomes": outcomes,
        "details": details,
    }
