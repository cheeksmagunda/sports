from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from nfl_oracle.contests.collector import ContestOutcome
from nfl_oracle.ingest.corpus_g import CorpusGStore
from nfl_oracle.recommendations import dayclose
from nfl_oracle.recommendations.store import RecommendationStore, migrate
from tests.unit.test_recommendation_contracts import NOW, sample_slate

GAME_ID = 1
SEASON = 2026
DAY = NOW.date()


class _FakeRefresh:
    def __init__(
        self,
        corpus_g_store: CorpusGStore,
        *,
        kind: str = "nfl",
        is_finalized: bool = True,
        entrants: int = 100,
    ) -> None:
        self.corpus_g_store = corpus_g_store
        self.kind = kind
        self.is_finalized = is_finalized
        self.entrants = entrants
        self.game_refresh_calls: list[tuple[tuple[int, ...], int]] = []

    async def refresh_contest(self, contest_id: int) -> ContestOutcome:
        return ContestOutcome(
            contest_id, self.kind, is_finalized=self.is_finalized, entrants=self.entrants
        )

    async def refresh_games(self, game_ids: list[int], *, season: int) -> None:
        self.game_refresh_calls.append((tuple(game_ids), season))


class _RaisingRefresh(_FakeRefresh):
    async def refresh_contest(self, contest_id: int) -> ContestOutcome:
        raise RuntimeError("boom")


def _setup_store(tmp_path: Path) -> RecommendationStore:
    engine = create_engine(f"sqlite:///{tmp_path / 'decisions.db'}")
    migrate(engine)
    return RecommendationStore(engine, writable=True, clock=lambda: NOW)


def _freeze_five(store: RecommendationStore) -> dict:
    return store.freeze(
        sample_slate(),
        {"picks": [{"player_id": i} for i in range(1, 6)]},
        model_fingerprint="model-v1",
        input_fingerprint="inputs-v1",
        decision_at=NOW,
    )


def _write_corpus_g_game(root: Path, *, values: dict[int, float]) -> CorpusGStore:
    store = CorpusGStore(root)
    game = {
        "id": GAME_ID,
        "sport": "nfl",
        "isPostProcessed": True,
        "seasonType": "regularseason",
        "season": SEASON,
        "homeTeamId": 1,
        "awayTeamId": 2,
        "dateTime": NOW.isoformat(),
        "postProcessedAt": (NOW + timedelta(hours=4)).isoformat(),
    }
    captured = NOW + timedelta(hours=5)
    store.persist_endpoint(
        game_id=GAME_ID,
        season=SEASON,
        endpoint="feed",
        payload={"game": game, "plays": []},
        source_url="https://example.invalid/feed",
        captured_at=captured,
    )
    boxes = [
        {"playerId": pid, "teamId": (pid - 1) % 2 + 1, "value": value, "position": "WR"}
        for pid, value in values.items()
    ]
    store.persist_endpoint(
        game_id=GAME_ID,
        season=SEASON,
        endpoint="stats",
        payload={"playerBoxScores": boxes},
        source_url="https://example.invalid/stats",
        captured_at=captured,
    )
    return store


def test_frozen_game_ids_reads_distinct_game_ids_from_picks() -> None:
    frozen = {"lineup": {"picks": [{"game_id": 5}, {"game_id": 5}, {"game_id": 7}]}}
    assert dayclose.frozen_game_ids(frozen) == [5, 7]


def test_frozen_game_ids_handles_missing_or_malformed_lineup() -> None:
    assert dayclose.frozen_game_ids({}) == []
    assert dayclose.frozen_game_ids({"lineup": {}}) == []
    assert dayclose.frozen_game_ids({"lineup": {"picks": "not-a-list"}}) == []


