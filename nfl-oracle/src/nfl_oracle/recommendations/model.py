"""Chronological Real-value model with explicit evidence and holdout diagnostics."""

from __future__ import annotations

import math
from collections import deque
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from statistics import mean, pstdev
from typing import Any, Literal, cast

from pydantic import Field, field_validator, model_validator

from nfl_oracle.baselines.ridge import RidgeRegressor
from nfl_oracle.recommendations.schema import (
    EvidenceClock,
    Finite,
    PositiveId,
    Record,
    Slate,
    fingerprint,
    utc,
)

EstimatorName = Literal["ridge", "player_prior", "position_mean", "global_mean"]


class HistoricalPerformance(Record):
    player_id: PositiveId
    external_id: str | None = None
    game_id: PositiveId
    position: str
    kickoff_at: datetime
    available_at: datetime
    captured_at: datetime
    value: Finite
    opportunity: Finite | None = None
    team_id: PositiveId | None = None
    opponent_team_id: PositiveId | None = None
    role: str | None = None
    did_not_play: bool = False
    context_features: dict[str, Finite] = Field(default_factory=dict)
    context_clock: EvidenceClock | None = None
    context_evidence_mode: Literal["prospective", "retrospective_reconstructed"] = "prospective"
    context_source_hashes: tuple[str, ...] = ()
    _aware = field_validator("kickoff_at", "available_at", "captured_at")(utc)

    @model_validator(mode="after")
    def finalized_after_start(self) -> HistoricalPerformance:
        if self.available_at <= self.kickoff_at:
            raise ValueError("label_not_postgame")
        if self.context_features and self.context_clock is None:
            raise ValueError("context_clock_required")
        if self.context_clock and self.context_evidence_mode == "prospective":
            self.context_clock.assert_available(self.kickoff_at)
        return self


class ContextAdjustment(Record):
    clock: EvidenceClock
    external_id: str | None = None
    mean_multiplier: Finite = Field(default=1, ge=0, le=3)
    availability_probability: Finite = Field(default=1, ge=0, le=1)
    uncertainty_multiplier: Finite = Field(default=1, ge=1, le=5)
    provenance: tuple[str, ...] = ()
    features: dict[str, Finite] = Field(default_factory=dict)


class Projection(Record):
    player_id: PositiveId
    mean: Finite
    stddev: Finite = Field(ge=0)
    conditional_mean: Finite
    availability_probability: Finite = Field(ge=0, le=1)
    prior_games: int = Field(ge=0)
    samples: tuple[Finite, ...]
    provenance: tuple[str, ...]


class RatingModel(Record):
    version: Literal[1] = 1
    trained_at: datetime
    training_fingerprint: str
    training_rows: int
    coefficients: tuple[Finite, ...]
    residuals: tuple[Finite, ...]
    evaluation: dict[str, float | int | str]
    label_provenance: str = "real_value_postgame_finalized"
    selected_estimator: EstimatorName = "ridge"
    feature_coverage: dict[str, float] = Field(default_factory=dict)
    ablation_evaluation: dict[str, float | int | str] = Field(default_factory=dict)
    context_feature_names: tuple[str, ...] = ()
    feature_names: tuple[str, ...] = (
        "intercept",
        "player_mean_shrunk",
        "recent_mean_shrunk",
        "position_mean",
        "prior_log_count",
        "prior_stddev",
        "opportunity_trend",
    )
    _aware = field_validator("trained_at")(utc)

    @property
    def model_fingerprint(self) -> str:
        return fingerprint(self.model_dump(mode="json"))


def _context_vector(values: Mapping[str, float], names: Sequence[str]) -> list[float]:
    return [v for name in names for v in (values.get(name, 0.0), float(name not in values))]


