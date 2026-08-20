"""Compatibility and dependency-health coverage for the WNBA API factory."""

from __future__ import annotations

import sqlalchemy as sa
from fastapi.testclient import TestClient

from wnba_oracle.api.app import create_app
from wnba_oracle.common.settings import Settings


class _RedisStub:
    def __init__(self, result: bool = True) -> None:
        self.result = result
        self.ping_calls = 0

    def ping(self) -> bool:
        self.ping_calls += 1
        return self.result


def test_api_preserves_root_docs_cors_routes_and_openapi_contract() -> None:
    application = create_app(settings=Settings())
    client = TestClient(application)

    assert client.get("/").json() == {"service": "wnba-oracle", "version": "0.1.0"}
    assert client.get("/health").json() == {"status": "ok", "version": "0.1.0"}
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 404

    preflight = client.options(
        "/",
        headers={
            "Origin": "https://example.test",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "*"
    assert "GET" in preflight.headers["access-control-allow-methods"]

    schema = application.openapi()
    assert schema["info"] == {"title": "WNBA Oracle API", "version": "0.1.0"}
    assert {
        "/",
        "/health",
        "/lineup",
        "/lineup/{slate_date}",
        "/lineup/{slate_date}/history",
        "/slate/{slate_date}",
        "/watchdog/today",
        "/watchdog/{slate_date}",
    }.issubset(schema["paths"])
    assert schema["paths"]["/"] == {
        "get": {
            "operationId": "root__get",
            "responses": {
                "200": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "additionalProperties": {"type": "string"},
                                "title": "Response Root  Get",
                                "type": "object",
                            }
                        }
                    },
                    "description": "Successful Response",
                }
            },
            "summary": "Root",
        }
    }
    assert schema["paths"]["/health"] == {
        "get": {
            "operationId": "health_health_get",
            "responses": {
                "200": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "additionalProperties": {"type": "string"},
                                "title": "Response Health Health Get",
                                "type": "object",
                            }
                        }
                    },
                    "description": "Successful Response",
                }
            },
            "summary": "Health",
        }
    }


def test_configured_database_and_redis_are_checked() -> None:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    redis = _RedisStub()
    application = create_app(
        settings=Settings(DATABASE_URL="postgresql://configured", REDIS_URL="redis://configured"),
        engine_factory=lambda: engine,
        redis_factory=lambda: redis,
    )

    response = TestClient(application).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "0.1.0"}
    assert redis.ping_calls == 1
    engine.dispose()


def test_database_health_failure_is_safe_and_returns_503() -> None:
    secret_marker = "database-password-must-not-leak"

    def broken_engine() -> sa.Engine:
        raise RuntimeError(secret_marker)

    redis = _RedisStub()
    application = create_app(
        settings=Settings(DATABASE_URL="postgresql://configured", REDIS_URL="redis://configured"),
        engine_factory=broken_engine,
        redis_factory=lambda: redis,
    )

    response = TestClient(application).get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "version": "0.1.0"}
    assert secret_marker not in response.text
    assert secret_marker not in str(response.headers)
    assert redis.ping_calls == 1


def test_redis_false_ping_returns_503_without_dependency_details() -> None:
    engine = sa.create_engine("sqlite+pysqlite:///:memory:")
    redis = _RedisStub(result=False)
    application = create_app(
        settings=Settings(DATABASE_URL="postgresql://configured", REDIS_URL="redis://configured"),
        engine_factory=lambda: engine,
        redis_factory=lambda: redis,
    )

    response = TestClient(application).get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "version": "0.1.0"}
    assert "database" not in response.text
    assert "redis" not in response.text
    engine.dispose()


def test_production_missing_dependencies_does_not_block_startup_but_fails_health() -> None:
    calls: list[str] = []

    def missing_database() -> sa.Engine:
        calls.append("database")
        raise RuntimeError("not configured")

    def missing_redis() -> _RedisStub:
        calls.append("redis")
        raise RuntimeError("not configured")

    application = create_app(
        settings=Settings(ENV="prod"),
        engine_factory=missing_database,
        redis_factory=missing_redis,
    )
    assert calls == []

    response = TestClient(application).get("/health")

    assert response.status_code == 503
    assert response.json() == {"status": "error", "version": "0.1.0"}
    assert calls == ["database", "redis"]
