"""Structured, redacted logging primitives for application adapters."""

from __future__ import annotations

import json
import logging
import sys
import traceback
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, TextIO

from oracle_core.redaction import RedactionPolicy, redact_text, redact_value

_STANDARD_RECORD_KEYS = frozenset(logging.makeLogRecord({}).__dict__) | {
    "message",
    "asctime",
}
_active_redaction_policy = RedactionPolicy()


@dataclass(frozen=True)
class LoggingConfig:
    """Configuration for JSON logging with secret-safe output."""

    level: str = "INFO"
    muted_loggers: tuple[str, ...] = ("httpx", "httpcore")
    redaction_policy: RedactionPolicy = field(default_factory=RedactionPolicy)
    replace_handlers: bool = False


class RedactingFilter(logging.Filter):
    """Redact message text before any attached handler captures it."""

    def __init__(self, policy: RedactionPolicy) -> None:
        super().__init__()
        self.policy = policy

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = redact_text(record.getMessage(), self.policy)
        record.args = ()
        return True


class JsonFormatter(logging.Formatter):
    """Render stdlib log records as one redacted JSON object per line."""

    def __init__(self, policy: RedactionPolicy | None = None) -> None:
        super().__init__()
        self.policy = policy or RedactionPolicy()

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
            "message": redact_text(record.getMessage(), self.policy),
        }
        if record.exc_info:
            error = record.exc_info[1]
            if error is not None:
                payload["exception"] = format_exception_safe(error, self.policy)
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_KEYS and not key.startswith("_"):
                payload[key] = redact_value(value, self.policy)
        return json.dumps(redact_value(payload, self.policy), default=str, sort_keys=True)


class StructuredLogger:
    """Small structured adapter over :class:`logging.Logger`.

    Event context stays flattened in the emitted JSON, matching common
    structured-log conventions. Values are redacted before they become
    ``LogRecord`` extras, so handlers and test capture do not receive secrets.
    """

    def __init__(
        self,
        logger: logging.Logger,
        *,
        context: Mapping[str, Any] | None = None,
        policy: RedactionPolicy | None = None,
    ) -> None:
        self._logger = logger
        self._context = dict(context or {})
        self._policy = policy or _active_redaction_policy

    @property
    def name(self) -> str:
        """Return the wrapped logger name."""

        return self._logger.name

    def bind(self, **context: Any) -> StructuredLogger:
        """Return a new logger with additional default event context."""

        return StructuredLogger(
            self._logger,
            context={**self._context, **context},
            policy=self._policy,
        )

    def isEnabledFor(self, level: int) -> bool:  # noqa: N802
        """Mirror the standard logger method for compatibility."""

        return self._logger.isEnabledFor(level)

    def setLevel(self, level: int | str) -> None:  # noqa: N802
        """Mirror the standard logger method for compatibility."""

        self._logger.setLevel(level)

    def log(self, level: int, event: str, *args: Any, **context: Any) -> None:
        self._log(level, event, *args, **context)

    def debug(self, event: str, *args: Any, **context: Any) -> None:
        self._log(logging.DEBUG, event, *args, **context)

    def info(self, event: str, *args: Any, **context: Any) -> None:
        self._log(logging.INFO, event, *args, **context)

    def warning(self, event: str, *args: Any, **context: Any) -> None:
        self._log(logging.WARNING, event, *args, **context)

    def warn(self, event: str, *args: Any, **context: Any) -> None:
        """Compatibility alias for :meth:`warning`."""

        self.warning(event, *args, **context)

    def error(self, event: str, *args: Any, **context: Any) -> None:
        self._log(logging.ERROR, event, *args, **context)

    def critical(self, event: str, *args: Any, **context: Any) -> None:
        self._log(logging.CRITICAL, event, *args, **context)

    def exception(self, event: str, *args: Any, **context: Any) -> None:
        """Log an error event with the currently handled exception."""

        context.setdefault("exc_info", True)
        self._log(logging.ERROR, event, *args, **context)

    def _log(self, level: int, event: str, *args: Any, **context: Any) -> None:
        control = {
            key: context.pop(key)
            for key in ("exc_info", "stack_info", "stacklevel")
            if key in context
        }
        extras = self._record_extras(context)
        self._logger.log(level, event, *args, extra=extras, **control)

    def _record_extras(self, context: Mapping[str, Any]) -> dict[str, Any]:
        merged = {**self._context, **context}
        redacted = redact_value(merged, self._policy)
        extras: dict[str, Any] = {}
        for raw_key, value in redacted.items():
            key = str(raw_key)
            if key in _STANDARD_RECORD_KEYS:
                key = f"context_{key}"
            extras[key] = value
        return extras


def _log_level(value: str) -> int:
    return getattr(logging, value.upper(), logging.INFO)


def _configure_handler(handler: logging.Handler, config: LoggingConfig) -> None:
    handler.setFormatter(JsonFormatter(config.redaction_policy))
    handler.filters = [item for item in handler.filters if not isinstance(item, RedactingFilter)]
    handler.addFilter(RedactingFilter(config.redaction_policy))


def configure_json_logging(
    config: LoggingConfig | None = None,
    *,
    stream: TextIO | None = None,
) -> logging.Logger:
    """Configure the root logger and return it.

    Existing handlers are preserved unless ``replace_handlers`` is requested.
    This makes the function safe for test harnesses and host applications that
    install their own log destination.
    """

    global _active_redaction_policy

    config = config or LoggingConfig()
    _active_redaction_policy = config.redaction_policy
    root = logging.getLogger()
    root.setLevel(_log_level(config.level))
    if config.replace_handlers:
        for handler in tuple(root.handlers):
            root.removeHandler(handler)
    if not root.handlers:
        root.addHandler(logging.StreamHandler(stream or sys.stdout))
    for handler in root.handlers:
        _configure_handler(handler, config)
    for name in config.muted_loggers:
        logging.getLogger(name).setLevel(logging.WARNING)
    return root


def configure_logging(
    level: str = "INFO",
    *,
    muted_loggers: tuple[str, ...] = ("httpx", "httpcore"),
    stream: TextIO | None = None,
) -> logging.Logger:
    """Compatibility convenience wrapper around :func:`configure_json_logging`."""

    config = LoggingConfig(level=level, muted_loggers=muted_loggers)
    return configure_json_logging(config, stream=stream)


def get_logger(name: str | None = None) -> StructuredLogger:
    """Return a structured adapter for an application-owned logger name."""

    return StructuredLogger(logging.getLogger(name), policy=_active_redaction_policy)


def format_exception_safe(
    error: BaseException,
    policy: RedactionPolicy | None = None,
) -> str:
    """Format an exception traceback with known credentials removed."""

    rendered = "".join(traceback.format_exception(error))
    return redact_text(rendered, policy)
