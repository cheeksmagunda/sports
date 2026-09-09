"""NFL prepare, publish, and lock lifecycle on the shared durable store.

Collection and training finish before the publish deadline. Publishing uses an
audited prepared artifact, refreshes the provider lock, and checks database time
inside the freeze transaction. These capabilities do not grant contest entry.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from nfl_oracle.recommendations.context import ContextBundle
from nfl_oracle.recommendations.model import (
    ContextAdjustment,
    HistoricalPerformance,
    RatingModel,
    predict,
)
from nfl_oracle.recommendations.optimizer import (
    FieldObservation,
    OptimizerConfig,
    Recommendation,
    ScoringPolicy,
    optimize,
)
from nfl_oracle.recommendations.provider import NFLReader
from nfl_oracle.recommendations.schema import Contest, Record, Slate, fingerprint, utc
from nfl_oracle.recommendations.store import RecommendationStore


class PipelinePolicy(Record):
    recommendations_enabled: bool = False
    freeze_minutes: Literal[40] = 40
    input_max_age_seconds: int = Field(default=900, ge=60, le=900)
    model_max_age_days: int = Field(default=8, ge=1, le=30)
    optimizer: OptimizerConfig = Field(default_factory=OptimizerConfig)
    contest_entry: Literal[False] = False


class ModelBundle(Record):
    model: RatingModel
    history: tuple[HistoricalPerformance, ...]
    source_hashes: tuple[str, ...]
    audit: dict[str, Any]
    contest_entry: Literal[False] = False

    @model_validator(mode="after")
    def training_integrity(self) -> ModelBundle:
        ordered = sorted(self.history, key=lambda r: (r.kickoff_at, r.game_id, r.player_id))
        if fingerprint([r.model_dump(mode="json") for r in ordered]) != (
            self.model.training_fingerprint
        ):
            raise ValueError("training_input_fingerprint_mismatch")
        if len(ordered) != self.model.training_rows:
            raise ValueError("training_row_count_mismatch")
        return self


class PreparedDecision(Record):
    slate: Slate
    recommendation: Recommendation
    context: ContextBundle
    model_sha256: str
    model_fingerprint: str
    prepared_at: datetime
    freeze_due_at: datetime
    policy_fingerprint: str
    contest_entry: Literal[False] = False

    _aware = field_validator("prepared_at", "freeze_due_at")(utc)


def freeze_due(slate: Slate) -> datetime:
    return slate.cutoff() - timedelta(minutes=40)


def validate_lock_refresh(original: Contest, current: Contest) -> None:
    """A refresh cannot silently substitute another contest or scoring law."""
    stable = ("contest_id", "contest_type", "sport", "day", "end_day", "slot_multipliers")
    if any(getattr(original, key) != getattr(current, key) for key in stable):
        raise ValueError("contest_changed_during_prepare")
    if current.is_locked or current.is_finalized:
        raise ValueError("provider_contest_locked")


class RecommendationPipeline:
    def __init__(
        self,
        store: RecommendationStore,
        *,
        policy: PipelinePolicy | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.store = store
        self.policy = policy or PipelinePolicy()
        self.clock = clock

    def active_model(self) -> tuple[str, ModelBundle]:
        activation = self.store.latest_artifact("active_model")
        if activation is None:
            raise ValueError("active_model_missing")
        artifact = self.store.get_artifact(activation["payload"]["model_sha256"])
        if artifact is None or artifact["kind"] != "model_bundle":
            raise ValueError("active_model_artifact_missing")
        bundle = ModelBundle.model_validate(artifact["payload"])
        age = utc(self.clock()) - bundle.model.trained_at
        if age.total_seconds() < 0 or age > timedelta(days=self.policy.model_max_age_days):
            raise ValueError("model_stale_or_future")
        return artifact["sha256"], bundle

    def activate_model(self, bundle: ModelBundle) -> str:
        """Activate a evaluated artifact; retain previous versions for rollback."""
        now = utc(self.clock())
        if bundle.model.trained_at > now:
            raise ValueError("future_model")
        evaluation = bundle.model.evaluation
        if int(evaluation.get("holdout_rows", 0)) < 1:
            raise ValueError("model_validation_missing")
        required = ("mae", "rmse", "player_prior_mae", "position_mean_mae", "global_mean_mae")
        if any(key not in evaluation for key in required):
            raise ValueError("model_baseline_comparison_missing")
        digest = self.store.put_artifact("model_bundle", bundle.model_dump(mode="json"))
        self.store.put_artifact(
            "active_model",
            {"model_sha256": digest, "activated_at": now.isoformat(), "contest_entry": False},
        )
        return digest

    def prepare(
        self,
        slate: Slate,
        context: ContextBundle,
        *,
        field: FieldObservation | None = None,
    ) -> PreparedDecision:
        now = utc(self.clock())
        slate.assert_prelock(now, max_age_seconds=self.policy.input_max_age_seconds)
        model_sha, bundle = self.active_model()
        if set(context.features_by_player) != {p.player_id for p in slate.candidates}:
            raise ValueError("context_player_pool_mismatch")
        adjustments = {
            pid: ContextAdjustment(
                clock=context.clocks_by_player[pid],
                external_id=context.external_ids.get(pid),
                features=features,
                provenance=(context.evidence_mode, *context.missing_by_player.get(pid, ())),
            )
            for pid, features in context.features_by_player.items()
        }
        projections = predict(
            slate, bundle.model, bundle.history, decision_at=now, context=adjustments
        )
        lineup = optimize(
            slate,
            projections,
            decision_at=now,
            scoring_policy=ScoringPolicy(),
            config=self.policy.optimizer,
            field=field,
        )
        prepared = PreparedDecision(
            slate=slate,
            recommendation=lineup,
            context=context,
            model_sha256=model_sha,
            model_fingerprint=bundle.model.model_fingerprint,
            prepared_at=now,
            freeze_due_at=freeze_due(slate),
            policy_fingerprint=fingerprint(self.policy.model_dump(mode="json")),
        )
        self.store.put_artifact(
            f"prepared:{slate.contest.day.isoformat()}", prepared.model_dump(mode="json")
        )
        self.store.record_run(
            slate.contest.day,
            status="waiting",
            detail_code="prepared_for_freeze",
            details={"next_freeze": prepared.freeze_due_at.isoformat()},
        )
        return prepared

    async def publish(self, day: date, reader: NFLReader) -> dict[str, Any] | None:
        if not self.policy.recommendations_enabled:
            raise PermissionError("recommendations_disabled")
        now = utc(self.clock())
        previous = self.store.latest(day)
        if previous is not None and now >= datetime.fromisoformat(previous["cutoff_at"]):
            self.store.record_run(day, status="locked", detail_code="saved_lineup_locked")
            return previous
        artifact = self.store.latest_artifact(f"prepared:{day.isoformat()}")
        if artifact is None:
            raise ValueError("prepared_decision_missing")
        prepared = PreparedDecision.model_validate(artifact["payload"])
        if prepared.policy_fingerprint != fingerprint(self.policy.model_dump(mode="json")):
            raise ValueError("prepared_policy_changed")
        if now < prepared.freeze_due_at:
            self.store.record_run(
                day,
                status="waiting",
                detail_code="waiting_for_freeze",
                details={"next_freeze": prepared.freeze_due_at.isoformat()},
            )
            return None
        prepared.slate.assert_prelock(now, max_age_seconds=self.policy.input_max_age_seconds)
        active_sha, _ = self.active_model()
        if active_sha != prepared.model_sha256:
            raise ValueError("prepared_model_changed")
        for clock in prepared.context.clocks_by_player.values():
            clock.assert_available(now)
        current = await reader.contest(prepared.slate.contest.contest_id)
        validate_lock_refresh(prepared.slate.contest, current)
        refreshed = prepared.slate.model_copy(update={"contest": current})
        decision_at = utc(self.clock())
        record = self.store.freeze(
            refreshed,
            prepared.recommendation.model_dump(mode="json"),
            model_fingerprint=prepared.model_fingerprint,
            input_fingerprint=artifact["sha256"],
            decision_at=decision_at,
        )
        self.store.record_run(day, status="ready", detail_code="five_picks_frozen")
        return record
