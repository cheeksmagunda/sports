"""RotoWire injury wiring: job1 persists is_out into features_json,
job2 filters those players before optimizing.

Until per-player minutes ingestion lands, the full minutes-redistribution
cascade can't fire; the binary drop-OUT-players half lives in this wiring and
is the bigger value lift anyway.
"""

from __future__ import annotations

import json

from wnba_oracle.ingest.rotowire import LineupEntry
from wnba_oracle.scheduler import job1, job2


def _entry(
    team: str, name: str, slot: int = 0, status: str = "", confirmed: bool = False
) -> LineupEntry:
    return LineupEntry(
        team=team,
        opponent="",
        is_home=False,
        starter_slot=slot,
        player_name=name,
        position="F",
        injury_status=status,
        confirmed=confirmed,
    )


def test_is_out_status_recognizes_canonical_tokens() -> None:
    assert job1.is_out_status("OUT")
    assert job1.is_out_status("IL")
    assert job1.is_out_status("INJ")
    assert job1.is_out_status("NA")
    assert job1.is_out_status("Out - Knee")
    assert job1.is_out_status("INACTIVE")


def test_is_out_status_rejects_questionable_and_empty() -> None:
    """GTD/DTD/Q/P are NOT confirmed-out; the operator should still
    consider these for the optimizer pool. The cascade fires only on
    confirmed OUT to avoid over-reacting to warmup-decision tags."""
    assert not job1.is_out_status("")
    assert not job1.is_out_status(None)
    assert not job1.is_out_status("GTD")
    assert not job1.is_out_status("DTD")
    assert not job1.is_out_status("Q")
    assert not job1.is_out_status("P")


def test_normalize_name_strips_suffixes_and_case() -> None:
    assert job1._normalize_name("A'ja Wilson") == "a'ja wilson"
    assert job1._normalize_name("Kelsey Plum Jr.") == "kelsey plum"
    assert job1._normalize_name("Bob III") == "bob"
    assert job1._normalize_name("") == ""


def test_index_rotowire_keys_by_team_normalized_name() -> None:
    entries = [
        _entry("LVA", "A'ja Wilson", slot=1, status=""),
        _entry("NYL", "Breanna Stewart", slot=1, status="OUT"),
    ]
    idx = job1._index_rotowire(entries)
    # Exact full-name lookup via the .get(team, name) API.
    assert idx.get("LVA", "A'ja Wilson") is not None
    stew = idx.get("NYL", "Breanna Stewart")
    assert stew is not None and stew.injury_status == "OUT"
    # __contains__ back-compat on (team, normalized_name).
    assert ("LVA", "a'ja wilson") in idx
    assert idx.get("LVA", "Unknown Player") is None


def test_index_rotowire_initial_fallback_bridges_abbreviated_names() -> None:
    """RotoWire abbreviates first names ('C. Zandalasini'); Real Sports sends
    full names. The first-initial + last-name fallback must still resolve."""
    entries = [_entry("GSV", "C. Zandalasini", slot=2, confirmed=True)]
    idx = job1._index_rotowire(entries)
    hit = idx.get("GSV", "Cecilia Zandalasini")  # full name from Real Sports
    assert hit is not None and hit.starter_slot == 2 and hit.confirmed is True
    # Different last name must not match on initial alone.
    assert idx.get("GSV", "Cecilia Williams") is None


def test_job2_is_out_from_features_handles_dict_string_and_missing() -> None:
    """The same features_json column reaches job2 as a parsed dict
    (psycopg JSONB), a string (older fixtures), or None (column absent
    on stale rows). _is_out_from_features must handle all three."""
    assert job2._is_out_from_features({"is_out": 1}) is True
    assert job2._is_out_from_features({"is_out": 0}) is False
    assert job2._is_out_from_features({}) is False
    assert job2._is_out_from_features('{"is_out": 1}') is True
    assert job2._is_out_from_features('{"is_out": 0}') is False
    assert job2._is_out_from_features(None) is False
    assert job2._is_out_from_features("not-json") is False


def test_features_dict_returns_empty_on_garbage() -> None:
    assert job2._features_dict(None) == {}
    assert job2._features_dict("") == {}
    assert job2._features_dict(123) == {}
    assert job2._features_dict("not json") == {}
    assert job2._features_dict('{"a": 1}') == {"a": 1}
    assert job2._features_dict({"a": 1}) == {"a": 1}


def test_features_json_carries_injury_fields_end_to_end() -> None:
    """Round-trip: build a features_json blob the way job1 does (with
    is_out/is_starter/injury_status), serialize to JSON, then read it
    back via job2's helpers."""
    blob = {
        "injury_status": "OUT - Knee",
        "is_out": 1,
        "is_starter": 0,
        "starter_slot": 0,
        "rotowire_confirmed": 1,
        "vegas_total": 165.5,
        "vegas_spread": -3.5,
        "is_home": 1,
    }
    serialized = json.dumps(blob)
    assert job2._is_out_from_features(serialized) is True
    total, spread = job2._vegas_from_features(serialized)
    assert total == 165.5
    assert spread == -3.5
