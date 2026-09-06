"""Provider stubs: auth probe + five-card shadow (no network)."""

from __future__ import annotations

import pytest

from nfl_oracle.providers.auth_status import probe_realsports_auth
from nfl_oracle.providers.cli import main as provider_main
from nfl_oracle.providers.five_card import (
    OFFLINE_RULE_NOTES,
    UNKNOWN_PROVIDER_RULES,
    FiveCardProviderStub,
    ProviderContractStatus,
    ProviderNotReady,
    offline_provider_rule_document,
)
from nfl_oracle.strategy.schema import FiveCardAction


def test_probe_realsports_auth_reports_missing_without_secrets() -> None:
    result = probe_realsports_auth()
    payload = result.to_json_obj()
    assert "usable" in payload
    assert payload["env_b64gz_set"] is False or isinstance(payload["env_b64gz_set"], bool)
    # Never leak secret-like fields
    blob = str(payload).lower()
    assert "cookie" not in blob
    assert "token" not in blob or "token_cache_exists" in blob
    assert "password" not in blob


def test_five_card_stub_blocks_live_and_submit() -> None:
    stub = FiveCardProviderStub()
    ready = stub.readiness()
    assert ready.contest_entry is False
    assert ready.status in {
        ProviderContractStatus.AUTH_MISSING,
        ProviderContractStatus.UNVERIFIED,
        ProviderContractStatus.STUB,
    }
    action = FiveCardAction(player_ids=(1, 2, 3, 4, 5))
    preview = stub.shadow_preview(action)
    assert preview["contest_entry"] is False
    assert preview["structurally_valid"] is True
    with pytest.raises(ProviderNotReady):
        stub.fetch_slate_inventory(slate_id="demo")
    with pytest.raises(ProviderNotReady, match="contest_entry_forbidden"):
        stub.submit(action)


def test_provider_cli_json(capsys: pytest.CaptureFixture[str]) -> None:
    assert provider_main(["--json", "--preview-ids", "10,20,30,40,50"]) == 0
    out = capsys.readouterr().out
    assert "provider" in out
    assert "contest_entry" in out
    assert "password" not in out.lower()


def test_offline_rule_notes_cover_unknown_rules_without_enabling_submit() -> None:
    assert len(UNKNOWN_PROVIDER_RULES) == 7
    for key in UNKNOWN_PROVIDER_RULES:
        assert key in OFFLINE_RULE_NOTES
        assert len(OFFLINE_RULE_NOTES[key]) > 40
    doc = offline_provider_rule_document()
    assert doc["contest_entry"] is False
    assert doc["submit_enabled"] is False
    assert doc["provider_contract_verified"] is False
    assert set(doc["unknown_rules"]) == set(UNKNOWN_PROVIDER_RULES)
    stub = FiveCardProviderStub()
    ready = stub.readiness()
    payload = ready.to_json_obj()
    assert payload["contest_entry"] is False
    assert payload["provider_contract_verified"] is False
    assert set(payload["offline_rule_notes"]) == set(UNKNOWN_PROVIDER_RULES)
