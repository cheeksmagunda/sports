"""Generic FastAPI service metadata and health behavior."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal, Protocol

from fastapi import APIRouter, FastAPI
from fastapi.responses import JSONResponse

from oracle_core.redaction import redact_text, redact_value


@dataclass(frozen=True)
class ServiceMetadata:
    """Non-domain service identity returned by the generic root route."""

    name: str
    version: str
    environment: str | None = None


@dataclass(frozen=True)
class HealthCheck:
    """One dependency's safe health result."""

    status: Literal["ok", "degraded", "error"] = "ok"
    detail: str | None = None
    metadata: Mapping[str, str | int | float | bool | None] = field(default_factory=dict)


class HealthContributor(Protocol):
    """Named synchronous or asynchronous health capability."""

    @property
    def name(self) -> str: ...

    def check(self) -> HealthCheck | Awaitable[HealthCheck]: ...


@dataclass(frozen=True)
class HealthStatus:
    """Aggregated service health without provider exception content."""

    status: Literal["ok", "degraded", "error"]
    checks: Mapping[str, HealthCheck]
    checked_at: datetime

    @property
    def healthy(self) -> bool:
        return self.status != "error"

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "checked_at": self.checked_at.isoformat(),
            "checks": {
                name: {
                    key: value
                    for key, value in {
                        "status": check.status,
                        "detail": redact_text(check.detail) if check.detail is not None else None,
                        "metadata": redact_value(dict(check.metadata)),
                    }.items()
                    if value not in (None, {})
                }
                for name, check in self.checks.items()
            },
        }


async def run_health_checks(
    contributors: Sequence[HealthContributor],
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> HealthStatus:
    """Run contributors in declaration order and convert exceptions to safe failures."""

    checks: dict[str, HealthCheck] = {}
    for contributor in contributors:
        if contributor.name in checks:
            raise ValueError(f"Duplicate health contributor {contributor.name!r}")
        try:
            result = contributor.check()
            if inspect.isawaitable(result):
                result = await result
            if not isinstance(result, HealthCheck):
                raise TypeError("Health contributors must return HealthCheck")
            checks[contributor.name] = result
        except Exception as error:
            checks[contributor.name] = HealthCheck(
                status="error",
                detail="health check failed",
                metadata={"error_type": type(error).__name__},
            )
    statuses = {check.status for check in checks.values()}
    overall: Literal["ok", "degraded", "error"]
    if "error" in statuses:
        overall = "error"
    elif "degraded" in statuses:
        overall = "degraded"
    else:
        overall = "ok"
    return HealthStatus(status=overall, checks=checks, checked_at=clock())


def create_service(
    metadata: ServiceMetadata,
    *,
    health_contributors: Sequence[HealthContributor] = (),
    routers: Sequence[APIRouter] = (),
    title: str | None = None,
    root_payload: Mapping[str, object] | None = None,
    health_payload_factory: Callable[[HealthStatus], Mapping[str, object]] | None = None,
) -> FastAPI:
    """Create a FastAPI app with generic root and health routes only.

    Payload overrides let applications preserve an existing provider-neutral
    response contract while core continues to own route construction and
    health execution.
    """

    application = FastAPI(title=title or metadata.name, version=metadata.version)

    @application.get("/", include_in_schema=False)
    async def root() -> dict[str, object]:
        if root_payload is not None:
            return dict(root_payload)
        payload: dict[str, object] = {"name": metadata.name, "version": metadata.version}
        if metadata.environment is not None:
            payload["environment"] = metadata.environment
        return payload

    @application.get("/health", include_in_schema=False)
    async def health() -> JSONResponse:
        status = await run_health_checks(health_contributors)
        if health_payload_factory is None:
            payload: Mapping[str, object] = {
                "service": metadata.name,
                "version": metadata.version,
                **status.as_dict(),
            }
        else:
            payload = health_payload_factory(status)
        return JSONResponse(payload, status_code=200 if status.healthy else 503)

    for router in routers:
        application.include_router(router)
    return application
