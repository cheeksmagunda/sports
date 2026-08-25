"""Security regression tests for the legacy stack-alignment diagnostic."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

import psycopg
import pytest


def _load_script() -> ModuleType:
    path = Path(__file__).parents[2] / "scripts" / "stack_alignment_check.py"
    spec = importlib.util.spec_from_file_location("stack_alignment_check", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_connect_strips_wrapping_quotes_and_redacts_failure() -> None:
    module = _load_script()
    leaked = "postgresql://readonly:do-not-print@example.invalid/db"
    with (
        patch.dict(module.os.environ, {"DATABASE_PUBLIC_URL": f"'{leaked}'"}, clear=True),
        patch.object(
            module.psycopg,
            "connect",
            side_effect=psycopg.OperationalError(f"connection failed for {leaked}"),
        ) as connect,
        pytest.raises(SystemExit) as caught,
    ):
        module._connect()

    assert str(caught.value) == "database connection failed; connection details redacted"
    assert leaked not in str(caught.value)
    connect.assert_called_once_with(leaked, connect_timeout=20)
