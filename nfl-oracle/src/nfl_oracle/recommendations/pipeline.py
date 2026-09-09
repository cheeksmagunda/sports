"""NFL prepare, publish, and lock lifecycle on the shared durable store.

Collection and training finish before the publish deadline. Publishing uses an
audited prepared artifact, refreshes the provider lock, and checks database time
inside the freeze transaction. These capabilities do not grant contest entry.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Literal

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
    Pick,
    Recommendation,
    ScoringPolicy,
    optimize,
)
from nfl_oracle.recommendations.provider import NFLReader
from nfl_oracle.recommendations.schema import (
    Contest,
    EvidenceClock,
    Record,
    Slate,
    fingerprint,
    utc,
)
from nfl_oracle.recommendations.store import RecommendationStore
from nfl_oracle.strategy.gates import (
    FreezeGateReport,
    GateItem,
    combine_gate_items,
    declare_boost_regime,
    gate_boost_regime,
    gate_clock_freshness,
    gate_identity_resolution,
    gate_no_submission_path,
    gate_pool_completeness,
)

if TYPE_CHECKING:
    from nfl_oracle.contests.boosts import BoostObservation


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


def gate_contest_state(
    original: Contest, current: Contest | None, *, refetch_error: str | None
) -> GateItem:
    """G5: refuse unless a re-checked contest reads unlocked and unchanged.

    ``current`` must come from an independent re-observation of the contest
    (a fresh provider read, or a separately re-captured slate artifact), not
    from ``original`` itself. When no re-check was performed, this refuses
    rather than assuming the originally prepared state still holds.
    """
    if current is None:
        return GateItem(
            key="G5_contest_state",
            ok=False,
            detail=f"contest_state_not_reverified: {refetch_error or 'no_recheck_performed'}",
        )
    try:
        validate_lock_refresh(original, current)
    except ValueError as error:
        return GateItem(key="G5_contest_state", ok=False, detail=str(error))
    return GateItem(
        key="G5_contest_state",
        ok=True,
        detail=(
            f"contest_id={current.contest_id} is_locked={current.is_locked} "
            f"is_finalized={current.is_finalized} "
            f"recheck_captured_at={current.clock.captured_at.isoformat()}"
        ),
    )


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


def gate_model_freshness(
    pipeline: RecommendationPipeline,
) -> tuple[GateItem, tuple[str, ModelBundle] | None]:
    """G6: refuse on a stale or unfingerprinted model bundle.

    Reuses ``RecommendationPipeline.active_model`` in full rather than
    duplicating a parallel freshness check: its sha256 is a content
    fingerprint of the canonical model payload (re-verified against the
    stored artifact on every read in ``RecommendationStore.get_artifact``),
    and the age check against ``policy.model_max_age_days`` already lives
    there. This function only reports that check's outcome as a gate.
    """
    try:
        model_sha, bundle = pipeline.active_model()
    except ValueError as error:
        return GateItem(key="G6_model_freshness", ok=False, detail=str(error)), None
    age_days = (utc(pipeline.clock()) - bundle.model.trained_at).total_seconds() / 86400
    detail = (
        f"model_sha256={model_sha} model_fingerprint={bundle.model.model_fingerprint} "
        f"trained_at={bundle.model.trained_at.isoformat()} age_days={age_days:.3f} "
        f"max_age_days={pipeline.policy.model_max_age_days}"
    )
    return GateItem(key="G6_model_freshness", ok=True, detail=detail), (model_sha, bundle)


# Proof statement carried verbatim in every emitted freeze artifact. Boost's
# contribution to total score never depends on slot assignment (see the
# module docstring's decomposition), so it holds for any per-player boosts,
# not only the all-zero week-1 regime this contest currently reads.
REARRANGEMENT_INEQUALITY_PROOF = (
    "Total score for five committed cards decomposes as "
    "sum(value_i * slot_i) + sum(value_i * boost_i). The second term is fixed "
    "once the five players are chosen and does not depend on which slot each "
    "player holds. In the first (rearrangement) term, for any two slots i < j "
    "the committed multipliers satisfy slot_i > slot_j. If the player in the "
    "higher slot has the lower projected value (value_i < value_j while "
    "player i holds slot i), swapping the two players' slots changes the "
    "rearrangement term by (value_j - value_i) * (slot_i - slot_j) > 0, a "
    "strict improvement. So no ascending-value adjacent pair can be optimal: "
    "the optimal committed order is strictly descending projected value, for "
    "any per-player boosts, once the five players are fixed."
)


@dataclass(frozen=True)
class FreezeOutcome:
    """Result of one ``freeze_dry_run`` call: a gate report, plus an artifact
    only when every gate passed."""

    gate_report: FreezeGateReport
    artifact: dict[str, Any] | None


def _boost_observation_clock(observation: BoostObservation) -> EvidenceClock:
    captured = utc(datetime.fromisoformat(observation.captured_at))
    return EvidenceClock(source_available_at=captured, captured_at=captured)


def freeze_dry_run(
    pipeline: RecommendationPipeline,
    *,
    slate: Slate,
    context: ContextBundle,
    boost_observation: BoostObservation,
    current_contest: Contest | None,
    refetch_error: str | None,
    now: datetime,
    require_freeze_window: bool,
) -> FreezeOutcome:
    """Run G1-G7 in order, then emit the five-pick freeze artifact, or refuse.

    ``require_freeze_window`` distinguishes a production freeze (must run at
    or after T-40 and before cutoff) from an explicit ``--dry-run`` rehearsal,
    where every other gate still applies and only that window check is
    skipped. Selection (``prepare``) only runs once every gate that does not
    depend on the selected five has already passed, so a bad model or a
    stale input is never fed into the optimizer. G3 (identity of the
    selected five) and the supplementary descending-value order check can
    only run after selection, so they are evaluated last even though they
    are reported under their G-numbers alongside every other gate.
    """
    now = utc(now)
    items: list[GateItem] = [gate_pool_completeness(slate)]

    worst_clock = (
        min(context.clocks_by_player.values(), key=lambda c: c.captured_at)
        if context.clocks_by_player
        else slate.contest.clock
    )
    clocks = {
        "contest": slate.contest.clock,
        "slate_capture": EvidenceClock(
            source_available_at=slate.captured_at, captured_at=slate.captured_at
        ),
        "context_worst_case": worst_clock,
        "boost_observation": _boost_observation_clock(boost_observation),
    }
    items.append(
        gate_clock_freshness(
            clocks, decision_at=now, max_age_seconds=pipeline.policy.input_max_age_seconds
        )
    )
    items.append(gate_boost_regime(boost_observation, slate))
    model_gate, model_result = gate_model_freshness(pipeline)
    items.append(model_gate)
    items.append(gate_contest_state(slate.contest, current_contest, refetch_error=refetch_error))
    items.append(gate_no_submission_path())

    prereqs_ok = all(item.ok for item in items)

    if prereqs_ok and require_freeze_window:
        due = freeze_due(slate)
        cutoff = slate.cutoff()
        if not (due <= now < cutoff):
            items.append(
                GateItem(
                    key="freeze_window",
                    ok=False,
                    detail=(
                        f"now={now.isoformat()} not in [{due.isoformat()}, {cutoff.isoformat()})"
                    ),
                )
            )
            prereqs_ok = False

    prepared: PreparedDecision | None = None
    if prereqs_ok:
        try:
            prepared = pipeline.prepare(slate, context)
        except ValueError as error:
            items.append(GateItem(key="selection", ok=False, detail=str(error)))
            prereqs_ok = False

    if prereqs_ok and prepared is not None:
        picks: Sequence[Pick] = prepared.recommendation.picks
        values = [pick.projected_value for pick in picks]
        descending = all(values[i] >= values[i + 1] for i in range(len(values) - 1))
        items.append(
            GateItem(
                key="order_verification",
                ok=descending,
                detail=f"projected_values_in_committed_slot_order={values}",
            )
        )
        items.append(gate_identity_resolution(slate, picks))
    else:
        items.append(GateItem(key="G3_identity", ok=False, detail="selection_not_attempted"))

    report = combine_gate_items(items)
    if not report.ok or prepared is None or model_result is None:
        return FreezeOutcome(gate_report=report, artifact=None)

    model_sha, bundle = model_result
    picks = prepared.recommendation.picks
    artifact: dict[str, Any] = {
        "contest_entry": False,
        "dry_run": not require_freeze_window,
        "contest_id": slate.contest.contest_id,
        "day": slate.contest.day.isoformat(),
        "game_ids": [g.game_id for g in slate.games],
        "decision_at": now.isoformat(),
        "picks": [
            {
                "slot": pick.slot,
                "slot_multiplier": pick.slot_multiplier,
                "player_id": pick.player_id,
                "name": pick.name,
                "team": pick.team,
                "position": pick.position,
                "card_boost": pick.card_boost,
                "projected_value": pick.projected_value,
                "projected_score": pick.projected_score,
            }
            for pick in picks
        ],
        "committed_slot_order": [pick.slot_multiplier for pick in picks],
        "projected_values_in_slot_order": [pick.projected_value for pick in picks],
        "rearrangement_inequality_proof": REARRANGEMENT_INEQUALITY_PROOF,
        "declared_boost_regime": declare_boost_regime(boost_observation),
        "boost_observation": {
            "captured_at": boost_observation.captured_at,
            "n_players": boost_observation.n_players,
            "n_nonzero": boost_observation.n_nonzero,
            "published": boost_observation.published,
        },
        "pool_completeness": {
            "method": slate.pool_method,
            "roster_count": slate.pool_roster_count,
            "matched_count": slate.pool_search_matched_count,
            "unmatched_ids": list(slate.pool_unmatched_ids),
        },
        "model_sha256": model_sha,
        "model_fingerprint": bundle.model.model_fingerprint,
        "model_trained_at": bundle.model.trained_at.isoformat(),
        "source_clocks": {
            name: {
                "captured_at": clock.captured_at.isoformat(),
                "source_available_at": clock.source_available_at.isoformat(),
            }
            for name, clock in clocks.items()
        },
        "gates": report.to_json_obj(),
    }
    return FreezeOutcome(gate_report=report, artifact=artifact)