def _validate_identity_links(rows: Sequence[HistoricalPerformance]) -> None:
    """Allow stable-ID aliases, while rejecting same-game identity conflicts."""
    stable_game: dict[tuple[str, int], int] = {}
    real_player_stable: dict[int, str] = {}
    for row in rows:
        if not row.external_id:
            continue
        stable_key = (row.external_id, row.game_id)
        prior_real = stable_game.get(stable_key)
        if prior_real is not None and prior_real != row.player_id:
            raise ValueError("duplicate_stable_identity_game")
        stable_game[stable_key] = row.player_id
        prior_stable = real_player_stable.get(row.player_id)
        if prior_stable is not None and prior_stable != row.external_id:
            raise ValueError("conflicting_external_identity")
        real_player_stable[row.player_id] = row.external_id


def attach_enrichment(
    history: Iterable[HistoricalPerformance], enrichment: Any
) -> tuple[HistoricalPerformance, ...]:
    """Attach strict historical context rows while preserving source clocks.

    Enrichment is keyed only by ``(player_id, game_id)``. Duplicate history or
    enrichment keys are rejected, and retrospective reconstructed snapshots
    retain their actual capture clock and evidence mode.
    """
    history_rows = tuple(history)
    enrichment_rows = tuple(getattr(enrichment, "rows", ()))
    by_key: dict[tuple[int, int], Any] = {}
    for row in history_rows:
        key = (row.player_id, row.game_id)
        if key in by_key:
            raise ValueError("duplicate_historical_player_game")
        by_key[key] = None
    enriched_by_key: dict[tuple[int, int], Any] = {}
    for row in enrichment_rows:
        key = (int(row.player_id), int(row.game_id))
        if key in enriched_by_key:
            raise ValueError("duplicate_historical_context_key")
        if key not in by_key:
            raise ValueError("context_without_historical_label")
        if row.evidence_mode not in {"prospective", "retrospective_reconstructed"}:
            raise ValueError("invalid_context_evidence_mode")
        enriched_by_key[key] = row
    result: list[HistoricalPerformance] = []
    for row in history_rows:
        context = enriched_by_key.get((row.player_id, row.game_id))
        if context is None:
            result.append(row)
            continue
        result.append(
            row.model_copy(
                update={
                    "external_id": getattr(context, "external_id", None),
                    "context_features": dict(context.features),
                    "context_clock": context.clock,
                    "context_evidence_mode": context.evidence_mode,
                    "context_source_hashes": tuple(context.source_hashes),
                }
            )
        )
    return tuple(result)


class _PlayerStats:
    __slots__ = (
        "sum",
        "sumsq",
        "count",
        "observations",
        "available",
        "values",
        "opportunities",
    )

    def __init__(self) -> None:
        self.sum = 0.0
        self.sumsq = 0.0
        self.count = 0
        self.observations = 0
        self.available = 0
        self.values: deque[tuple[datetime, float]] = deque(maxlen=8)
        self.opportunities: deque[tuple[datetime, float]] = deque(maxlen=8)

    def add(self, row: HistoricalPerformance) -> None:
        self.observations += 1
        self.available += int(not row.did_not_play)
        # Availability is modeled separately. A DNP label must not also enter
        # the conditional performance prior, or it would be counted twice.
        if row.did_not_play:
            return
        self.sum += row.value
        self.sumsq += row.value * row.value
        self.count += 1
        self.values.append((row.kickoff_at, row.value))
        if row.opportunity is not None:
            self.opportunities.append((row.kickoff_at, row.opportunity))

    @staticmethod
    def recent(source: deque[tuple[datetime, float]]) -> list[float]:
        return [value for _, value in sorted(source, key=lambda item: item[0])[-4:]]


