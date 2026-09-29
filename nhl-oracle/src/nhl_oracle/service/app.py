"""Read-only NHL staging API scaffold.

Serves ``/health`` plus placeholder slate/lineup routes until a real hosted
lifecycle exists. Never claims contest readiness and never enters contests.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, FastAPI
from oracle_core import ServiceMetadata, create_service

from nhl_oracle import __version__
from nhl_oracle.scheduler.readiness import empty_snapshot_readiness
from nhl_oracle.service import lineup_store


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
    # The worker writes T-40 lineups; the API only reads them (#675).
    engine = lineup_store.engine_from_env()

    @stubs.get("/slate/{slate_date}")
    async def slate_placeholder(slate_date: str) -> dict[str, object]:
        # TODO: serve real slate timing / pool context once freeze artifacts exist.
        # boost_regime stays none until every team has >=1 GP (contract.boost_gate).
        return {
            "date": slate_date,
            "status": "placeholder",
            "observation_only": True,
            "contest_entry": False,
            "boost_regime": "none",
            "detail": "hosted NHL slate surface not implemented yet",
        }

    @stubs.get("/readiness")
    async def readiness() -> dict[str, object]:
        # Latest worker cycle when one is stored. Otherwise fail closed.
        latest = None if engine is None else lineup_store.load_latest(engine)
        if latest is not None:
            report = dict(latest["readiness"])
            report["status"] = latest["status"]
            report["day"] = latest["day"]
            report["decided_at"] = latest["decided_at"]
            return report
        report = empty_snapshot_readiness().to_dict()
        report["status"] = "no_live_slate"
        return report

    @stubs.get("/lineup/{slate_date}")
    async def lineup(slate_date: str) -> dict[str, object]:
        # Frozen five when the worker froze one; otherwise the latest preview.
        # Card boost stays 0 while the all-teams-played gate is closed.
        stored = None if engine is None else lineup_store.load_day(engine, slate_date)
        if stored is not None:
            return {**stored, "date": slate_date, "observation_only": True}
        return {
            "date": slate_date,
            "status": "none",
            "observation_only": True,
            "contest_entry": False,
            "boost_regime": "none",
            "lineup": None,
            "detail": "no T-40 cycle stored for this date",
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
