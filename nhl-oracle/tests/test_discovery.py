from __future__ import annotations

from nhl_oracle.contract.discovery import discover_contract
from nhl_oracle.contract.schema import BoostRegime, ContestFormat, LockScope


def test_discover_contract_resolves_five_card_ordered_from_explicit_payload() -> None:
    meta = {
        "info": {
            "isLocked": False,
            "contest": {"sport": "nhl", "additionalInfo": {"lineupSize": 5}},
        }
    }
    draftinfo = {"info": {"defaultMultipliers": [2.0, 1.8, 1.6, 1.4, 1.2], "lineupSize": 5}}
    players = [
        {
            "players": [
                {"id": 1, "position": "C", "fantasyPoints": 10.0},
                {"id": 2, "position": "G", "fantasyPoints": 8.0, "multiplierBonus": 0.2},
                {"id": 3, "position": "LW", "value": 7.0},
                {"id": 4, "position": "RW", "value": 6.0},
                {"id": 5, "position": "D", "value": 5.0},
            ]
        }
    ]
    contract, evidence, candidates = discover_contract(
        meta=meta,
        draftinfo=draftinfo,
        players_payloads=players,
        contest_ids=(42,),
        game_ids=(7,),
        games_scheduled=1,
        games_captured=1,
        captured_at="2026-09-25T00:00:00Z",
    )
    assert contract.format is ContestFormat.FIVE_CARD_ORDERED
    assert contract.lock_scope is LockScope.PER_CONTEST
    assert contract.boost_regime is BoostRegime.FLAT
    assert contract.goalie_eligible is True
    assert contract.score_value_label == "fantasyPoints"
    assert contract.slot_multipliers == (2.0, 1.8, 1.6, 1.4, 1.2)
    assert contract.open_questions() == ()
    assert evidence.players_seen == 5
    assert evidence.players_resolved == 5
    assert len(candidates) == 5


def test_discover_contract_leaves_unknowns_when_payload_sparse() -> None:
    contract, evidence, candidates = discover_contract(
        meta={"info": {}},
        draftinfo={"info": {}},
        players_payloads=[{"players": []}],
        contest_ids=(),
        game_ids=(),
        games_scheduled=0,
        games_captured=0,
        captured_at="2026-09-25T00:00:00Z",
    )
    assert contract.format is ContestFormat.UNKNOWN
    assert contract.lock_scope is LockScope.UNKNOWN
    assert contract.boost_regime is BoostRegime.UNKNOWN
    assert contract.goalie_eligible is None
    assert contract.score_value_label is None
    assert contract.open_questions()
    assert evidence.players_seen == 0
    assert candidates == ()


def test_discover_contract_uses_contest_stats_values_for_candidates() -> None:
    meta = {
        "info": {
            "isLocked": True,
            "contest": {"sport": "nhl", "additionalInfo": {"lineupSize": 5}},
        }
    }
    draftinfo = {"info": {"defaultMultipliers": [2.0, 1.8, 1.6, 1.4, 1.2], "lineupSize": 5}}
    # Live game cards often omit score/value; draftStats carries authoritative value.
    players = [{"players": [{"id": 101, "position": "G"}, {"id": 102, "position": "C"}]}]
    contest_stats = {
        "draftStats": [
            {
                "players": [
                    {"playerId": 101, "value": 4.5, "multiplierBonus": 0.2},
                    {"playerId": 102, "value": 3.1, "multiplierBonus": 0.0},
                    {"playerId": 103, "value": 2.0, "multiplierBonus": 0.1},
                ]
            }
        ]
    }
    contract, evidence, candidates = discover_contract(
        meta=meta,
        draftinfo=draftinfo,
        players_payloads=players,
        contest_ids=(1901,),
        game_ids=(7,),
        games_scheduled=1,
        games_captured=1,
        captured_at="2026-09-25T00:00:00Z",
        contest_stats=contest_stats,
    )
    assert contract.score_value_label == "value"
    # Live player cards omit boost fields; historical draftStats must not override.
    assert contract.boost_regime is BoostRegime.NONE
    assert any("pre-boost" in n for n in evidence.notes)
    assert any(
        "historical_contest_draftStats_had_nonzero_multiplierBonus" in n for n in evidence.notes
    )
    assert contract.goalie_eligible is True
    assert evidence.players_seen == 3
    by_id = {c.player_id: c for c in candidates}
    assert by_id[101].score_value == 4.5
    assert by_id[101].position == "G"
    assert by_id[103].position == "UNK"
    assert all(c.score_value is not None for c in candidates)


def test_discover_contract_preboost_when_live_cards_lack_bonus_fields() -> None:
    """Current-slate cards without boost fields => none, even with empty stats."""

    meta = {
        "info": {
            "isLocked": False,
            "contest": {"sport": "nhl", "additionalInfo": {"lineupSize": 5}},
        }
    }
    draftinfo = {"info": {"defaultMultipliers": [2.0, 1.8, 1.6, 1.4, 1.2], "lineupSize": 5}}
    players = [
        {
            "players": [
                {"id": 1, "position": "C", "value": 10.0},
                {"id": 2, "position": "G", "value": 8.0},
            ]
        }
    ]
    contract, evidence, _candidates = discover_contract(
        meta=meta,
        draftinfo=draftinfo,
        players_payloads=players,
        contest_ids=(),
        game_ids=(7,),
        games_scheduled=1,
        games_captured=1,
        captured_at="2026-09-25T00:00:00Z",
    )
    assert contract.boost_regime is BoostRegime.NONE
    assert any("pre-boost" in n for n in evidence.notes)


def test_discover_contract_flat_only_from_live_card_bonuses() -> None:
    meta = {
        "info": {
            "isLocked": False,
            "contest": {"sport": "nhl", "additionalInfo": {"lineupSize": 5}},
        }
    }
    draftinfo = {"info": {"defaultMultipliers": [2.0, 1.8, 1.6, 1.4, 1.2], "lineupSize": 5}}
    players = [
        {
            "players": [
                {"id": 1, "position": "C", "value": 10.0, "multiplierBonus": 0.0},
                {"id": 2, "position": "G", "value": 8.0, "multiplierBonus": 1.5},
            ]
        }
    ]
    contract, evidence, _candidates = discover_contract(
        meta=meta,
        draftinfo=draftinfo,
        players_payloads=players,
        contest_ids=(1,),
        game_ids=(7,),
        games_scheduled=1,
        games_captured=1,
        captured_at="2026-09-25T00:00:00Z",
    )
    assert contract.boost_regime is BoostRegime.FLAT
    assert any("live player cards" in n for n in evidence.notes)
