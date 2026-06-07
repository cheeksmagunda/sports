"""D74: RotoWire URL + CSS selector fix.

The WNBA lineup page moved from /basketball/wnba-lineups.php to
/wnba/lineups.php, and the lineup box class changed from 'is-wnba' to
'is-nba'. These tests verify the constants without hitting the network.
"""

from __future__ import annotations

from wnba_oracle.ingest import rotowire


def test_rotowire_url_uses_wnba_namespace() -> None:
    assert "/wnba/" in rotowire.URL
    assert "wnba-lineups.php" not in rotowire.URL


def test_rotowire_url_is_correct_path() -> None:
    assert rotowire.URL == "https://www.rotowire.com/wnba/lineups.php"
