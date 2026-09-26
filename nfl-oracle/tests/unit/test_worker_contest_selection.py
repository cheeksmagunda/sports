from __future__ import annotations

import pytest

from nfl_oracle.recommendations import cli


def test_select_contest_id_defaults_to_lowest_available(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NFL_CONTEST_ID", raising=False)
    assert cli._select_contest_id([3002, 3001]) == 3001


def test_select_contest_id_honors_configured_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NFL_CONTEST_ID", "3002")
    assert cli._select_contest_id([3001, 3002]) == 3002


def test_select_contest_id_rejects_override_not_on_slate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NFL_CONTEST_ID", "9999")
    assert cli._select_contest_id([3001, 3002]) is None