def test_grades_a_finalized_day(tmp_path: Path) -> None:
    store = _setup_store(tmp_path)
    _freeze_five(store)
    values = {1: 5.2, 2: 0.2, 3: 3.5, 4: 0.7, 5: 3.3}
    corpus_store = _write_corpus_g_game(tmp_path / "nfl-oracle", values=values)
    refresh = _FakeRefresh(corpus_store)

    result = dayclose.run(store, target_day=DAY, refresh=refresh, catchup_window_days=1)

    assert result["status"] == "success"
    assert result["outcomes"][DAY.isoformat()] == "graded"
    assert refresh.game_refresh_calls == [((GAME_ID,), SEASON)]

    artifact = store.latest_artifact(dayclose.dayclose_grade_kind(DAY))
    assert artifact is not None
    grade = artifact["payload"]["grade"]
    assert grade["status"] == "complete"
    assert grade["total_value"] == pytest.approx(
        5.2 * 2.0 + 0.2 * 1.8 + 3.5 * 1.6 + 0.7 * 1.4 + 3.3 * 1.2
    )
    assert artifact["payload"]["field_size"] == 100


def test_not_finalized_degrades_without_writing_artifact(tmp_path: Path) -> None:
    store = _setup_store(tmp_path)
    _freeze_five(store)
    refresh = _FakeRefresh(CorpusGStore(tmp_path / "nfl-oracle"), is_finalized=False)

    result = dayclose.run(store, target_day=DAY, refresh=refresh, catchup_window_days=1)

    assert result["status"] == "degraded"
    assert result["outcomes"][DAY.isoformat()] == "not_finalized"
    assert store.latest_artifact(dayclose.dayclose_grade_kind(DAY)) is None
    assert refresh.game_refresh_calls == []


def test_no_freeze_for_day_is_not_an_error(tmp_path: Path) -> None:
    store = _setup_store(tmp_path)
    refresh = _FakeRefresh(CorpusGStore(tmp_path / "nfl-oracle"))

    result = dayclose.run(store, target_day=DAY, refresh=refresh, catchup_window_days=1)

    assert result["status"] == "success"
    assert result["outcomes"][DAY.isoformat()] == "no_freeze"


def test_already_graded_day_is_skipped_without_touching_the_network(tmp_path: Path) -> None:
    store = _setup_store(tmp_path)
    _freeze_five(store)
    store.put_artifact(dayclose.dayclose_grade_kind(DAY), {"already": True})
    refresh = _RaisingRefresh(CorpusGStore(tmp_path / "nfl-oracle"))

    result = dayclose.run(store, target_day=DAY, refresh=refresh, catchup_window_days=1)

    assert result["outcomes"][DAY.isoformat()] == "already_graded"
    assert result["status"] == "success"


def test_error_on_one_day_is_isolated_and_reported(tmp_path: Path) -> None:
    store = _setup_store(tmp_path)
    _freeze_five(store)
    refresh = _RaisingRefresh(CorpusGStore(tmp_path / "nfl-oracle"))

    result = dayclose.run(store, target_day=DAY, refresh=refresh, catchup_window_days=1)

    assert result["status"] == "failed"
    assert result["outcomes"][DAY.isoformat()] == "error"
    assert result["details"][DAY.isoformat()] == "RuntimeError"


def test_catchup_window_regrades_an_earlier_missed_day(tmp_path: Path) -> None:
    store = _setup_store(tmp_path)
    _freeze_five(store)
    values = {1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0}
    corpus_store = _write_corpus_g_game(tmp_path / "nfl-oracle", values=values)
    refresh = _FakeRefresh(corpus_store)

    later_target = DAY + timedelta(days=2)
    result = dayclose.run(store, target_day=later_target, refresh=refresh, catchup_window_days=5)

    assert result["outcomes"][later_target.isoformat()] == "no_freeze"
    assert result["outcomes"][DAY.isoformat()] == "graded"


def test_default_day_uses_eastern_yesterday_not_utc(tmp_path: Path) -> None:
    # 2026-09-10T02:00Z is still 2026-09-09 22:00 in US/Eastern (EDT, UTC-4),
    # so "yesterday" relative to the Eastern slate-day must be 2026-09-08, not
    # the UTC-naive 2026-09-09.
    store = _setup_store(tmp_path)
    refresh = _FakeRefresh(CorpusGStore(tmp_path / "nfl-oracle"))
    now = datetime(2026, 9, 10, 2, 0, tzinfo=UTC)

    result = dayclose.run(store, now=now, refresh=refresh, catchup_window_days=1)

    assert result["processed_day"] == "2026-09-08"
