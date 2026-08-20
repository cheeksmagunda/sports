"""Secret redaction helpers for logs, diagnostics, and HTTP URLs."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

DEFAULT_SENSITIVE_KEYS = frozenset(
    {
        "access_token",
        "api_key",
        "apikey",
        "authorization",
        "client_secret",
        "cookie",
        "credential",
        "credentials",
        "password",
        "proxy_authorization",
        "refresh_token",
        "secret",
        "set_cookie",
        "token",
        "x_api_key",
    }
)

_QUERY_SECRET_RE = re.compile(
    r"([?&](?:access[_-]?token|api[_-]?key|apikey|authorization|client[_-]?secret|"
    r"credential|password|refresh[_-]?token|secret|token)=)[^&\s]+",
    re.IGNORECASE,
)

_HEADER_SECRET_RE = re.compile(
    r"((?:authorization|proxy-authorization|x-api-key|cookie|set-cookie)\s*[:=]\s*)"
    r"[^\r\n,;]+",
    re.IGNORECASE,
)

_ASSIGNMENT_SECRET_RE = re.compile(
    r"((?:access[_-]?token|api[_-]?key|apikey|authorization|client[_-]?secret|"
    r"credential|password|refresh[_-]?token|secret|token)\s*[:=]\s*)"
    r"(?:\"[^\"]*\"|'[^']*'|[^\s,;]+)",
    re.IGNORECASE,
)

_URL_USERINFO_RE = re.compile(r"(https?://[^\s:/@]+:)[^\s/@]+(@)", re.IGNORECASE)


@dataclass(frozen=True)
class RedactionPolicy:
    """Defines how sensitive mapping keys and URL query values are hidden."""

    sensitive_keys: frozenset[str] = field(default_factory=lambda: DEFAULT_SENSITIVE_KEYS)
    replacement: str = "[REDACTED]"

    def is_sensitive_key(self, key: object) -> bool:
        normalized = str(key).casefold().replace("-", "_")
        return normalized in self.sensitive_keys or any(
            token in normalized
            for token in ("authorization", "cookie", "password", "secret", "token", "api_key")
        )


def redact_url(url: str, policy: RedactionPolicy | None = None) -> str:
    """Return a URL with sensitive query values and user-info hidden."""

    policy = policy or RedactionPolicy()
    parsed = urlsplit(url)
    query = urlencode(
        [
            (key, policy.replacement if policy.is_sensitive_key(key) else value)
            for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        ],
        doseq=True,
    )
    netloc = parsed.netloc
    if "@" in netloc:
        userinfo, host = netloc.rsplit("@", 1)
        if ":" in userinfo:
            username, _password = userinfo.split(":", 1)
            netloc = f"{username}:{policy.replacement}@{host}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, query, parsed.fragment))


def redact_text(value: str, policy: RedactionPolicy | None = None) -> str:
    """Redact URL, header, and query-string secrets embedded in text."""

    policy = policy or RedactionPolicy()
    redacted = _QUERY_SECRET_RE.sub(rf"\1{policy.replacement}", value)
    redacted = _HEADER_SECRET_RE.sub(rf"\1{policy.replacement}", redacted)
    redacted = _ASSIGNMENT_SECRET_RE.sub(rf"\1{policy.replacement}", redacted)
    return _URL_USERINFO_RE.sub(rf"\1{policy.replacement}\2", redacted)


def redact_headers(
    headers: Mapping[str, Any], policy: RedactionPolicy | None = None
) -> dict[str, Any]:
    """Return a copy of HTTP headers with sensitive values hidden."""

    return redact_value(headers, policy)


def redact_value(value: Any, policy: RedactionPolicy | None = None) -> Any:
    """Return a recursively redacted copy of a JSON-like value."""

    policy = policy or RedactionPolicy()
    if isinstance(value, Mapping):
        return {
            str(key): policy.replacement
            if policy.is_sensitive_key(key)
            else redact_value(item, policy)
            for key, item in value.items()
        }
    if isinstance(value, str):
        return redact_text(value, policy)
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [redact_value(item, policy) for item in value]
    return value