class _PriorBank:
    def __init__(self) -> None:
        self.total = 0.0
        self.count = 0
        self.positions: dict[str, tuple[float, float, int]] = {}
        self.players: dict[int, _PlayerStats] = {}
        self.external_players: dict[str, _PlayerStats] = {}
        self.observed_did_not_play = False

    def add(self, row: HistoricalPerformance) -> None:
        if not row.did_not_play:
            self.total += row.value
            self.count += 1
            role = row.role or row.position
            total, sumsq, count = self.positions.get(role, (0.0, 0.0, 0))
            self.positions[role] = total + row.value, sumsq + row.value * row.value, count + 1
        self.players.setdefault(row.player_id, _PlayerStats()).add(row)
        if row.external_id:
            self.external_players.setdefault(row.external_id, _PlayerStats()).add(row)
        self.observed_did_not_play = self.observed_did_not_play or row.did_not_play

    def _stats(self, player_id: int, external_id: str | None = None) -> _PlayerStats:
        if external_id:
            stats = self.external_players.get(external_id)
            if stats is not None and stats.count:
                return stats
        stats = self.players.get(player_id)
        if stats is not None and stats.count:
            return stats
        return _PlayerStats()

    def vector(self, player_id: int, position: str, external_id: str | None = None) -> list[float]:
        total, _, count = self.positions.get(position, (self.total, 0.0, self.count))
        pm = total / count if count else 0.0
        stats = self._stats(player_id, external_id)
        recent = stats.recent(stats.values)
        opportunities = stats.recent(stats.opportunities)
        trend = 0.0
        if len(opportunities) >= 4:
            base = mean(opportunities)
            trend = (mean(opportunities[-3:]) - base) / max(1, abs(base))
        variance = (
            max(0.0, stats.sumsq / stats.count - (stats.sum / stats.count) ** 2)
            if stats.count
            else 0.0
        )
        return [
            1,
            (stats.sum + 5 * pm) / (stats.count + 5),
            (sum(recent) + 3 * pm) / (len(recent) + 3),
            pm,
            math.log1p(stats.count),
            math.sqrt(variance),
            trend,
        ]

    def player_availability(self, player_id: int, external_id: str | None = None) -> float:
        stats = self._stats(player_id, external_id)
        if stats.observations == 0:
            return 1.0
        return (stats.available + 2.0) / (stats.observations + 2.0)

    def player_count(self, player_id: int, external_id: str | None = None) -> int:
        return self._stats(player_id, external_id).count

    @property
    def availability_provenance(self) -> str:
        return (
            "historical_did_not_play_rate"
            if self.observed_did_not_play
            else "appearance_only_availability_prior"
        )


def _design(
    rows: Sequence[HistoricalPerformance], names: Sequence[str] = ()
) -> tuple[list[list[float]], list[float]]:
    """Reconstruct source-clock priors; later captures are not prospective proof."""
    x: list[list[float]] = []
    y: list[float] = []
    available = sorted(rows, key=lambda r: r.available_at)
    bank = _PriorBank()
    cursor = 0
    for row in sorted(rows, key=lambda r: r.kickoff_at):
        while cursor < len(available) and available[cursor].available_at < row.kickoff_at:
            bank.add(available[cursor])
            cursor += 1
        if row.did_not_play:
            continue
        if bank.count:
            x.append(
                bank.vector(row.player_id, row.role or row.position, row.external_id)
                + _context_vector(row.context_features, names)
            )
            y.append(row.value)
    return x, y


