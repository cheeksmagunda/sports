from fastapi.testclient import TestClient

from nba_oracle.api.app import create_app


def test_health_returns_ok() -> None:
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}


def test_root_identity() -> None:
    client = TestClient(create_app())
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"service": "nba-oracle", "version": "0.1.0"}
