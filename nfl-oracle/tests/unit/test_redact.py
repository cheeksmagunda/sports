"""Tests for Corpus G identity redaction."""

from __future__ import annotations

import pytest

from nfl_oracle.ingest.redact import assert_no_identity_leak, redact_corpus_payload


def test_redact_strips_userid_and_user(sample_stats: dict) -> None:
    assert "userId" in sample_stats
    redacted = redact_corpus_payload(sample_stats)
    assert "userId" not in redacted
    assert "user" not in redacted
    assert "playerBoxScores" in redacted
    assert_no_identity_leak(redacted)


def test_assert_no_identity_leak_raises() -> None:
    with pytest.raises(ValueError, match="identity key leaked"):
        assert_no_identity_leak({"nested": {"userId": 1}})
