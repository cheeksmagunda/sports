"""Hard zero-boost gate: multiplier stays 0 while any team is at 0 GP."""

from __future__ import annotations

from datetime import UTC, datetime

from nhl_oracle.contract.boost_gate import (
    BOOST_MULTIPLIER_GATED,
    NHL_EXPECTED_TEAM_COUNT,
    effective_boost_multiplier,
    evaluate_boost_eligibility,
    force_none_while_gated,
)
from nhl_oracle.contract.discovery import boost_regime_from_players_and_stats
from nhl_oracle.contract.gates import evaluate_nhl_audit
from nhl_oracle.contract.schema import (
    BoostRegime,
    ContestFormat,
    LockScope,
    NhlAuditFixture,
    NhlCandidate,
    NhlContestContract,
)


def _full_coverage(*, zero_team: str | None = None) -> dict[str, int]:
    """32-team map; optionally leave one club at 0 GP."""

    coverage = {f"T{i:02d}": 1 for i in range(NHL_EXPECTED_TEAM_COUNT)}
    if zero_team is not None:
        coverage[zero_team] = 0
    return coverage


def test_boost_multiplier_zero_while_any_team_at_zero_gp() -> None:
    coverage = _full_coverage(zero_team="T00")
    eligibility = evaluate_boost_eligibility(coverage)
    assert eligibility.boost_allowed is False
    assert eligibility.boost_multiplier == BOOST_MULTIPLIER_GATED
    assert eligibility.teams_at_zero_gp == 1
    assert eligibility.zero_gp_team_ids == ("T00",)
    assert effective_boost_multiplier(coverage, proposed_multiplier=1.5) == 0.0
    assert effective_boost_multiplier(coverage, proposed_multiplier=0.75) == 0.0


def test_boost_multiplier_zero_when_coverage_incomplete() -> None:
    # Fail closed: missing clubs keep the early-slate gap armed.
    partial = {f"T{i:02d}": 2 for i in range(NHL_EXPECTED_TEAM_COUNT - 3)}
    eligibility = evaluate_boost_eligibility(partial)
    assert eligibility.boost_allowed is False
    assert eligibility.boost_multiplier == 0.0
    assert effective_boost_multiplier(None) == 0.0
    assert effective_boost_multiplier({}) == 0.0


def test_boost_clears_only_when_every_team_has_played() -> None:
    coverage = _full_coverage()
    eligibility = evaluate_boost_eligibility(coverage)
    assert eligibility.boost_allowed is True
    assert eligibility.boost_multiplier == 1.0
    assert eligibility.teams_at_zero_gp == 0
    assert effective_boost_multiplier(coverage, proposed_multiplier=1.25) == 1.25


def test_force_none_while_gated_overrides_flat_cards() -> None:
    eligibility = evaluate_boost_eligibility(_full_coverage(zero_team="T07"))
    regime, _ = force_none_while_gated(BoostRegime.FLAT, eligibility)
    assert regime is BoostRegime.NONE


def test_discovery_forces_none_when_live_cards_show_flat_but_team_still_at_zero() -> None:
    players = [
        {
            "players": [
                {"id": 1, "position": "C", "value": 10.0, "multiplierBonus": 0.2},
                {"id": 2, "position": "G", "value": 8.0, "multiplierBonus": 0.1},
            ]
        }
    ]
    regime, notes = boost_regime_from_players_and_stats(
        players,
        team_games_played=_full_coverage(zero_team="T03"),
    )
    assert regime is BoostRegime.NONE
    assert any("hard_zero_boost_gate" in n for n in notes)
    assert any("zero_boost_gate_active" in n for n in notes)
    assert any("gap" in n.lower() or "mispricing" in n for n in notes)


def test_discovery_allows_flat_only_when_all_teams_have_played() -> None:
    players = [
        {
            "players": [
                {"id": 1, "position": "C", "value": 10.0, "multiplierBonus": 0.2},
                {"id": 2, "position": "G", "value": 8.0, "multiplierBonus": 0.1},
            ]
        }
    ]
    regime, notes = boost_regime_from_players_and_stats(
        players,
        team_games_played=_full_coverage(),
    )
    assert regime is BoostRegime.FLAT
    assert any("zero_boost_gate_cleared" in n for n in notes)


def test_audit_blocks_flat_regime_while_team_at_zero_gp() -> None:
    from nhl_oracle.contract.boost_gate import TeamGamesPlayed

    contract = NhlContestContract(
        format=ContestFormat.FIVE_CARD_ORDERED,
        lock_scope=LockScope.PER_CONTEST,
        boost_regime=BoostRegime.FLAT,
        score_value_label="value",
        slot_multipliers=(2.0, 1.8, 1.6, 1.4, 1.2),
        goalie_eligible=True,
    )
    candidates = tuple(
        NhlCandidate(
            player_id=100 + i,
            position="C",
            score_value=float(i),
            captured_at="2026-09-30T23:00:00+00:00",
        )
        for i in range(5)
    )
    coverage = tuple(
        TeamGamesPlayed(team_id=team_id, games_played=gp)
        for team_id, gp in _full_coverage(zero_team="T11").items()
    )
    fixture = NhlAuditFixture(
        contract=contract,
        candidates=candidates,
        expected_roster_size=5,
        team_games_played=coverage,
    )
    report = evaluate_nhl_audit(
        fixture,
        decision_at=datetime(2026, 10, 1, 0, 0, tzinfo=UTC),
    )
    assert "zero_boost_until_all_teams_played" in report.blocked_reasons
    assert report.contest_entry is False
