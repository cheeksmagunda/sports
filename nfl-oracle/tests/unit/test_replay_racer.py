"""Offline unit tests for nfl_oracle.replay.racer (#339)."""

from __future__ import annotations

from datetime import date

import pytest

from nfl_oracle.replay import racer as nfl_racer
from nfl_oracle.replay.contest_pool_replay import ContestPoolResult
from nfl_oracle.replay.racer import (
    DEFAULT_CLOSE_BAND,
    EvalContext,
    Variant,
    classify_scores,
    close_band_from_ratios,
    evaluate,
    gap_fraction,
    make_evaluate_fn,
    observation_from_contest_pool_result,
    picker_knobs_from_variant,
    race_contract_source,
)


def _result(
    *,
    contest_id: int = 7,
    production_score: float = 100.0,
    winner_score: float | None = 110.0,
    entrants: int = 5000,
    profile: str = "identity",
) -> ContestPoolResult:
    return ContestPoolResult(
        contest_id=contest_id,
        day=date(2024, 9, 8),
        is_zero_boost=True,
        law_verified=True,
        entrants=entrants,
        fold="7",
        game_ids=(1000,),
        visible_pool_size=20,
        candidate_count=18,
        pool_missing_from_history=0,
        value_mismatches=0,
        ceiling_score=120.0,
        hindsight_player_ids=(1, 2, 3, 4, 5),
        production_player_ids=(1, 2, 3, 4, 5),
        production_score=production_score,
        capture_ratio=production_score / 120.0,
        ordered_capture_ratio=production_score / 120.0,
        hindsight_overlap=5,
        winner_score=winner_score,
        winner_capture_ratio=(winner_score / 120.0) if winner_score else None,
        winner_player_ids=(1, 2, 3, 4, 5),
        winner_overlap=5 if winner_score is not None else None,
        beats_winner=((production_score > winner_score) if winner_score is not None else None),
        beats_visible_entries=0,
        visible_entries=20,
        diversity_relaxed=False,
        picker_profile=profile,
    )


def test_gap_fraction_and_close_band_median() -> None:
    assert gap_fraction(90.0, 100.0) == pytest.approx(0.10)
    assert gap_fraction(0.0, 100.0) is None
    assert gap_fraction(90.0, 0.0) is None
    # medians of 0.05, 0.10, 0.15
    band = close_band_from_ratios(((95.0, 100.0), (90.0, 100.0), (85.0, 100.0)))
    assert band == pytest.approx(0.10)
    assert close_band_from_ratios(()) == DEFAULT_CLOSE_BAND


def test_classify_scores_win_implies_close() -> None:
    won, close = classify_scores(110.0, 100.0, b=0.10)
    assert won is True and close is True
    # Tie with winner is a WIN under race fitness (>=), unlike beats_winner (>).
    won, close = classify_scores(100.0, 100.0, b=0.10)
    assert won is True and close is True
    # Inside CLOSE band, not a WIN.
    won, close = classify_scores(91.0, 100.0, b=0.10)
    assert won is False and close is True
    # Below CLOSE floor.
    won, close = classify_scores(89.0, 100.0, b=0.10)
    assert won is False and close is False
    with pytest.raises(ValueError, match="close_band_out_of_range"):
        classify_scores(100.0, 100.0, b=1.5)


def test_observation_from_contest_pool_result_uses_winner_score() -> None:
    result = _result(production_score=95.0, winner_score=100.0)
    obs = observation_from_contest_pool_result(result, b=0.10)
    assert obs is not None
    assert obs.slate_id == "7"
    assert obs.score == pytest.approx(95.0)
    assert obs.won is False
    assert obs.close is True
    assert obs.field_size == 5000
    assert observation_from_contest_pool_result(_result(winner_score=None), b=0.10) is None


def test_evaluate_stub_reads_precomputed_results_from_extras() -> None:
    results = (
        _result(contest_id=1, production_score=120.0, winner_score=100.0),
        _result(contest_id=2, production_score=85.0, winner_score=100.0),
        _result(contest_id=3, production_score=95.0, winner_score=None),
    )
    variant = Variant({"profile": "identity", "boost_rank_blend": 0.0})
    context = EvalContext(
        extras={
            "contest_pool_results": results,
            "close_band": 0.10,
        }
    )
    slate = evaluate(variant, context)
    assert slate.variant_id == variant.id
    assert len(slate.observations) == 2  # missing winner_score dropped
    assert slate.observations[0].won is True
    assert slate.observations[1].won is False
    assert slate.observations[1].close is False


def test_make_evaluate_fn_selects_by_profile() -> None:
    by_profile = {
        "identity": (_result(contest_id=1, production_score=100.0, winner_score=100.0),),
        "boost_0.75": (_result(contest_id=1, production_score=90.0, winner_score=100.0),),
    }
    fn = make_evaluate_fn(by_profile, b=0.10)
    identity = fn(Variant({"profile": "identity"}), EvalContext())
    boosted = fn(Variant({"profile": "boost_0.75"}), EvalContext())
    assert identity.observations[0].won is True
    assert boosted.observations[0].won is False
    assert boosted.observations[0].close is True


def test_picker_knobs_from_variant_and_empty_evaluate() -> None:
    knobs = picker_knobs_from_variant(
        Variant({"boost_rank_blend": 0.75, "position_calibration": 0.0, "profile": "boost_0.75"})
    )
    assert knobs.boost_rank_blend == pytest.approx(0.75)
    assert knobs.profile == "boost_0.75"
    empty = evaluate(Variant({"profile": "x"}), EvalContext())
    assert empty.observations == ()
    assert race_contract_source() in {"oracle_core.race", "nfl_oracle.replay.racer.stub"}
    # Module stays importable either way.
    assert nfl_racer.DEFAULT_CLOSE_BAND == DEFAULT_CLOSE_BAND
