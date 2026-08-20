"""WNBA compatibility surface over oracle-core structured logging."""

from __future__ import annotations

from oracle_core.logging import (
    LoggingConfig,
    StructuredLogger,
    configure_json_logging,
    get_logger,
)


def configure_logging(level: str = "INFO") -> None:
    configure_json_logging(LoggingConfig(level=level))


__all__ = ["StructuredLogger", "configure_logging", "get_logger"]
