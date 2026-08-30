from __future__ import annotations

import pytest

from wnba_oracle.common.feature_payload import parse_feature_mapping


@pytest.mark.parametrize(
    "raw",
    [None, "", "not-json", b"\xff", "[1]", 123],
)
def test_invalid_or_non_mapping_feature_payloads_are_flagged(raw: object) -> None:
    assert parse_feature_mapping(raw) == ({}, True)


@pytest.mark.parametrize("raw", [{"a": 1}, '{"a": 1}', b'{"a": 1}'])
def test_mapping_feature_payloads_decode_consistently(raw: object) -> None:
    assert parse_feature_mapping(raw) == ({"a": 1}, False)
