"""Compat wrappers around strategy.schema clock gates."""

from __future__ import annotations

from nfl_oracle.strategy.schema import clocks_allow_feature


def feature_clocks_ok(
    *,
    source_available_at: str | None,
    captured_at: str | None,
    decision_at: str | None,
    lock_at: str | None = None,
) -> bool:
    return clocks_allow_feature(
        feature_name="__clock_probe__",
        source_available_at=source_available_at,
        captured_at=captured_at,
        decision_at=decision_at,
        lock_at=lock_at,
    )


def live_feature_allowed(feature_key: str, *, decision_at: str | None) -> bool:
    if decision_at is None:
        return False
    return clocks_allow_feature(
        feature_name=feature_key,
        source_available_at=decision_at,
        captured_at=decision_at,
        decision_at=decision_at,
        lock_at=None,
    )
