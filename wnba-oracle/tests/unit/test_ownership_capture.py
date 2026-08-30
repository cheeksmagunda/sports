"""D90/#38: job2's post-freeze projected-ownership recording.

_record_projected_ownership_safe runs after the freeze has already
succeeded, so it must never raise regardless of what fails inside it.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from wnba_oracle.picker.field import FieldPlayerSpec
from wnba_oracle.scheduler import job2

_FIELDS = [
    FieldPlayerSpec(player_id=101, pred_real_score=2.0, card_boost=0.5, measured_drafts=4.0),
    FieldPlayerSpec(player_id=102, pred_real_score=1.0, card_boost=0.2),
]


def test_records_projected_ownership_for_every_field_player() -> None:
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = MagicMock()
    engine.begin.return_value.__exit__.return_value = None

    with (
        patch("wnba_oracle.db.engine.get_engine", return_value=engine),
        patch("wnba_oracle.scheduler.placements.record_projected_ownership") as record,
    ):
        record.return_value = 2
        job2._record_projected_ownership_safe("2026-08-30", _FIELDS)

    record.assert_called_once()
    kwargs = record.call_args.kwargs
    assert kwargs["slate_date"] == "2026-08-30"
    assert set(kwargs["projected_ownership"]) == {101, 102}
    assert abs(sum(kwargs["projected_ownership"].values()) - 1.0) < 1e-9
    # Only player 101 carried a measured draft count.
    assert kwargs["projected_drafts"] == {101: 4}


def test_never_raises_when_engine_is_unavailable() -> None:
    with patch("wnba_oracle.db.engine.get_engine", side_effect=RuntimeError("no db")):
        job2._record_projected_ownership_safe("2026-08-30", _FIELDS)  # must not raise


def test_never_raises_when_writer_fails() -> None:
    engine = MagicMock()
    engine.begin.return_value.__enter__.return_value = MagicMock()
    engine.begin.return_value.__exit__.return_value = None

    with (
        patch("wnba_oracle.db.engine.get_engine", return_value=engine),
        patch(
            "wnba_oracle.scheduler.placements.record_projected_ownership",
            side_effect=Exception("boom"),
        ),
    ):
        job2._record_projected_ownership_safe("2026-08-30", _FIELDS)  # must not raise


def test_empty_fields_records_nothing() -> None:
    with patch("wnba_oracle.scheduler.placements.record_projected_ownership") as record:
        job2._record_projected_ownership_safe("2026-08-30", [])
    record.assert_not_called()
