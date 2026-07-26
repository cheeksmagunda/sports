"""Structlog setup with JSON output. Importing this module configures the root."""

from __future__ import annotations

import logging
import sys

import structlog


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    # httpx/httpcore log their own "HTTP Request: GET <url> ..." line at INFO,
    # and the url includes query params -- The Odds API takes its API key as
    # ?apiKey=..., so that line leaks the key into every ingest job's stdout
    # (Railway log aggregation). The app already logs its own structured,
    # secret-free events per request (odds_fetch, odds_quota, etc.); this
    # generic line adds no signal those don't already carry. WARNING still
    # surfaces httpx's own connection-level failures.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
