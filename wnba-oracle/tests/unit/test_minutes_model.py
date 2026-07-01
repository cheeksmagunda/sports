"""Minutes/role model (D55): scoring formula, predictor, ingest, job2 wiring."""

from __future__ import annotations

import json

from wnba_oracle.predict.minutes import (
    MinutesConfig,
    blended_real_score,
    minutes_volatility,
    per_minute_rate,
    project_minutes,
    recent_minutes,
)
from wnba_oracle.predict.scoring import box_to_real_score


# ---- scoring formula ----
def test_box_to_real_score_reasonable() -> None:
    # A solid two-way line should land in the mid real_score range (~2.5-6).
    rs = box_to_real_score(
        {
            "pts": 18,
            "reb": 6,
            "ast": 4,
            "stl": 1,
            "blk": 1,
            "tov": 2,
            "fgm": 7,
            "fga": 14,
            "fg3m": 1,
            "ftm": 3,
            "fta": 4,
        }
    )
    assert 2.0 < rs < 8.0


def test_box_to_real_score_floor_and_empty() -> None:
    assert box_to_real_score({}) >= 0.0
    assert box_to_real_score({"tov": 10}) == 0.0  # all-negative line floored


# ---- rate + projection ----
def test_per_minute_rate_thin_history_uses_league() -> None:
    cfg = MinutesConfig()
    assert per_minute_rate([], [], cfg=cfg) == cfg.league_rate


def test_per_minute_rate_computes_and_clamps() -> None:
    # 3.0 real over 30 min = 0.10/min.
    r = per_minute_rate([3.0, 3.0, 3.0], [30.0, 30.0, 30.0])
    assert abs(r - 0.10) < 1e-6


def test_confirmed_start_lifts_a_low_minute_player() -> None:
    # History says 12 min, but confirmed starter tonight -> projects up.
    cfg = MinutesConfig()
    base = recent_minutes([12, 12, 12], cfg=cfg)
    proj = project_minutes([12, 12, 12], rotowire_confirmed=True, is_starter=True, cfg=cfg)
    assert proj > base + 5  # pulled toward the 30-min starter anchor


def test_confirmed_sit_drops_a_starter() -> None:
    proj = project_minutes([30, 30, 30], rotowire_confirmed=True, is_starter=False)
    assert proj < 25  # pulled toward the bench anchor


def test_injury_bonus_adds_minutes() -> None:
    base = project_minutes([20, 20, 20])
    boosted = project_minutes([20, 20, 20], injury_bonus_min=6.0)
    assert abs((boosted - base) - 6.0) < 1e-6


# ---- the shipped blend ----
def test_blend_no_history_is_boost() -> None:
    # n_games=0 -> pure boost prior.
    out = blended_real_score(recent_min=0.0, rate=0.0, n_games=0, boost_prior=2.7)
    assert abs(out - 2.7) < 1e-6


def test_blend_leans_minutes_with_history() -> None:
    # A 30-min, 0.12/min established starter (~3.6 real) vs a boost prior of 1.8.
    out = blended_real_score(recent_min=30.0, rate=0.12, n_games=12, boost_prior=1.8)
    assert out > 2.8  # pulled well above the boost prior toward the minutes pred


def test_minutes_volatility_band() -> None:
    assert minutes_volatility([30, 30, 30, 30]) >= 0.0
    assert minutes_volatility([10]) == 5.0  # thin -> default


