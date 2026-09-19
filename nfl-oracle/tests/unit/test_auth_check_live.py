"""NFL parity for wnba-oracle's auth-check-live value-free contract.

scripts/auth-check-live must report presence/validity of Real Sports auth
material without ever printing the material itself, whether the payload is
valid, invalid, or a sentinel-bearing real one.
"""

from __future__ import annotations

import base64
import gzip
import importlib.machinery
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
HOOK_PATH = WORKSPACE_ROOT / "nfl-oracle" / "scripts" / "auth-check-live"


def _load_live_hook() -> Any:
    spec = importlib.util.spec_from_file_location(
        "nfl_auth_check_live_test",
        HOOK_PATH,
        loader=importlib.machinery.SourceFileLoader("nfl_auth_check_live_test", str(HOOK_PATH)),
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _encode(payload: dict[str, Any]) -> str:
    raw = gzip.compress(json.dumps(payload).encode())
    return base64.b64encode(raw).decode()


def test_real_sports_check_accepts_valid_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    hook = _load_live_hook()
    monkeypatch.setenv(
        "REALSPORTS_STORAGE_STATE_B64GZ",
        _encode({"cookies": [], "origins": [{"origin": "https://example.invalid"}]}),
    )
    assert hook.check_real_sports() == 0


def test_real_sports_check_rejects_invalid_structure(monkeypatch: pytest.MonkeyPatch) -> None:
    hook = _load_live_hook()
    monkeypatch.setenv("REALSPORTS_STORAGE_STATE_B64GZ", _encode({"no_origins": True}))
    assert hook.check_real_sports() == 1


def test_real_sports_check_rejects_malformed_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    hook = _load_live_hook()
    monkeypatch.setenv("REALSPORTS_STORAGE_STATE_B64GZ", "not-valid-base64")
    assert hook.check_real_sports() == 1


def test_real_sports_check_reports_not_configured_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hook = _load_live_hook()
    monkeypatch.delenv("REALSPORTS_STORAGE_STATE_B64GZ", raising=False)
    assert hook.check_real_sports() == 0


def test_live_hook_output_is_value_free_end_to_end(tmp_path: Path) -> None:
    """Run the hook as a subprocess with a sentinel-bearing real payload and
    confirm the sentinel never reaches stdout or stderr, matching wnba's
    test_auth_check_output_is_value_free contract."""
    sentinel_origin = "https://sentinel-do-not-print.invalid"
    encoded = _encode(
        {
            "cookies": [],
            "origins": [
                {
                    "origin": sentinel_origin,
                    "localStorage": [{"name": "e-accounts", "value": "token-sentinel-value"}],
                }
            ],
        }
    )
    env = {
        "PATH": "/usr/bin:/bin",
        "REALSPORTS_STORAGE_STATE_B64GZ": encoded,
    }
    result = subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
        cwd=tmp_path,
    )
    combined = result.stdout + result.stderr
    assert sentinel_origin not in combined
    assert "token-sentinel-value" not in combined
    assert encoded not in combined
    assert "Real Sports derived session: payload structure valid" in combined
