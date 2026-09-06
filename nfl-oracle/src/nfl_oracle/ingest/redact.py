"""Redact identity fields from Real Sports NFL payloads before persistence."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from oracle_core.redaction import RedactionPolicy, redact_value

_CORPUS_IDENTITY_KEYS = frozenset(
    {
        "userid",
        "user_id",
        "user",
        "username",
        "email",
        "phone",
        "phonenumber",
        "phone_number",
    }
)


def _is_identity_key(key: object) -> bool:
    normalized = str(key).casefold().replace("-", "_")
    if normalized in _CORPUS_IDENTITY_KEYS:
        return True
    return normalized.startswith("user_") or normalized in {"userprofile", "userinfo"}


def redact_corpus_payload(value: Any, policy: RedactionPolicy | None = None) -> Any:
    """Return a deep copy with account identity and secrets removed."""

    policy = policy or RedactionPolicy()
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, item in value.items():
            key_s = str(key)
            if _is_identity_key(key_s) or policy.is_sensitive_key(key_s):
                continue
            out[key_s] = redact_corpus_payload(item, policy)
        return out
    if isinstance(value, list):
        return [redact_corpus_payload(item, policy) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_corpus_payload(item, policy) for item in value)
    if isinstance(value, str):
        return redact_value(value, policy)
    return value


def assert_no_identity_leak(payload: Any, *, path: str = "$") -> None:
    """Raise ValueError if a forbidden identity key remains after redaction."""

    if isinstance(payload, Mapping):
        for key, item in payload.items():
            key_s = str(key)
            if _is_identity_key(key_s):
                raise ValueError(f"identity key leaked at {path}.{key_s}")
            assert_no_identity_leak(item, path=f"{path}.{key_s}")
    elif isinstance(payload, Sequence) and not isinstance(payload, (str, bytes, bytearray)):
        for index, item in enumerate(payload):
            assert_no_identity_leak(item, path=f"{path}[{index}]")
