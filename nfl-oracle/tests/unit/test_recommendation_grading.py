from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from nfl_oracle.recommendations.grading import grade_frozen_lineup, replay_leaderboard
from nfl_oracle.recommendations.model import HistoricalPerformance
from nfl_oracle.recommendations.schema import fingerprint

NOW = datetime(2026, 9, 9, 12, tzinfo=UTC)


def freeze(*, ids: tuple[int, ...] = (1, 2, 3, 4, 5), boosts: tuple[float, ...] | None = None):
    boosts = boosts or (0.0,) * 5
    body = {
        "schema_version": 1,
        "slate_date": "2026-09-09",
        "contest_id": 2141,
        "lineup": {
            "picks": [
                {
                    "player_id": pid,
                    "game_id": 700,
                    "slot": slot,
                    "card_boost": boosts[slot - 1],
                    "slot_multiplier": (2.0, 1.8, 1.6, 1.4, 1.2)[slot - 1],
                }
                for slot, pid in enumerate(ids, 1)
            ]
        },
    }
    return {**body, "digest": fingerprint(body)}


def labels(ids: tuple[int, ...] = (1, 2, 3, 4, 5)) -> list[HistoricalPerformance]:
    return [
        HistoricalPerformance(
            player_id=pid,
            game_id=700,
            position="WR",
            kickoff_at=NOW - timedelta(days=1),
            available_at=NOW,
            captured_at=NOW,
            value=float(pid if pid < 5 else -5),
        )
        for pid in ids
    ]


def test_grade_uses_frozen_slots_boosts_and_negative_values() -> None:
    report = grade_frozen_lineup(freeze(boosts=(3, 2, 1, 0, 0)), labels())
    assert report.status == "complete"
    assert report.finalized_count == 5
    assert report.total_value == pytest.approx(1 * 5 + 2 * 3.8 + 3 * 2.6 + 4 * 1.4 + -5 * 1.2)
    assert report.picks[0].player_boost == 3
    assert report.picks[-1].actual_real_score == -5
    assert report.picks[-1].total_value == -6


def test_grade_reports_missing_finalized_rows_without_total() -> None:
    report = grade_frozen_lineup(freeze(), labels((1, 2, 3, 4)))
    assert report.status == "incomplete"
    assert report.finalized_count == 4
    assert report.missing_player_ids == (5,)
    assert report.total_value is None


def test_replay_calculates_regret_only_across_supplied_frozen_lineups() -> None:
    first = freeze()
    competitor = freeze(ids=(5, 4, 3, 2, 1))
    replay = replay_leaderboard(first, labels(), [competitor])
    assert replay.status == "complete"
    assert len(replay.entries) == 2
    assert replay.holdout_regret == pytest.approx(0)
    assert all(entry.rank is not None for entry in replay.entries)


def test_replay_does_not_claim_regret_with_incomplete_labels() -> None:
    replay = replay_leaderboard(freeze(), labels((1, 2, 3, 4)))
    assert replay.status == "incomplete"
    assert replay.holdout_regret is None
    assert replay.entries[0].rank is None
