"""FastAPI app via oracle-core — research/schema routes only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Query
from oracle_core.service import HealthCheck, ServiceMetadata, create_service
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from nfl_oracle import __version__
from nfl_oracle.data.catalog import load_season_game_catalog
from nfl_oracle.data.summary import research_data_summary
from nfl_oracle.features.schema import features_document, live_ok_feature_names
from nfl_oracle.labels.schema import schema_document as label_schema
from nfl_oracle.providers.auth_status import probe_realsports_auth
from nfl_oracle.providers.five_card import FiveCardProviderStub
from nfl_oracle.strategy.algebra import (
    OBSERVED_DEFAULT_SLOT_MULTIPLIERS,
    contest_score_to_json,
    contest_shadow_score,
    scoring_document,
)
from nfl_oracle.strategy.document import strategy_document
from nfl_oracle.strategy.enumerate import best_shadow_ordering, rank_shadow_orderings
from nfl_oracle.strategy.gates import evaluate_entry_gates
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
    boosts_by_player: dict[str, float] = Field(default_factory=dict)
    use_contest_algebra: bool = True
    include_best_ordering: bool = True


class RankOrderingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_ids: tuple[int, int, int, int, int]
    values_by_player: dict[str, float]
    boosts_by_player: dict[str, float] = Field(default_factory=dict)
    slot_multipliers: tuple[float, float, float, float, float] | None = None
    top_k: int = Field(default=10, ge=1, le=120)
    use_contest_algebra: bool = True


def _parse_float_map(raw: dict[str, float]) -> dict[int, float]:
    out: dict[int, float] = {}
    for key, val in raw.items():
        try:
            out[int(key)] = float(val)
        except (TypeError, ValueError):
            continue
    return out


def _action_from_body(
    player_ids: tuple[int, int, int, int, int],
    slot_multipliers: tuple[float, float, float, float, float] | None,
    notes: str = "",
) -> FiveCardAction:
    try:
        return FiveCardAction(
            player_ids=player_ids,
            slot_multipliers=slot_multipliers,
            notes=notes,
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


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

    @router.get("/schemas/scoring")
    def scoring() -> dict[str, Any]:
        return scoring_document()

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

    @router.get("/gates/entry")
    def entry_gates() -> dict[str, Any]:
        """Readiness checklist; contest_entry is always false."""

        return evaluate_entry_gates(stub=stub).to_json_obj()

    @router.post("/shadow/preview")
    def shadow_preview(body: ShadowPreviewRequest) -> dict[str, Any]:
        action = _action_from_body(body.player_ids, body.slot_multipliers, body.notes)
        preview = stub.shadow_preview(action)
        values = _parse_float_map(body.values_by_player)
        boosts = _parse_float_map(body.boosts_by_player)
        if values:
            if body.use_contest_algebra:
                # Apply observed defaults when caller omitted multipliers.
                if action.slot_multipliers is None:
                    action = FiveCardAction(
                        player_ids=action.player_ids,
                        slot_multipliers=OBSERVED_DEFAULT_SLOT_MULTIPLIERS,
                        notes=action.notes,
                    )
                score = contest_shadow_score(
                    action,
                    values,
                    boosts_by_player=boosts or None,
                )
                preview["contest_shadow_score"] = contest_score_to_json(score)
                preview["shadow_score"] = {
                    "total": score.total,
                    "per_slot": [item.score for item in score.per_slot],
                    "structural_ok": score.structural_ok,
                    "notes": score.notes,
                }
            else:
                from nfl_oracle.strategy.scoring import shadow_weighted_score

                score_simple = shadow_weighted_score(action, values)
                preview["shadow_score"] = {
                    "total": score_simple.total,
                    "per_slot": list(score_simple.per_slot),
                    "structural_ok": score_simple.structural_ok,
                    "notes": score_simple.notes,
                }
            if body.include_best_ordering:
                try:
                    best, best_total = best_shadow_ordering(
                        body.player_ids,
                        values,
                        slot_multipliers=body.slot_multipliers,
                        boosts_by_player=boosts or None,
                        use_contest_algebra=body.use_contest_algebra,
                    )
                    if best.slot_multipliers is not None:
                        best_slots: list[float] | None = list(best.slot_multipliers)
                    elif body.use_contest_algebra:
                        best_slots = list(OBSERVED_DEFAULT_SLOT_MULTIPLIERS)
                    else:
                        best_slots = None
                    preview["best_ordering"] = {
                        "player_ids": list(best.player_ids),
                        "slot_multipliers": best_slots,
                        "total": best_total,
                        "contest_entry": False,
                    }
                except ValueError as exc:
                    preview["best_ordering"] = {
                        "error": str(exc),
                        "contest_entry": False,
                    }
        preview["contest_entry"] = False
        return preview

    @router.post("/shadow/rank-orderings")
    def shadow_rank_orderings(body: RankOrderingsRequest) -> dict[str, Any]:
        values = _parse_float_map(body.values_by_player)
        if len(values) < 1:
            raise HTTPException(status_code=422, detail="values_by_player_required")
        # Structural validate first for clear 422s
        _action_from_body(body.player_ids, body.slot_multipliers)
        try:
            ranked = rank_shadow_orderings(
                body.player_ids,
                values,
                slot_multipliers=body.slot_multipliers,
                boosts_by_player=_parse_float_map(body.boosts_by_player) or None,
                top_k=body.top_k,
                use_contest_algebra=body.use_contest_algebra,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return {
            "contest_entry": False,
            "observation_only": True,
            "use_contest_algebra": body.use_contest_algebra,
            "orderings_evaluated": 120,
            "returned": len(ranked),
            "rankings": ranked,
        }

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
    def research_status(
        include_gates: bool = Query(default=True),
    ) -> dict[str, Any]:
        ready = stub.readiness()
        payload: dict[str, Any] = {
            "app": "nfl-oracle",
            "version": __version__,
            "mode": "research_shadow",
            "contest_entry": False,
            "posture": posture_from_readiness(ready).value,
            "provider": ready.to_json_obj(),
            "data": research_data_summary(project_root=project_root),
            "scoring": {
                "observed_default_slot_multipliers": list(OBSERVED_DEFAULT_SLOT_MULTIPLIERS),
                "schema": "/research/schemas/scoring",
            },
            "railway": {
                "in_repo_config": False,
                "dockerfile": False,
                "staging_project_name": "nfl-oracle-staging",
                "staging_service_name": "nfl-oracle",
                "deploy_source_connected": False,
                "note": "external staging placeholders only; do not deploy from this package",
            },
            "auth": {
                "usable": ready.auth.usable,
                "status": ready.status.value,
                "note": "presence only; secret values never returned",
            },
        }
        if include_gates:
            payload["entry_gates"] = evaluate_entry_gates(stub=stub).to_json_obj()
        return payload

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
