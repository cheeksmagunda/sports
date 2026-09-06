"""FastAPI app via oracle-core — research/schema routes only."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Query
from oracle_core.service import HealthCheck, ServiceMetadata, create_service
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from nfl_oracle import __version__
from nfl_oracle.calendar.schedule import research_schedule_summary
from nfl_oracle.data.catalog import load_season_game_catalog
from nfl_oracle.data.summary import research_data_summary
from nfl_oracle.features.schema import (
    features_document,
    live_ok_feature_names,
    offline_stub_feature_names,
)
from nfl_oracle.identity.load import research_identity_summary
from nfl_oracle.labels.schema import ValueLabel
from nfl_oracle.labels.schema import schema_document as label_schema
from nfl_oracle.providers.auth_status import probe_realsports_auth
from nfl_oracle.providers.five_card import (
    OFFLINE_RULE_NOTES,
    UNKNOWN_PROVIDER_RULES,
    FiveCardProviderStub,
    offline_provider_rule_document,
)
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
from nfl_oracle.strategy.readiness_score import readiness_score_from_summaries
from nfl_oracle.strategy.schema import FiveCardAction
from nfl_oracle.strategy.value_preds import resolve_shadow_values, value_model_strategy_note


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


class TrainLabelIn(BaseModel):
    """Minimal train label row for optional feature_ridge shadow values."""

    model_config = ConfigDict(extra="forbid")

    player_id: int
    game_id: int = 0
    season: int
    position: str
    value: float
    team_id: int | None = None


class ShadowPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_ids: tuple[int, int, int, int, int]
    slot_multipliers: tuple[float, float, float, float, float] | None = None
    notes: str = ""
    values_by_player: dict[str, float] = Field(default_factory=dict)
    boosts_by_player: dict[str, float] = Field(default_factory=dict)
    use_contest_algebra: bool = True
    include_best_ordering: bool = True
    # Default False = offline-safe explicit values path (no model fit).
    use_feature_value_model: bool = False
    player_positions: dict[str, str] = Field(default_factory=dict)
    decision_season: int | None = None
    train_labels: list[TrainLabelIn] = Field(default_factory=list)
    value_model_alpha: float = 1.0


class RankOrderingsRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    player_ids: tuple[int, int, int, int, int]
    values_by_player: dict[str, float] = Field(default_factory=dict)
    boosts_by_player: dict[str, float] = Field(default_factory=dict)
    slot_multipliers: tuple[float, float, float, float, float] | None = None
    top_k: int = Field(default=10, ge=1, le=120)
    use_contest_algebra: bool = True
    use_feature_value_model: bool = False
    player_positions: dict[str, str] = Field(default_factory=dict)
    decision_season: int | None = None
    train_labels: list[TrainLabelIn] = Field(default_factory=list)
    value_model_alpha: float = 1.0


def _parse_float_map(raw: dict[str, float]) -> dict[int, float]:
    out: dict[int, float] = {}
    for key, val in raw.items():
        try:
            out[int(key)] = float(val)
        except (TypeError, ValueError):
            continue
    return out


def _parse_str_map(raw: dict[str, str]) -> dict[int, str]:
    out: dict[int, str] = {}
    for key, val in raw.items():
        try:
            out[int(key)] = str(val)
        except (TypeError, ValueError):
            continue
    return out


def _train_labels_from_body(rows: list[TrainLabelIn]) -> list[ValueLabel]:
    return [
        ValueLabel(
            player_id=row.player_id,
            game_id=row.game_id,
            season=row.season,
            position=row.position,
            value=row.value,
            team_id=row.team_id,
        )
        for row in rows
    ]


def _resolve_request_values(
    *,
    player_ids: tuple[int, int, int, int, int],
    values_by_player: dict[str, float],
    use_feature_value_model: bool,
    player_positions: dict[str, str],
    decision_season: int | None,
    train_labels: list[TrainLabelIn],
    value_model_alpha: float,
) -> tuple[dict[int, float], dict[str, Any]]:
    try:
        return resolve_shadow_values(
            player_ids=list(player_ids),
            values_by_player=_parse_float_map(values_by_player),
            use_feature_value_model=use_feature_value_model,
            player_positions=_parse_str_map(player_positions),
            decision_season=decision_season,
            train_labels=_train_labels_from_body(train_labels),
            alpha=value_model_alpha,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
    """Research FastAPI app with split OpenAPI tags (observation only)."""

    # Split tags so /docs groups schemas / provider / shadow / data / status
    # instead of one flat "research" bucket.
    schemas = APIRouter(prefix="/research", tags=["research-schemas"])
    provider = APIRouter(prefix="/research", tags=["research-provider"])
    shadow = APIRouter(prefix="/research", tags=["research-shadow"])
    data = APIRouter(prefix="/research", tags=["research-data"])
    status = APIRouter(prefix="/research", tags=["research-status"])
    stub = FiveCardProviderStub()

    @schemas.get("/schemas/labels")
    def labels() -> dict[str, Any]:
        return label_schema()

    @schemas.get("/schemas/strategy")
    def strategy() -> dict[str, Any]:
        return strategy_document()

    @schemas.get("/schemas/features")
    def features() -> dict[str, Any]:
        return features_document()

    @schemas.get("/schemas/scoring")
    def scoring() -> dict[str, Any]:
        return scoring_document()

    @schemas.get("/features/live-ok")
    def features_live_ok() -> dict[str, Any]:
        live = list(live_ok_feature_names())
        stubs = list(offline_stub_feature_names())
        return {
            "live_ok": live,
            "live_ok_count": len(live),
            "offline_stub_features": stubs,
            "offline_stub_count": len(stubs),
            "contest_entry": False,
            "observation_only": True,
        }

    @provider.get("/provider/status")
    def provider_status() -> dict[str, Any]:
        ready = stub.readiness()
        payload = ready.to_json_obj()
        payload["posture"] = posture_from_readiness(ready).value
        return payload

    @provider.get("/provider/rules-offline")
    def provider_rules_offline() -> dict[str, Any]:
        """Best-effort public-rules notes; does not enable submit."""

        return offline_provider_rule_document()

    @status.get("/gates/entry")
    def entry_gates() -> dict[str, Any]:
        """Readiness checklist; contest_entry is always false."""

        return evaluate_entry_gates(stub=stub).to_json_obj()

    @shadow.post("/shadow/preview")
    def shadow_preview(body: ShadowPreviewRequest) -> dict[str, Any]:
        action = _action_from_body(body.player_ids, body.slot_multipliers, body.notes)
        preview = stub.shadow_preview(action)
        values, value_meta = _resolve_request_values(
            player_ids=body.player_ids,
            values_by_player=body.values_by_player,
            use_feature_value_model=body.use_feature_value_model,
            player_positions=body.player_positions,
            decision_season=body.decision_season,
            train_labels=body.train_labels,
            value_model_alpha=body.value_model_alpha,
        )
        preview["value_model"] = value_meta
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

    @shadow.post("/shadow/rank-orderings")
    def shadow_rank_orderings(body: RankOrderingsRequest) -> dict[str, Any]:
        values, value_meta = _resolve_request_values(
            player_ids=body.player_ids,
            values_by_player=body.values_by_player,
            use_feature_value_model=body.use_feature_value_model,
            player_positions=body.player_positions,
            decision_season=body.decision_season,
            train_labels=body.train_labels,
            value_model_alpha=body.value_model_alpha,
        )
        if len(values) < 1:
            raise HTTPException(
                status_code=422,
                detail=(
                    "values_by_player_required"
                    if not body.use_feature_value_model
                    else "feature_value_model_produced_no_values"
                ),
            )
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
            "use_feature_value_model": body.use_feature_value_model,
            "value_model": value_meta,
            "values_by_player": {str(k): v for k, v in values.items()},
            "orderings_evaluated": 120,
            "returned": len(ranked),
            "rankings": ranked,
        }

    @data.get("/catalog/seasons")
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

    @data.get("/coverage/summary")
    def coverage_summary() -> dict[str, Any]:
        return research_data_summary(project_root=project_root)

    @data.get("/schedule/summary")
    def schedule_summary() -> dict[str, Any]:
        """Offline nflverse schedule density; never enables contest entry."""

        data_sum = research_data_summary(project_root=project_root)
        catalog = data_sum.get("catalog") or {}
        seed_count = int(catalog.get("seed_game_count") or 0)
        seasons = catalog.get("seasons") or {}
        return research_schedule_summary(
            project_root=project_root,
            catalog_seed_count=seed_count,
            catalog_seasons=seasons if isinstance(seasons, dict) else None,
        )

    @data.get("/identity/density")
    def identity_density() -> dict[str, Any]:
        """Offline identity field-fill density; never enables contest entry."""

        return research_identity_summary(project_root=project_root)

    def _build_readiness_score() -> dict[str, Any]:
        data_sum = research_data_summary(project_root=project_root)
        identity = research_identity_summary(project_root=project_root)
        ready = stub.readiness()
        report = readiness_score_from_summaries(
            data_summary=data_sum,
            identity_summary=identity,
            live_ok_feature_count=len(live_ok_feature_names()),
            unknown_provider_rule_count=len(UNKNOWN_PROVIDER_RULES),
            offline_rule_note_count=len(OFFLINE_RULE_NOTES),
            auth_usable=ready.auth.usable,
        )
        payload = report.to_json_obj()
        payload["posture"] = posture_from_readiness(ready).value
        payload["auth"] = {
            "usable": ready.auth.usable,
            "status": ready.status.value,
            "note": "presence only; secret values never returned",
        }
        return payload

    @status.get("/health/readiness-score")
    def health_readiness_score() -> dict[str, Any]:
        """0–100 research density score; never authorizes contest entry."""

        return _build_readiness_score()

    @status.get("/status")
    def research_status(
        include_gates: bool = Query(default=True),
        include_readiness_score: bool = Query(default=True),
    ) -> dict[str, Any]:
        ready = stub.readiness()
        data_sum = research_data_summary(project_root=project_root)
        identity = research_identity_summary(project_root=project_root)
        entry = evaluate_entry_gates(stub=stub)
        railway = {
            "in_repo_config": False,
            "dockerfile": False,
            "staging_project_name": "nfl-oracle-staging",
            "staging_service_name": "nfl-oracle",
            "deploy_source_connected": False,
            "note": "external staging placeholders only; do not deploy from this package",
        }
        payload: dict[str, Any] = {
            "app": "nfl-oracle",
            "version": __version__,
            "mode": "research_shadow",
            "contest_entry": False,
            "posture": posture_from_readiness(ready).value,
            "provider": ready.to_json_obj(),
            "data": data_sum,
            "identity": identity,
            "scoring": {
                "observed_default_slot_multipliers": list(OBSERVED_DEFAULT_SLOT_MULTIPLIERS),
                "schema": "/research/schemas/scoring",
            },
            "value_model": {
                **value_model_strategy_note(),
                "shadow_flag": "use_feature_value_model",
                "shadow_flag_default": False,
                "default_offline_safe": True,
            },
            "railway": railway,
            "auth": {
                "usable": ready.auth.usable,
                "status": ready.status.value,
                "note": "presence only; secret values never returned",
            },
            "draft_readiness": {
                "observation_only": True,
                "contest_entry": False,
                "submit_hard_denied": True,
                "all_research_gates_ok": entry.all_research_gates_ok,
                "auth_usable": ready.auth.usable,
                "coverage_seed_game_count": data_sum.get("density", {}).get(
                    "catalog_seed_game_count", 0
                ),
                "identity_n": identity.get("n_identities", 0),
                "railway_deploy_ready": False,
                "policy": "deny_by_default_entry_gates",
            },
            "openapi_tags": [
                "research-schemas",
                "research-provider",
                "research-shadow",
                "research-data",
                "research-status",
            ],
        }
        if include_gates:
            payload["entry_gates"] = entry.to_json_obj()
        if include_readiness_score:
            score_payload = readiness_score_from_summaries(
                data_summary=data_sum,
                identity_summary=identity,
                live_ok_feature_count=len(live_ok_feature_names()),
                unknown_provider_rule_count=len(UNKNOWN_PROVIDER_RULES),
                offline_rule_note_count=len(OFFLINE_RULE_NOTES),
                auth_usable=ready.auth.usable,
            ).to_json_obj()
            payload["readiness_score"] = score_payload
            payload["draft_readiness"]["readiness_score"] = score_payload["score"]
            payload["draft_readiness"]["readiness_band"] = score_payload["band"]
        return payload

    meta = ServiceMetadata(name="nfl-oracle", version=__version__, environment="research")
    return create_service(
        meta,
        routers=(schemas, provider, shadow, data, status),
        health_contributors=(_AuthHealth(),),
        title="NFL Oracle Research",
        root_payload={
            "app": "nfl-oracle",
            "contest_entry": False,
            "mode": "research_shadow",
        },
    )
