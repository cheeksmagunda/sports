"""Sanity tests that the package imports and the api app builds."""

from __future__ import annotations


def test_package_importable() -> None:
    import wnba_oracle

    assert wnba_oracle.__version__ == "0.1.0"


def test_settings_loads_with_no_env() -> None:
    from wnba_oracle.common.settings import get_settings

    s = get_settings()
    assert s.env == "dev"


def test_api_app_health() -> None:
    from fastapi.testclient import TestClient

    from wnba_oracle.api.app import app

    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
