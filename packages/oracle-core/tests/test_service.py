from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

from oracle_core.service import (
    HealthCheck,
    ServiceMetadata,
    create_service,
    run_health_checks,
)


class StaticHealth:
    def __init__(self, name: str, result: HealthCheck) -> None:
        self.name = name
        self.result = result

    def check(self) -> HealthCheck:
        return self.result


class AsyncHealth:
    name = "async"

    async def check(self) -> HealthCheck:
        return HealthCheck(metadata={"latency_ms": 2})


class BrokenHealth:
    name = "database"

    def check(self) -> HealthCheck:
        raise RuntimeError("password=do-not-expose")


def test_run_health_checks_aggregates_sync_and_async_results() -> None:
    checked_at = datetime(2026, 8, 20, 12, tzinfo=UTC)
    status = asyncio.run(
        run_health_checks(
            [StaticHealth("cache", HealthCheck(status="degraded", detail="slow")), AsyncHealth()],
            clock=lambda: checked_at,
        )
    )

    assert status.status == "degraded"
    assert status.healthy
    assert status.checked_at == checked_at
    assert status.as_dict()["checks"] == {
        "cache": {"status": "degraded", "detail": "slow"},
        "async": {"status": "ok", "metadata": {"latency_ms": 2}},
    }


def test_health_metadata_and_detail_are_redacted() -> None:
    status = asyncio.run(
        run_health_checks(
            [
                StaticHealth(
                    "provider",
                    HealthCheck(detail="token=private", metadata={"password": "also-private"}),
                )
            ]
        )
    )

    rendered = str(status.as_dict())
    assert "private" not in rendered
    assert rendered.count("[REDACTED]") == 2


def test_health_exception_is_safe_and_unhealthy() -> None:
    status = asyncio.run(run_health_checks([BrokenHealth()]))

    assert status.status == "error"
    assert not status.healthy
    rendered = str(status.as_dict())
    assert "do-not-expose" not in rendered
    assert "RuntimeError" in rendered


def test_duplicate_health_names_are_rejected() -> None:
    contributors = [
        StaticHealth("same", HealthCheck()),
        StaticHealth("same", HealthCheck()),
    ]
    with pytest.raises(ValueError, match="Duplicate"):
        asyncio.run(run_health_checks(contributors))


def test_service_factory_provides_only_generic_routes_plus_application_routers() -> None:
    router = APIRouter()

    @router.get("/domain-owned")
    async def domain_owned() -> dict[str, bool]:
        return {"ok": True}

    application = create_service(
        ServiceMetadata("test-service", "1.2.3", environment="test"),
        health_contributors=[StaticHealth("cache", HealthCheck())],
        routers=[router],
    )
    client = TestClient(application)

    assert client.get("/").json() == {
        "name": "test-service",
        "version": "1.2.3",
        "environment": "test",
    }
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert client.get("/domain-owned").json() == {"ok": True}
    assert client.get("/docs").status_code == 200
    assert client.get("/redoc").status_code == 200
    assert set(application.openapi()["paths"]) == {"/domain-owned"}


def test_service_health_returns_503_on_error() -> None:
    application = create_service(
        ServiceMetadata("test-service", "1"), health_contributors=[BrokenHealth()]
    )

    response = TestClient(application).get("/health")
    assert response.status_code == 503
    assert response.json()["status"] == "error"


def test_service_payload_overrides_preserve_existing_contracts() -> None:
    application = create_service(
        ServiceMetadata("test-service", "1.2.3"),
        root_payload={"service": "existing", "version": "1.2.3"},
        health_payload_factory=lambda status: {
            "status": status.status,
            "version": "1.2.3",
        },
    )
    client = TestClient(application)

    assert client.get("/").json() == {"service": "existing", "version": "1.2.3"}
    assert client.get("/health").json() == {"status": "ok", "version": "1.2.3"}


def test_service_factory_supports_application_docs_and_schema_compatibility() -> None:
    application = create_service(
        ServiceMetadata("test-service", "1.2.3"),
        docs_url="/api/docs",
        redoc_url=None,
        root_include_in_schema=True,
        health_include_in_schema=True,
        root_response_model=dict[str, str],
        health_response_model=dict[str, str],
    )
    client = TestClient(application)

    assert client.get("/api/docs").status_code == 200
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    schema = application.openapi()
    assert set(schema["paths"]) == {"/", "/health"}
    assert schema["paths"]["/"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["additionalProperties"] == {"type": "string"}
    assert schema["paths"]["/health"]["get"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]["additionalProperties"] == {"type": "string"}
