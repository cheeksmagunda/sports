"""Research service scaffold smoke tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from nfl_oracle.service.app import create_app


def test_research_routes_offline() -> None:
    root = Path(__file__).resolve().parents[2]
    app = create_app(project_root=root)
    client = TestClient(app)
    assert client.get("/").json()["contest_entry"] is False
    labels = client.get("/research/schemas/labels").json()
    assert labels["name"] == "real_value_label"
    strategy = client.get("/research/schemas/strategy").json()
    assert strategy["contest_entry"] is False
    features = client.get("/research/schemas/features").json()
    assert features["version"] == 1
    catalog = client.get("/research/catalog/seasons").json()
    assert catalog["season_count"] >= 1
    assert "2025" in catalog["seasons"]


def test_provider_status_route() -> None:
    client = TestClient(create_app())
    resp = client.get("/research/provider/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["contest_entry"] is False
    assert "status" in body
    assert "auth" in body