def fit_model(rows: Sequence[HistoricalPerformance], *, trained_at: datetime) -> RatingModel:
    now = utc(trained_at)
    if len({(r.player_id, r.game_id) for r in rows}) != len(rows):
        raise ValueError("duplicate_historical_player_game")
    if any(max(r.available_at, r.captured_at) > now for r in rows):
        raise ValueError("future_training_label")
    if any(
        r.context_clock is not None
        and max(r.context_clock.source_available_at, r.context_clock.captured_at) > now
        for r in rows
    ):
        raise ValueError("future_context_evidence")
    _validate_identity_links(rows)
    ordered = sorted(rows, key=lambda r: (r.kickoff_at, r.game_id, r.player_id))
    times = sorted({r.kickoff_at for r in ordered})
    if len(times) < 5 or len(ordered) < 30:
        raise ValueError("insufficient_training_history")
    split = times[max(2, int(len(times) * 0.8))]
    train = [r for r in ordered if r.available_at < split]
    holdout = [r for r in ordered if r.kickoff_at >= split]
    names = tuple(sorted({key for row in train for key in row.context_features}))
    x, y = _design(train, names)
    if len(x) < 10 or not holdout:
        raise ValueError("insufficient_chronological_evaluation")
    fitted = RidgeRegressor(alpha=10).fit(x, y)
    ablation_x, ablation_y = _design(train)
    ablation_fit = RidgeRegressor(alpha=10).fit(ablation_x, ablation_y)
    bank = _PriorBank()
    for record in train:
        bank.add(record)
    errors: list[float] = []
    baseline_player: list[float] = []
    baseline_position: list[float] = []
    baseline_global: list[float] = []
    ablation_errors: list[float] = []
    train_values = [record.value for record in train if not record.did_not_play]
    global_mean = mean(train_values) if train_values else 0.0
    position_values: dict[str, list[float]] = {}
    for record in train:
        if record.did_not_play:
            continue
        position_values.setdefault(record.role or record.position, []).append(record.value)
    for row in holdout:
        # Frozen training block, no within-holdout updates or shared-game labels.
        if row.did_not_play:
            continue
        features = bank.vector(
            row.player_id, row.role or row.position, row.external_id
        ) + _context_vector(row.context_features, names)
        errors.append(row.value - fitted.predict([features])[0])
        ablation_features = bank.vector(row.player_id, row.role or row.position, row.external_id)
        ablation_errors.append(row.value - ablation_fit.predict([ablation_features])[0])
        baseline_player.append(row.value - features[1])
        position_mean = mean(position_values.get(row.role or row.position, train_values or [0.0]))
        baseline_position.append(row.value - position_mean)
        baseline_global.append(row.value - global_mean)
    if not errors:
        raise ValueError("insufficient_conditional_holdout")
    baseline_errors = {
        "player_prior": baseline_player,
        "position_mean": baseline_position,
        "global_mean": baseline_global,
    }
    candidates_mae = {"ridge": mean(abs(e) for e in errors)} | {
        name: mean(abs(e) for e in values) for name, values in baseline_errors.items()
    }
    # Keep the ridge tie-breaker first, but never claim the fitted model won
    # when a simple frozen baseline has lower holdout error.
    selected_estimator = cast(
        EstimatorName,
        min(candidates_mae, key=lambda name: (candidates_mae[name], name != "ridge")),
    )
    final_x, final_y = _design(ordered, names)
    final = RidgeRegressor(alpha=10).fit(final_x, final_y)
    context_width = 2 * len(names)
    if selected_estimator == "ridge":
        selected_coefficients = tuple(final.coefficients or ())
        selected_errors = errors
    elif selected_estimator == "player_prior":
        selected_coefficients = (0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0) + (0.0,) * context_width
        selected_errors = baseline_player
    elif selected_estimator == "position_mean":
        selected_coefficients = (0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0) + (0.0,) * context_width
        selected_errors = baseline_position
    else:
        selected_coefficients = (global_mean, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0) + (0.0,) * context_width
        selected_errors = baseline_global
    performance_train = [row for row in train if not row.did_not_play]
    feature_coverage = {
        name: mean(float(name in row.context_features) for row in performance_train)
        for name in names
    }
    retrospective_rows = sum(
        row.context_evidence_mode == "retrospective_reconstructed"
        for row in train
        if row.context_features and not row.did_not_play
    )
    prospective_rows = sum(
        row.context_evidence_mode == "prospective"
        for row in train
        if row.context_features and not row.did_not_play
    )
    return RatingModel(
        trained_at=now,
        training_rows=len(ordered),
        context_feature_names=names,
        training_fingerprint=fingerprint([r.model_dump(mode="json") for r in ordered]),
        coefficients=selected_coefficients,
        residuals=tuple(selected_errors),
        selected_estimator=selected_estimator,
        feature_coverage=feature_coverage,
        ablation_evaluation={
            "with_context_mae": mean(abs(e) for e in errors),
            "without_context_mae": mean(abs(e) for e in ablation_errors),
            "context_mae_delta": mean(abs(e) for e in errors)
            - mean(abs(e) for e in ablation_errors),
            "context_train_rows": sum(bool(row.context_features) for row in performance_train),
            "context_retrospective_rows": retrospective_rows,
            "context_prospective_rows": prospective_rows,
        },
        evaluation={
            "kind": "retrospective_source_clock_frozen_holdout",
            "capture_clock_replay": "not_prospective_validation",
            "holdout_rows": len(errors),
            "holdout_did_not_play_rows": sum(row.did_not_play for row in holdout),
            "train_rows": len(train),
            "mae": mean(abs(e) for e in errors),
            "rmse": math.sqrt(mean(e * e for e in errors)),
            "bias": -mean(errors),
            "player_prior_mae": mean(abs(e) for e in baseline_player),
            "position_mean_mae": mean(abs(e) for e in baseline_position),
            "global_mean_mae": mean(abs(e) for e in baseline_global),
            "player_prior_rmse": math.sqrt(mean(e * e for e in baseline_player)),
            "position_mean_rmse": math.sqrt(mean(e * e for e in baseline_position)),
            "global_mean_rmse": math.sqrt(mean(e * e for e in baseline_global)),
            "selected_estimator": selected_estimator,
            "selected_mae": candidates_mae[selected_estimator],
            "context_evidence_disclosure": (
                "retrospective_reconstructed_context_included"
                if retrospective_rows
                else "prospective_or_missing_context_only"
            ),
            "split_at": split.isoformat(),
        },
    )


