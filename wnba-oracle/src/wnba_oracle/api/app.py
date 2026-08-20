"""FastAPI app. Read-only surface over the frozen lineup."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from oracle_core import (
    HealthCheck,
    HealthContributor,
    HealthStatus,
    ServiceMetadata,
    create_service,
)
from sqlalchemy.engine import Engine

from wnba_oracle import __version__
from wnba_oracle.common.logging import configure_logging
from wnba_oracle.common.settings import Settings, get_settings
from wnba_oracle.db.engine import get_engine, get_redis


class _RedisPingClient(Protocol):
    def ping(self) -> object: ...


class _DatabaseHealth:
    name = "database"

    def __init__(self, engine_factory: Callable[[], Engine]) -> None:
        self._engine_factory = engine_factory

    def check(self) -> HealthCheck:
        with self._engine_factory().connect() as connection:
            value = connection.execute(sa.text("SELECT 1")).scalar_one()
        return HealthCheck(status="ok" if value == 1 else "error")


class _RedisHealth:
    name = "redis"

    def __init__(self, client_factory: Callable[[], _RedisPingClient]) -> None:
        self._client_factory = client_factory

    def check(self) -> HealthCheck:
        return HealthCheck(status="ok" if self._client_factory().ping() else "error")


def _health_payload(status: HealthStatus) -> dict[str, str]:
    return {"status": status.status, "version": __version__}


def _get_redis_ping_client() -> _RedisPingClient:
    return get_redis()


def create_app(
    *,
    settings: Settings | None = None,
    engine_factory: Callable[[], Engine] | None = None,
    redis_factory: Callable[[], _RedisPingClient] | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    health_contributors: list[HealthContributor] = []
    if settings.env == "prod" or settings.database_url:
        health_contributors.append(_DatabaseHealth(engine_factory or get_engine))
    if settings.env == "prod" or settings.redis_url:
        health_contributors.append(_RedisHealth(redis_factory or _get_redis_ping_client))

    from wnba_oracle.api.lineup import router as lineup_router
    from wnba_oracle.api.slate import router as slate_router
    from wnba_oracle.api.watchdog_router import router as watchdog_router

    app = create_service(
        ServiceMetadata(name="wnba-oracle", version=__version__),
        health_contributors=health_contributors,
        routers=[lineup_router, slate_router, watchdog_router],
        title="WNBA Oracle API",
        docs_url="/docs",
        redoc_url=None,
        root_payload={"service": "wnba-oracle", "version": __version__},
        health_payload_factory=_health_payload,
        root_include_in_schema=True,
        health_include_in_schema=True,
        root_response_model=dict[str, str],
        health_response_model=dict[str, str],
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"],
    )

    return app


app = create_app()
