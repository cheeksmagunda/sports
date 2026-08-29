"""Placement catch-up sweep: recent slates with a frozen lineup but no
contest_placements row must eventually be revisited, not lost forever once
they stop being "yesterday".

See MODEL_PICK_POSTMORTEM_2026-08-28.md ("Task B") for the incident this
closes: 2026-08-28's dayclose run came back degraded because slate_labels /
contest_leaderboards weren't populated yet, and nothing ever re-invoked
_auto_record_placement for that date again once a later run's "yesterday"
moved past it.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import polars as pl

from wnba_oracle.scheduler import job_dayclose

YESTERDAY = "2026-08-27"


def _patched_find(candidates: list[str]):
    return patch.object(job_dayclose, "_find_slates_missing_placement", return_value=candidates)


# ---------------------------------------------------------------------------
# _catch_up_missing_placements: sweep orchestration
# ---------------------------------------------------------------------------


def test_catchup_fills_exactly_one_missing_older_date() -> None:
    """One older date is missing a placement; the sweep finds it, records it,
    and reports it as recorded -- without touching yesterday itself (that is
    a separate, already-existing call in run())."""
    record = MagicMock(return_value={"status": "success", "entry_rank": 5})
    with (
        _patched_find(["2026-08-20"]),
        patch.object(job_dayclose, "_auto_record_placement", record),
    ):
        outcome = job_dayclose._catch_up_missing_placements(YESTERDAY)

    record.assert_called_once_with("2026-08-20")
    assert outcome == {
        "status": "success",
        "dates_checked": 1,
        "dates_recorded": ["2026-08-20"],
        "dates_still_missing": [],
    }


def test_catchup_leaves_still_missing_date_degraded_with_no_write() -> None:
    """A candidate date whose slate_labels/contest_leaderboards still aren't
    available must come back degraded, going through the exact same
    _auto_record_placement path (and therefore the exact same "no write"
    behavior) as the primary yesterday-only call."""
    degraded_outcome = {"status": "degraded", "reason": "missing_labels_or_leaderboard"}
    record = MagicMock(return_value=degraded_outcome)
    with (
        _patched_find(["2026-08-20"]),
        patch.object(job_dayclose, "_auto_record_placement", record),
    ):
        outcome = job_dayclose._catch_up_missing_placements(YESTERDAY)

    record.assert_called_once_with("2026-08-20")
    assert outcome["status"] == "degraded"
    assert outcome["dates_recorded"] == []
    assert outcome["dates_still_missing"] == [{"slate_date": "2026-08-20", **degraded_outcome}]


def test_catchup_is_a_noop_when_no_candidates_found() -> None:
    """No candidates (the common case once the backlog is cleared) does no
    work and stays success."""
    record = MagicMock()
    with (
        _patched_find([]),
        patch.object(job_dayclose, "_auto_record_placement", record),
    ):
        outcome = job_dayclose._catch_up_missing_placements(YESTERDAY)

    record.assert_not_called()
    assert outcome == {"status": "success", "dates_checked": 0, "dates_recorded": []}


def test_catchup_rerun_is_idempotent_once_a_date_is_captured() -> None:
    """Re-running the sweep daily must be a cheap no-op once a date has been
    captured. Because the candidate list itself comes from a "zero
    contest_placements rows" filter (_find_slates_missing_placement), a date
    that was just recorded is excluded from the NEXT scan -- simulate that by
    having the scan return the date once, then not again."""
    record = MagicMock(return_value={"status": "success", "entry_rank": 5})
    with (
        _patched_find(["2026-08-20"]),
        patch.object(job_dayclose, "_auto_record_placement", record),
    ):
        first = job_dayclose._catch_up_missing_placements(YESTERDAY)

    assert first["dates_recorded"] == ["2026-08-20"]
    record.assert_called_once_with("2026-08-20")

    # Next run's scan no longer surfaces 2026-08-20 (it now has a
    # contest_placements row), so the sweep must not re-attempt it.
    record.reset_mock()
    with (
        _patched_find([]),
        patch.object(job_dayclose, "_auto_record_placement", record),
    ):
        second = job_dayclose._catch_up_missing_placements(YESTERDAY)

    record.assert_not_called()
    assert second == {"status": "success", "dates_checked": 0, "dates_recorded": []}


def test_catchup_scan_failure_is_degraded_not_raised() -> None:
    """A DB error while scanning for candidates must not blow up day-close;
    it degrades this substep exactly like every other data-availability
    problem in this module."""
    with patch.object(
        job_dayclose,
        "_find_slates_missing_placement",
        side_effect=RuntimeError("db unavailable"),
    ):
        outcome = job_dayclose._catch_up_missing_placements(YESTERDAY)

    assert outcome["status"] == "degraded"
    assert outcome["reason"] == "scan_failed"


def test_catchup_one_bad_date_does_not_block_another_good_one() -> None:
    """A candidate date that raises must not stop the sweep from still
    recording a different candidate date in the same run."""

    def _side_effect(slate_date: str) -> dict[str, object]:
        if slate_date == "2026-08-19":
            raise ValueError("frozen lineup does not contain five players")
        return {"status": "success", "entry_rank": 12}

    record = MagicMock(side_effect=_side_effect)
    with (
        _patched_find(["2026-08-19", "2026-08-20"]),
        patch.object(job_dayclose, "_auto_record_placement", record),
    ):
        outcome = job_dayclose._catch_up_missing_placements(YESTERDAY)

    assert outcome["status"] == "degraded"
    assert outcome["dates_recorded"] == ["2026-08-20"]
    assert outcome["dates_still_missing"] == [
        {"slate_date": "2026-08-19", "error_type": "ValueError"}
    ]


def test_catchup_date_still_missing_labels_writes_nothing() -> None:
    """End-to-end (not mocking _auto_record_placement itself): a catch-up
    candidate whose slate_labels/contest_leaderboards are still empty must
    hit the exact same early-return path the yesterday-only call already
    uses, and never reach the database engine at all -- i.e. no write is
    even attempted, not just "no row appears"."""
    empty_labels = pl.DataFrame(
        schema={
            "slate_date": pl.Utf8,
            "platform_player_id": pl.Int64,
            "real_score": pl.Float64,
            "card_boost": pl.Float64,
        }
    )
    empty_board = pl.DataFrame(
        schema={
            "slate_date": pl.Utf8,
            "score": pl.Float64,
            "contest_id": pl.Int64,
            "num_brawlers": pl.Int64,
        }
    )
    get_engine = MagicMock()

    with (
        patch.object(job_dayclose, "get_settings", return_value=MagicMock(database_url="x")),
        patch("wnba_oracle.db.reads.read_slate_labels", return_value=empty_labels),
        patch("wnba_oracle.db.reads.read_leaderboards", return_value=empty_board),
        patch("wnba_oracle.db.engine.get_engine", get_engine),
    ):
        outcome = job_dayclose._auto_record_placement("2026-08-20")

    assert outcome == {"status": "degraded", "reason": "missing_labels_or_leaderboard"}
    get_engine.assert_not_called()


# ---------------------------------------------------------------------------
# _find_slates_missing_placement: query shape (window bounds + idempotency
# guard live in the SQL itself)
# ---------------------------------------------------------------------------


def test_find_missing_uses_lookback_window_and_excludes_before_date() -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [("2026-08-20",), ("2026-08-22",)]
    engine = MagicMock()
    engine.connect.return_value.__enter__.return_value = conn

    with (
        patch.object(job_dayclose, "get_settings", return_value=MagicMock(database_url="x")),
        patch("wnba_oracle.db.engine.get_engine", return_value=engine),
    ):
        result = job_dayclose._find_slates_missing_placement(
            before_date="2026-08-27", lookback_days=7
        )

    assert result == ["2026-08-20", "2026-08-22"]
    call_args = conn.execute.call_args
    params = call_args.args[1]
    assert params == {"window_start": "2026-08-20", "before_date": "2026-08-27"}
    sql_text = str(call_args.args[0])
    assert "NOT EXISTS" in sql_text
    assert "contest_placements" in sql_text
    assert "frozen_lineups" in sql_text


def test_find_missing_requires_database_url() -> None:
    with patch.object(job_dayclose, "get_settings", return_value=MagicMock(database_url=None)):
        try:
            job_dayclose._find_slates_missing_placement(before_date="2026-08-27", lookback_days=7)
        except RuntimeError as exc:
            assert "DATABASE_URL" in str(exc)
        else:
            raise AssertionError("expected RuntimeError for missing DATABASE_URL")


# ---------------------------------------------------------------------------
# run(): the existing yesterday-only behavior is preserved, catch-up is
# additive and scoped to the same "yesterday" reference date.
# ---------------------------------------------------------------------------


def test_run_still_calls_auto_record_placement_for_yesterday_only() -> None:
    """The pre-existing single-date call is untouched: it still fires exactly
    once, for previous_slate_date(), regardless of the new catch-up sweep."""
    import datetime as dt

    auto_record = MagicMock(return_value={"status": "success"})
    catchup = MagicMock(
        return_value={"status": "success", "dates_checked": 0, "dates_recorded": []}
    )
    with (
        patch.object(job_dayclose, "get_settings", return_value=MagicMock(database_url="x")),
        patch.object(job_dayclose, "discover_wnba_contest_id", return_value=2100),
        patch.object(job_dayclose, "run_historical_backfill", return_value=0),
        patch.object(job_dayclose, "_audit_label_coverage", return_value={"status": "success"}),
        patch.object(job_dayclose, "_auto_record_placement", auto_record),
        patch.object(job_dayclose, "_catch_up_missing_placements", catchup),
        patch.object(job_dayclose, "_backfill_shadow_results", return_value={"status": "success"}),
        patch.object(
            job_dayclose, "_refresh_current_game_logs", return_value={"status": "success"}
        ),
        patch.object(
            job_dayclose, "_cleanup_append_only_tables", return_value={"status": "success"}
        ),
        patch.object(job_dayclose, "previous_slate_date", return_value=dt.date(2026, 8, 27)),
    ):
        result = job_dayclose.run()

    auto_record.assert_called_once_with("2026-08-27")
    catchup.assert_called_once_with("2026-08-27")
    assert result.details["substeps"]["placement_capture"] == {"status": "success"}
