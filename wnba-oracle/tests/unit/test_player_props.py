"""D80: per-event player-prop fetch + parse.

The aggregate `/odds` endpoint returns HTTP 422 for `player_*` markets; props
are only available per-event. These tests pin the parse of a per-event odds
response (the shape The Odds API returns from `/events/{id}/odds`) so the
multiplier in job2 has data to act on.
"""

from __future__ import annotations

from wnba_oracle.ingest.odds import (
    _event_in_slate_window,
    _parse_event_props,
    build_props_lookup,
)

# Mirrors a real /events/{id}/odds response (player_points market), trimmed.
EVENT_FIXTURE = {
    "id": "18efb9afbb0874aa11d7e420ed9c1e5f",
    "sport_key": "basketball_wnba",
    "home_team": "Connecticut Sun",
    "away_team": "New York Liberty",
    "bookmakers": [
        {
            "key": "draftkings",
            "markets": [
                {
                    "key": "player_points",
                    "outcomes": [
                        {"name": "Over", "description": "Satou Sabally", "point": 12.5, "price": 1.90},
                        {"name": "Under", "description": "Satou Sabally", "point": 12.5, "price": 1.90},
                        {"name": "Over", "description": "Jonquel Jones", "point": 13.5, "price": 1.80},
                        {"name": "Under", "description": "Jonquel Jones", "point": 13.5, "price": 2.00},
                    ],
                },
                {
                    # A non-points market must be ignored when markets=player_points.
                    "key": "player_rebounds",
                    "outcomes": [
                        {"name": "Over", "description": "Satou Sabally", "point": 7.5, "price": 1.91},
                    ],
                },
            ],
        },
        {
            "key": "fanduel",
            "markets": [
                {
                    "key": "player_points",
                    "outcomes": [
                        {"name": "Over", "description": "Satou Sabally", "point": 12.5, "price": 1.86},
                        {"name": "Under", "description": "Satou Sabally", "point": 12.5, "price": 1.94},
                    ],
                }
            ],
        },
    ],
}


def test_parse_event_props_filters_market_and_splits_sides() -> None:
    props = _parse_event_props(EVENT_FIXTURE, markets=("player_points",))
    # 4 DK + 2 FD player_points outcomes; the rebounds market is excluded.
    assert len(props) == 6
    assert all(p.market == "player_points" for p in props)
    overs = [p for p in props if p.over_price is not None]
    unders = [p for p in props if p.under_price is not None]
    assert len(overs) == 3
    assert len(unders) == 3


def test_parse_event_props_reads_player_from_description() -> None:
    props = _parse_event_props(EVENT_FIXTURE, markets=("player_points",))
    names = {p.player_name for p in props}
    assert names == {"Satou Sabally", "Jonquel Jones"}


def test_build_props_lookup_merges_to_per_player_over_prob() -> None:
    props = _parse_event_props(EVENT_FIXTURE, markets=("player_points",))
    lookup = build_props_lookup(props)
    key = ("satou sabally", "player_points")
    assert key in lookup
    entry = lookup[key]
    assert entry["line"] == 12.5
    # Median over price across DK 1.90 / FD 1.86 -> implied over prob in (0,1).
    assert 0.0 < entry["implied_over_prob"] < 1.0
    assert 0.0 < entry["implied_under_prob"] < 1.0


def test_parse_event_props_empty_on_no_bookmakers() -> None:
    assert _parse_event_props({"id": "x", "bookmakers": []}, markets=("player_points",)) == []


def test_slate_window_includes_evening_and_late_tips() -> None:
    # 7pm ET (23:00 UTC same day) and 10pm ET (02:00 UTC next day) both belong
    # to the 2026-06-08 slate; the next night's game does not.
    assert _event_in_slate_window("2026-06-08T23:00:00Z", "2026-06-08") is True
    assert _event_in_slate_window("2026-06-09T02:00:00Z", "2026-06-08") is True
    assert _event_in_slate_window("2026-06-09T23:00:00Z", "2026-06-08") is False
    # A morning-UTC time before the window (e.g. yesterday's slate) is excluded.
    assert _event_in_slate_window("2026-06-08T10:00:00Z", "2026-06-08") is False


def test_slate_window_keeps_unparseable() -> None:
    assert _event_in_slate_window("", "2026-06-08") is True
    assert _event_in_slate_window("2026-06-08T23:00:00Z", "not-a-date") is True
