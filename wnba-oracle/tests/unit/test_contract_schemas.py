"""External-API schema contract tests.

These hit the live upstreams and assert the response SHAPE our parsers depend
on, so a silent schema change (RotoWire CSS rename, stats.wnba.com column drop,
Odds API field rename) is caught nightly by `pytest -m contract` BEFORE it
degrades a live fire into empty/zero-filled features. They are marked `contract`
and excluded from the default suite (`addopts = -m 'not contract'`), so the
normal run stays hermetic and credit-free.

Run: uv run --extra dev python -m pytest -m contract -q
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.contract


def test_rotowire_html_shape_unchanged() -> None:
    """The RotoWire WNBA page still exposes the selectors fetch_lineups parses.
    A rename (they moved is-wnba -> is-nba once already, D74) would silently
    yield zero entries; this fails loudly instead."""
    from wnba_oracle.ingest.rotowire import fetch_lineups

    entries = fetch_lineups(use_cache=False)
    if not entries:
        pytest.skip("no WNBA games posted right now (offseason / pre-slate)")
    e = entries[0]
    assert e.team and e.player_name  # core fields parsed
    assert isinstance(e.confirmed, bool) and isinstance(e.starter_slot, int)


def test_nba_api_playergamelogs_columns_present() -> None:
    """stats.wnba.com PlayerGameLogs still returns the columns the head-feature
    corpus + minutes refresh depend on."""
    import datetime as dt

    from wnba_oracle.ingest.minutes_backfill import COLS, _fetch_season_logs

    df = _fetch_season_logs(str(dt.date.today().year))
    if df is None or df.empty:
        pytest.skip("nba_api returned no current-season rows (offseason / outage)")
    missing = [c for c in COLS if c not in df.columns]
    assert not missing, f"PlayerGameLogs missing expected columns: {missing}"


def test_odds_api_events_shape() -> None:
    """The Odds API events endpoint (free, 0 credits) still returns id + team
    names + commence_time, which props/odds fetching keys on."""
    if not os.environ.get("ODDS_API_KEY"):
        pytest.skip("ODDS_API_KEY not set")
    from wnba_oracle.ingest.odds import fetch_wnba_events

    events = fetch_wnba_events()
    if not events:
        pytest.skip("no upcoming WNBA events right now")
    ev = events[0]
    for key in ("id", "home_team", "away_team", "commence_time"):
        assert key in ev, f"Odds API event missing '{key}'"
