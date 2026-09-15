"""Evidence-backed FeatureSpec wiring landed for issue #189.

Offline only: no Real Sports auth, no NWS call, no nflverse download. Every
fixture below is shaped like the payloads already parsed elsewhere in tree.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from nfl_oracle.features.live import (
    injury_category,
    injury_features,
    injury_indicator_features,
    weather_features,
)
from nfl_oracle.features.matchup import (
    NFL_DIVISIONS,
    division_for_team,
    franchise_code,
    is_divisional_matchup,
)
from nfl_oracle.features.opponent_defense import (
    RealValueHistoryIndex,
    ValueAllowedObservation,
    observations_from_history,
    opponent_adjusted_prior,
    opponent_defense_factor,
)

BASE = datetime(2025, 9, 7, 17, tzinfo=UTC)


# --- is_divisional -----------------------------------------------------------


def test_division_map_covers_all_thirty_two_teams_in_eight_divisions() -> None:
    assert len(NFL_DIVISIONS) == 32
    sizes: dict[str, int] = {}
    for division in NFL_DIVISIONS.values():
        sizes[division] = sizes.get(division, 0) + 1
    assert len(sizes) == 8
    assert set(sizes.values()) == {4}


def test_relocated_franchises_resolve_to_their_current_division() -> None:
    # None of the 2002+ relocations changed division, so the historical
    # abbreviation must classify exactly like the current one.
    for historical, current in (
        ("OAK", "LV"),
        ("SD", "LAC"),
        ("STL", "LAR"),
        ("LA", "LAR"),
        ("JAC", "JAX"),
        ("WSH", "WAS"),
        ("ARZ", "ARI"),
    ):
        assert franchise_code(historical) == current
        assert division_for_team(historical) == division_for_team(current)


def test_is_divisional_matchup_uses_normalized_franchise_codes() -> None:
    assert is_divisional_matchup("OAK", "KC") is True
    assert is_divisional_matchup("SD", "DEN") is True
    assert is_divisional_matchup("STL", "SEA") is True
    assert is_divisional_matchup("NE", "SEA") is False
    assert is_divisional_matchup("jac", "ten") is True


def test_is_divisional_matchup_is_none_when_a_team_is_unusable() -> None:
    assert is_divisional_matchup("NE", None) is None
    assert is_divisional_matchup("", "BUF") is None
    assert is_divisional_matchup("NOT_A_TEAM", "BUF") is None
    # A team is never its own divisional opponent.
    assert is_divisional_matchup("NE", "NE") is None


# --- injury_status / injury_status_available ---------------------------------


def test_injury_features_come_from_the_real_card_field() -> None:
    assert injury_features("Questionable") == {
        "injury_status": "questionable",
        "injury_status_available": True,
    }
    assert injury_features("Active")["injury_status"] == "active"
    assert injury_category("Injured Reserve") == "ir"


def test_injury_features_are_null_and_unavailable_when_not_captured() -> None:
    for missing in (None, "", "   "):
        row = injury_features(missing)
        assert row["injury_status"] is None
        assert row["injury_status_available"] is False


def test_unrecognized_designation_is_still_an_observation() -> None:
    row = injury_features("Probable-ish")
    assert row["injury_status"] == "unknown"
    assert row["injury_status_available"] is True
    indicators = injury_indicator_features("Probable-ish")
    assert indicators["injury_unknown"] == 1.0
    assert indicators["injury_status_available"] == 1.0


def test_injury_indicator_vector_is_float_only_and_one_hot() -> None:
    vector = injury_indicator_features("Out")
    assert all(isinstance(v, float) for v in vector.values())
    assert vector["injury_out"] == 1.0
    assert (
        sum(
            v
            for k, v in vector.items()
            if k.startswith("injury_") and k != "injury_status_available"
        )
        == 1.0
    )


# --- weather_* / weather_available -------------------------------------------


def test_weather_features_pass_through_a_captured_forecast() -> None:
    row = weather_features(
        {"weather_temp_f": 61.0, "weather_wind_mph": 9.0, "weather_precip_prob": 0.2}
    )
    assert row["weather_temp_f"] == 61.0
    assert row["weather_available"] is True


def test_weather_features_are_null_indoors_and_when_uncaptured() -> None:
    indoor = weather_features({"weather_temp_f": 72.0}, indoor=True)
    assert indoor["weather_temp_f"] is None
    assert indoor["weather_available"] is False
    missing = weather_features(None)
    assert missing["weather_wind_mph"] is None
    assert missing["weather_available"] is False


def test_partial_forecast_reports_available_without_inventing_the_rest() -> None:
    row = weather_features({"weather_wind_mph": 14.0})
    assert row["weather_wind_mph"] == 14.0
    assert row["weather_temp_f"] is None
    assert row["weather_precip_prob"] is None
    assert row["weather_available"] is True


# --- opp_def_value_allowed_prior / opponent_adjusted_prior -------------------


def _history_row(
    *,
    player_id: int,
    opponent: int,
    days: int,
    value: float,
    position: str = "WR",
    dnp: bool = False,
) -> SimpleNamespace:
    return SimpleNamespace(
        player_id=player_id,
        opponent_team_id=opponent,
        kickoff_at=BASE + timedelta(days=days),
        value=value,
        position=position,
        did_not_play=dnp,
    )


def test_observations_skip_rows_without_an_opponent_value_or_that_did_not_play() -> None:
    rows = [
        _history_row(player_id=1, opponent=20, days=0, value=8.0),
        _history_row(player_id=2, opponent=20, days=0, value=0.0, dnp=True),
        SimpleNamespace(player_id=3, opponent_team_id=None, kickoff_at=BASE, value=5.0),
        SimpleNamespace(player_id=4, opponent_team_id=20, kickoff_at=BASE, value=None),
    ]
    observations = observations_from_history(rows)
    assert [o.player_id for o in observations] == [1]


def test_opponent_allowed_prior_is_walk_forward_and_excludes_its_own_game() -> None:
    rows = [
        _history_row(player_id=1, opponent=20, days=0, value=10.0),
        _history_row(player_id=2, opponent=20, days=7, value=20.0),
        # Same kickoff as the decision below; must not enter its own prior.
        _history_row(player_id=3, opponent=20, days=14, value=99.0),
    ]
    index = RealValueHistoryIndex(observations_from_history(rows))
    decision = BASE + timedelta(days=14)
    prior = index.opponent_allowed_prior(20, decision, until=decision)
    assert prior.n == 2
    assert prior.mean == 15.0


def test_prior_respects_the_twenty_four_hour_event_buffer() -> None:
    index = RealValueHistoryIndex(
        (ValueAllowedObservation(player_id=1, opponent_team_id=20, kickoff_at=BASE, value=10.0),)
    )
    too_soon = index.opponent_allowed_prior(20, BASE + timedelta(hours=12))
    assert too_soon.n == 0
    assert too_soon.mean is None
    settled = index.opponent_allowed_prior(20, BASE + timedelta(hours=36))
    assert settled.mean == 10.0


def test_position_split_is_used_only_when_it_has_support() -> None:
    rows = [
        _history_row(player_id=p, opponent=20, days=d, value=v, position=pos)
        for p, d, v, pos in (
            (1, 0, 30.0, "QB"),
            (2, 1, 30.0, "QB"),
            (3, 2, 30.0, "QB"),
            (4, 3, 2.0, "WR"),
        )
    ]
    index = RealValueHistoryIndex(observations_from_history(rows))
    decision = BASE + timedelta(days=30)
    # QB has three observations, so the split wins.
    assert index.opponent_allowed_prior(20, decision, position="QB").mean == 30.0
    # WR has one, so it falls back to the all-position mean for that defense.
    assert index.opponent_allowed_prior(20, decision, position="WR").n == 4


def test_defense_factor_is_clamped_and_refuses_thin_support() -> None:
    generous = RealValueHistoryIndex(
        observations_from_history(
            [
                _history_row(player_id=1, opponent=20, days=0, value=40.0),
                _history_row(player_id=2, opponent=21, days=0, value=4.0),
            ]
        )
    )
    decision = BASE + timedelta(days=10)
    allowed = generous.opponent_allowed_prior(20, decision)
    league = generous.league_allowed_prior(decision)
    factor = opponent_defense_factor(allowed, league)
    assert factor == 1.5  # raw ratio is 40/22, clamped
    stingy = opponent_defense_factor(generous.opponent_allowed_prior(21, decision), league)
    assert stingy == 0.5

    empty = RealValueHistoryIndex(())
    assert (
        opponent_defense_factor(
            empty.opponent_allowed_prior(20, decision), empty.league_allowed_prior(decision)
        )
        is None
    )


def test_opponent_adjusted_prior_needs_both_sides() -> None:
    index = RealValueHistoryIndex(
        observations_from_history(
            [
                _history_row(player_id=1, opponent=20, days=0, value=12.0),
                _history_row(player_id=1, opponent=21, days=1, value=12.0),
                _history_row(player_id=2, opponent=20, days=2, value=12.0),
            ]
        )
    )
    decision = BASE + timedelta(days=10)
    player = index.player_prior(1, decision)
    factor = opponent_defense_factor(
        index.opponent_allowed_prior(20, decision), index.league_allowed_prior(decision)
    )
    assert opponent_adjusted_prior(player, factor) == 12.0
    assert opponent_adjusted_prior(player, None) is None
    assert opponent_adjusted_prior(index.player_prior(999, decision), factor) is None
