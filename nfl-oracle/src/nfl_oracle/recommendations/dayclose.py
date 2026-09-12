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

The catch-up sweep itself (attempt a day, isolate one day's failure, retry a
bounded window of earlier ungraded days) is provider-neutral orchestration
shared with every other sport application; that shape lives in
oracle_core.dayclose.run_sweep. This module supplies only the NFL-specific
`close_one_day` callback and the NFL-specific default target day.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from oracle_core.dayclose import DayCloseOutcome, default_target_day, run_sweep
from oracle_core.jobs import JobStatus

from nfl_oracle.calendar.season import season_label_for_date
from nfl_oracle.common.paths import resolve_project_root
from nfl_oracle.contests.collector import ContestOutcome, ContestScanner
from nfl_oracle.contests.parse import load_contest
from nfl_oracle.contests.store import ContestStore
from nfl_oracle.ingest.corpus_g import CorpusGStore, ingest_game
from nfl_oracle.ingest.realsports import capture_live_headers, headers_or_capture
from nfl_oracle.recommendations.grading import grade_frozen_lineup
from nfl_oracle.recommendations.history import load_history
from nfl_oracle.recommendations.store import RecommendationStore

DAYCLOSE_GRADE_KIND_PREFIX = "dayclose_grade"
DEFAULT_CATCHUP_WINDOW_DAYS = 7
EASTERN = ZoneInfo("America/New_York")

# grade_day's steady-state outcomes: a successful grade, or an idempotent
# no-decision case, neither of which should make a sweep report "degraded".
# "not_finalized", "contest_unresolved", and "no_performances" are left out
# on purpose -- each means a day that still needs attention.
SETTLED_STATUSES = frozenset({"graded", "already_graded", "no_freeze", "no_game_ids"})


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


def _slate_results(contest_store: ContestStore, contest_id: int) -> dict[str, Any] | None:
    """Full-field results for the whole contest: leaderboard and every
    player's draft stats, not just our own five picks.

    Built entirely from the existing, tested contests.parse.load_contest,
    which already parses and law-verifies the same entries.json/stats.json
    routes RealSportsRefresh.refresh_contest just wrote to disk.
    """

    parsed = load_contest(contest_store, contest_id)
    if parsed is None:
        return None
    return {
        "contest": parsed.contest.model_dump(mode="json"),
        "top_entries": [entry.model_dump(mode="json") for entry in parsed.entries],
        "player_draft_stats": [row.model_dump(mode="json") for row in parsed.draft_stats],
        "law_verified": parsed.law_verified,
        "missing_routes": list(parsed.missing_routes),
    }


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
    project_root: Path,
) -> DayCloseOutcome:
    """Grade one day's frozen lineup against finalized results, if ready."""

    if store.latest_artifact(dayclose_grade_kind(day)) is not None:
        return DayCloseOutcome(day, "already_graded")

    frozen = store.latest(day)
    if frozen is None:
        return DayCloseOutcome(day, "no_freeze")

    contest_id = int(frozen["contest_id"])
    outcome = asyncio.run(refresh.refresh_contest(contest_id))
    if outcome.kind != "nfl":
        return DayCloseOutcome(day, "contest_unresolved", detail=outcome.kind)
    if not outcome.is_finalized:
        return DayCloseOutcome(day, "not_finalized")

    game_ids = frozen_game_ids(frozen)
    if not game_ids:
        return DayCloseOutcome(day, "no_game_ids")

    asyncio.run(refresh.refresh_games(game_ids, season=season))

    rows, excluded = load_history(refresh.corpus_g_store.raw_root)
    wanted = set(game_ids)
    performances = [row for row in rows if row.game_id in wanted]
    if not performances:
        return DayCloseOutcome(day, "no_performances", detail=str(excluded))

    report = grade_frozen_lineup(frozen, performances)
    payload = {
        "schema_version": 2,
        "day": day.isoformat(),
        "contest_id": contest_id,
        "field_size": outcome.entrants,
        "grade": report.model_dump(mode="json"),
        "slate_results": _slate_results(ContestStore(project=project_root), contest_id),
    }
    store.put_artifact(dayclose_grade_kind(day), payload)
    return DayCloseOutcome(day, "graded", detail=report.status)


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

    Delegates the sweep shape to oracle_core.dayclose.run_sweep; only the
    exit-code mapping below is NFL-owned. run_sweep's JobResult.exit_code
    maps DEGRADED to a non-zero code, which is right for a generic job
    runner but wrong here: a day that is not finalized yet and will be
    retried tomorrow is not an incident. The CLI checks this dict's
    "status" string directly rather than JobResult.exit_code, so only
    "failed" (an uncaught exception in a single day's grading) is
    non-zero.
    """

    root = project_root or resolve_project_root(__file__)
    live = refresh or RealSportsRefresh(project_root=root)
    current = now or datetime.now(UTC)
    day = target_day or default_target_day(current, EASTERN)

    def close_one_day(target: date) -> DayCloseOutcome:
        return grade_day(
            store, live, target, season=season_label_for_date(target), project_root=root
        )

    job_result = run_sweep(
        target_day=day,
        close_one_day=close_one_day,
        catchup_window_days=catchup_window_days,
        settled_statuses=SETTLED_STATUSES,
    )

    if job_result.status == JobStatus.FAILED:
        status = "failed"
    elif job_result.status == JobStatus.DEGRADED:
        status = "degraded"
    else:
        status = "success"
    return {
        "status": status,
        "processed_day": job_result.details["processed_day"],
        "outcomes": job_result.details["outcomes"],
        "details": job_result.details["details"],
    }
