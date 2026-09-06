"""Contest scoring algebra + entry gates (observation only)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nfl_oracle.features.rows import build_prior_rows_for_players
from nfl_oracle.labels.schema import ValueLabel
from nfl_oracle.providers.auth_status import AuthProbeResult
from nfl_oracle.providers.five_card import (
    FiveCardProviderStub,
    ProviderContractStatus,
    ProviderReadiness,
)
from nfl_oracle.service.app import create_app
from nfl_oracle.strategy.algebra import (
    OBSERVED_DEFAULT_SLOT_MULTIPLIERS,
    contest_shadow_score,
    scoring_document,
)
from nfl_oracle.strategy.enumerate import best_shadow_ordering, rank_shadow_orderings
from nfl_oracle.strategy.gates import evaluate_entry_gates
from nfl_oracle.strategy.schema import FiveCardAction, Posture


def test_observed_default_multipliers() -> None:
    assert OBSERVED_DEFAULT_SLOT_MULTIPLIERS == (2.0, 1.8, 1.6, 1.4, 1.2)


def test_contest_algebra_lawrence_example() -> None:
    """Replay D. Lawrence highestScore check from playbook (contest 1069)."""

    action = FiveCardAction(
        player_ids=(1, 2, 3, 4, 5),
        slot_multipliers=OBSERVED_DEFAULT_SLOT_MULTIPLIERS,
    )
    # Put Lawrence in slot index 1 (positionOfHighestScore=2 → 1-indexed).
    values = {2: 7.866925222222221}
    boosts = {2: 2.4}
    score = contest_shadow_score(action, values, boosts_by_player=boosts)
    assert score.non_negative_branch
    lawrence = score.per_slot[1]
    assert lawrence.score == pytest.approx(33.04108593333333)
    assert lawrence.effective_multiplier == pytest.approx(1.8 + 2.4)


def test_contest_algebra_refuses_negative_without_override() -> None:
    action = FiveCardAction(
        player_ids=(1, 2, 3, 4, 5),
        slot_multipliers=OBSERVED_DEFAULT_SLOT_MULTIPLIERS,
    )
    score = contest_shadow_score(action, {1: -0.5, 2: 1.0, 3: 1.0, 4: 1.0, 5: 1.0})
    assert not score.non_negative_branch
    assert score.total == 0.0
    assert "unresolved" in score.notes


def test_best_ordering_contest_algebra_sorts_by_value_when_boosts_equal() -> None:
    values = {1: 10.0, 2: 5.0, 3: 4.0, 4: 3.0, 5: 2.0}
    action, total = best_shadow_ordering(
        (1, 2, 3, 4, 5),
        values,
        use_contest_algebra=True,
    )
    assert action.player_ids[0] == 1
    assert action.player_ids[-1] == 5
    assert total == pytest.approx(10 * 2.0 + 5 * 1.8 + 4 * 1.6 + 3 * 1.4 + 2 * 1.2)


def test_rank_shadow_orderings_top_k() -> None:
    ranked = rank_shadow_orderings(
        (1, 2, 3, 4, 5),
        {1: 10.0, 2: 5.0, 3: 4.0, 4: 3.0, 5: 2.0},
        top_k=3,
    )
    assert len(ranked) == 3
    assert ranked[0]["rank"] == 1
    assert ranked[0]["player_ids"][0] == 1
    assert ranked[0]["total"] >= ranked[1]["total"] >= ranked[2]["total"]


def test_entry_gates_always_forbid_contest_entry() -> None:
    report = evaluate_entry_gates()
    assert report.contest_entry is False
    assert "package_submit_hard_deny" in report.blocked_reasons
    assert report.posture in {
        Posture.BLOCKED,
        Posture.SHADOW_ONLY,
        Posture.READY_PENDING_CONTRACT,
        Posture.CAPTURE_ONLY,
    }

    # Even if every research flag is flipped, package hard-deny remains.
    class _ReadyStub(FiveCardProviderStub):
        def readiness(self) -> ProviderReadiness:
            return ProviderReadiness(
                status=ProviderContractStatus.VERIFIED,
                contest_entry=False,
                auth=AuthProbeResult(
                    usable=True,
                    storage_state_path=None,
                    storage_state_exists=False,
                    env_path_set=False,
                    env_b64gz_set=True,
                    device_uuid_set=True,
                    device_name_set=True,
                    token_cache_exists=False,
                    sibling_wnba_storage_exists=False,
                    notes=(),
                ),
                unknown_rules=(),
                issue_refs=("#91",),
            )

    forced = evaluate_entry_gates(
        stub=_ReadyStub(),
        provider_contract_verified=True,
        pre_lock_capture_proven=True,
        submit_explicitly_authorized=True,
    )
    assert forced.contest_entry is False
    assert "package_submit_hard_deny" in forced.blocked_reasons


def test_prior_feature_rows_walk_forward() -> None:
    train = [
        ValueLabel(player_id=1, game_id=1, season=2022, position="QB", value=10.0),
        ValueLabel(player_id=1, game_id=2, season=2022, position="QB", value=14.0),
        ValueLabel(player_id=2, game_id=3, season=2022, position="RB", value=8.0),
        ValueLabel(player_id=1, game_id=4, season=2024, position="QB", value=99.0),
    ]
    rows = build_prior_rows_for_players(
        train_labels=train,
        players=[(1, "QB"), (99, "QB")],
        decision_season=2024,
        week=1,
    )
    assert rows[0]["player_prior_mean"] == 12.0
    assert rows[0]["same_slate_final_value"] is None
    assert rows[0]["week"] == 1
    assert rows[1]["prior_fallback"] == "position"


def test_scoring_schema_and_research_routes() -> None:
    doc = scoring_document()
    assert doc["contest_entry"] is False
    assert doc["observed_default_slot_multipliers"] == [2.0, 1.8, 1.6, 1.4, 1.2]

    client = TestClient(create_app())
    scoring = client.get("/research/schemas/scoring").json()
    assert scoring["name"] == "nfl_contest_scoring_algebra"
    gates = client.get("/research/gates/entry").json()
    assert gates["contest_entry"] is False
    assert any(g["key"] == "package_submit_hard_deny" for g in gates["gates"])

    preview = client.post(
        "/research/shadow/preview",
        json={
            "player_ids": [1, 2, 3, 4, 5],
            "values_by_player": {"1": 10, "2": 5, "3": 4, "4": 3, "5": 2},
            "boosts_by_player": {"5": 3.0},
            "use_contest_algebra": True,
        },
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["contest_entry"] is False
    assert "contest_shadow_score" in body
    assert "best_ordering" in body
    assert body["best_ordering"]["player_ids"][0] == 1

    ranked = client.post(
        "/research/shadow/rank-orderings",
        json={
            "player_ids": [1, 2, 3, 4, 5],
            "values_by_player": {"1": 10, "2": 5, "3": 4, "4": 3, "5": 2},
            "top_k": 5,
        },
    )
    assert ranked.status_code == 200
    rbody = ranked.json()
    assert rbody["returned"] == 5
    assert rbody["contest_entry"] is False

    status = client.get("/research/status").json()
    assert status["entry_gates"]["contest_entry"] is False
    assert status["railway"]["in_repo_config"] is False
    assert status["auth"]["usable"] is False or isinstance(status["auth"]["usable"], bool)

    bad = client.post(
        "/research/shadow/preview",
        json={"player_ids": [1, 1, 3, 4, 5], "values_by_player": {"1": 1}},
    )
    # duplicate ids are structurally invalid but pydantic accepts the tuple;
    # stub preview still returns 200 with structurally_valid=False
    assert bad.status_code == 200
    assert bad.json()["structurally_valid"] is False

    live = client.get("/research/features/live-ok").json()
    assert "week" in live["live_ok"]
    assert "card_boost_post_settlement" not in live["live_ok"]
    assert "same_slate_final_value" not in live["live_ok"]
