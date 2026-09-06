"""FastAPI app via oracle-core — research/schema routes only."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, FastAPI
from oracle_core.service import ServiceMetadata, create_service

from nfl_oracle import __version__
from nfl_oracle.data.catalog import load_season_game_catalog
from nfl_oracle.features.schema import features_document
from nfl_oracle.labels.schema import schema_document as label_schema
from nfl_oracle.strategy.document import strategy_document


def create_app(*, project_root: Path | None = None) -> FastAPI:
    router = APIRouter(prefix="/research", tags=["research"])

    @router.get("/schemas/labels")
    def labels() -> dict:
        return label_schema()

    @router.get("/schemas/strategy")
    def strategy() -> dict:
        return strategy_document()

    @router.get("/schemas/features")
    def features() -> dict:
        return features_document()

    @router.get("/catalog/seasons")
    def catalog_seasons() -> dict:
        try:
            cat = load_season_game_catalog(
                None
                if project_root is None
                else project_root / "data" / "catalog" / "season_game_ids.json"
            )
        except FileNotFoundError:
            return {"seasons": {}, "error": "catalog_missing"}
        return {
            "seasons": cat.to_json_obj(),
            "season_count": len(cat.seasons),
            "contest_entry": False,
        }

    meta = ServiceMetadata(name="nfl-oracle", version=__version__, environment="research")
    return create_service(
        meta,
        routers=(router,),
        title="NFL Oracle Research",
        root_payload={
            "app": "nfl-oracle",
            "contest_entry": False,
            "mode": "research_shadow",
        },
    )
