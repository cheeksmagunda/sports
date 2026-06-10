"""D85: supplemental slate_labels from top-20 finisher lineups.

The three draftStats sections cover ~30 players per slate; finisher
lineups carry the platform's per-player realized `value` verbatim for
anyone a top-20 entry drafted. Those become section="leaderboard_lineup"
rows, persisted with DO NOTHING so the canonical sections always win.
"""

from __future__ import annotations

from wnba_oracle.ingest.backfill import SUPPLEMENT_SQL, UPSERT_SQL
from wnba_oracle.ingest.contest_stats import (
    LeaderboardEntry,
    labels_from_leaderboard_entries,
)


def _entry(lineup: list[dict], rank: int = 1, entry_id: int = 100) -> LeaderboardEntry:
    return LeaderboardEntry(
        contest_id=1853,
        slate_date="2026-06-08",
        entry_id=entry_id,
        rank=rank,
        paged_rank=rank,
        user_id="u1",
        score=42.0,
        lineup=lineup,
        num_brawlers=5000,
    )


def test_parses_player_value_verbatim() -> None:
    lineup = [
        {"playerId": 726, "displayName": "J. Loyd", "value": "0.8", "multiplier": 2.0},
        {"playerId": 627, "displayName": "A. Boston", "value": "+2.94", "multiplier": 1.5},
    ]
    labels = labels_from_leaderboard_entries([_entry(lineup)])
    by_pid = {label.platform_player_id: label for label in labels}
    assert by_pid[726].real_score == 0.8
    assert by_pid[627].real_score == 2.94
    assert by_pid[726].display_name == "J. Loyd"
    assert all(label.section == "leaderboard_lineup" for label in labels)
    assert all(label.contest_id == 1853 for label in labels)


def test_user_multiplier_is_not_card_boost() -> None:
    """`multiplier` is the finisher's slot choice; it must never leak into
    card_boost. Without a multiplierBonus field the boost is 0.0."""
    lineup = [{"playerId": 1, "value": "3.0", "multiplier": 3.0}]
    labels = labels_from_leaderboard_entries([_entry(lineup)])
    assert labels[0].card_boost == 0.0


def test_multiplier_bonus_used_when_present() -> None:
    lineup = [{"playerId": 1, "value": "3.0", "multiplierBonus": 1.5}]
    labels = labels_from_leaderboard_entries([_entry(lineup)])
    assert labels[0].card_boost == 1.5


def test_dedupes_across_entries_keeping_first() -> None:
    e1 = _entry([{"playerId": 7, "value": "5.0"}], rank=1, entry_id=100)
    e2 = _entry([{"playerId": 7, "value": "5.0"}, {"playerId": 8, "value": "1.0"}],
                rank=2, entry_id=101)
    labels = labels_from_leaderboard_entries([e1, e2])
    assert [label.platform_player_id for label in labels] == [7, 8]


def test_skips_malformed_lineup_items() -> None:
    lineup = [
        "not-a-dict",
        {"value": "2.0"},  # no playerId
        {"playerId": 9, "value": "not-a-number"},
    ]
    labels = labels_from_leaderboard_entries([_entry(lineup)])
    assert len(labels) == 1
    assert labels[0].platform_player_id == 9
    assert labels[0].real_score is None
    assert labels[0].display_name == "Player 9"
    assert labels[0].team_key == "UNK"


def test_team_key_from_nested_team_object() -> None:
    lineup = [{"playerId": 9, "value": "1.0", "team": {"key": "lva"}}]
    labels = labels_from_leaderboard_entries([_entry(lineup)])
    assert labels[0].team_key == "LVA"


def test_supplement_sql_never_clobbers_canonical_rows() -> None:
    """The supplemental insert must DO NOTHING on conflict, unlike the
    canonical UPSERT which updates in place."""
    supplement = str(SUPPLEMENT_SQL)
    canonical = str(UPSERT_SQL)
    assert "DO NOTHING" in supplement
    assert "DO UPDATE" not in supplement
    assert "DO UPDATE" in canonical
