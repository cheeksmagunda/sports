"""Unit tests for the identity resolver. No network: uses the static catalog."""

from __future__ import annotations

from wnba_oracle.ingest.identity import Resolver, _normalize_name
from wnba_oracle.ingest.identity_map import build_unambiguous_backfill


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


def test_resolver_reports_ambiguous_name_without_guessing() -> None:
    r = Resolver()
    r._by_norm_name["duplicate player"] = [  # type: ignore[attr-defined]
        {"id": 10, "full_name": "Duplicate Player One"},
        {"id": 11, "full_name": "Duplicate Player Two"},
    ]

    outcome = r.resolve_with_outcome(
        "rs-ambiguous",
        display_name="Duplicate Player",
        first_name="Duplicate",
        last_name="Player",
    )

    assert outcome.status == "ambiguous"
    assert outcome.wnba_player_id is None
    assert (
        r.resolve(
            "rs-ambiguous",
            display_name="Duplicate Player",
            first_name="Duplicate",
            last_name="Player",
        )
        is None
    )


def test_backfill_skips_ambiguous_rows_and_keeps_single_unambiguous_mapping() -> None:
    r = Resolver()
    r._by_norm_name["duplicate player"] = [  # type: ignore[attr-defined]
        {"id": 10, "full_name": "Duplicate Player One"},
        {"id": 11, "full_name": "Duplicate Player Two"},
    ]

    report = build_unambiguous_backfill(
        r,
        [
            {
                "real_sports_id": "100",
                "display_name": "A'ja Wilson",
                "first_name": "A'ja",
                "last_name": "Wilson",
                "team": "LVA",
            },
            {
                "real_sports_id": "200",
                "display_name": "Duplicate Player",
                "first_name": "Duplicate",
                "last_name": "Player",
                "team": "LVA",
            },
        ],
    )

    assert [mapping.real_sports_player_id for mapping in report.mappings] == ["100"]
    assert report.ambiguous_real_sports_ids == ("200",)
    assert report.unresolved_real_sports_ids == ()
