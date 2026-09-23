from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest

from nfl_oracle.calendar.schedule import ScheduledGame
from nfl_oracle.recommendations.model import HistoricalPerformance, fit_model
from nfl_oracle.recommendations.pipeline import (
    ModelBundle,
    RecommendationPipeline,
    model_staleness_reason,
    model_weekly_retrain_boundary,
)

BASE = datetime(2026, 9, 1, 12, tzinfo=UTC)


def _history_rows() -> list[HistoricalPerformance]:
    rows: list[HistoricalPerformance] = []
    for game in range(6):
        kickoff = BASE + timedelta(days=game)
        for player in range(1, 7):
            rows.append(
                HistoricalPerformance(
                    player_id=player,
                    external_id=f"p-{player}",
                    game_id=1000 + game * 10 + player,
                    position="WR",
                    kickoff_at=kickoff,
                    available_at=kickoff + timedelta(hours=2),
                    captured_at=kickoff + timedelta(hours=3),
                    value=float(player + game),
                    did_not_play=False,
                )
            )
    return rows


def _schedule_games() -> tuple[ScheduledGame, ...]:
    return (
        ScheduledGame(
            season=2026,
            week=2,
            game_id="2026_02_TNF",
            gameday=date(2026, 9, 17),
            home_team="KC",
            away_team="DEN",
        ),
        ScheduledGame(
            season=2026,
            week=2,
            game_id="2026_02_SNF",
            gameday=date(2026, 9, 20),
            home_team="DAL",
            away_team="PHI",
        ),
    )


def _bundle(*, trained_at: datetime) -> ModelBundle:
    history = tuple(_history_rows())
    model = fit_model(history, trained_at=trained_at)
    return ModelBundle(
        model=model,
        history=history,
        source_hashes=("a" * 64,),
        audit={"history_rows": len(history)},
    )


class _Store:
    def __init__(self, bundle: ModelBundle) -> None:
        self.bundle = bundle

    def latest_artifact(self, kind: str) -> dict[str, object] | None:
        if kind != "active_model":
            return None
        return {"payload": {"model_sha256": "bundle-sha"}}

    def get_artifact(self, sha256: str) -> dict[str, object] | None:
        if sha256 != "bundle-sha":
            return None
        return {"kind": "model_bundle", "payload": self.bundle.model_dump(mode="json")}


def test_weekly_boundary_anchors_to_the_slate_week_tuesday() -> None:
    decision_at = datetime(2026, 9, 20, 17, tzinfo=UTC)

    boundary = model_weekly_retrain_boundary(decision_at, _schedule_games())

    assert boundary is not None
    assert boundary == datetime(2026, 9, 15, 4, tzinfo=UTC)


@pytest.mark.parametrize(
    ("decision_at", "trained_at"),
    [
        (
            datetime(2026, 9, 17, 18, tzinfo=UTC),
            datetime(2026, 9, 15, 12, tzinfo=UTC),
        ),
        (
            datetime(2026, 9, 20, 17, tzinfo=UTC),
            datetime(2026, 9, 19, 3, tzinfo=UTC),
        ),
    ],
)
def test_model_trained_this_week_stays_fresh_through_tnf_and_sunday(
    decision_at: datetime,
    trained_at: datetime,
) -> None:
    assert (
        model_staleness_reason(
            trained_at=trained_at,
            decision_at=decision_at,
            max_age_days=8,
            schedule_games=_schedule_games(),
        )
        is None
    )


def test_weekly_boundary_refuses_missed_retrain_even_when_fixed_day_ttl_would_pass() -> None:
    decision_at = datetime(2026, 9, 17, 18, tzinfo=UTC)
    trained_at = datetime(2026, 9, 14, 23, 59, tzinfo=UTC)

    assert (
        model_staleness_reason(
            trained_at=trained_at,
            decision_at=decision_at,
            max_age_days=8,
            schedule_games=_schedule_games(),
        )
        == "model_stale_for_nfl_week"
    )


def test_fixed_day_backstop_still_refuses_old_models_when_week_boundary_cannot_help() -> None:
    decision_at = datetime(2026, 9, 20, 17, tzinfo=UTC)
    trained_at = decision_at - timedelta(days=9)

    assert (
        model_staleness_reason(
            trained_at=trained_at,
            decision_at=decision_at,
            max_age_days=8,
            schedule_games=(),
        )
        == "model_stale_or_future"
    )


def test_active_model_uses_weekly_boundary_before_the_fixed_day_backstop() -> None:
    pipeline = RecommendationPipeline(
        _Store(_bundle(trained_at=datetime(2026, 9, 14, 23, 59, tzinfo=UTC))),
        clock=lambda: datetime(2026, 9, 17, 18, tzinfo=UTC),
        schedule_games=_schedule_games(),
    )

    with pytest.raises(ValueError, match="model_stale_for_nfl_week"):
        pipeline.active_model()
