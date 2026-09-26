from __future__ import annotations

from pathlib import Path


def test_backend_ci_runs_nba_and_nhl_app_tests() -> None:
    workflow = Path(__file__).resolve().parents[2] / ".github/workflows/backend-ci.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "make test-nba" in text
    assert "make test-nhl" in text
