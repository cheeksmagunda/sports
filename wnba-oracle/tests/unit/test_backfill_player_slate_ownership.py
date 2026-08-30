"""Pure planning-logic tests for the player_slate_ownership backfill (D90/#38).

Only ``plan_backfill`` (a pure function with no I/O) is exercised here; the
script is write-capable against production and must not run as part of the
test suite. See its module docstring for the safety gating (--execute,
dry-run default).
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
        "backfill_player_slate_ownership",
        SCRIPTS_DIR / "backfill_player_slate_ownership.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_plan_normalizes_shares_to_one_per_slate() -> None:
    mod = _load_backfill()
    rows = [("2026-08-29", 1, 2), ("2026-08-29", 2, 4), ("2026-08-29", 3, 194)]
    plan = mod.plan_backfill(rows, already_done=set())
    assert set(plan) == {"2026-08-29"}
    shares = plan["2026-08-29"]
    assert shares[1] == (2 / 200, 2)
    assert shares[2] == (4 / 200, 4)
    assert shares[3] == (194 / 200, 194)
    assert abs(sum(s for s, _ in shares.values()) - 1.0) < 1e-9


def test_plan_skips_slates_already_backfilled() -> None:
    mod = _load_backfill()
    rows = [("2026-08-29", 1, 2), ("2026-08-30", 1, 5)]
    plan = mod.plan_backfill(rows, already_done={"2026-08-29"})
    assert set(plan) == {"2026-08-30"}


def test_plan_skips_slate_with_zero_total_drafts() -> None:
    mod = _load_backfill()
    plan = mod.plan_backfill([("2026-08-29", 1, 0)], already_done=set())
    assert plan == {}


def test_plan_handles_no_rows() -> None:
    mod = _load_backfill()
    assert mod.plan_backfill([], already_done=set()) == {}
