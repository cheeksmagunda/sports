"""Classify empty RotoWire HTML (#319)."""

from wnba_oracle.ingest.rotowire import empty_lineups_reason, parse_lineups_html


def test_no_games_scheduled_reason() -> None:
    html = "<html><body>There are no games on the WNBA schedule today.</body></html>"
    assert parse_lineups_html(html) == []
    assert empty_lineups_reason(html) == "no_games_scheduled"


def test_subscriber_paywall_reason() -> None:
    html = "<html><body>Tomorrow's schedule is reserved for RotoWire subscribers.</body></html>"
    assert empty_lineups_reason(html) == "subscriber_paywall"


def test_parse_empty_fallback() -> None:
    html = '<html><body><div class="lineups"></div></body></html>'
    assert empty_lineups_reason(html) == "parse_empty"
