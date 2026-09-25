"""Unit tests for scripts/codespace-railway-env auth preference (no live Railway)."""

from __future__ import annotations

import importlib.machinery
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_path = ROOT / "scripts" / "codespace-railway-env"
_loader = importlib.machinery.SourceFileLoader("codespace_railway_env", str(_path))
_spec = importlib.util.spec_from_loader(_loader.name, _loader)
assert _spec and _spec.loader
cre = importlib.util.module_from_spec(_spec)
sys.modules["codespace_railway_env"] = cre
_spec.loader.exec_module(cre)


def test_prefer_auth_order_session_first_when_both_present() -> None:
    assert cre.prefer_auth_order(session_ok=True, api_token_present=True) == [
        "cli-session",
        "api-token",
    ]


def test_prefer_auth_order_api_only_when_no_session() -> None:
    assert cre.prefer_auth_order(session_ok=False, api_token_present=True) == [
        "api-token"
    ]


def test_prefer_auth_order_session_only() -> None:
    assert cre.prefer_auth_order(session_ok=True, api_token_present=False) == [
        "cli-session"
    ]


def test_prefer_auth_order_empty_when_neither() -> None:
    assert cre.prefer_auth_order(session_ok=False, api_token_present=False) == []


def test_cli_session_present_detects_access_and_refresh(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps(
            {
                "user": {
                    "accessToken": "access-example",
                    "refreshToken": "refresh-example",
                }
            }
        ),
        encoding="utf-8",
    )
    assert cre.cli_session_present(cfg) is True


def test_cli_session_present_false_when_missing_tokens(tmp_path: Path) -> None:
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"user": {"id": "x"}}), encoding="utf-8")
    assert cre.cli_session_present(cfg) is False


def test_cli_session_present_false_when_no_file(tmp_path: Path) -> None:
    assert cre.cli_session_present(tmp_path / "missing.json") is False


def test_build_env_prefers_session_over_api_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_whoami(env: dict[str, str]) -> tuple[bool, str]:
        if env.get("RAILWAY_API_TOKEN"):
            calls.append("api")
            return False, "Unauthorized"
        calls.append("session")
        return True, "Logged in as Cheeks Magunda"

    monkeypatch.setenv("RAILWAY_TOKEN", "project-should-be-dropped")
    monkeypatch.setenv("RAILWAY_API_TOKEN", "broken-api-token")

    env = cre.build_env(
        whoami_fn=fake_whoami,
        session_present_fn=lambda: True,
        load_api_token_fn=lambda: "broken-api-token",
    )

    assert "RAILWAY_TOKEN" not in env
    assert "RAILWAY_API_TOKEN" not in env
    assert calls == ["session"]


def test_build_env_falls_back_to_api_when_session_whoami_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def fake_whoami(env: dict[str, str]) -> tuple[bool, str]:
        if env.get("RAILWAY_API_TOKEN") == "good-api":
            calls.append("api-ok")
            return True, "Logged in as API User"
        calls.append("session-fail")
        return False, "session expired"

    monkeypatch.delenv("RAILWAY_API_TOKEN", raising=False)
    monkeypatch.setenv("RAILWAY_TOKEN", "drop-me")

    env = cre.build_env(
        whoami_fn=fake_whoami,
        session_present_fn=lambda: True,
        load_api_token_fn=lambda: "good-api",
    )

    assert env.get("RAILWAY_API_TOKEN") == "good-api"
    assert "RAILWAY_TOKEN" not in env
    assert calls == ["session-fail", "api-ok"]
