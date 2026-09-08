"""Strategy scaffold: clocks, five-card legality, snapshots."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nfl_oracle.strategy.cli import main as strategy_main
from nfl_oracle.strategy.clocks import feature_clocks_ok, live_feature_allowed
from nfl_oracle.strategy.schema import (
    FiveCardAction,
    Posture,
    ShadowDecisionSnapshot,
    check_action,
    clocks_allow_feature,
    strategy_document,
)


def test_feature_clocks_ok_requires_all_and_ordering() -> None:
    assert feature_clocks_ok(
        source_available_at="2026-09-01T12:00:00+00:00",
        captured_at="2026-09-01T12:05:00+00:00",
        decision_at="2026-09-01T13:00:00+00:00",
    )
    assert not feature_clocks_ok(
        source_available_at="2026-09-01T14:00:00+00:00",
        captured_at="2026-09-01T12:05:00+00:00",
        decision_at="2026-09-01T13:00:00+00:00",
    )
    assert not feature_clocks_ok(
        source_available_at="2026-09-01T12:00:00+00:00",
        captured_at="2026-09-01T12:05:00+00:00",
        decision_at=None,
    )


def test_clocks_allow_feature_respects_lock_and_blacklist() -> None:
    assert clocks_allow_feature(
        feature_name="position_prior_mean",
        source_available_at="2026-09-01T12:00:00+00:00",
        captured_at="2026-09-01T12:05:00+00:00",
        decision_at="2026-09-01T13:00:00+00:00",
        lock_at="2026-09-01T17:00:00+00:00",
    )
    assert not clocks_allow_feature(
        feature_name="same_slate_final_value",
        source_available_at="2026-09-01T12:00:00+00:00",
        captured_at="2026-09-01T12:05:00+00:00",
        decision_at="2026-09-01T13:00:00+00:00",
        lock_at="2026-09-01T17:00:00+00:00",
    )


def test_live_feature_blacklist_keys_forbidden() -> None:
    assert (
        live_feature_allowed("same_slate_final_value", decision_at="2026-09-01T13:00:00+00:00")
        is False
    )
    assert (
        live_feature_allowed("position_prior_mean", decision_at="2026-09-01T13:00:00+00:00") is True
    )
    assert live_feature_allowed("position_prior_mean", decision_at=None) is False


def test_validate_five_card_structural() -> None:
    ok = check_action(FiveCardAction(player_ids=(1, 2, 3, 4, 5)))
    assert ok.ok
    assert "provider lock semantics" in ok.unknown_rules
    bad = check_action(FiveCardAction(player_ids=(1, 1, 3, 4, 5)))
    assert not bad.ok
    assert "duplicate_player_ids" in bad.structural_errors


def test_shadow_snapshot_forbids_contest_entry() -> None:
    snap = ShadowDecisionSnapshot(decision_at="2026-09-01T13:00:00+00:00")
    assert snap.posture == Posture.READY_PENDING_CONTRACT
    assert snap.contest_entry is False
    with pytest.raises(ValidationError):
        ShadowDecisionSnapshot(decision_at="t", contest_entry=True)  # type: ignore[arg-type]


def test_strategy_document_and_cli(capsys) -> None:
    doc = strategy_document()
    assert doc["contest_entry"] is False
    assert doc["name"] == "nfl_strategy_scaffold"
    assert "playbook" in doc
    assert strategy_main(["--schema-only"]) == 0
    out = capsys.readouterr().out
    assert "nfl_strategy_scaffold" in out
