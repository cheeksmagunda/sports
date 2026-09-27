"""Read-only NHL staging API scaffold.

Serves ``/health`` plus placeholder slate/lineup routes until a real hosted
lifecycle exists. Never claims contest readiness and never enters contests.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, FastAPI
from oracle_core import ServiceMetadata, create_service

from nhl_oracle import __version__


def create_app() -> FastAPI:
    """Build the staging FastAPI app (health + stub domain routes)."""

    environment = os.environ.get("NHL_ORACLE_ENVIRONMENT") or os.environ.get(
        "RAILWAY_ENVIRONMENT_NAME"
    )
    metadata = ServiceMetadata(
        name="nhl-oracle",
        version=__version__,
        environment=environment,
    )

    stubs = APIRouter()

    @stubs.get("/slate/{slate_date}")
    async def slate_placeholder(slate_date: str) -> dict[str, object]:
        # TODO: serve real slate timing / pool context once freeze artifacts exist.
        return {
            "date": slate_date,
            "status": "placeholder",
            "observation_only": True,
            "contest_entry": False,
            "detail": "hosted NHL slate surface not implemented yet",
        }

    @stubs.get("/lineup/{slate_date}")
    async def lineup_placeholder(slate_date: str) -> dict[str, object]:
        # TODO: serve frozen five-card lineup once the hosted lifecycle publishes.
        return {
            "date": slate_date,
            "status": "placeholder",
            "observation_only": True,
            "contest_entry": False,
            "lineup": None,
            "detail": "hosted NHL lineup surface not implemented yet",
        }

    return create_service(
        metadata,
        routers=[stubs],
        title="NHL Oracle",
        root_payload={
            "name": metadata.name,
            "version": metadata.version,
            "observation_only": True,
            "contest_entry": False,
            **({"environment": environment} if environment else {}),
        },
        health_payload_factory=lambda status: {
            "service": metadata.name,
            "version": metadata.version,
            "observation_only": True,
            "contest_entry": False,
            **status.as_dict(),
        },
    )