def predict(
    slate: Slate,
    model: RatingModel,
    history: Sequence[HistoricalPerformance],
    *,
    decision_at: datetime,
    context: Mapping[int, ContextAdjustment] | None = None,
) -> tuple[Projection, ...]:
    now = utc(decision_at)
    slate.assert_prelock(now)
    if model.trained_at > now:
        raise ValueError("future_model")
    if not model.residuals or len(model.coefficients) != len(model.feature_names) + 2 * len(
        model.context_feature_names
    ):
        raise ValueError("invalid_model_artifact")
    game_ids = {g.game_id for g in slate.games}
    prior = [
        r
        for r in history
        if max(r.available_at, r.captured_at) <= now
        and r.game_id not in game_ids
        and r.kickoff_at < now
    ]
    if not prior:
        raise ValueError("no_available_history")
    _validate_identity_links(prior)
    bank = _PriorBank()
    for record in prior:
        bank.add(record)
    # Center residual draws by their arithmetic mean so the empirical sample
    # distribution has mean exactly equal to the conditional projection.
    residual_center = mean(model.residuals)
    result = []
    for player in slate.candidates:
        adjustment = (context or {}).get(player.player_id)
        if adjustment:
            adjustment.clock.assert_available(now)
        external_id = adjustment.external_id if adjustment else None
        features = bank.vector(player.player_id, player.position, external_id) + _context_vector(
            adjustment.features if adjustment else {}, model.context_feature_names
        )
        conditional = sum(a * b for a, b in zip(model.coefficients, features, strict=True))
        historical_probability = bank.player_availability(player.player_id, external_id)
        probability = (
            min(historical_probability, adjustment.availability_probability)
            if adjustment
            else historical_probability
        )
        if (player.injury_status or "").lower() in {"out", "inactive", "suspended", "ir"}:
            probability = 0.0
        conditional *= adjustment.mean_multiplier if adjustment else 1.0
        uncertainty = adjustment.uncertainty_multiplier if adjustment else 1.0
        n = bank.player_count(player.player_id, external_id)
        uncertainty *= math.sqrt(1 + 5 / (n + 1))
        samples = tuple(conditional + (e - residual_center) * uncertainty for e in model.residuals)
        conditional_variance = pstdev(samples) ** 2
        result.append(
            Projection(
                player_id=player.player_id,
                mean=conditional * probability,
                conditional_mean=conditional,
                availability_probability=probability,
                stddev=math.sqrt(
                    probability * conditional_variance
                    + probability * (1 - probability) * conditional**2
                ),
                prior_games=n,
                samples=samples,
                provenance=(
                    f"real_value_chronological_{model.selected_estimator}",
                    "empirical_holdout_residuals",
                    bank.availability_provenance,
                    "cold_start_uncertainty_estimate",
                )
                + (adjustment.provenance if adjustment else ("context_unavailable",)),
            )
        )
    return tuple(result)
