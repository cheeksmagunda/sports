"""FastAPI app via oracle-core — research/schema routes only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException
from oracle_core.service import HealthCheck, ServiceMetadata, create_service
from pydantic import BaseModel, ConfigDict, Field

from nfl_oracle import __version__
from nfl_oracle.data.catalog import load_season_game_catalog
from nfl_oracle.data.summary import research_data_summary
from nfl_oracle.features.schema import features_document, live_ok_feature_names
from nfl_oracle.labels.schema import schema_document as label_schema
from nfl_oracle.providers.auth_status import probe_realsports_auth
from nfl_oracle.providers.five_card import FiveCardProviderStub
from nfl_oracle.strategy.document import strategy_document
from nfl_oracle.strategy.posture import posture_from_readiness
from nfl_oracle.strategy.schema import FiveCardAction


class _AuthHealth:
    name = "realsports_auth"

    def check(self) -> HealthCheck:
        probe = probe_realsports_auth()
        if probe.usable:
            return HealthCheck(
                status="ok",
                detail="storage_state_or_b64gz_present",
                metadata={"usable": True},
            )
        return HealthCheck(
            status="degraded",
            detail="auth_missing_research_ok",
            metadata={"usable": False},
        )


class ShadowPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_ids: tuple[int, int, int, int, int]
    slot_multipliers: tuple[float, float, float, float, float] | None = None
    notes: str = ""
    values_by_player: dict[str, float] = Field(default_factory=dict)


def create_app(*, project_root: Path | None = None) -> FastAPI:
    router = APIRouter(prefix="/research", tags=["research"])
    stub = FiveCardProviderStub()

    @router.get("/schemas/labels")
    def labels() -> dict[str, Any]:
        return label_schema()

    @router.get("/schemas/strategy")
    def strategy() -> dict[str, Any]:
        return strategy_document()

    @router.get("/schemas/features")
    def features() -> dict[str, Any]:
        return features_document()

    @router.get("/features/live-ok")
    def features_live_ok() -> dict[str, Any]:
        return {
            "live_ok": list(live_ok_feature_names()),
            "contest_entry": False,
            "observation_only": True,
        }

    @router.get("/provider/status")
    def provider_status() -> dict[str, Any]:
        ready = stub.readiness()
        payload = ready.to_json_obj()
        payload["posture"] = posture_from_readiness(ready).value
        return payload

    @router.post("/shadow/preview")
    def shadow_preview(body: ShadowPreviewRequest) -> dict[str, Any]:
        try:
            action = FiveCardAction(
                player_ids=body.player_ids,
                slot_multipliers=body.slot_multipliers,
                notes=body.notes,
            )
        except Exception as exc:  # pydantic ValidationError
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        preview = stub.shadow_preview(action)
        values: dict[int, float] = {}
        for key, val in body.values_by_player.items():
            try:
                values[int(key)] = float(val)
            except (TypeError, ValueError):
                continue
        if values:
            from nfl_oracle.strategy.scoring import shadow_weighted_score

            score = shadow_weighted_score(action, values)
            preview["shadow_score"] = {
                "total": score.total,
                "per_slot": list(score.per_slot),
                "structural_ok": score.structural_ok,
                "notes": score.notes,
            }
        return preview

    @router.get("/catalog/seasons")
    def catalog_seasons() -> dict[str, Any]:
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

    @router.get("/coverage/summary")
    def coverage_summary() -> dict[str, Any]:
        return research_data_summary(project_root=project_root)

    @router.get("/status")
    def research_status() -> dict[str, Any]:
        ready = stub.readiness()
        return {
            "app": "nfl-oracle",
            "version": __version__,
            "mode": "research_shadow",
            "contest_entry": False,
            "posture": posture_from_readiness(ready).value,
            "provider": ready.to_json_obj(),
            "data": research_data_summary(project_root=project_root),
            "railway": {
                "in_repo_config": False,
                "dockerfile": False,
                "staging_project_name": "nfl-oracle-staging",
                "staging_service_name": "nfl-oracle",
                "deploy_source_connected": False,
                "note": "external staging placeholders only; do not deploy from this package",
            },
        }

    meta = ServiceMetadata(name="nfl-oracle", version=__version__, environment="research")
    return create_service(
        meta,
        routers=(router,),
        health_contributors=(_AuthHealth(),),
        title="NFL Oracle Research",
        root_payload={
            "app": "nfl-oracle",
            "contest_entry": False,
            "mode": "research_shadow",
        },
    )
