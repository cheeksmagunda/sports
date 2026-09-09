from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from nfl_oracle.recommendations.provider import ProviderError, parse_contest
from nfl_oracle.recommendations.schema import Candidate, Contest, EvidenceClock, Game, Slate

NOW = datetime(2026, 9, 9, 20, tzinfo=UTC)


def sample_slate(*, teams: int = 2, players: int = 8) -> Slate:
    clock = EvidenceClock(source_available_at=NOW, captured_at=NOW)
    games = tuple(
        Game(
            game_id=g + 1,
            season=2026,
            kickoff_at=NOW + timedelta(hours=4),
            home_team_id=g * 2 + 1,
            away_team_id=g * 2 + 2,
            home_team=f"T{g * 2 + 1}",
            away_team=f"T{g * 2 + 2}",
            status="scheduled",
        )
        for g in range((teams + 1) // 2)
    )
    candidates = tuple(
        Candidate(
            player_id=i + 1,
            game_id=(i % teams) // 2 + 1,
            team_id=i % teams + 1,
            name=f"Player {i + 1}",
            position="WR",
            team=f"T{i % teams + 1}",
            opponent="Opponent",
            injury_status="Active",
            card_boost=0,
            clock=clock,
        )
        for i in range(players)
    )
    return Slate(
        contest=Contest(
            contest_id=2141,
            day=NOW.date(),
            end_day=NOW.date(),
            slot_multipliers=(2, 1.8, 1.6, 1.4, 1.2),
            is_locked=False,
            is_finalized=False,
            clock=clock,
            evidence_sha256="a" * 64,
        ),
        games=games,
        candidates=candidates,
        captured_at=NOW,
        source_hashes=("b" * 64,),
        pool_roster_count=players,
        pool_search_matched_count=players,
    )


def test_submission_cannot_be_enabled() -> None:
    data = sample_slate().contest.model_dump()
    data["contest_entry"] = True
    with pytest.raises(ValidationError):
        Contest.model_validate(data)


def test_live_clocks_fail_closed() -> None:
    slate = sample_slate()
    slate.assert_prelock(NOW)
    for when in (NOW - timedelta(seconds=1), NOW + timedelta(minutes=16), slate.cutoff()):
        with pytest.raises(ValueError):
            slate.assert_prelock(when)


def test_unknown_lock_is_not_promoted_to_provider_fact() -> None:
    slate = sample_slate()
    assert slate.contest.provider_lock_at is None
    assert slate.cutoff() == min(g.kickoff_at for g in slate.games)


def test_slate_declares_complete_pool_and_boost_regime() -> None:
    complete = sample_slate()
    assert complete.pool_complete is True
    assert complete.boost_regime == "zero_boost"
    assert complete.boost_nonzero_count == 0
    assert complete.boost_max == 0.0

    boosted_data = complete.model_dump(mode="json")
    boosted_data["candidates"][0]["card_boost"] = 0.5
    boosted_data["boost_regime"] = "provider_boosts_present"
    boosted_data["boost_nonzero_count"] = 1
    boosted_data["boost_max"] = 0.5
    boosted = Slate.model_validate(boosted_data)
    assert boosted.boost_regime == "provider_boosts_present"
    assert boosted.boost_nonzero_count == 1
    assert boosted.boost_max == 0.5

    with pytest.raises(ValidationError, match="boost_regime_declaration_mismatch"):
        Slate.model_validate(
            {
                **boosted_data,
                "boost_regime": "zero_boost",
                "boost_nonzero_count": 1,
                "boost_max": 0.5,
            }
        )


def test_incomplete_pool_fails_prelock_gate() -> None:
    slate = sample_slate()
    partial = Slate.model_validate(
        {
            **slate.model_dump(mode="json"),
            "candidates": slate.model_dump(mode="json")["candidates"][:6],
            "pool_roster_count": 7,
            "pool_search_matched_count": 6,
            "pool_unmatched_ids": [7],
            "pool_complete": False,
        }
    )
    assert partial.pool_complete is False
    with pytest.raises(ValueError, match="incomplete_player_pool"):
        partial.assert_prelock(NOW)


def test_identity_and_nonfinite_values_rejected() -> None:
    data = sample_slate().model_dump()
    data["candidates"] = [data["candidates"][0]] * 5
    with pytest.raises(ValidationError, match="duplicate_player"):
        Slate.model_validate(data)
    data = sample_slate().candidates[0].model_dump()
    data["card_boost"] = float("nan")
    with pytest.raises(ValidationError):
        Candidate.model_validate(data)


def test_provider_contest_namespace_and_contract() -> None:
    raw = {
        "id": 2141,
        "sport": "nfl",
        "day": "2026-09-09",
        "endDay": "2026-09-09",
        "isFinalized": False,
        "additionalInfo": {"lineupSize": 5},
    }
    meta = {"info": {"contest": raw, "isLocked": False}}
    draft = {
        "info": {
            "sport": "nfl",
            "day": "2026-09-09",
            "endDay": "2026-09-09",
            "lineupSize": 5,
            "defaultMultipliers": [2, 1.8, 1.6, 1.4, 1.2],
        }
    }
    parsed = parse_contest(meta, draft, contest_id=2141, captured_at=NOW, hashes=("a", "b"))
    assert parsed.contest_entry is False
    raw["sport"] = "nba"
    with pytest.raises(ProviderError, match="identity"):
        parse_contest(meta, draft, contest_id=2141, captured_at=NOW, hashes=("a", "b"))


def test_presence_tests_do_not_read_host_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    from nfl_oracle.providers.five_card import FiveCardProviderStub
    from nfl_oracle.strategy.gates import evaluate_entry_gates

    # Even affirmative readiness arguments cannot enable submission.
    report = evaluate_entry_gates(
        stub=FiveCardProviderStub(),
        provider_contract_verified=True,
        pre_lock_capture_proven=True,
        submit_explicitly_authorized=True,
    )
    assert report.contest_entry is False
    assert "package_submit_hard_deny" in report.blocked_reasons
