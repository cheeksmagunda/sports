from __future__ import annotations

import pytest

from nhl_oracle.contract.schema import (
    BoostRegime,
    ContestFormat,
    LockScope,
    NhlCandidate,
    NhlContestContract,
)


def test_default_contract_matches_live_audit_defaults() -> None:
    """Defaults were updated after the Week 2 live Real Sports audit (#299)."""

    contract = NhlContestContract()
    assert contract.format is ContestFormat.FIVE_CARD_ORDERED
    assert contract.lock_scope is LockScope.PER_CONTEST
    assert contract.boost_regime is BoostRegime.FLAT
    assert contract.score_value_label == "value"
    assert contract.roster_size == 5
    assert contract.slot_multipliers == (2.0, 1.8, 1.6, 1.4, 1.2)
    assert contract.goalie_eligible is True
    assert contract.open_questions() == ()


def test_unknown_fields_still_surface_open_questions() -> None:
    contract = NhlContestContract(
        format=ContestFormat.UNKNOWN,
        lock_scope=LockScope.UNKNOWN,
        boost_regime=BoostRegime.UNKNOWN,
        score_value_label=None,
        slot_multipliers=None,
        goalie_eligible=None,
    )
    questions = contract.open_questions()
    assert "contest_format_five_card_ordered_vs_roster_construction" in questions
    assert "lock_scope_per_contest_vs_per_game" in questions
    assert "goalie_eligibility_unconfirmed" in questions
    assert "boost_regime_unconfirmed" in questions
    assert "score_value_label_unconfirmed" in questions


def test_confirmed_contract_has_no_open_questions() -> None:
    contract = NhlContestContract(
        format=ContestFormat.FIVE_CARD_ORDERED,
        lock_scope=LockScope.PER_CONTEST,
        boost_regime=BoostRegime.FLAT,
        score_value_label="fantasyPoints",
        slot_multipliers=(2.0, 1.8, 1.6, 1.4, 1.2),
        goalie_eligible=True,
    )
    assert contract.open_questions() == ()


def test_slot_multipliers_length_must_match_roster_size() -> None:
    with pytest.raises(ValueError, match="slot_multipliers_length_must_match_roster_size"):
        NhlContestContract(roster_size=5, slot_multipliers=(1.0, 1.0))


def test_slot_multipliers_must_be_positive() -> None:
    with pytest.raises(ValueError, match="slot_multipliers_must_be_positive"):
        NhlContestContract(roster_size=2, slot_multipliers=(1.0, -1.0))


def test_candidate_requires_positive_player_id() -> None:
    with pytest.raises(ValueError, match="player_id_must_be_positive"):
        NhlCandidate(
            player_id=0,
            position="C",
            score_value=1.0,
            captured_at="2026-01-01T00:00:00+00:00",
        )


def test_candidate_requires_position() -> None:
    with pytest.raises(ValueError, match="position_required"):
        NhlCandidate(
            player_id=1,
            position="",
            score_value=1.0,
            captured_at="2026-01-01T00:00:00+00:00",
        )
