from __future__ import annotations

from datetime import UTC, datetime

from nhl_oracle.contract.boost_gate import NHL_EXPECTED_TEAM_COUNT, TeamGamesPlayed
from nhl_oracle.contract.gates import evaluate_nhl_audit
from nhl_oracle.contract.schema import (
    BoostRegime,
    ContestFormat,
    LockScope,
    NhlAuditFixture,
    NhlCandidate,
    NhlContestContract,
)

DECISION_AT = datetime(2026, 10, 1, 0, 0, tzinfo=UTC)


def _all_teams_played() -> tuple[TeamGamesPlayed, ...]:
    return tuple(
        TeamGamesPlayed(team_id=f"T{i:02d}", games_played=1) for i in range(NHL_EXPECTED_TEAM_COUNT)
    )


def _confirmed_contract() -> NhlContestContract:
    return NhlContestContract(
        format=ContestFormat.FIVE_CARD_ORDERED,
        lock_scope=LockScope.PER_CONTEST,
        boost_regime=BoostRegime.FLAT,
        score_value_label="fantasyPoints",
        slot_multipliers=(2.0, 1.8, 1.6, 1.4, 1.2),
        goalie_eligible=True,
    )


def _complete_candidates() -> tuple[NhlCandidate, ...]:
    return tuple(
        NhlCandidate(
            player_id=100 + i,
            position="C",
            score_value=float(i),
            captured_at="2026-09-30T23:00:00+00:00",
        )
        for i in range(5)
    )


def test_complete_pool_passes_all_gates() -> None:
    fixture = NhlAuditFixture(
        contract=_confirmed_contract(),
        candidates=_complete_candidates(),
        expected_roster_size=5,
        team_games_played=_all_teams_played(),
    )
    report = evaluate_nhl_audit(fixture, decision_at=DECISION_AT)
    assert report.all_gates_ok is True
    assert report.contest_entry is False
    assert report.blocked_reasons == ()


def test_slate_denominator_rejects_five_player_stub() -> None:
    fixture = NhlAuditFixture(
        contract=_confirmed_contract(),
        candidates=_complete_candidates(),
        expected_roster_size=5,
        expected_pool_size=8,
        games_scheduled=2,
        games_captured=2,
        team_games_played=_all_teams_played(),
    )
    report = evaluate_nhl_audit(fixture, decision_at=DECISION_AT)
    assert "pool_completeness" in report.blocked_reasons


def test_uncaptured_games_fail_pool_completeness_gate() -> None:
    fixture = NhlAuditFixture(
        contract=_confirmed_contract(),
        candidates=_complete_candidates(),
        expected_roster_size=5,
        expected_pool_size=5,
        games_scheduled=2,
        games_captured=1,
        team_games_played=_all_teams_played(),
    )
    report = evaluate_nhl_audit(fixture, decision_at=DECISION_AT)
    assert "pool_completeness" in report.blocked_reasons


def test_incomplete_pool_fails_pool_completeness_gate() -> None:
    fixture = NhlAuditFixture(
        contract=_confirmed_contract(),
        candidates=_complete_candidates()[:3],
        expected_roster_size=5,
        team_games_played=_all_teams_played(),
    )
    report = evaluate_nhl_audit(fixture, decision_at=DECISION_AT)
    assert "pool_completeness" in report.blocked_reasons


def test_ambiguous_boost_regime_fails_boost_regime_gate() -> None:
    contract = NhlContestContract(
        format=ContestFormat.FIVE_CARD_ORDERED,
        lock_scope=LockScope.PER_CONTEST,
        boost_regime=BoostRegime.UNKNOWN,
        score_value_label="fantasyPoints",
        slot_multipliers=(2.0, 1.8, 1.6, 1.4, 1.2),
        goalie_eligible=True,
    )
    fixture = NhlAuditFixture(
        contract=contract,
        candidates=_complete_candidates(),
        expected_roster_size=5,
        team_games_played=_all_teams_played(),
    )
    report = evaluate_nhl_audit(fixture, decision_at=DECISION_AT)
    assert "boost_regime" in report.blocked_reasons
    assert "boost_regime_unconfirmed" in report.open_questions


def test_future_capture_fails_clock_freshness_gate() -> None:
    future_candidate = NhlCandidate(
        player_id=999,
        position="G",
        score_value=1.0,
        captured_at="2026-10-02T00:00:00+00:00",
    )
    fixture = NhlAuditFixture(
        contract=_confirmed_contract(),
        candidates=(*_complete_candidates()[:4], future_candidate),
        expected_roster_size=5,
        team_games_played=_all_teams_played(),
    )
    report = evaluate_nhl_audit(fixture, decision_at=DECISION_AT)
    assert "clock_freshness" in report.blocked_reasons


def test_unresolved_identity_fails_identity_resolution_gate() -> None:
    unresolved_candidate = NhlCandidate(
        player_id=999,
        position="G",
        score_value=1.0,
        captured_at="2026-09-30T23:00:00+00:00",
        identity_resolved=False,
    )
    fixture = NhlAuditFixture(
        contract=_confirmed_contract(),
        candidates=(*_complete_candidates()[:4], unresolved_candidate),
        expected_roster_size=5,
        team_games_played=_all_teams_played(),
    )
    report = evaluate_nhl_audit(fixture, decision_at=DECISION_AT)
    assert "identity_resolution" in report.blocked_reasons


def test_unknown_lock_scope_fails_lock_scope_gate() -> None:
    contract = NhlContestContract(
        format=ContestFormat.FIVE_CARD_ORDERED,
        lock_scope=LockScope.UNKNOWN,
        boost_regime=BoostRegime.FLAT,
        score_value_label="fantasyPoints",
        slot_multipliers=(2.0, 1.8, 1.6, 1.4, 1.2),
        goalie_eligible=True,
    )
    fixture = NhlAuditFixture(
        contract=contract,
        candidates=_complete_candidates(),
        expected_roster_size=5,
        team_games_played=_all_teams_played(),
    )
    report = evaluate_nhl_audit(fixture, decision_at=DECISION_AT)
    assert "lock_scope" in report.blocked_reasons


def test_flat_regime_blocked_while_any_team_at_zero_gp() -> None:
    coverage = list(_all_teams_played())
    coverage[0] = TeamGamesPlayed(team_id="T00", games_played=0)
    fixture = NhlAuditFixture(
        contract=_confirmed_contract(),
        candidates=_complete_candidates(),
        expected_roster_size=5,
        team_games_played=tuple(coverage),
    )
    report = evaluate_nhl_audit(fixture, decision_at=DECISION_AT)
    assert "zero_boost_until_all_teams_played" in report.blocked_reasons
    assert report.contest_entry is False
