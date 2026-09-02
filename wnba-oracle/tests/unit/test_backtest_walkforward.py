"""Point-in-time ownership in scripts/backtest_walkforward.py.

The pre-fix PART 2 fed slate N's own ``slate_labels.drafts`` (realized field
ownership, written by day-close after the fact) into the contrarian tilt.
These tests pin the causal replacement: each player's most recent PRIOR slate
draft count, never the target slate's.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import polars as pl

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "backtest_walkforward.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("backtest_walkforward", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_DRAFTS = {
    "2026-05-01": {1: 100, 2: 50},
    "2026-05-02": {1: 300, 3: 20},
    "2026-05-03": {1: 999, 2: 999, 3: 999, 4: 999},
    "2026-05-04": {1: 5},
}


def test_causal_drafts_never_reads_target_or_later_slates() -> None:
    mod = _load_script()
    out = mod.causal_drafts_for_slate("2026-05-03", _DRAFTS)
    # Most recent prior observation per player; 05-03 and 05-04 are invisible.
    assert out == {1: 300, 3: 20, 2: 50}
    assert 4 not in out


def test_causal_drafts_restricts_to_pool_and_is_empty_for_first_slate() -> None:
    mod = _load_script()
    assert mod.causal_drafts_for_slate("2026-05-03", _DRAFTS, pool_pids={1, 4}) == {1: 300}
    assert mod.causal_drafts_for_slate("2026-05-01", _DRAFTS) == {}


def test_drafts_by_slate_from_frame_skips_null_drafts() -> None:
    mod = _load_script()
    frame = pl.DataFrame(
        {
            "slate_date": ["2026-05-01", "2026-05-01", "2026-05-02"],
            "platform_player_id": [1, 2, 1],
            "drafts": [10, None, 20],
        }
    )
    assert mod._drafts_by_slate_from_frame(frame) == {
        "2026-05-01": {1: 10},
        "2026-05-02": {1: 20},
    }
