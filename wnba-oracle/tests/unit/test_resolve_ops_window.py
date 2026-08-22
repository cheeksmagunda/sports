from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"


def _load_resolver() -> ModuleType:
    common_spec = importlib.util.spec_from_file_location(
        "ops_common", SCRIPTS_DIR / "ops_common.py"
    )
    assert common_spec is not None and common_spec.loader is not None
    common = importlib.util.module_from_spec(common_spec)
    sys.modules[common_spec.name] = common
    common_spec.loader.exec_module(common)

    resolver_spec = importlib.util.spec_from_file_location(
        "resolve_ops_window", SCRIPTS_DIR / "resolve_ops_window.py"
    )
    assert resolver_spec is not None and resolver_spec.loader is not None
    resolver = importlib.util.module_from_spec(resolver_spec)
    sys.modules[resolver_spec.name] = resolver
    resolver_spec.loader.exec_module(resolver)
    return resolver


resolve_ops_window = _load_resolver()


def test_scheduled_job1_window_uses_current_wnba_slate_date() -> None:
    now = dt.datetime(2026, 8, 22, 13, 35, tzinfo=dt.UTC)

    window = resolve_ops_window.scheduled_window("job1", now=now)

    assert window.slate_date == "2026-08-22"
    assert window.started_at == dt.datetime(2026, 8, 22, 12, 45, tzinfo=dt.UTC)
    assert window.ended_at == dt.datetime(2026, 8, 22, 13, 30, tzinfo=dt.UTC)


def test_scheduled_dayclose_window_targets_previous_wnba_slate() -> None:
    now = dt.datetime(2026, 8, 22, 7, 5, tzinfo=dt.UTC)

    window = resolve_ops_window.scheduled_window("dayclose", now=now)

    assert window.slate_date == "2026-08-21"
    assert window.started_at == dt.datetime(2026, 8, 22, 5, 45, tzinfo=dt.UTC)
    assert window.ended_at == dt.datetime(2026, 8, 22, 7, 0, tzinfo=dt.UTC)


def test_complete_manual_window_is_preserved() -> None:
    environment = {
        "MANUAL_SLATE_DATE": "2026-08-19",
        "MANUAL_RUN_START_UTC": "2026-08-19T12:50:00Z",
        "MANUAL_RUN_END_UTC": "2026-08-19T13:20:00Z",
    }

    window = resolve_ops_window.resolve_window(
        "job1",
        environment=environment,
        now=dt.datetime(2026, 8, 22, tzinfo=dt.UTC),
    )

    assert window.slate_date == "2026-08-19"
    assert window.contains(dt.datetime(2026, 8, 19, 13, 0, tzinfo=dt.UTC))


def test_partial_manual_window_fails_closed() -> None:
    with pytest.raises(ValueError, match="must be supplied together"):
        resolve_ops_window.resolve_window(
            "job1",
            environment={"MANUAL_SLATE_DATE": "2026-08-19"},
            now=dt.datetime(2026, 8, 22, tzinfo=dt.UTC),
        )


def test_github_environment_output_is_value_only(tmp_path: Path) -> None:
    destination = tmp_path / "github-env"
    window = resolve_ops_window.scheduled_window(
        "dayclose", now=dt.datetime(2026, 8, 22, 7, 5, tzinfo=dt.UTC)
    )

    resolve_ops_window.append_github_environment(destination, window)

    assert destination.read_text() == (
        "INPUT_SLATE_DATE=2026-08-21\n"
        "INPUT_RUN_START_UTC=2026-08-22T05:45:00Z\n"
        "INPUT_RUN_END_UTC=2026-08-22T07:00:00Z\n"
    )
