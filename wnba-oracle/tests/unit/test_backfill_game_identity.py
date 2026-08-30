"""Pure planning-logic tests for the game_id backfill script (#32).

This script is write-capable against production and must not be run as
part of the test suite or any automated job -- only ``plan_backfill`` (a
pure function with no I/O) is exercised here. See the script's module
docstring for the safety gating (--execute, dry-run default).
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
from types import ModuleType

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[2] / "scripts"


def _load_common() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "corpus_backup_common", SCRIPTS_DIR / "corpus_backup_common.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_backfill() -> ModuleType:
    _load_common()
    spec = importlib.util.spec_from_file_location(
        "backfill_game_identity", SCRIPTS_DIR / "backfill_game_identity.py"
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_backfills_row_with_unambiguous_start_time_match() -> None:
    mod = _load_backfill()
    rows = [
        (1, "2026-06-08", "4512", "2026-06-08T23:00:00Z"),  # has game_id
        (2, "2026-06-08", None, "2026-06-08T23:00:00Z"),  # missing, same start
    ]
    plan = mod.plan_backfill(rows)
    assert plan == {"2026-06-08": [(2, "4512")]}


def test_skips_row_when_start_time_has_no_known_game_id() -> None:
    mod = _load_backfill()
    rows = [(1, "2026-06-08", None, "2026-06-08T23:00:00Z")]
    assert mod.plan_backfill(rows) == {}


def test_skips_row_when_start_time_maps_to_conflicting_game_ids() -> None:
    """Two different game_ids reported for the same start time is a data
    problem in its own right; do not guess which one is correct."""
    mod = _load_backfill()
    rows = [
        (1, "2026-06-08", "4512", "2026-06-08T23:00:00Z"),
        (2, "2026-06-08", "9999", "2026-06-08T23:00:00Z"),
        (3, "2026-06-08", None, "2026-06-08T23:00:00Z"),
    ]
    assert mod.plan_backfill(rows) == {}


def test_skips_row_with_no_start_time_at_all() -> None:
    mod = _load_backfill()
    rows = [(1, "2026-06-08", None, None)]
    assert mod.plan_backfill(rows) == {}


def test_does_not_cross_slate_boundaries() -> None:
    """The same clock time on two different slate_dates must not cross-match."""
    mod = _load_backfill()
    rows = [
        (1, "2026-06-08", "4512", "2026-06-08T23:00:00Z"),
        (2, "2026-06-09", None, "2026-06-08T23:00:00Z"),
    ]
    assert mod.plan_backfill(rows) == {}


def test_leaves_rows_that_already_have_a_game_id_untouched() -> None:
    mod = _load_backfill()
    rows = [
        (1, "2026-06-08", "4512", "2026-06-08T23:00:00Z"),
        (2, "2026-06-08", "4512", "2026-06-08T23:00:00Z"),
    ]
    assert mod.plan_backfill(rows) == {}
