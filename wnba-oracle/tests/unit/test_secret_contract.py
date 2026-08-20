from __future__ import annotations

import base64
import gzip
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


@pytest.fixture
def portable_portfolio(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    root = tmp_path / "sports"
    project = root / "wnba-oracle"
    scripts = root / "scripts"
    fake_bin = tmp_path / "bin"
    home = tmp_path / "home"
    scripts.mkdir(parents=True)
    project.mkdir()
    fake_bin.mkdir()
    home.mkdir()

    for name in ("with-secrets", "auth-check"):
        shutil.copy2(WORKSPACE_ROOT / "scripts" / name, scripts / name)
        (scripts / name).chmod(0o755)

    (root / ".env.example").write_text("# auth:optional\nROOT_ONLY=\nSHARED=\n", encoding="utf-8")
    (project / ".env.example").write_text("# auth:optional\nAPP_ONLY=\n", encoding="utf-8")

    root_secrets = root / ".secrets"
    app_secrets = project / ".secrets"
    root_secrets.mkdir(mode=0o700)
    app_secrets.mkdir(mode=0o700)
    root_file = root_secrets / "common.sops.env"
    app_file = app_secrets / "local.sops.env"
    root_file.write_text(
        json.dumps({"ROOT_ONLY": "root-sentinel", "SHARED": "root-choice"}),
        encoding="utf-8",
    )
    app_file.write_text(
        json.dumps({"APP_ONLY": "app-sentinel", "SHARED": "app-choice"}),
        encoding="utf-8",
    )
    root_file.chmod(0o600)
    app_file.chmod(0o600)

    _write_executable(
        fake_bin / "sops",
        "#!/usr/bin/env python3\n"
        "from pathlib import Path\n"
        "import sys\n"
        "sys.stdout.write(Path(sys.argv[-1]).read_text())\n",
    )
    _write_executable(fake_bin / "age", "#!/bin/sh\nexit 0\n")
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"
    env["HOME"] = str(home)
    env.pop("SOPS_AGE_KEY_FILE", None)
    env.pop("SPORTS_SECRETS_ACTIVE", None)
    env.pop("ROOT_ONLY", None)
    env.pop("APP_ONLY", None)
    env.pop("SHARED", None)
    return root, env


def _run_loader(root: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    code = (
        "import json, os; "
        "print(json.dumps({k: os.environ[k] for k in "
        "('ROOT_ONLY', 'APP_ONLY', 'SHARED')}))"
    )
    return subprocess.run(
        [
            str(root / "scripts" / "with-secrets"),
            "wnba-oracle",
            "--",
            sys.executable,
            "-c",
            code,
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_secret_precedence_is_explicit_then_app_then_root(
    portable_portfolio: tuple[Path, dict[str, str]],
) -> None:
    root, env = portable_portfolio
    result = _run_loader(root, env)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "ROOT_ONLY": "root-sentinel",
        "APP_ONLY": "app-sentinel",
        "SHARED": "app-choice",
    }

    env["SHARED"] = "explicit-choice"
    result = _run_loader(root, env)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["SHARED"] == "explicit-choice"


def test_secret_loader_rejects_permissive_files_without_leaking_values(
    portable_portfolio: tuple[Path, dict[str, str]],
) -> None:
    root, env = portable_portfolio
    secret_file = root / "wnba-oracle" / ".secrets" / "local.sops.env"
    secret_file.chmod(0o644)
    result = _run_loader(root, env)
    assert result.returncode == 78
    combined = result.stdout + result.stderr
    assert "mode 0600" in combined
    assert "root-sentinel" not in combined
    assert "app-sentinel" not in combined


def test_loader_creates_no_plaintext_files(
    portable_portfolio: tuple[Path, dict[str, str]],
) -> None:
    root, env = portable_portfolio
    before = {
        path.relative_to(root): (path.read_bytes(), _mode(path))
        for path in root.rglob("*")
        if path.is_file()
    }
    result = subprocess.run(
        [
            str(root / "scripts" / "with-secrets"),
            "wnba-oracle",
            "--",
            sys.executable,
            "-c",
            "pass",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    after = {
        path.relative_to(root): (path.read_bytes(), _mode(path))
        for path in root.rglob("*")
        if path.is_file()
    }
    assert after == before


def test_auth_check_output_is_value_free(
    portable_portfolio: tuple[Path, dict[str, str]],
) -> None:
    root, env = portable_portfolio
    result = subprocess.run(
        [str(root / "scripts" / "auth-check"), "wnba-oracle", "--offline"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stderr
    combined = result.stdout + result.stderr
    assert "auth-check: offline checks passed" in combined
    assert "root-sentinel" not in combined
    assert "app-sentinel" not in combined
    assert "root-choice" not in combined
    assert "app-choice" not in combined


def test_storage_state_seed_is_atomic_and_private(tmp_path: Path) -> None:
    project = tmp_path / "wnba-oracle"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    seed_script = scripts / "seed_storage_state.py"
    shutil.copy2(WORKSPACE_ROOT / "wnba-oracle" / "scripts" / seed_script.name, seed_script)
    payload = {"cookies": [], "origins": [{"origin": "https://example.invalid"}]}
    encoded = base64.b64encode(gzip.compress(json.dumps(payload).encode())).decode()
    env = os.environ.copy()
    env["REALSPORTS_STORAGE_STATE_B64GZ"] = encoded

    result = subprocess.run(
        [sys.executable, str(seed_script)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    target = project / "scraper" / "storage_state.json"
    assert result.returncode == 0, result.stderr
    assert json.loads(target.read_text()) == payload
    assert _mode(target.parent) == 0o700
    assert _mode(target) == 0o600
    assert not list(target.parent.glob(".storage-state-*"))


def test_invalid_storage_state_fails_without_writing(tmp_path: Path) -> None:
    project = tmp_path / "wnba-oracle"
    scripts = project / "scripts"
    scripts.mkdir(parents=True)
    seed_script = scripts / "seed_storage_state.py"
    shutil.copy2(WORKSPACE_ROOT / "wnba-oracle" / "scripts" / seed_script.name, seed_script)
    env = os.environ.copy()
    env["REALSPORTS_STORAGE_STATE_B64GZ"] = "not-valid-base64"
    result = subprocess.run(
        [sys.executable, str(seed_script)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 78
    assert not (project / "scraper" / "storage_state.json").exists()


def test_railway_graphql_output_redacts_environment_and_variable_secrets(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module_path = WORKSPACE_ROOT / "wnba-oracle" / "scripts" / "rwgql.py"
    spec = importlib.util.spec_from_file_location("rwgql_contract_test", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setenv("RAILWAY_WORKSPACE_TOKEN", "environment-sentinel")
    variables = {"password": "variable-sentinel"}
    redactions = module.collect_redactions(variables)
    body = json.dumps(
        {
            "data": {
                "token": "environment-sentinel",
                "message": "variable-sentinel",
            }
        }
    ).encode()
    assert module.emit_response(body, redactions)
    output = capsys.readouterr().out
    assert "environment-sentinel" not in output
    assert "variable-sentinel" not in output
    assert "[REDACTED]" in output
