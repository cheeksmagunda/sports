"""Point-in-time ownership for offline replay (#289).

Pins that benchmark / tournament measured-draft feeds never see same-slate
post-lock drafts, matching scripts/backtest_walkforward.py's prior-slate guard.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from wnba_oracle.eval.point_in_time import causal_drafts_for_slate

_DRAFTS = {
    "2026-05-01": {1: 100, 2: 50},
    "2026-05-02": {1: 300, 3: 20},
    "2026-05-03": {1: 999, 2: 999, 3: 999, 4: 999},
    "2026-05-04": {1: 5},
}

BENCHMARK = Path(__file__).resolve().parents[2] / "scripts" / "build_model_research_benchmark.py"


def _load_benchmark() -> ModuleType:
    spec = importlib.util.spec_from_file_location("build_model_research_benchmark", BENCHMARK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_causal_drafts_never_reads_target_or_later_slates() -> None:
    out = causal_drafts_for_slate("2026-05-03", _DRAFTS)
    assert out == {1: 300, 3: 20, 2: 50}
    assert 4 not in out


def test_causal_drafts_restricts_to_pool_and_is_empty_for_first_slate() -> None:
    assert causal_drafts_for_slate("2026-05-03", _DRAFTS, pool_pids={1, 4}) == {1: 300}
    assert causal_drafts_for_slate("2026-05-01", _DRAFTS) == {}


def test_benchmark_measured_loader_defaults_to_prior_slate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_precompute_slates must patch job2._load_measured_drafts with prior-slate
    drafts by default, never the target slate's own post-lock counts."""
    mod = _load_benchmark()

    import polars as pl

    import wnba_oracle.scheduler.job2 as job2

    labels = pl.DataFrame(
        {
            "contest_id": [1, 1, 1, 1],
            "slate_date": ["2026-05-01", "2026-05-01", "2026-05-02", "2026-05-02"],
            "section": ["main"] * 4,
            "platform_player_id": [10, 11, 10, 11],
            "display_name": ["A", "B", "A", "B"],
            "team_key": ["MIN", "LVA", "MIN", "LVA"],
            "card_boost": [0.5, 0.5, 0.5, 0.5],
            "drafts": [100, 50, 999, 999],
            "real_score": [1.0, 1.0, 1.0, 1.0],
            "ingested_at": ["x"] * 4,
        }
    )
    # Empty leaderboards / identity so the slate loop drops everything after
    # the measured-draft patch is installed; we only assert the patch itself.
    empty_lb = pl.DataFrame(
        {
            "contest_id": pl.Series([], dtype=pl.Int64),
            "slate_date": pl.Series([], dtype=pl.Utf8),
            "entry_id": pl.Series([], dtype=pl.Utf8),
            "rank": pl.Series([], dtype=pl.Int64),
            "paged_rank": pl.Series([], dtype=pl.Int64),
            "user_id": pl.Series([], dtype=pl.Utf8),
            "score": pl.Series([], dtype=pl.Float64),
            "lineup_json": pl.Series([], dtype=pl.Utf8),
            "num_brawlers": pl.Series([], dtype=pl.Int64),
            "ingested_at": pl.Series([], dtype=pl.Utf8),
        }
    )

    monkeypatch.setattr(mod, "load_labels_csv", lambda _p: labels)
    monkeypatch.setattr(mod, "load_leaderboards_csv", lambda _p: empty_lb)
    monkeypatch.setattr(mod, "load_game_identity_csv", lambda _p: None)
    monkeypatch.setattr(mod, "load_game_logs_csv", lambda _p: None)
    monkeypatch.setattr(mod, "index_game_identity", lambda _x: {})

    original = job2._load_measured_drafts
    try:
        mod._precompute_slates(
            max_slates=None,
            labels_csv=Path("/tmp/labels.csv"),
            leaderboards_csv=Path("/tmp/lb.csv"),
        )
        loader = job2._load_measured_drafts
        # Same-slate post-lock drafts must be invisible.
        assert loader("2026-05-02") == {10: 100, 11: 50}
        assert loader("2026-05-01") == {}
        assert 999 not in loader("2026-05-02").values()
    finally:
        job2._load_measured_drafts = original


def test_benchmark_leak_flag_restores_same_slate_drafts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mod = _load_benchmark()

    import polars as pl

    import wnba_oracle.scheduler.job2 as job2

    labels = pl.DataFrame(
        {
            "contest_id": [1, 1],
            "slate_date": ["2026-05-01", "2026-05-02"],
            "section": ["main", "main"],
            "platform_player_id": [10, 10],
            "display_name": ["A", "A"],
            "team_key": ["MIN", "MIN"],
            "card_boost": [0.5, 0.5],
            "drafts": [100, 999],
            "real_score": [1.0, 1.0],
            "ingested_at": ["x", "x"],
        }
    )
    empty_lb = pl.DataFrame(
        {
            "contest_id": pl.Series([], dtype=pl.Int64),
            "slate_date": pl.Series([], dtype=pl.Utf8),
            "entry_id": pl.Series([], dtype=pl.Utf8),
            "rank": pl.Series([], dtype=pl.Int64),
            "paged_rank": pl.Series([], dtype=pl.Int64),
            "user_id": pl.Series([], dtype=pl.Utf8),
            "score": pl.Series([], dtype=pl.Float64),
            "lineup_json": pl.Series([], dtype=pl.Utf8),
            "num_brawlers": pl.Series([], dtype=pl.Int64),
            "ingested_at": pl.Series([], dtype=pl.Utf8),
        }
    )
    monkeypatch.setattr(mod, "load_labels_csv", lambda _p: labels)
    monkeypatch.setattr(mod, "load_leaderboards_csv", lambda _p: empty_lb)
    monkeypatch.setattr(mod, "load_game_identity_csv", lambda _p: None)
    monkeypatch.setattr(mod, "load_game_logs_csv", lambda _p: None)
    monkeypatch.setattr(mod, "index_game_identity", lambda _x: {})

    original = job2._load_measured_drafts
    try:
        mod._precompute_slates(
            max_slates=None,
            labels_csv=Path("/tmp/labels.csv"),
            leaderboards_csv=Path("/tmp/lb.csv"),
            leak_same_slate_ownership=True,
        )
        assert job2._load_measured_drafts("2026-05-02") == {10: 999}
    finally:
        job2._load_measured_drafts = original
