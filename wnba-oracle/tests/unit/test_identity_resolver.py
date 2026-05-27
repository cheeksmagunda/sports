"""Unit tests for the identity resolver. No network: uses the static catalog."""

from __future__ import annotations

from wnba_oracle.ingest.identity import Resolver, _normalize_name


def test_normalize_name_handles_accents_and_punctuation() -> None:
    assert _normalize_name("A'ja Wilson") == "aja wilson"
    assert _normalize_name("DiJonai Carrington") == "dijonai carrington"
    assert _normalize_name("Napheesa Collier ") == "napheesa collier"


def test_resolver_trusts_nba_id() -> None:
    r = Resolver()
    # Bypass name lookup entirely
    assert r.resolve("rs1", display_name="X. Y", nba_id=12345) == 12345


def test_resolver_name_match_known_player() -> None:
    r = Resolver()
    # A'ja Wilson is in the static WNBA catalog
    pid = r.resolve("rs1", display_name="A'ja Wilson", first_name="A'ja", last_name="Wilson")
    assert pid is not None and pid > 0


def test_resolver_returns_none_for_unknown() -> None:
    r = Resolver()
    pid = r.resolve(
        "rs1",
        display_name="No Such Player",
        first_name="No",
        last_name="Such-Player-Xyzzy",
    )
    assert pid is None
