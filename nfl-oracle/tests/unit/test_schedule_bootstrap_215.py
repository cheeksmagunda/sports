"""Image bootstrap schedules survive an empty volume remount (#215)."""

from __future__ import annotations

from pathlib import Path

from nfl_oracle.calendar.schedule import (
    BOOTSTRAP_SCHEDULE_ENV,
    ensure_offline_schedules,
    resolve_schedule_csv_path,
)

CSV_HEADER = "season,week,game_id,gameday,home_team,away_team,game_type"


def _write_bootstrap(
    boot: Path,
    *,
    body: str | None = None,
) -> Path:
    if body is None:
        body = f"{CSV_HEADER}\n2026,1,g1,2026-09-10,KC,LAC,REG\n"
    boot.mkdir(parents=True, exist_ok=True)
    csv_path = boot / "schedules.csv"
    csv_path.write_text(body, encoding="utf-8")
    (boot / "README.md").write_text("bootstrap\n", encoding="utf-8")
    return csv_path


def test_ensure_offline_schedules_copies_when_volume_missing(
    tmp_path: Path, monkeypatch
) -> None:
    boot = tmp_path / "bootstrap"
    data = tmp_path / "data"
    _write_bootstrap(boot)
    monkeypatch.setenv(BOOTSTRAP_SCHEDULE_ENV, str(boot))

    dest = ensure_offline_schedules(data)
    assert dest is not None
    assert dest.is_file()
    assert dest == data / "schedule" / "schedules.csv"
    assert "2026,1,g1" in dest.read_text(encoding="utf-8")
    assert (data / "schedule" / "README.md").is_file()


def test_ensure_offline_schedules_never_overwrites_volume_copy(
    tmp_path: Path, monkeypatch
) -> None:
    boot = tmp_path / "bootstrap"
    data = tmp_path / "data"
    _write_bootstrap(
        boot,
        body=f"{CSV_HEADER}\n2025,1,old,2025-09-07,BUF,MIA,REG\n",
    )
    monkeypatch.setenv(BOOTSTRAP_SCHEDULE_ENV, str(boot))
    existing = data / "schedule"
    existing.mkdir(parents=True)
    volume_csv = existing / "schedules.csv"
    volume_csv.write_text(
        f"{CSV_HEADER}\n2026,2,keep,2026-09-17,DAL,NYG,REG\n",
        encoding="utf-8",
    )

    dest = ensure_offline_schedules(data)
    assert dest == volume_csv
    assert "keep" in volume_csv.read_text(encoding="utf-8")
    assert "old" not in volume_csv.read_text(encoding="utf-8")


def test_resolve_falls_back_to_bootstrap_without_data_root(
    tmp_path: Path, monkeypatch
) -> None:
    boot = tmp_path / "bootstrap"
    _write_bootstrap(boot)
    monkeypatch.setenv(BOOTSTRAP_SCHEDULE_ENV, str(boot))
    resolved = resolve_schedule_csv_path(None)
    assert resolved == boot / "schedules.csv"


def test_resolve_materializes_into_empty_volume(
    tmp_path: Path, monkeypatch
) -> None:
    boot = tmp_path / "bootstrap"
    data = tmp_path / "data"
    _write_bootstrap(boot)
    monkeypatch.setenv(BOOTSTRAP_SCHEDULE_ENV, str(boot))
    resolved = resolve_schedule_csv_path(data)
    assert resolved == data / "schedule" / "schedules.csv"
    assert resolved.is_file()
