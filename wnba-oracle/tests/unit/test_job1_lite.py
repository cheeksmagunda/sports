"""Credit-free confirmed-lineup refresh.

run_lite re-scrapes RotoWire and JSONB-merges only the RotoWire-authoritative
fields onto existing enrichment, with no Odds/props re-fetch.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from wnba_oracle.ingest.rotowire import LineupEntry
from wnba_oracle.scheduler import job1


def _entry(team, name, slot=0, status="", confirmed=False) -> LineupEntry:
    return LineupEntry(
        team=team,
        opponent="",
        is_home=False,
        starter_slot=slot,
        player_name=name,
        position="G",
        injury_status=status,
        confirmed=confirmed,
    )


def test_rotowire_patch_carries_starter_and_confirmed() -> None:
    p = job1.rotowire_patch(_entry("LVA", "A'ja Wilson", slot=1, confirmed=True))
    assert p == {"is_starter": 1, "starter_slot": 1, "rotowire_confirmed": 1}


def test_rotowire_patch_includes_injury_only_when_present() -> None:
    # Fresh OUT from RotoWire -> patch updates injury + is_out.
    p = job1.rotowire_patch(_entry("NYL", "B. Stewart", slot=2, status="OUT"))
    assert p["is_out"] == 1 and p["injury_status"] == "OUT" and p["is_starter"] == 1
    # No RotoWire injury -> do NOT touch injury_status (don't wipe a RS-sourced OUT).
    p2 = job1.rotowire_patch(_entry("NYL", "B. Stewart", slot=2, status=""))
    assert "injury_status" not in p2 and "is_out" not in p2


def test_run_lite_noop_without_lineups() -> None:
    with patch.object(job1, "fetch_lineups", return_value=[]):
        res = job1.run_lite("2026-06-21")
    assert res.persisted_rows == 0


def test_run_lite_patches_matched_existing_rows() -> None:
    lineups = [_entry("GSV", "C. Zandalasini", slot=2, confirmed=True)]
    # Existing enrichment row uses the Real Sports full name; the initial-key
    # fallback must still match it.
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [(101, "Cecilia Zandalasini", "GSV")]
    eng = MagicMock()
    eng.begin.return_value.__enter__.return_value = conn
    settings = MagicMock(database_url="postgresql://x")
    with (
        patch.object(job1, "fetch_lineups", return_value=lineups),
        patch.object(job1, "get_settings", return_value=settings),
        patch.object(job1, "get_engine", return_value=eng),
    ):
        res = job1.run_lite("2026-06-21")
    assert res.n_pool == 1 and res.persisted_rows == 1
    # The UPDATE (second execute call) carried the row id + a JSON patch.
    update_call = conn.execute.call_args_list[-1]
    assert update_call.args[1]["id"] == 101
    assert "rotowire_confirmed" in update_call.args[1]["patch"]