# ---- ingest: build_minutes_features (walk-forward, monkeypatched fetch) ----
def test_build_minutes_features_walkforward(monkeypatch) -> None:
    from wnba_oracle.ingest import minutes_features as mf

    fake = [
        # A. Wilson: 3 prior games + 1 ON the slate date (must be excluded)
        {
            "PLAYER_NAME": "A'ja Wilson",
            "TEAM_ABBREVIATION": "LVA",
            "GAME_DATE": "2026-05-20T00:00:00",
            "MIN": 34,
            "PTS": 26,
            "REB": 9,
            "OREB": 2,
            "DREB": 7,
            "AST": 3,
            "STL": 1,
            "BLK": 2,
            "TOV": 2,
            "FGM": 10,
            "FGA": 18,
            "FG3M": 0,
            "FTM": 6,
            "FTA": 7,
        },
        {
            "PLAYER_NAME": "A'ja Wilson",
            "TEAM_ABBREVIATION": "LVA",
            "GAME_DATE": "2026-05-22T00:00:00",
            "MIN": 36,
            "PTS": 30,
            "REB": 11,
            "OREB": 3,
            "DREB": 8,
            "AST": 4,
            "STL": 2,
            "BLK": 1,
            "TOV": 1,
            "FGM": 11,
            "FGA": 20,
            "FG3M": 1,
            "FTM": 7,
            "FTA": 8,
        },
        {
            "PLAYER_NAME": "A'ja Wilson",
            "TEAM_ABBREVIATION": "LVA",
            "GAME_DATE": "2026-05-24T00:00:00",
            "MIN": 35,
            "PTS": 22,
            "REB": 8,
            "OREB": 2,
            "DREB": 6,
            "AST": 2,
            "STL": 1,
            "BLK": 1,
            "TOV": 3,
            "FGM": 8,
            "FGA": 17,
            "FG3M": 0,
            "FTM": 6,
            "FTA": 6,
        },
        {
            "PLAYER_NAME": "A'ja Wilson",
            "TEAM_ABBREVIATION": "LVA",
            "GAME_DATE": "2026-05-25T00:00:00",
            "MIN": 99,
            "PTS": 99,
            "REB": 99,
            "OREB": 9,
            "DREB": 9,
            "AST": 9,
            "STL": 9,
            "BLK": 9,
            "TOV": 0,
            "FGM": 9,
            "FGA": 9,
            "FG3M": 9,
            "FTM": 9,
            "FTA": 9,
        },  # same-day: excluded
    ]
    monkeypatch.setattr(mf, "_fetch_league_logs", lambda season: fake if season == "2026" else [])
    feats = mf.build_minutes_features(as_of_date="2026-05-25", seasons=["2026", "2025"])
    f = mf.lookup(feats, display_name="A. Wilson", team="LVA")
    assert f is not None
    assert f.n_games == 3  # the 2026-05-25 game is excluded (walk-forward)
    assert 33 < f.recent_minutes < 37  # ~35 min
    assert 0.04 <= f.per_min_rate <= 0.18


def test_build_minutes_features_empty_on_fetch_failure(monkeypatch) -> None:
    from wnba_oracle.ingest import minutes_features as mf

    def boom(season):
        raise RuntimeError("stats.wnba.com 503")

    monkeypatch.setattr(mf, "_fetch_league_logs", boom)
    assert mf.build_minutes_features(as_of_date="2026-05-25", seasons=["2026"]) == {}


# ---- job2 helpers ----
def test_job2_minutes_features_extraction() -> None:
    from wnba_oracle.scheduler.job2 import _minutes_features

    assert _minutes_features("{}") is None
    fj = json.dumps(
        {"recent_minutes": 28.0, "per_min_rate": 0.1, "minutes_vol": 4.0, "n_min_games": 9}
    )
    out = _minutes_features(fj)
    assert out["recent_minutes"] == 28.0 and out["n_min_games"] == 9


def test_job2_cascade_redistributes_out_minutes() -> None:
    from wnba_oracle.scheduler.job2 import _cascade_bonuses

    def row(pid, mins, is_out, pos="F"):
        return {
            "real_sports_player_id": str(pid),
            "team": "LVA",
            "position": pos,
            "features_json": json.dumps(
                {
                    "recent_minutes": mins,
                    "per_min_rate": 0.1,
                    "minutes_vol": 4.0,
                    "n_min_games": 8,
                    "is_out": int(is_out),
                }
            ),
        }

    # Starter OUT (28 min) -> active teammates inherit some of it.
    bonuses = _cascade_bonuses([row(1, 28, True), row(2, 14, False), row(3, 10, False)])
    assert sum(bonuses.values()) > 0
    assert 1 not in bonuses  # the OUT donor is not a recipient
