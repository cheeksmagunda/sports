"""Staging HTTP service and Docker/Railway scaffold contracts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nhl_oracle.service.app import create_app
from nhl_oracle.service.cli import main

ROOT = Path(__file__).parents[1]


def test_health_and_stub_routes_are_observation_only() -> None:
    client = TestClient(create_app())
    health = client.get("/health")
    assert health.status_code == 200
    body = health.json()
    assert body["service"] == "nhl-oracle"
    assert body["status"] == "ok"
    assert body["contest_entry"] is False
    assert body["observation_only"] is True

    slate = client.get("/slate/2026-09-27")
    assert slate.status_code == 200
    assert slate.json()["contest_entry"] is False
    assert slate.json()["status"] == "placeholder"
    assert slate.json()["boost_regime"] == "none"

    lineup = client.get("/lineup/2026-09-27")
    assert lineup.status_code == 200
    assert lineup.json()["lineup"] is None
    assert lineup.json()["contest_entry"] is False
    assert lineup.json()["boost_regime"] == "none"

    readiness = client.get("/readiness")
    assert readiness.status_code == 200
    body = readiness.json()
    assert body["contest_entry"] is False
    assert body["observation_only"] is True
    assert body["freeze_ready"] is False
    assert body["pick_player_ids"] is None
    assert body["zero_boost_active"] is True
    assert "no_live_slate_snapshot" in body["blocked_reasons"]


def test_worker_once_emits_idle_heartbeat(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["worker", "--once"]) == 0
    line = capsys.readouterr().out.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["role"] == "worker"
    assert payload["status"] == "idle"
    assert payload["contest_entry"] is False
    assert payload["observation_only"] is True
    assert payload["freeze_ready"] is False
    assert payload["readiness"]["pick_player_ids"] is None
    assert "no_live_slate_snapshot" in payload["readiness"]["blocked_reasons"]


def test_dockerfile_and_railway_mirror_nfl_role_split() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text()
    assert "nhl-pipeline serve" in dockerfile
    assert "NHL_PIPELINE_ROLE=api" in dockerfile
    assert "storage_state.json" not in dockerfile
    assert "alembic upgrade" not in dockerfile
    assert "REALSPORTS" not in dockerfile

    railway = (ROOT / "railway.toml").read_text()
    assert 'dockerfilePath = "nhl-oracle/Dockerfile"' in railway
    assert "nhl-pipeline worker" in railway
    assert "nhl-pipeline serve" in railway


def test_root_dockerignore_allowlists_nhl_image_paths() -> None:
    """Railway root-context builds fail closed when nhl-oracle/src is ignored."""

    text = (ROOT.parent / ".dockerignore").read_text().splitlines()
    for line in (
        "!nhl-oracle/",
        "!nhl-oracle/Dockerfile",
        "!nhl-oracle/railway.toml",
        "!nhl-oracle/pyproject.toml",
        "!nhl-oracle/README.md",
        "!nhl-oracle/src/",
        "!nhl-oracle/src/**",
    ):
        assert line in text


def test_readiness_command_fail_closed_without_slate(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["readiness"]) == 0
    payload = json.loads(capsys.readouterr().out.strip())
    assert payload["freeze_ready"] is False
    assert payload["contest_entry"] is False
    assert payload["zero_boost_active"] is True
    assert payload["boost_multiplier"] == 0.0
