"""Offline unit tests for ``wnba_oracle.picker.shark_signal``."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from wnba_oracle.picker.shark_signal import (
    SharkSignalError,
    compute_shark_draft_rates,
    identify_sharks,
    shark_draft_rate_array,
)


def _lineup(player_ids: list[int]) -> str:
    return json.dumps(
        [
            {"playerId": pid, "multiplier": 2.0 - 0.2 * i, "multiplierBonus": 0.0}
            for i, pid in enumerate(player_ids)
        ]
    )


def _leaderboard(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


def _labels(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


class TestIdentifySharks:
    def test_identifies_repeat_top_finishers(self) -> None:
        lb = _leaderboard(
            [
                {"slate_date": "2026-06-10", "rank": 1, "user_id": "shark1", "lineup": _lineup([1, 2, 3, 4, 5])},
                {"slate_date": "2026-06-11", "rank": 3, "user_id": "shark1", "lineup": _lineup([1, 2, 3, 4, 5])},
                {"slate_date": "2026-06-12", "rank": 2, "user_id": "shark1", "lineup": _lineup([1, 2, 3, 4, 5])},
                {"slate_date": "2026-06-10", "rank": 5, "user_id": "onetime", "lineup": _lineup([1, 2, 3, 4, 5])},
            ]
        )
        sharks = identify_sharks(lb, "2026-06-13", top_n=20, min_prior_appearances=3)
        assert sharks == {"shark1"}

    def test_prior_only_excludes_target_slate(self) -> None:
        lb = _leaderboard(
            [
                {"slate_date": "2026-06-10", "rank": 1, "user_id": "u", "lineup": _lineup([1, 2, 3, 4, 5])},
                {"slate_date": "2026-06-11", "rank": 1, "user_id": "u", "lineup": _lineup([1, 2, 3, 4, 5])},
                {"slate_date": "2026-06-12", "rank": 1, "user_id": "u", "lineup": _lineup([1, 2, 3, 4, 5])},
            ]
        )
        sharks = identify_sharks(lb, "2026-06-12", top_n=20, min_prior_appearances=2)
        # Only 2026-06-10 and 2026-06-11 are strictly before target.
        assert sharks == {"u"}

    def test_top_n_filter(self) -> None:
        lb = _leaderboard(
            [
                {"slate_date": "2026-06-10", "rank": 21, "user_id": "u", "lineup": _lineup([1, 2, 3, 4, 5])},
                {"slate_date": "2026-06-11", "rank": 1, "user_id": "u", "lineup": _lineup([1, 2, 3, 4, 5])},
                {"slate_date": "2026-06-12", "rank": 1, "user_id": "u", "lineup": _lineup([1, 2, 3, 4, 5])},
            ]
        )
        sharks = identify_sharks(lb, "2026-06-13", top_n=20, min_prior_appearances=2)
        # Rank 21 on first slate does not count, so only two prior appearances remain.
        assert sharks == {"u"}

    def test_no_sharks_when_below_threshold(self) -> None:
        lb = _leaderboard(
            [
                {"slate_date": "2026-06-10", "rank": 1, "user_id": "u", "lineup": _lineup([1, 2, 3, 4, 5])},
            ]
        )
        assert identify_sharks(lb, "2026-06-11", min_prior_appearances=2) == set()

    def test_invalid_top_n(self) -> None:
        with pytest.raises(SharkSignalError, match="top_n must be >= 1"):
            identify_sharks(_leaderboard([]), "2026-06-11", top_n=0)


class TestComputeSharkDraftRates:
    def test_basic_draft_rate(self) -> None:
        lb = _leaderboard(
            [
                {"slate_date": "2026-06-10", "rank": 1, "user_id": "shark1", "lineup": _lineup([1, 2, 3, 4, 5])},
                {"slate_date": "2026-06-11", "rank": 2, "user_id": "shark1", "lineup": _lineup([1, 2, 3, 6, 7])},
                {"slate_date": "2026-06-10", "rank": 5, "user_id": "onetime", "lineup": _lineup([1, 2, 3, 4, 5])},
            ]
        )
        labels = _labels(
            [
                {"slate_date": "2026-06-12", "platform_player_id": 1},
                {"slate_date": "2026-06-12", "platform_player_id": 6},
                {"slate_date": "2026-06-12", "platform_player_id": 99},
            ]
        )
        result = compute_shark_draft_rates(
            lb, labels, "2026-06-12", top_n=20, min_prior_appearances=2
        )
        assert result.sharks == {"shark1"}
        assert result.total_shark_lineups == 2
        assert result.prior_slates == ["2026-06-10", "2026-06-11"]

        rates = result.rates.set_index("platform_player_id")["shark_draft_rate"]
        assert rates[1] == pytest.approx(1.0)  # in both shark lineups
        assert rates[6] == pytest.approx(0.5)  # in one of two
        assert rates[99] == pytest.approx(0.0)

        counts = result.rates.set_index("platform_player_id")["shark_draft_count"]
        assert counts[1] == 2
        assert counts[6] == 1
        assert counts[99] == 0

    def test_prior_only_does_not_use_target_slate(self) -> None:
        lb = _leaderboard(
            [
                {"slate_date": "2026-06-10", "rank": 1, "user_id": "shark1", "lineup": _lineup([1, 2, 3, 4, 5])},
                {"slate_date": "2026-06-11", "rank": 1, "user_id": "shark1", "lineup": _lineup([1, 2, 3, 4, 5])},
                # Target-slate appearances must not influence shark status or rates.
                {"slate_date": "2026-06-12", "rank": 1, "user_id": "new", "lineup": _lineup([99] * 5)},
            ]
        )
        labels = _labels([{"slate_date": "2026-06-12", "platform_player_id": 99}])
        result = compute_shark_draft_rates(
            lb, labels, "2026-06-12", top_n=20, min_prior_appearances=2
        )
        assert result.sharks == {"shark1"}
        assert 99 not in result.rates["platform_player_id"].values

    def test_lookback_window(self) -> None:
        lb = _leaderboard(
            [
                {"slate_date": "2026-06-10", "rank": 1, "user_id": "shark1", "lineup": _lineup([1, 2, 3, 4, 5])},
                {"slate_date": "2026-06-11", "rank": 1, "user_id": "shark1", "lineup": _lineup([6, 7, 8, 9, 10])},
                {"slate_date": "2026-06-12", "rank": 1, "user_id": "shark1", "lineup": _lineup([11, 12, 13, 14, 15])},
            ]
        )
        labels = _labels([{"slate_date": "2026-06-13", "platform_player_id": pid} for pid in (1, 11)])

        with_lookback = compute_shark_draft_rates(
            lb, labels, "2026-06-13", top_n=20, min_prior_appearances=1, max_lookback_slates=1
        )
        rates = with_lookback.rates.set_index("platform_player_id")["shark_draft_rate"]
        assert rates[11] == pytest.approx(1.0)
        assert rates[1] == pytest.approx(0.0)
        assert with_lookback.prior_slates == ["2026-06-12"]

        no_lookback = compute_shark_draft_rates(
            lb, labels, "2026-06-13", top_n=20, min_prior_appearances=1
        )
        rates = no_lookback.rates.set_index("platform_player_id")["shark_draft_rate"]
        assert rates[11] == pytest.approx(1.0 / 3)
        assert rates[1] == pytest.approx(1.0 / 3)

    def test_no_sharks_returns_zero_rate(self) -> None:
        lb = _leaderboard(
            [
                {"slate_date": "2026-06-10", "rank": 1, "user_id": "u", "lineup": _lineup([1, 2, 3, 4, 5])},
            ]
        )
        labels = _labels([{"slate_date": "2026-06-11", "platform_player_id": 1}])
        result = compute_shark_draft_rates(
            lb, labels, "2026-06-11", top_n=20, min_prior_appearances=2
        )
        assert result.sharks == set()
        assert result.total_shark_lineups == 0
        assert result.rates["shark_draft_rate"].iloc[0] == pytest.approx(0.0)
        assert result.rates["total_shark_lineups"].iloc[0] == 0

    def test_empty_target_pool_returns_empty_rates(self) -> None:
        lb = _leaderboard(
            [
                {"slate_date": "2026-06-10", "rank": 1, "user_id": "shark1", "lineup": _lineup([1, 2, 3, 4, 5])},
                {"slate_date": "2026-06-11", "rank": 1, "user_id": "shark1", "lineup": _lineup([1, 2, 3, 4, 5])},
            ]
        )
        labels = _labels([{"slate_date": "2026-06-12", "platform_player_id": 99}])
        result = compute_shark_draft_rates(
            lb, labels, "2026-06-13", top_n=20, min_prior_appearances=2
        )
        assert result.rates.empty

    def test_validates_leaderboard_columns(self) -> None:
        with pytest.raises(SharkSignalError, match="leaderboards missing columns"):
            compute_shark_draft_rates(
                pd.DataFrame({"slate_date": ["2026-06-11"]}),
                _labels([{"slate_date": "2026-06-11", "platform_player_id": 1}]),
                "2026-06-11",
            )

    def test_validates_label_columns(self) -> None:
        with pytest.raises(SharkSignalError, match="labels missing columns"):
            compute_shark_draft_rates(
                _leaderboard([]),
                pd.DataFrame({"slate_date": ["2026-06-11"]}),
                "2026-06-11",
            )

    def test_rejects_bad_lineup(self) -> None:
        lb = _leaderboard(
            [
                {"slate_date": "2026-06-10", "rank": 1, "user_id": "u", "lineup": "not json"},
            ]
        )
        labels = _labels([{"slate_date": "2026-06-11", "platform_player_id": 1}])
        with pytest.raises(SharkSignalError, match="unparseable lineup"):
            compute_shark_draft_rates(lb, labels, "2026-06-11")

    def test_rejects_short_lineup(self) -> None:
        lb = _leaderboard(
            [
                {"slate_date": "2026-06-10", "rank": 1, "user_id": "u", "lineup": json.dumps([{"playerId": 1}])},
            ]
        )
        labels = _labels([{"slate_date": "2026-06-11", "platform_player_id": 1}])
        with pytest.raises(SharkSignalError, match="lineup must be a list of exactly 5 picks"):
            compute_shark_draft_rates(lb, labels, "2026-06-11")


class TestSharkDraftRateArray:
    def test_series_wrapper(self) -> None:
        lb = _leaderboard(
            [
                {"slate_date": "2026-06-10", "rank": 1, "user_id": "shark1", "lineup": _lineup([1, 2, 3, 4, 5])},
                {"slate_date": "2026-06-11", "rank": 1, "user_id": "shark1", "lineup": _lineup([1, 2, 3, 4, 5])},
            ]
        )
        labels = _labels(
            [
                {"slate_date": "2026-06-12", "platform_player_id": 1},
                {"slate_date": "2026-06-12", "platform_player_id": 2},
            ]
        )
        series = shark_draft_rate_array(lb, labels, "2026-06-12", min_prior_appearances=2)
        assert series[1] == pytest.approx(1.0)
        assert series[2] == pytest.approx(1.0)
