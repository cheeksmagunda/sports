"""Extra research/service/strategy scaffolding tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nfl_oracle.data.summary import research_data_summary
from nfl_oracle.features.schema import live_ok_feature_names
from nfl_oracle.providers.auth_status import AuthProbeResult
from nfl_oracle.providers.five_card import (
    FiveCardProviderStub,
    ProviderContractStatus,
    ProviderReadiness,
)
from nfl_oracle.service.app import create_app
from nfl_oracle.strategy.enumerate import (
    ORDERINGS_PER_SET,
    best_shadow_ordering,
    ordered_five_card_actions,
)
from nfl_oracle.strategy.posture import posture_from_readiness
from nfl_oracle.strategy.schema import Posture


def _auth(*, usable: bool = False) -> AuthProbeResult:
    return AuthProbeResult(
        usable=usable,
        storage_state_path=None,
        storage_state_exists=False,
        env_path_set=False,
        env_b64gz_set=usable,
        device_uuid_set=False,
        device_name_set=False,
        token_cache_exists=False,
        sibling_wnba_storage_exists=False,
        notes=(),
    )


def test_ordered_five_card_actions_count() -> None:
    actions = ordered_five_card_actions((1, 2, 3, 4, 5))
    assert len(actions) == ORDERINGS_PER_SET
    assert len({a.player_ids for a in actions}) == ORDERINGS_PER_SET


def test_ordered_five_card_rejects_duplicates() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        ordered_five_card_actions((1, 1, 3, 4, 5))


def test_best_shadow_ordering_puts_highest_value_first_with_slot_weights() -> None:
    values = {1: 10.0, 2: 5.0, 3: 4.0, 4: 3.0, 5: 2.0}
    action, total = best_shadow_ordering(
        (1, 2, 3, 4, 5),
        values,
        slot_multipliers=(3.0, 2.0, 1.0, 1.0, 1.0),
    )
    assert action.player_ids[0] == 1
    assert action.player_ids[1] == 2
    assert total == 3 * 10 + 2 * 5 + 4 + 3 + 2


def test_posture_from_readiness_mapping() -> None:
    blocked = ProviderReadiness(
        status=ProviderContractStatus.AUTH_MISSING,
        contest_entry=False,
        auth=_auth(usable=False),
        unknown_rules=(),
        issue_refs=("#91",),
    )
    assert posture_from_readiness(blocked) == Posture.BLOCKED
    pending = ProviderReadiness(
        status=ProviderContractStatus.UNVERIFIED,
        contest_entry=False,
        auth=_auth(usable=True),
        unknown_rules=(),
        issue_refs=("#91",),
    )
    assert posture_from_readiness(pending) == Posture.READY_PENDING_CONTRACT


def test_research_data_summary_from_catalog() -> None:
    root = Path(__file__).resolve().parents[2]
    summary = research_data_summary(project_root=root)
    assert summary["contest_entry"] is False
    assert summary["catalog"]["season_count"] >= 1
    assert summary["catalog"]["seed_game_count"] >= 1


def test_live_ok_excludes_same_slate_final() -> None:
    names = live_ok_feature_names()
    assert "player_prior_mean" in names
    assert "same_slate_final_value" not in names


def test_research_status_and_shadow_preview_routes() -> None:
    root = Path(__file__).resolve().parents[2]
    client = TestClient(create_app(project_root=root))
    status = client.get("/research/status").json()
    assert status["contest_entry"] is False
    assert status["railway"]["in_repo_config"] is False
    assert "posture" in status
    coverage = client.get("/research/coverage/summary").json()
    assert coverage["catalog"]["season_count"] >= 1
    live = client.get("/research/features/live-ok").json()
    assert "player_prior_mean" in live["live_ok"]
    preview = client.post(
        "/research/shadow/preview",
        json={
            "player_ids": [1, 2, 3, 4, 5],
            "slot_multipliers": [3, 2, 1, 1, 1],
            "values_by_player": {"1": 10, "2": 5, "3": 4, "4": 3, "5": 2},
        },
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["contest_entry"] is False
    assert body["structurally_valid"] is True
    assert body["shadow_score"]["total"] == 3 * 10 + 2 * 5 + 4 + 3 + 2
    health = client.get("/health").json()
    assert "checks" in health
    assert "realsports_auth" in health["checks"]


def test_provider_stub_submit_still_forbidden() -> None:
    from nfl_oracle.strategy.schema import FiveCardAction

    stub = FiveCardProviderStub()
    with pytest.raises(Exception, match="contest_entry_forbidden"):
        stub.submit(FiveCardAction(player_ids=(1, 2, 3, 4, 5)))
