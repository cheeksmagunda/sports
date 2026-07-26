"""httpx logs the full request URL (incl. query-string secrets like The Odds
API's ?apiKey=...) at INFO. configure_logging must silence that logger so
credentials never reach stdout / Railway log aggregation.
"""

from __future__ import annotations

import logging

import pytest

from wnba_oracle.common.logging import configure_logging


def test_httpx_logger_silenced_below_warning() -> None:
    configure_logging("INFO")
    assert logging.getLogger("httpx").level == logging.WARNING
    assert logging.getLogger("httpcore").level == logging.WARNING


def test_httpx_info_log_does_not_reach_root_handler(caplog: pytest.LogCaptureFixture) -> None:
    configure_logging("INFO")
    with caplog.at_level(logging.INFO):
        logging.getLogger("httpx").info(
            "HTTP Request: GET https://api.the-odds-api.com/v4/x?apiKey=SECRET"
        )
    assert not any("SECRET" in r.message for r in caplog.records)
