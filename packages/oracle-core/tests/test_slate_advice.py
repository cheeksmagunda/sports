"""Slate advice freshness and tilt clamp (#574)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from oracle_core.slate_advice import advice_is_fresh, tilt_map_from_payload


def test_fresh_advice_clamps_and_drops_identity() -> None:
    now = datetime(2026, 9, 28, 16, 0, tzinfo=UTC)
    payload = {
        "sport": "nfl",
        "slate_id": "2026-09-28",
        "written_at": (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "max_age_seconds": 3600,
        "tilts": [
            {"player_id": 1, "mult": 1.4},
            {"player_id": 2, "mult": 1.0},
            {"player_id": "3", "mult": 0.5},
        ],
    }
    assert advice_is_fresh(payload, sport="nfl", slate_id="2026-09-28", now=now)
    assert tilt_map_from_payload(payload) == {1: 1.15, 3: 0.85}


def test_stale_wrong_slate_and_future_are_not_fresh() -> None:
    now = datetime(2026, 9, 28, 16, 0, tzinfo=UTC)
    base = {
        "sport": "wnba",
        "slate_id": "2026-09-28",
        "max_age_seconds": 60,
    }
    stale = {
        **base,
        "written_at": (now - timedelta(hours=2)).isoformat().replace("+00:00", "Z"),
    }
    future = {
        **base,
        "written_at": (now + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
    }
    wrong = {
        **base,
        "slate_id": "2026-09-27",
        "written_at": now.isoformat().replace("+00:00", "Z"),
    }
    assert advice_is_fresh(stale, sport="wnba", slate_id="2026-09-28", now=now) is False
    assert advice_is_fresh(future, sport="wnba", slate_id="2026-09-28", now=now) is False
    assert advice_is_fresh(wrong, sport="wnba", slate_id="2026-09-28", now=now) is False
