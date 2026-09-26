from __future__ import annotations

import pytest

from oracle_core.fitness import (
    WinCloseBand,
    is_close,
    is_win,
    win_close,
    win_close_band,
)

# --------------------------------------------------------------------------- #
# win_close_band
# --------------------------------------------------------------------------- #


def test_win_close_band_is_median_of_ratios() -> None:
    # ratios: 80/100=0.80, 90/120=0.75, 60/80=0.75 -> median 0.75
    band = win_close_band([100.0, 120.0, 80.0], [80.0, 90.0, 60.0])
    assert band.b == pytest.approx(0.75)
    assert band.slate_count == 3


def test_win_close_band_two_slates_averages() -> None:
    # median of two values is their average
    band = win_close_band([100.0, 120.0], [80.0, 90.0])
    assert band.b == pytest.approx(0.775)
    assert band.slate_count == 2


def test_win_close_band_skips_nonpositive_winners() -> None:
    band = win_close_band([100.0, 0.0, -5.0], [80.0, 50.0, 50.0])
    assert band.b == pytest.approx(0.80)
    assert band.slate_count == 1


def test_win_close_band_requires_alignment() -> None:
    with pytest.raises(ValueError):
        win_close_band([100.0, 120.0], [80.0])


def test_win_close_band_requires_one_usable_slate() -> None:
    with pytest.raises(ValueError):
        win_close_band([0.0, -1.0], [0.0, 0.0])


def test_win_close_band_close_threshold() -> None:
    band = WinCloseBand(b=0.775, slate_count=2)
    assert band.close_threshold(100.0) == pytest.approx(22.5)
    # non-positive winner -> 0.0 (no band on that slate)
    assert band.close_threshold(0.0) == 0.0
    assert band.close_threshold(-3.0) == 0.0


# --------------------------------------------------------------------------- #
# is_win / is_close / win_close
# --------------------------------------------------------------------------- #


def test_is_win() -> None:
    assert is_win(100.0, 100.0) is True
    assert is_win(100.5, 100.0) is True
    assert is_win(99.9, 100.0) is False
    # non-positive winner -> nobody won
    assert is_win(100.0, 0.0) is False
    assert is_win(100.0, -5.0) is False


def test_is_close_with_float_band() -> None:
    # b = 0.775 -> close threshold = (1 - 0.775) * 100 = 22.5
    assert is_close(22.5, 100.0, 0.775) is True
    assert is_close(22.4, 100.0, 0.775) is False
    assert is_close(100.0, 100.0, 0.775) is True


def test_is_close_with_win_close_band() -> None:
    band = WinCloseBand(b=0.775, slate_count=2)
    assert is_close(22.5, 100.0, band) is True
    assert is_close(22.4, 100.0, band) is False


def test_is_close_nonpositive_winner_is_false() -> None:
    assert is_close(100.0, 0.0, 0.775) is False
    assert is_close(100.0, -5.0, 0.775) is False
    band = WinCloseBand(b=0.775, slate_count=2)
    assert is_close(100.0, 0.0, band) is False


def test_is_close_band_from_corpus_end_to_end() -> None:
    # Build a band from a corpus, then apply it to fresh scores.
    band = win_close_band([100.0, 120.0], [80.0, 90.0])  # b = 0.775
    # winner=100 -> close threshold = 22.5
    assert is_close(22.5, 100.0, band) is True
    assert is_close(22.4, 100.0, band) is False
    # winner=120 -> close threshold = (1 - 0.775) * 120 = 27.0
    assert is_close(27.0, 120.0, band) is True
    assert is_close(26.9, 120.0, band) is False


def test_win_close_returns_both_flags() -> None:
    band = WinCloseBand(b=0.775, slate_count=2)
    # score above winner -> (True, True)
    assert win_close(100.0, 100.0, band) == (True, True)
    # score between close threshold and winner -> (False, True)
    assert win_close(50.0, 100.0, band) == (False, True)
    # score below close threshold -> (False, False)
    assert win_close(10.0, 100.0, band) == (False, False)


def test_win_close_nonpositive_winner_is_neither() -> None:
    band = WinCloseBand(b=0.775, slate_count=2)
    assert win_close(100.0, 0.0, band) == (False, False)
