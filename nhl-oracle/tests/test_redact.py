from __future__ import annotations

import pytest

from nhl_oracle.ingest.redact import assert_no_identity_leak, redact_corpus_payload


def test_redact_corpus_payload_drops_identity_keys() -> None:
    payload = {
        "players": [{"id": 1, "position": "C", "userId": "secret", "email": "a@b.c"}],
        "user": {"id": 9},
        "ok": True,
    }
    redacted = redact_corpus_payload(payload)
    assert "userId" not in redacted["players"][0]
    assert "email" not in redacted["players"][0]
    assert "user" not in redacted
    assert redacted["players"][0]["id"] == 1
    assert redacted["ok"] is True
    assert_no_identity_leak(redacted)


def test_assert_no_identity_leak_raises() -> None:
    with pytest.raises(ValueError):
        assert_no_identity_leak({"userId": "x"})
