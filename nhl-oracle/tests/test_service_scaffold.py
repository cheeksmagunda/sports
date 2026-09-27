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

    lineup = client.get("/lineup/2026-09-27")
    assert lineup.status_code == 200
    assert lineup.json()["lineup"] is None
    assert lineup.json()["contest_entry"] is False


def test_worker_once_emits_idle_heartbeat(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["worker", "--once"]) == 0
    line = capsys.readouterr().out.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["role"] == "worker"
    assert payload["status"] == "idle"
    assert payload["contest_entry"] is False
    assert payload["observation_only"] is True


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
