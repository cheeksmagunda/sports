"""RotoWire HTML parse coverage (D100 fix).

Before this, the confirmed-status extraction and abbreviated-name handling in
ingest/rotowire.py had ZERO coverage -- the confirmed-starter signal had been
silently dark in production (rotowire_confirmed=0 for every player). These
tests parse a checked-in fixture (mirroring the live DOM verified 2026-06-21)
so the per-team status read and the name fallback are pinned.
"""

from __future__ import annotations

from pathlib import Path

from wnba_oracle.ingest.rotowire import parse_lineups_html
from wnba_oracle.scheduler.job1 import _index_rotowire

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "rotowire_lineups.html"


def _entries():
    return parse_lineups_html(FIXTURE.read_text())


def test_parse_extracts_both_teams_per_game() -> None:
    entries = _entries()
    teams = {e.team for e in entries}
    assert {"GSV", "LVA", "NYL", "ATL"} <= teams
    # GSV (visit) and LVA (home) each contribute their listed players.
    gsv = [e for e in entries if e.team == "GSV"]
    lva = [e for e in entries if e.team == "LVA"]
    assert len(gsv) == 3 and len(lva) == 3


def test_confirmed_is_read_per_team_not_per_box() -> None:
    """The pre-fix bug stamped one box-level status on both teams. The GSV
    visitor list is Expected; the LVA home list is Confirmed -- they must
    differ."""
    by_team = {}
    for e in _entries():
        by_team.setdefault(e.team, []).append(e)
    assert all(not e.confirmed for e in by_team["GSV"]), "visitor was Expected"
    assert all(e.confirmed for e in by_team["LVA"]), "home was Confirmed"
    # The fully-Expected second game stays unconfirmed for both teams.
    assert all(not e.confirmed for e in by_team["NYL"])
    assert all(not e.confirmed for e in by_team["ATL"])


def test_parse_carries_position_and_injury() -> None:
    entries = {(e.team, e.player_name): e for e in _entries()}
    smith = entries[("LVA", "NaLyssa Smith")]
    assert smith.injury_status == "OUT"
    assert smith.position == "F"
    gray = entries[("LVA", "Chelsea Gray")]
    assert gray.injury_status == ""
    assert gray.starter_slot == 1


def test_abbreviated_first_name_matches_real_sports_full_name() -> None:
    """RotoWire abbreviates the visiting team's first names ('C. Zandalasini')
    while Real Sports emits full names ('Cecilia Zandalasini'). The initial-key
    fallback must bridge them so rotowire_confirmed/is_starter actually attach
    (D100)."""
    idx = _index_rotowire(_entries())
    # Real Sports would hand job1 the full name; it must still resolve.
    hit = idx.get("GSV", "Cecilia Zandalasini")
    assert hit is not None
    assert hit.player_name == "C. Zandalasini"
    assert hit.starter_slot == 1
    # Exact full-name match still works for the home (full-name) side.
    gray = idx.get("LVA", "Chelsea Gray")
    assert gray is not None and gray.confirmed is True
    # Wrong team must not cross-match.
    assert idx.get("LVA", "Cecilia Zandalasini") is None
