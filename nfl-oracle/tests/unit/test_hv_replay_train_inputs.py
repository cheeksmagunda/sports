"""Replay uses the same HV/TDV train target and display weights as production (#620)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from nfl_oracle.recommendations.model import HistoricalPerformance
from nfl_oracle.replay.hv_train_inputs import prepare_hv_replay_train_inputs
from nfl_oracle.replay.production_backtest import (
    _production_fit,
    bind_contest_boost_fitter,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "corpus_c_hv"


def _row(*, player_id: int, game_id: int, value: float) -> HistoricalPerformance:
    kickoff = datetime(2025, 9, 15, 17, tzinfo=UTC)
    available = kickoff + timedelta(hours=4)
    return HistoricalPerformance(
        player_id=player_id,
        game_id=game_id,
        position="WR",
        kickoff_at=kickoff,
        available_at=available,
        captured_at=available,
        value=value,
    )


def test_linked_corpus_c_upweights_hv_board_not_raw_box() -> None:
    rows = [
        _row(player_id=401, game_id=19457, value=1.0),
        _row(player_id=999, game_id=19457, value=80.0),
        _row(player_id=401, game_id=99999, value=9.0),
    ]
    prepared = prepare_hv_replay_train_inputs(
        Path("nfl-oracle"),
        rows,
        corpus_c_root=FIXTURES,
        export_root=Path("/tmp/nfl-hv-export-absent-620"),
        hv_corpus_root=Path("/tmp/nfl-hv-corpus-absent-620"),
    )
    assert prepared.applied is True
    assert len(prepared.rows) == 1
    assert prepared.rows[0].player_id == 401
    assert prepared.rows[0].game_id == 19457
    assert prepared.rows[0].label_kind == "hv_tdv_leaderboard"
    assert prepared.rows[0].value == 5.0


def test_unlinked_archive_keeps_raw_rows_unchanged(tmp_path: Path) -> None:
    rows = [
        _row(player_id=1, game_id=11, value=1.0),
        _row(player_id=2, game_id=11, value=9.0),
    ]
    prepared = prepare_hv_replay_train_inputs(
        tmp_path,
        rows,
        corpus_c_root=tmp_path / "empty_c",
        export_root=tmp_path / "empty_export",
        hv_corpus_root=tmp_path / "empty_hv",
    )
    assert prepared.applied is False
    assert prepared.contest_boosts is None
    assert [(row.player_id, row.value, row.label_kind) for row in prepared.rows] == [
        (1, 1.0, "raw_box"),
        (2, 9.0, "raw_box"),
    ]
    assert prepared.hv_overlay is not None
    assert prepared.hv_overlay.get("replay_fallback") == "raw_box_no_linked_hv_board"


def test_bind_contest_boost_fitter_only_wraps_production() -> None:
    boosts = {(1, 10): 2.0}

    def custom(rows, trained_at, fit_config):
        return object()

    assert bind_contest_boost_fitter(custom, boosts) is custom
    assert bind_contest_boost_fitter(_production_fit, None) is _production_fit
    assert bind_contest_boost_fitter(_production_fit, boosts) is not _production_fit
