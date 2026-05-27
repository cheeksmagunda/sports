"""Smoke test the slate-feature assembler against a tiny synthetic input.

This is intentionally not a full integration test - the goal is to catch
column-set drift between the builder, the allowlist, and the spec.
"""

from __future__ import annotations

import polars as pl

from wnba_oracle.features.build import build_slate_features, team_key_from_full_name
from wnba_oracle.ingest.identity import Resolver
from wnba_oracle.ingest.odds import GameOdds
from wnba_oracle.ingest.realsports import PlatformPlayer


def _pool() -> list[PlatformPlayer]:
    """Use real WNBA names so the static-catalog Resolver matches them.
    The platform_id values are arbitrary; the resolver matches by name
    against `nba_api`'s WNBA player static catalog."""
    seeds = [
        ("A'ja", "Wilson", "C", "LVA"),
        ("Caitlin", "Clark", "G", "IND"),
        ("Napheesa", "Collier", "F", "MIN"),
        ("Breanna", "Stewart", "F", "NYL"),
        ("Sabrina", "Ionescu", "G", "NYL"),
        ("Kelsey", "Plum", "G", "LAS"),
    ]
    return [
        PlatformPlayer(
            platform_id=str(1000 + i),
            first_name=first,
            last_name=last,
            display_name=f"{first[0]}. {last}",
            position=pos,
            team=team,
            multiplier_bonus=float(0.5 + (i % 4) * 0.5),
            primary_ranking=i + 1,
            injury_status="Active",
        )
        for i, (first, last, pos, team) in enumerate(seeds)
    ]


def _odds() -> list[GameOdds]:
    return [
        GameOdds(
            home_team="Las Vegas Aces",
            away_team="New York Liberty",
            commence_time="2026-05-27T23:00:00Z",
            h2h_home=1.85,
            h2h_away=1.95,
            spread_home_point=-3.5,
            spread_home_price=1.91,
            spread_away_point=3.5,
            spread_away_price=1.91,
            total_point=161.5,
            total_over_price=1.91,
            total_under_price=1.91,
        )
    ]


def _team_stats() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "TEAM_ABBREVIATION": ["LVA", "NYL"],
            "TEAM_NAME": ["Aces", "Liberty"],
            "GP": [12, 11],
            "PACE": [80.5, 78.2],
            "OFF_RATING": [108.5, 105.2],
            "DEF_RATING": [99.1, 101.3],
            "NET_RATING": [9.4, 3.9],
            "TS_PCT": [0.58, 0.55],
            "EFG_PCT": [0.54, 0.51],
        }
    )


def test_team_key_from_full_name_known_and_unknown() -> None:
    assert team_key_from_full_name("Las Vegas Aces") == "LVA"
    assert team_key_from_full_name("New York Liberty") == "NYL"
    # Unknown name: takes the first three letters uppercase.
    assert team_key_from_full_name("Wholly Made Up Team Name") == "WHO"


def test_build_slate_features_output_shape_and_allowlist() -> None:
    """Builder must produce one row per resolved player + a column set that
    passes the predict-time allowlist."""
    from wnba_oracle.features.allowlist import assert_predict_features_allowed

    resolver = Resolver()
    df = build_slate_features(
        slate_date="2026-05-26",
        pool=_pool(),
        game_logs_by_player={},  # rookies / no history -> zero-fill rolling
        team_stats=_team_stats(),
        odds=_odds(),
        lineups=[],
        resolver=resolver,
    )
    # 6 pool players may or may not resolve via the static catalog; we
    # assert the shape is rectangular and the allowlist passes.
    assert not df.is_empty()
    assert_predict_features_allowed(df.columns)
    # Slate / identity columns are present
    for col in ("slate_date", "player_id", "platform_player_id", "team", "cohort"):
        assert col in df.columns
    # Joined Vegas + team context columns are present
    for col in ("vegas_total", "implied_team_total", "team_pace", "opp_pace"):
        assert col in df.columns


def test_build_slate_features_empty_pool() -> None:
    resolver = Resolver()
    df = build_slate_features(
        slate_date="2026-05-26",
        pool=[],
        game_logs_by_player={},
        team_stats=_team_stats(),
        odds=_odds(),
        lineups=[],
        resolver=resolver,
    )
    assert df.is_empty()
