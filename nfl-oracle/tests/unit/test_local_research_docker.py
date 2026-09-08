"""Local nfl-oracle-local research Docker assets (observation-only; no secrets)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_local_research_dockerfile_observation_only() -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "nfl-research-serve" in text
    assert "NOT for Railway" in text
    assert "observation-only" in text.lower() or "Observation only" in text
    assert "REALSPORTS_STORAGE_STATE" not in text
    assert "RAILWAY_TOKEN" not in text
    assert "PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD" in text


def test_local_research_compose_no_secrets() -> None:
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "nfl-oracle-local" in text
    assert "env_file" not in text
    assert "8088:8088" in text
    assert "Not Railway" in text or "not Railway" in text.lower()
    assert "storage_state" not in text.lower()


def test_docker_research_make_target_skips_without_docker() -> None:
    """Make target must exit 0 when docker is unavailable (graceful skip)."""

    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    assert "docker-research-smoke" in makefile
    assert "docker not available; skip" in makefile
    if shutil.which("docker") is not None:
        pytest.skip("docker present; skip-path covered by Makefile text + optional build")
    env = os.environ.copy()
    # Force PATH without docker even if a stub appears later.
    env["PATH"] = "/usr/bin:/bin"
    proc = subprocess.run(
        ["make", "docker-research-smoke"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "docker not available; skip" in (proc.stdout + proc.stderr)


@pytest.mark.skipif(shutil.which("docker") is None, reason="docker not available")
def test_docker_research_image_builds_when_docker_available() -> None:
    proc = subprocess.run(
        ["make", "docker-research-smoke"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "research image build OK" in (proc.stdout + proc.stderr)
