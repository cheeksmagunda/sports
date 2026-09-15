"""Tests for schedule bootstrap into an empty worker data volume."""

from __future__ import annotations

from pathlib import Path

from nfl_oracle.calendar.schedule import ensure_offline_schedules, resolve_schedule_csv_path


def _write_bootstrap(tmp_path: Path) -> tuple[Path, str]:
    bootstrap = tmp_path / "bootstrap" / "schedule"
    bootstrap.mkdir(parents=True)
    contents = "season,week\n2026,2\n"
    (bootstrap / "schedules.csv").write_text(contents, encoding="utf-8")
    return bootstrap, contents


def test_ensure_offline_schedules_copies_missing_volume_schedule_once(
    tmp_path: Path, monkeypatch
) -> None:
    bootstrap, contents = _write_bootstrap(tmp_path)
    monkeypatch.setenv("NFL_SCHEDULE_BOOTSTRAP_DIR", str(bootstrap))
    data_root = tmp_path / "volume" / "data"

    copied = ensure_offline_schedules(data_root)

    destination = data_root / "schedule" / "schedules.csv"
    assert copied == destination
    assert destination.read_text(encoding="utf-8") == contents


def test_ensure_offline_schedules_leaves_existing_volume_schedule_unchanged(
    tmp_path: Path, monkeypatch
) -> None:
    bootstrap, _contents = _write_bootstrap(tmp_path)
    monkeypatch.setenv("NFL_SCHEDULE_BOOTSTRAP_DIR", str(bootstrap))
    destination = tmp_path / "volume" / "data" / "schedule" / "schedules.csv"
    destination.parent.mkdir(parents=True)
    destination.write_text("volume schedule\n", encoding="utf-8")

    resolved = ensure_offline_schedules(destination.parents[1])

    assert resolved == destination
    assert destination.read_text(encoding="utf-8") == "volume schedule\n"


def test_ensure_offline_schedules_is_idempotent(tmp_path: Path, monkeypatch) -> None:
    bootstrap, contents = _write_bootstrap(tmp_path)
    monkeypatch.setenv("NFL_SCHEDULE_BOOTSTRAP_DIR", str(bootstrap))
    data_root = tmp_path / "volume" / "data"

    first = ensure_offline_schedules(data_root)
    (bootstrap / "schedules.csv").write_text("changed bootstrap\n", encoding="utf-8")
    second = ensure_offline_schedules(data_root)

    assert first == second
    assert first is not None
    assert first.read_text(encoding="utf-8") == contents


def test_resolve_schedule_csv_path_uses_bootstrap_after_data_root_candidates(
    tmp_path: Path, monkeypatch
) -> None:
    bootstrap, _contents = _write_bootstrap(tmp_path)
    monkeypatch.setenv("NFL_SCHEDULE_BOOTSTRAP_DIR", str(bootstrap))

    assert resolve_schedule_csv_path(tmp_path / "empty-data") == bootstrap / "schedules.csv"
