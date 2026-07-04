"""Tests for scheduler.shadow. Pure metric compute + writer contract."""

from __future__ import annotations

from wnba_oracle.scheduler import shadow


def test_score_rank_orders_by_ceiling_contribution() -> None:
    head = {
        1: {"p50": 3.0},
        2: {"p50": 4.0},
        3: {"p50": 2.0},
    }
    boosts = {1: 3.0, 2: 0.0, 3: 1.0}
    ranked = shadow._score_rank(head, boosts)
    # p50 * (2 + boost):
    #   1 -> 3 * 5 = 15
    #   2 -> 4 * 2 = 8
    #   3 -> 2 * 3 = 6
    assert ranked == [1, 2, 3]


def test_score_rank_drops_missing_and_infinite_p50() -> None:
    head = {
        1: {"p50": float("nan")},
        2: {"p50": 3.0},
        3: {},
    }
    ranked = shadow._score_rank(head, {1: 0.0, 2: 0.0, 3: 0.0})
    assert ranked == [2]


def test_rbo_at_k_identity() -> None:
    assert shadow._rbo_at_k([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) == 1.0


def test_rbo_at_k_no_overlap() -> None:
    assert shadow._rbo_at_k([1, 2, 3, 4, 5], [6, 7, 8, 9, 10]) == 0.0


def test_rbo_at_k_empty() -> None:
    assert shadow._rbo_at_k([], [1, 2, 3, 4, 5]) == 0.0


def test_ndcg_at_k_identity() -> None:
    assert abs(shadow._ndcg_at_k([1, 2, 3, 4, 5], [1, 2, 3, 4, 5]) - 1.0) < 1e-9


def test_ndcg_at_k_no_overlap() -> None:
    assert shadow._ndcg_at_k([6, 7, 8, 9, 10], [1, 2, 3, 4, 5]) == 0.0


def test_compute_shadow_full_agreement() -> None:
    head = {i: {"p50": float(6 - i)} for i in range(1, 6)}
    boosts = dict.fromkeys(range(1, 6), 0.0)
    result = shadow.compute_shadow(
        "2026-07-04",
        incumbent_sha="a" * 64,
        challenger_sha="b" * 64,
        incumbent_head=head,
        challenger_head=head,
        boost_by_pid=boosts,
    )
    assert result is not None
    assert result.rbo_at_5 == 1.0
    assert abs(result.ndcg_at_5 - 1.0) < 1e-9
    assert result.incumbent_top5 == [1, 2, 3, 4, 5]
    assert result.challenger_top5 == [1, 2, 3, 4, 5]


def test_compute_shadow_returns_none_on_empty_rank() -> None:
    result = shadow.compute_shadow(
        "2026-07-04",
        incumbent_sha="a" * 64,
        challenger_sha="b" * 64,
        incumbent_head={1: {"p50": 3.0}},
        challenger_head={},
        boost_by_pid={1: 0.0},
    )
    assert result is None


def test_realized_delta_positive_when_challenger_wins() -> None:
    inc_top5 = [1, 2, 3, 4, 5]
    ch_top5 = [10, 11, 12, 13, 14]
    scores = {
        1: 2.0,
        2: 2.0,
        3: 2.0,
        4: 2.0,
        5: 2.0,  # inc sum = 10
        10: 5.0,
        11: 5.0,
        12: 5.0,
        13: 5.0,
        14: 5.0,  # ch sum = 25
    }
    delta = shadow._realized_delta_from_scores(inc_top5, ch_top5, scores)
    assert delta == 15.0


def test_realized_delta_missing_players_zero_out() -> None:
    delta = shadow._realized_delta_from_scores(
        [1, 2],
        [3, 4],
        {1: 3.0},  # 4 pids referenced, only 1 has a score
    )
    assert delta == -3.0
