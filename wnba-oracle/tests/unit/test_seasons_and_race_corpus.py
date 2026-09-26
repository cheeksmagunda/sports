"""Unit tests for seasons_common and build_race_corpus (offline, no DB).

Tests seasons_common parse/filter helpers and build_race_corpus's
parquet-writing logic against synthetic DataFrames.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import patch

import polars as pl
import pytest

# ---- bootstrap the scripts/ directory onto sys.path -----------------------
_SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import seasons_common  # noqa: E402


# ====================================================================
# seasons_common.parse_seasons
# ====================================================================


class TestParseSeasons:
    def test_single_year(self):
        assert seasons_common.parse_seasons("2026") == ["2026"]

    def test_multiple_years_sorted(self):
        assert seasons_common.parse_seasons("2026,2025") == ["2025", "2026"]

    def test_dedup(self):
        assert seasons_common.parse_seasons("2026,2026") == ["2026"]

    def test_whitespace_stripped(self):
        assert seasons_common.parse_seasons(" 2025 , 2026 ") == ["2025", "2026"]

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="at least one year"):
            seasons_common.parse_seasons("")

    def test_non_numeric_raises(self):
        with pytest.raises(ValueError, match="Invalid season year"):
            seasons_common.parse_seasons("abc")

    def test_out_of_range_low(self):
        with pytest.raises(ValueError, match="Invalid season year"):
            seasons_common.parse_seasons("1999")

    def test_out_of_range_high(self):
        with pytest.raises(ValueError, match="Invalid season year"):
            seasons_common.parse_seasons("2100")

    def test_default_value(self):
        assert seasons_common.DEFAULT_SEASONS == "2025,2026"


# ====================================================================
# seasons_common.in_seasons
# ====================================================================


class TestInSeasons:
    def test_match(self):
        assert seasons_common.in_seasons("2026-07-15", ["2026"]) is True

    def test_no_match(self):
        assert seasons_common.in_seasons("2025-07-15", ["2026"]) is False

    def test_multi_season(self):
        assert seasons_common.in_seasons("2025-06-01", ["2025", "2026"]) is True

    def test_boundary_jan1(self):
        assert seasons_common.in_seasons("2026-01-01", ["2026"]) is True

    def test_boundary_dec31(self):
        assert seasons_common.in_seasons("2026-12-31", ["2026"]) is True


# ====================================================================
# seasons_common.add_seasons_argument
# ====================================================================


class TestAddSeasonsArgument:
    def test_default(self):
        import argparse

        parser = argparse.ArgumentParser()
        seasons_common.add_seasons_argument(parser)
        args = parser.parse_args([])
        assert args.seasons == seasons_common.DEFAULT_SEASONS

    def test_custom(self):
        import argparse

        parser = argparse.ArgumentParser()
        seasons_common.add_seasons_argument(parser)
        args = parser.parse_args(["--seasons", "2024,2025"])
        assert args.seasons == "2024,2025"


# ====================================================================
# build_race_corpus.build_race_corpus (offline with mocked engine)
# ====================================================================


def _make_labels() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "contest_id": [1, 1, 2, 2],
            "slate_date": ["2025-08-01", "2025-08-01", "2026-06-15", "2026-06-15"],
            "section": ["sec_a", "sec_a", "sec_a", "sec_a"],
            "platform_player_id": [100, 101, 200, 201],
            "display_name": ["Alice", "Bob", "Carol", "Dave"],
            "team_key": ["NYL", "CHI", "NYL", "CHI"],
            "card_boost": [1.0, 0.5, 1.5, 0.8],
            "drafts": [10, 20, 15, 25],
            "real_score": [12.5, 8.3, 15.0, 10.2],
        }
    )


def _make_leaderboards() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "contest_id": [1] * 3 + [2] * 3,
            "slate_date": ["2025-08-01"] * 3 + ["2026-06-15"] * 3,
            "entry_id": [10, 11, 12, 20, 21, 22],
            "rank": [1, 2, 3, 1, 2, 3],
            "paged_rank": [1, 2, 3, 1, 2, 3],
            "user_id": ["u1", "u2", "u3", "u4", "u5", "u6"],
            "score": [50.0, 45.0, 40.0, 60.0, 55.0, 50.0],
            "lineup_json": ["[]"] * 6,
            "num_brawlers": [100, 100, 100, 120, 120, 120],
        }
    )


@pytest.fixture()
def _mock_build_race(tmp_path, monkeypatch):
    """Patch the DB reads in build_race_corpus to return synthetic data."""
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    src_path = str(Path(__file__).resolve().parents[2] / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    import build_race_corpus as mod

    monkeypatch.setattr(mod, "_read_all_labels", lambda _eng: _make_labels())
    monkeypatch.setattr(mod, "_read_all_leaderboards", lambda _eng: _make_leaderboards())
    monkeypatch.setattr(
        mod,
        "_get_backup_engine",
        lambda: types.SimpleNamespace(),
    )
    return mod, tmp_path


class TestBuildRaceCorpus:
    def test_single_season_filter(self, _mock_build_race):
        mod, tmp_path = _mock_build_race
        summary = mod.build_race_corpus(
            output_dir=tmp_path, seasons=["2026"], top_n=20
        )
        assert "2026" in summary
        assert "2025" not in summary
        labels = pl.read_parquet(tmp_path / "labels_2026.parquet")
        assert labels.height == 2
        assert set(labels["slate_date"].to_list()) == {"2026-06-15"}

    def test_multi_season(self, _mock_build_race):
        mod, tmp_path = _mock_build_race
        summary = mod.build_race_corpus(
            output_dir=tmp_path, seasons=["2025", "2026"], top_n=20
        )
        assert "2025" in summary
        assert "2026" in summary
        lb_2025 = pl.read_parquet(tmp_path / "leaderboards_2025.parquet")
        lb_2026 = pl.read_parquet(tmp_path / "leaderboards_2026.parquet")
        assert lb_2025.height == 3
        assert lb_2026.height == 3

    def test_top_n_filter(self, _mock_build_race):
        mod, tmp_path = _mock_build_race
        mod.build_race_corpus(
            output_dir=tmp_path, seasons=["2025", "2026"], top_n=2
        )
        lb_2025 = pl.read_parquet(tmp_path / "leaderboards_2025.parquet")
        assert lb_2025.height == 2

    def test_empty_season_skipped(self, _mock_build_race):
        mod, tmp_path = _mock_build_race
        summary = mod.build_race_corpus(
            output_dir=tmp_path, seasons=["2024"], top_n=20
        )
        assert summary == {}
        assert not (tmp_path / "labels_2024.parquet").exists()

    def test_user_id_preserved(self, _mock_build_race):
        mod, tmp_path = _mock_build_race
        mod.build_race_corpus(
            output_dir=tmp_path, seasons=["2026"], top_n=20
        )
        lb = pl.read_parquet(tmp_path / "leaderboards_2026.parquet")
        assert "user_id" in lb.columns
        assert set(lb["user_id"].to_list()) == {"u4", "u5", "u6"}


class TestBuildRaceCorpusCLI:
    def test_main_success(self, _mock_build_race):
        mod, tmp_path = _mock_build_race
        rc = mod.main(["--output-dir", str(tmp_path), "--seasons", "2026"])
        assert rc == 0
        assert (tmp_path / "labels_2026.parquet").exists()

    def test_main_empty_returns_1(self, _mock_build_race):
        mod, tmp_path = _mock_build_race
        rc = mod.main(["--output-dir", str(tmp_path), "--seasons", "2024"])
        assert rc == 1
