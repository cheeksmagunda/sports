"""Health-only FastAPI app for Railway mono `nba-api` scaffold.

No contest, provider, or domain routes. Domain work stays behind later
milestones; this process exists so Dockerfile builds can reach SUCCESS on
`sports-oracle` / `nba-staging` without Railpack guessing the monorepo.
"""

from __future__ import annotations

from fastapi import FastAPI
from oracle_core import HealthStatus, ServiceMetadata, create_service

from nba_oracle import __version__


def _health_payload(status: HealthStatus) -> dict[str, str]:
    return {"status": status.status, "version": __version__}


def create_app() -> FastAPI:
    """Build the scaffold API: root identity + `/health` only."""

    return create_service(
        ServiceMetadata(name="nba-oracle", version=__version__),
        title="NBA Oracle API",
        docs_url="/docs",
        redoc_url=None,
        root_payload={"service": "nba-oracle", "version": __version__},
        health_payload_factory=_health_payload,
        root_include_in_schema=True,
        health_include_in_schema=True,
        root_response_model=dict[str, str],
        health_response_model=dict[str, str],
    )


app = create_app()
