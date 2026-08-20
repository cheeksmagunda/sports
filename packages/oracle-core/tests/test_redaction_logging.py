from __future__ import annotations

import io
import json
import logging

from oracle_core.logging import (
    LoggingConfig,
    configure_json_logging,
    format_exception_safe,
    get_logger,
)
from oracle_core.redaction import redact_headers, redact_text, redact_url, redact_value


def test_redact_url_hides_query_and_userinfo_secrets() -> None:
    value = redact_url("https://name:password@example.test/path?apiKey=secret&ok=yes")

    assert "password" not in value
    assert "secret" not in value
    assert "ok=yes" in value


def test_redact_value_handles_nested_mappings() -> None:
    value = redact_value({"token": "abc", "nested": [{"ok": "yes"}]})

    assert value == {"token": "[REDACTED]", "nested": [{"ok": "yes"}]}


def test_redaction_hides_headers_and_embedded_credentials() -> None:
    headers = redact_headers({"Authorization": "Bearer private", "Accept": "application/json"})
    message = redact_text(
        "Authorization: Bearer private\nhttps://name:password@host.test/?client_secret=hidden"
    )

    assert headers == {"Authorization": "[REDACTED]", "Accept": "application/json"}
    assert "private" not in message
    assert "password" not in message
    assert "hidden" not in message


def test_safe_exception_formatting_redacts_assignments() -> None:
    try:
        raise RuntimeError("password=plain-text token: also-plain")
    except RuntimeError as error:
        rendered = format_exception_safe(error)

    assert "plain-text" not in rendered
    assert "also-plain" not in rendered
    assert rendered.count("[REDACTED]") >= 2


def test_json_logging_redacts_and_mutes_http_clients() -> None:
    stream = io.StringIO()
    root = configure_json_logging(LoggingConfig(replace_handlers=True), stream=stream)
    get_logger("sample").info("request", url="https://host.test/?token=secret")

    payload = json.loads(stream.getvalue())
    assert payload["level"] == "info"
    assert "secret" not in stream.getvalue()
    assert payload["url"] == "https://host.test/?token=[REDACTED]"
    assert logging.getLogger("httpx").level == logging.WARNING
    root.handlers.clear()


def test_structured_logger_binds_flattened_redacted_context() -> None:
    stream = io.StringIO()
    root = configure_json_logging(LoggingConfig(replace_handlers=True), stream=stream)

    get_logger("worker").bind(job="refresh").info(
        "completed",
        slate_date="2026-08-20",
        token="not-for-output",
        message="reserved-name",
    )

    payload = json.loads(stream.getvalue())
    assert payload["job"] == "refresh"
    assert payload["slate_date"] == "2026-08-20"
    assert payload["token"] == "[REDACTED]"
    assert payload["context_message"] == "reserved-name"
    assert "not-for-output" not in stream.getvalue()
    root.handlers.clear()
