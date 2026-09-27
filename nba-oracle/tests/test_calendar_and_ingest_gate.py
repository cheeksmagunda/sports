from datetime import date

from nba_oracle.calendar.season import (
    NEXT_REGULAR_SEASON_OPEN,
    days_until_next_regular_open,
    season_label_for_date,
    tracked_seasons,
)
from nba_oracle.data.coverage_matrix import empty_gap_matrix, matrix_to_dict
from nba_oracle.ingest.auth import auth_presence
from nba_oracle.ingest.backfill import run


def test_season_label_october_opens_new_season() -> None:
    assert season_label_for_date(date(2026, 10, 20)) == 2026
    assert season_label_for_date(date(2026, 1, 15)) == 2025
    assert season_label_for_date(date(2026, 8, 1)) == 2026


def test_tracked_seasons_include_multi_year_gap_range() -> None:
    seasons = tracked_seasons(date(2026, 9, 26))
    assert seasons[0] == 2002
    assert seasons[-1] == 2026
    assert len(seasons) == 25


def test_next_regular_open_constant() -> None:
    assert NEXT_REGULAR_SEASON_OPEN == date(2026, 10, 20)
    assert days_until_next_regular_open(date(2026, 9, 26)) == 24


def test_empty_gap_matrix_all_blocked() -> None:
    rows = empty_gap_matrix(now=date(2026, 9, 26))
    payload = matrix_to_dict(rows)
    assert payload["gap_summary"]["blocked"] == 25
    assert payload["gap_summary"]["known"] == 0
    assert rows[0].blocked_reason == "realsports_auth_unavailable"


def test_auth_presence_blocked_without_env(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("REALSPORTS_STORAGE_STATE_B64GZ", raising=False)
    monkeypatch.delenv("REALSPORTS_STORAGE_STATE_PATH", raising=False)
    monkeypatch.delenv("RAILWAY_VOLUME_MOUNT_PATH", raising=False)
    presence = auth_presence()
    assert presence.ready is False
    assert presence.blocked_reason == "realsports_auth_unavailable"


def test_backfill_gate_exits_blocked_without_auth(monkeypatch, tmp_path) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.delenv("REALSPORTS_STORAGE_STATE_B64GZ", raising=False)
    monkeypatch.delenv("REALSPORTS_STORAGE_STATE_PATH", raising=False)
    monkeypatch.delenv("RAILWAY_VOLUME_MOUNT_PATH", raising=False)
    out = tmp_path / "season_matrix.json"
    code = run(dry_run=False, matrix_out=out)
    assert code == 2
    assert out.is_file()
