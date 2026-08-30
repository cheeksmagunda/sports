"""Shared decoding for the persisted WNBA feature payload shape."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any


def parse_feature_mapping(raw: object) -> tuple[dict[str, Any], bool]:
    """Return a feature mapping and whether the input was invalid JSON data."""
    if isinstance(raw, Mapping):
        return dict(raw), False
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8")
        except UnicodeDecodeError:
            return {}, True
    if isinstance(raw, str):
        try:
            decoded = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return {}, True
        return (dict(decoded), False) if isinstance(decoded, Mapping) else ({}, True)
    return {}, True
