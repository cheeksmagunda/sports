"""Read-only recommendation API. Provider credentials are never loaded here."""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import Response
from oracle_core.service import HealthCheck, ServiceMetadata, create_service
from oracle_core.storage import PoolOptions, create_postgres_engine

from .schema import utc
from .store import RecommendationStore


class DatabaseHealth:
    name = "recommendation_database"

    def __init__(self, store: RecommendationStore) -> None:
        self.store = store

    def check(self) -> HealthCheck:
        self.store.healthy()
        return HealthCheck()


def create_app(
    store: RecommendationStore,
    *,
    frontend_dir: Path | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> FastAPI:
    app = create_service(
        ServiceMetadata(name="nfl-oracle", version="1.0.0"),
        health_contributors=[DatabaseHealth(store)],
    )
    # Root's default metadata route is replaced by the explicitly packaged page.
    app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) != "/"]
    assets = frontend_dir or Path(__file__).parent / "frontend"

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Any) -> Response:
        response: Response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        return response

    def asset(name: str, media_type: str) -> Response:
        try:
            return Response((assets / name).read_bytes(), media_type=media_type)
        except OSError:
            raise HTTPException(503, "frontend_unavailable") from None

    @app.get("/", include_in_schema=False)
    def index() -> Response:
        return asset("index.html", "text/html")

    @app.get("/app.js", include_in_schema=False)
    def javascript() -> Response:
        return asset("app.js", "application/javascript")

    @app.get("/style.css", include_in_schema=False)
    def stylesheet() -> Response:
        return asset("style.css", "text/css")

    def snapshot(day: date) -> dict[str, Any]:
        now = utc(clock())
        try:
            frozen = store.latest(day)
            run = store.latest_run(day)
        except Exception:
            raise HTTPException(503, "recommendations_unavailable") from None
        payload: dict[str, Any] = {
            "slate_date": day.isoformat(),
            "server_time": now.isoformat(),
            "contest_entry": False,
            "lineup": None,
            "games": [],
            "run": run,
        }
        if frozen is None:
            fresh = (
                run is not None
                and 0 <= (now - datetime.fromisoformat(run["checked_at"])).total_seconds() <= 900
            )
            payload["status"] = run["status"] if run is not None and fresh else "waiting"
            if payload["status"] == "ready":
                payload["status"] = "waiting"
            payload["stale"] = not fresh
            if run is not None and isinstance(run.get("details"), dict):
                payload["next_freeze"] = run["details"].get("next_freeze")
            return payload
        cutoff = datetime.fromisoformat(frozen["cutoff_at"])
        age = (now - datetime.fromisoformat(frozen["frozen_at"])).total_seconds()
        locked = now >= cutoff
        payload.update(
            status="locked" if locked else "frozen",
            stale=not locked and age > 900,
            lineup=frozen["lineup"],
            games=frozen["slate"]["games"],
            cutoff_at=frozen["cutoff_at"],
            frozen_at=frozen["frozen_at"],
            sequence=frozen["sequence"],
            digest=frozen["digest"],
            model_fingerprint=frozen["model_fingerprint"],
            input_fingerprint=frozen["input_fingerprint"],
        )
        # A newer failed refresh cannot be hidden by a previously valid freeze.
        if run is not None and run["status"] in {"blocked", "error", "no_slate"}:
            if (
                datetime.fromisoformat(run["checked_at"])
                > datetime.fromisoformat(frozen["frozen_at"])
                and not locked
            ):
                payload["stale"] = True
        return payload

    @app.get("/lineup/{day}")
    def lineup(day: date) -> dict[str, Any]:
        return snapshot(day)

    @app.get("/slate/{day}")
    def slate(day: date) -> dict[str, Any]:
        payload = snapshot(day)
        payload.pop("lineup", None)
        return payload

    @app.get("/history")
    def history(day: date | None = None, limit: int = Query(50, ge=1, le=500)) -> dict[str, Any]:
        try:
            records = store.history(day, limit=limit)
        except Exception:
            raise HTTPException(503, "recommendations_unavailable") from None
        # Serving only the public decision. Raw source/model feature inputs stay private.
        keys = {
            "slate_date",
            "contest_id",
            "sequence",
            "frozen_at",
            "cutoff_at",
            "digest",
            "model_fingerprint",
            "input_fingerprint",
            "lineup",
            "contest_entry",
        }
        return {"records": [{k: v for k, v in r.items() if k in keys} for r in records]}

    return app


def app_from_env() -> FastAPI:
    url = os.environ.get("NFL_DATABASE_URL", "")
    if not url:
        raise RuntimeError("NFL_DATABASE_URL_required")
    engine = create_postgres_engine(
        url,
        pool=PoolOptions(pool_size=3, max_overflow=2, pool_timeout=5),
        connect_args={
            "connect_timeout": 5,
            "options": "-c default_transaction_read_only=on -c statement_timeout=5000",
        },
    )
    return create_app(RecommendationStore(engine))
