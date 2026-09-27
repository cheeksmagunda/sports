"""HV train/backtest target + contest algebra + T-40 coherence (#535)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from oracle_core.high_tv import HighPotentialLabelKind
from oracle_core.jobs import JobContext, JobStatus
from oracle_core.logging import get_logger
from oracle_core.testing import FixedClock

from nhl_oracle.baselines.walk_forward import evaluate_walk_forward
from nhl_oracle.contest import select_five_player_pick
from nhl_oracle.contest.algebra import item_score, score_ordered_lineup
from nhl_oracle.contract.boost_gate import evaluate_boost_eligibility
from nhl_oracle.contract.schema import ContestFormat, LockScope, NhlContestContract
from nhl_oracle.eval.backtest import backtest_pick_against_hv
from nhl_oracle.features.own_model_map import (
    classify_feature,
    map_pre_slate_features,
    own_model_gap_matrix,
)
from nhl_oracle.labels import (
    TRAINING_LABEL_SECTION,
    ValueLabel,
    extract_hv_board,
    hv_board_to_high_tv,
    hv_rows_to_value_labels,
    report_hv_corpus_gap,
    schema_document,
)
from nhl_oracle.scheduler.freeze import run_freeze_cycle
from nhl_oracle.scheduler.t40 import evaluate_freeze_coherence, t40_window


def _hv_stats() -> dict:
    return {
        "draftStats": [
            {
                "sectionName": TRAINING_LABEL_SECTION,
                "players": [
                    {"playerId": 1, "value": 5.0, "position": "C", "multiplierBonus": 0.5},
                    {"playerId": 2, "value": 4.0, "position": "LW", "multiplierBonus": 0.0},
                    {"playerId": 3, "value": 3.5, "position": "RW"},
                    {"playerId": 4, "value": 3.0, "position": "D"},
                    {"playerId": 5, "value": 2.5, "position": "G"},
                    {"playerId": 6, "value": 2.0, "position": "C"},
                    {"playerId": 7},  # missing value -> skipped
                ],
            }
        ]
    }


def test_extract_hv_board_forces_zero_boost_and_skips_missing_value() -> None:
    extract = extract_hv_board(_hv_stats(), contest_id=1901, force_zero_boost=True)
    assert extract.has_train_labels
    assert extract.status == "hv_section_present"
    assert extract.skipped_missing_value == 1
    assert extract.rows[0].player_id == 1
    assert extract.rows[0].card_boost == 0.0
    assert extract.rows[0].approx_total_value == 10.0  # 5 * (2 + 0)
    board = hv_board_to_high_tv(extract)
    assert board is not None
    assert board.label_kind is HighPotentialLabelKind.HIGH_TOTAL_VALUE_BOARD
    assert board.top_value_player_ids == (1, 2, 3, 4, 5)
    doc = board.to_schemaorg()
    assert doc["@context"]["@vocab"] == "https://schema.org/"


def test_extract_hv_board_reports_missing_contest_stats() -> None:
    extract = extract_hv_board(None, contest_id=1)
    assert extract.status == "contest_stats_missing"
    assert not extract.has_train_labels
    with pytest.raises(ValueError, match="hv_labels_unavailable"):
        hv_rows_to_value_labels(extract, season=2025, game_id=10)


def test_hv_rows_to_value_labels_and_walk_forward_prefer_hv() -> None:
    extract = extract_hv_board(_hv_stats(), contest_id=1901)
    labels_2024 = hv_rows_to_value_labels(extract, season=2024, game_id=100)
    labels_2025 = hv_rows_to_value_labels(extract, season=2025, game_id=101)
    # Unsectioned decoy must not dilute HV-preferring walk-forward.
    decoy = ValueLabel(
        player_id=99,
        game_id=102,
        season=2025,
        position="C",
        value=99.0,
    )
    report = evaluate_walk_forward([*labels_2024, *labels_2025, decoy])
    assert report.n_labels == len(labels_2024) + len(labels_2025)
    assert any("HV-tagged" in note for note in report.notes)
    assert report.to_dict()["train_label_section"] == TRAINING_LABEL_SECTION


def test_schema_document_names_hv_train_section() -> None:
    doc = schema_document()
    assert doc["train_label_section"] == TRAINING_LABEL_SECTION
    assert "winning_drafts" in doc["train"]["must_not_use"]


def test_report_hv_corpus_gap_when_raw_missing(tmp_path) -> None:
    gap = report_hv_corpus_gap(tmp_path)
    assert gap.hv_ingest_ready is False
    assert "gap" in gap.detail.casefold()


def test_five_player_pick_and_algebra_under_zero_boost_gate() -> None:
    eligibility = evaluate_boost_eligibility(None)  # fail closed
    assert eligibility.boost_multiplier == 0.0
    assert item_score(5.0, 2.0, card_boost=0.5, eligibility=eligibility) == 10.0
    pick = select_five_player_pick(
        {1: 5.0, 2: 4.0, 3: 3.0, 4: 2.0, 5: 1.0, 6: 0.5},
        card_boosts={1: 0.5},
        eligibility=eligibility,
    )
    assert pick.player_ids == (1, 2, 3, 4, 5)
    assert pick.slot_multipliers == (2.0, 1.8, 1.6, 1.4, 1.2)
    assert pick.lineup_score.boost_gated is True
    # slot1: 5*(2+0)=10; slot2: 4*1.8=7.2; ...
    assert pick.lineup_score.total_score == pytest.approx(10 + 7.2 + 4.8 + 2.8 + 1.2)


def test_backtest_pick_against_hv_board() -> None:
    extract = extract_hv_board(_hv_stats(), contest_id=1901)
    pick = select_five_player_pick({row.player_id: row.value for row in extract.rows})
    result = backtest_pick_against_hv(extract, pick)
    assert result.section == TRAINING_LABEL_SECTION
    assert result.capture_ratio == pytest.approx(1.0)
    assert result.reference_player_ids == (1, 2, 3, 4, 5)


def test_own_model_map_drops_leakage_and_none() -> None:
    assert classify_feature("toi_l5") == "history_feature"
    assert classify_feature("lgbm_primary_score") == "lgbm_forbidden"
    assert classify_feature("same_slate_final_value") == "leakage_blocked"
    mapped = map_pre_slate_features(
        {
            "toi_l5": 18.5,
            "same_slate_final_value": 9.0,
            "lgbm_primary_score": 1.0,
            "days_rest": None,
            "position": "C",
        }
    )
    assert mapped == {"toi_l5": 18.5, "position": "C"}
    matrix = own_model_gap_matrix()
    assert any(row["status"] == "lgbm_forbidden" for row in matrix)


def test_t40_window_and_freeze_coherence() -> None:
    lock = datetime(2026, 10, 1, 23, 0, tzinfo=UTC)
    window = t40_window(lock)
    assert window.open_at == lock - timedelta(minutes=40)
    contract = NhlContestContract()
    assert contract.format is ContestFormat.FIVE_CARD_ORDERED
    assert contract.lock_scope is LockScope.PER_CONTEST
    pick = select_five_player_pick({1: 5.0, 2: 4.0, 3: 3.0, 4: 2.0, 5: 1.0})
    ok = evaluate_freeze_coherence(
        pick=pick,
        contract=contract,
        now=lock - timedelta(minutes=20),
        lock_at=lock,
    )
    assert ok.ok is True
    assert ok.in_t40_window is True
    early = evaluate_freeze_coherence(
        pick=pick,
        contract=contract,
        now=lock - timedelta(minutes=50),
        lock_at=lock,
    )
    assert early.ok is False
    assert "before_t40_window" in early.reasons


def test_freeze_cycle_fails_closed_on_t40_incoherent() -> None:
    clock = FixedClock(datetime(2026, 10, 1, 0, 0, tzinfo=UTC))
    context = JobContext(
        job_name="nhl_freeze_cycle",
        role="worker",
        run_id="t40",
        started_at=clock(),
        clock=clock,
        logger=get_logger("nhl_oracle.test"),
    )
    result, record = run_freeze_cycle(
        context,
        collect=lambda: None,
        ensure_t40_coherent=lambda: False,
    )
    assert result.status == JobStatus.RETRYABLE_FAILURE
    assert record.t40_coherent is False
    assert record.prepared is False
    assert record.contest_entry is False


def test_score_ordered_lineup_rejects_short_lineup() -> None:
    with pytest.raises(ValueError, match="exactly_5"):
        score_ordered_lineup([1, 2, 3], {1: 1.0, 2: 1.0, 3: 1.0})
