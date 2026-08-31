import datetime as dt

from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.scheduler.freshness import assess_publish_freshness

NOW = dt.datetime(2026, 8, 31, 18, 0, tzinfo=dt.UTC)
LOCK = NOW + dt.timedelta(hours=1)


def _row(pid: int = 1, *, captured_at: object = NOW) -> dict:
    return {
        "real_sports_player_id": pid,
        "captured_at": captured_at,
        "features_json": {
            "injury_status": "",
            "recent_minutes": 28.0,
            "per_min_rate": 0.9,
        },
    }


def _fields() -> list[FieldPlayerSpec]:
    return [
        FieldPlayerSpec(player_id=pid, pred_real_score=1.0 + pid / 10, card_boost=0.0)
        for pid in range(1, 6)
    ]


def _assessment(rows: list[dict] | None = None, **kwargs):
    rows = rows or [_row(pid) for pid in range(1, 6)]
    return assess_publish_freshness(
        rows,
        projection_by_pid={row["real_sports_player_id"]: {"pred_real_score_p50": 1.0} for row in rows},
        field_specs=_fields(),
        lock_time=LOCK,
        now_utc=NOW,
        **kwargs,
    )


def test_fresh_complete_inputs_are_publishable() -> None:
    result = _assessment()
    assert result.ready is True
    assert result.reasons == ()


def test_missing_lock_blocks_publish() -> None:
    result = assess_publish_freshness(
        [_row(pid) for pid in range(1, 6)],
        projection_by_pid={pid: {} for pid in range(1, 6)},
        field_specs=_fields(),
        lock_time=None,
        now_utc=NOW,
    )
    assert "slate_lock_missing" in result.reasons


def test_stale_capture_blocks_publish() -> None:
    result = _assessment([_row(pid, captured_at=NOW - dt.timedelta(hours=7)) for pid in range(1, 6)])
    assert "source_capture_stale" in result.reasons


def test_missing_minutes_blocks_publish() -> None:
    rows = [_row(pid) for pid in range(1, 6)]
    rows[0]["features_json"].pop("recent_minutes")
    rows[1]["features_json"].pop("recent_minutes")
    assert "minutes_coverage_insufficient" in _assessment(rows).reasons


def test_missing_injury_status_blocks_publish() -> None:
    rows = [_row(pid) for pid in range(1, 6)]
    rows[0]["features_json"].pop("injury_status")
    assert "injury_status_missing" in _assessment(rows).reasons


def test_missing_projection_blocks_publish() -> None:
    rows = [_row(pid) for pid in range(1, 6)]
    result = assess_publish_freshness(
        rows,
        projection_by_pid={pid: {} for pid in range(1, 5)},
        field_specs=_fields(),
        lock_time=LOCK,
        now_utc=NOW,
    )
    assert "projection_missing" in result.reasons
