"""Offline unit tests for wnba_oracle.eval.racer (#356)."""

from __future__ import annotations

import pytest

from wnba_oracle.eval.racer import (
    DEFAULT_CLOSE_BAND,
    EvalContext,
    SlateScore,
    Variant,
    evaluate,
    make_evaluate_fn,
    observation_from_slate,
    race_contract_source,
)


def test_observation_win_close_out() -> None:
    win = observation_from_slate(
        SlateScore(slate_id="2026-08-20", score=100.0, winner_score=100.0),
        b=0.10,
    )
    close = observation_from_slate(
        SlateScore(slate_id="2026-08-21", score=91.0, winner_score=100.0),
        b=0.10,
    )
    out = observation_from_slate(
        SlateScore(slate_id="2026-08-22", score=80.0, winner_score=100.0),
        b=0.10,
    )
    assert win.won is True and win.close is True
    assert close.won is False and close.close is True
    assert out.won is False and out.close is False


def test_evaluate_reads_precomputed_slates() -> None:
    slates = (
        SlateScore("a", score=120.0, winner_score=100.0, field_size=4000),
        {"slate_id": "b", "score": 85.0, "winner_score": 100.0},
        {"slate_id": "skip"},
    )
    slate = evaluate(
        Variant({"profile": "identity"}),
        EvalContext(extras={"slate_scores": slates, "close_band": 0.10}),
    )
    assert len(slate.observations) == 2
    assert slate.observations[0].won is True
    assert slate.observations[1].won is False
    assert slate.observations[1].close is False
    assert slate.observations[0].field_size == 4000


def test_make_evaluate_fn_and_empty() -> None:
    fn = make_evaluate_fn(
        (SlateScore("a", score=90.0, winner_score=100.0),),
        b=0.10,
    )
    close = fn(Variant({"profile": "x"}), EvalContext())
    assert close.observations[0].won is False
    assert close.observations[0].close is True
    empty = evaluate(Variant({"profile": "x"}), EvalContext())
    assert empty.observations == ()
    assert race_contract_source() in {"oracle_core.race", "wnba_oracle.eval.racer.stub"}
    assert DEFAULT_CLOSE_BAND == 0.10
    with pytest.raises(ValueError, match="close_band_out_of_range"):
        make_evaluate_fn((), b=1.5)
