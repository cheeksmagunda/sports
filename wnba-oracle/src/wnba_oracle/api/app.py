"""FastAPI app. Read-only surface over the frozen lineup."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from wnba_oracle import __version__
from wnba_oracle.common.logging import configure_logging
from wnba_oracle.common.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="WNBA Oracle API",
        version=__version__,
        docs_url="/docs",
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["GET", "OPTIONS"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.get("/")
    def root() -> dict[str, str]:
        return {"service": "wnba-oracle", "version": __version__}

    from wnba_oracle.api.lineup import router as lineup_router
    from wnba_oracle.api.slate import router as slate_router
    from wnba_oracle.api.watchdog import router as watchdog_router

    app.include_router(lineup_router)
    app.include_router(slate_router)
    app.include_router(watchdog_router)

    return app


app = create_app()
