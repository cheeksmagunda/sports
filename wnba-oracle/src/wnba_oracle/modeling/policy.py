"""Immutable, versioned policy passed across the infrastructure/model seam."""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any, ClassVar, Literal

from wnba_oracle.features.game_script_minutes import GameScriptMinutesConfig
from wnba_oracle.picker.game_script import GameScriptConfig
from wnba_oracle.picker.optimize import OptimizeConfig
from wnba_oracle.picker.popularity import ContrarianConfig
from wnba_oracle.predict.availability import AvailabilityConfig
from wnba_oracle.predict.minutes import MinutesConfig

PayoutRegime = Literal["top_50", "top_20", "top_1"]


@dataclass(frozen=True)
class ModelPolicy:
    """Every setting and built-in constant that may change a served decision.

    The scheduler compiles its environment-backed ``Settings`` into this value
    once.  Numerical code receives this policy instead of receiving the full
    application configuration object or reading process state itself.
    """

    SCHEMA_VERSION: ClassVar[int] = 2
    LEGACY_SCHEMA_VERSION: ClassVar[int] = 1
    _V2_OPTIMIZER_FIELDS: ClassVar[frozenset[str]] = frozenset(
        {"contextual_stacking_enabled", "contextual_stack_ev_margin"}
    )

    optimizer: OptimizeConfig
    artifact_sha: str = ""
    payout_regime: PayoutRegime = "top_20"
    contrarian: ContrarianConfig = field(default_factory=ContrarianConfig)
    mixture_variance_enabled: bool = True
    slot_multipliers: tuple[float, ...] = (2.0, 1.8, 1.6, 1.4, 1.2)

    starter_signal_enabled: bool = True
    starter_signal_use_expected: bool = True
    starter_unknown_fade: float = 0.75
    starter_minutes_lift_enabled: bool = False
    starter_minutes_norm: float = 25.0
    starter_minutes_lift_weight: float = 0.6
    starter_minutes_lift_cap: float = 1.3
    prop_signal_scale: float = 0.0
    picker_floor_tilt_weight: float = 0.0
    picker_floor_tilt_max_boost: float = 2.0
    picker_boost_tail_lift: bool = False
    boost_tail_lift_threshold: float = 2.0
    boost_tail_lift_factor: float = 1.5
    minutes_model_enabled: bool = True
    game_script_minutes_enabled: bool = False
    availability_model_enabled: bool = False
    ceiling_sigma_blowout_boost: float = 0.0
    ceiling_sigma_low_history_boost: float = 0.0
    field_measured_ownership_enabled: bool = True

    minutes: MinutesConfig = field(default_factory=MinutesConfig)
    availability: AvailabilityConfig = field(default_factory=AvailabilityConfig)
    game_script_minutes: GameScriptMinutesConfig = field(default_factory=GameScriptMinutesConfig)
    game_script: GameScriptConfig = field(default_factory=GameScriptConfig)
    # Preserve the canonical payload version when replaying a historical
    # policy. This field is deliberately excluded from equality and payloads.
    _payload_schema_version: int = field(default=SCHEMA_VERSION, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._payload_schema_version not in (
            self.LEGACY_SCHEMA_VERSION,
            self.SCHEMA_VERSION,
        ):
            raise ValueError(
                f"unsupported model policy schema_version {self._payload_schema_version!r}"
            )
        self._validate_finite_values()
        self._validate_identity()
        self._validate_optimizer()
        self._validate_prediction_policy()
        self._validate_model_configs()

    def _validate_identity(self) -> None:
        if self.artifact_sha and not re.fullmatch(r"[0-9a-fA-F]{64}", self.artifact_sha):
            raise ValueError("artifact_sha must be empty or a 64-character SHA-256")
        if self.payout_regime not in {"top_50", "top_20", "top_1"}:
            raise ValueError(f"unsupported payout_regime {self.payout_regime!r}")
        if len(self.slot_multipliers) != 5 or any(value <= 0 for value in self.slot_multipliers):
            raise ValueError("slot_multipliers must contain five positive values")
        if tuple(sorted(self.slot_multipliers, reverse=True)) != self.slot_multipliers:
            raise ValueError("slot_multipliers must be in descending slot order")

    def _validate_optimizer(self) -> None:
        if self.optimizer.top_n_filter < 5:
            raise ValueError("optimizer.top_n_filter must be at least 5")
        if self.optimizer.n_samples <= 0:
            raise ValueError("optimizer.n_samples must be positive")
        if self.optimizer.n_field_lineups <= 0:
            raise ValueError("optimizer.n_field_lineups must be positive")
        if not 1 <= self.optimizer.max_per_team <= 5:
            raise ValueError("optimizer.max_per_team must be between 1 and 5")
        if self.optimizer.score_offset <= 0:
            raise ValueError("optimizer.score_offset must be positive")
        if self.optimizer.min_anchors < 0 or self.optimizer.min_anchors > 5:
            raise ValueError("optimizer.min_anchors must be between 0 and 5")
        if self.optimizer.boost_sum_cap < 0 or self.optimizer.max_single_boost < 0:
            raise ValueError("optimizer boost caps must be non-negative")
        if self.optimizer.skip_if_expected_payout_below < 0:
            raise ValueError("optimizer skip payout threshold must be non-negative")
        if (
            self.optimizer.caveat_if_expected_payout_below
            < self.optimizer.skip_if_expected_payout_below
        ):
            raise ValueError("optimizer caveat threshold must be at least the skip threshold")
        if self.optimizer.game_stack_bonus < 0:
            raise ValueError("optimizer.game_stack_bonus must be non-negative")
        if self.optimizer.contextual_stack_ev_margin < 0:
            raise ValueError("optimizer.contextual_stack_ev_margin must be non-negative")
        if (
            min(
                self.optimizer.leverage_weight,
                self.optimizer.ceiling_weight,
                self.optimizer.duplication_weight,
            )
            < 0
        ):
            raise ValueError("optimizer objective weights must be non-negative")
        if self.optimizer.field_same_game_boost <= 0 or self.optimizer.field_same_team_boost <= 0:
            raise ValueError("optimizer field stack boosts must be positive")

    def _validate_prediction_policy(self) -> None:
        if self.starter_unknown_fade < 0:
            raise ValueError("starter_unknown_fade must be non-negative")
        if self.starter_minutes_norm <= 0:
            raise ValueError("starter_minutes_norm must be positive")
        if not 0 <= self.starter_minutes_lift_weight <= 1:
            raise ValueError("starter_minutes_lift_weight must be between 0 and 1")
        if self.starter_minutes_lift_cap < 1:
            raise ValueError("starter_minutes_lift_cap must be at least 1")
        if self.prop_signal_scale < 0:
            raise ValueError("prop_signal_scale must be non-negative")
        if not 0 <= self.picker_floor_tilt_weight <= 1:
            raise ValueError("picker_floor_tilt_weight must be between 0 and 1")
        if self.picker_floor_tilt_max_boost <= 0:
            raise ValueError("picker_floor_tilt_max_boost must be positive")
        if self.boost_tail_lift_threshold < 0 or self.boost_tail_lift_factor <= 0:
            raise ValueError("boost-tail policy values must be non-negative")
        if self.ceiling_sigma_blowout_boost < 0 or self.ceiling_sigma_low_history_boost < 0:
            raise ValueError("ceiling sigma boosts must be non-negative")

    def _validate_model_configs(self) -> None:
        if self.contrarian.strength < 0 or self.contrarian.max_penalty < 0:
            raise ValueError("contrarian strength and max penalty must be non-negative")
        if self.contrarian.star_score_anchor <= 0:
            raise ValueError("contrarian.star_score_anchor must be positive")

        minutes = self.minutes
        if minutes.half_life <= 0 or minutes.min_rate <= 0 or minutes.max_rate < minutes.min_rate:
            raise ValueError("minutes rate bounds and half_life must be positive and ordered")
        if not minutes.min_rate <= minutes.league_rate <= minutes.max_rate:
            raise ValueError("minutes.league_rate must be within the configured rate bounds")
        if minutes.min_minutes < 0 or minutes.max_minutes < minutes.min_minutes:
            raise ValueError("minutes bounds must be non-negative and ordered")
        if not 0 <= minutes.confirm_weight <= 1 or not 0 < minutes.blowout_trim <= 1:
            raise ValueError("minutes weights must be within their probability bounds")
        if minutes.min_obs_for_history <= 0 or minutes.blend_k0 < 0:
            raise ValueError("minutes observation and blend parameters are invalid")

        availability = self.availability
        probabilities = (
            availability.neutral_prior,
            availability.prior_active,
            availability.confirmed_starter_active,
            availability.confirmed_bench_active,
            availability.p_min,
            availability.p_max,
        )
        if any(value < 0 or value > 1 for value in probabilities):
            raise ValueError("availability probabilities must be between 0 and 1")
        if availability.p_min > availability.p_max:
            raise ValueError("availability probability bounds must be ordered")
        if availability.active_minutes_floor < 0 or availability.min_vol <= 0:
            raise ValueError("availability minute parameters are invalid")
        if availability.confidence_k0 < 0:
            raise ValueError("availability.confidence_k0 must be non-negative")

        game_script = self.game_script
        ceilings = (
            game_script.defensive_grind_ceiling,
            game_script.balanced_ceiling,
            game_script.fast_paced_ceiling,
        )
        if tuple(sorted(ceilings)) != ceilings:
            raise ValueError("game-script total ceilings must be ordered")
        game_multipliers = (
            game_script.defensive_grind_mult,
            game_script.balanced_mult,
            game_script.fast_paced_mult,
            game_script.track_meet_mult,
            game_script.blowout_penalty,
        )
        if any(value <= 0 for value in game_multipliers):
            raise ValueError("game-script multipliers must be positive")
        if game_script.blowout_spread_threshold < 0:
            raise ValueError("game-script blowout threshold must be non-negative")

        game_minutes = self.game_script_minutes
        if game_minutes.soft_margin < 0 or game_minutes.hard_margin <= game_minutes.soft_margin:
            raise ValueError("game-script minute margins must be non-negative and ordered")
        if not 0 <= game_minutes.max_blowout_prob <= 1:
            raise ValueError("game-script maximum blowout probability must be between 0 and 1")
        if not 0 <= game_minutes.starter_trim_fraction <= 1:
            raise ValueError("game-script starter trim fraction must be between 0 and 1")
        if not 0 <= game_minutes.redistribution_rate <= 1:
            raise ValueError("game-script redistribution rate must be between 0 and 1")
        if game_minutes.starter_minutes_floor < 0 or game_minutes.per_player_cap_minutes < 0:
            raise ValueError("game-script minute limits must be non-negative")

    def _validate_finite_values(self) -> None:
        def visit(value: Any, path: str) -> None:
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"{path} must be finite")
            if is_dataclass(value) and not isinstance(value, type):
                for field in fields(value):
                    visit(getattr(value, field.name), f"{path}.{field.name}")
            elif isinstance(value, (tuple, list)):
                for index, item in enumerate(value):
                    visit(item, f"{path}[{index}]")

        for model_field in fields(self):
            visit(getattr(self, model_field.name), model_field.name)

    def to_payload(self) -> dict[str, Any]:
        """Canonical JSON-compatible policy payload retained with a freeze."""
        values = asdict(self)
        schema_version = values.pop("_payload_schema_version")
        if schema_version == self.LEGACY_SCHEMA_VERSION:
            optimizer = values["optimizer"]
            for name in self._V2_OPTIMIZER_FIELDS:
                optimizer.pop(name, None)
        return {"schema_version": schema_version, **values}

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> ModelPolicy:
        """Rebuild and validate a persisted policy for an exact replay."""
        schema_version = payload.get("schema_version")
        if schema_version not in (cls.LEGACY_SCHEMA_VERSION, cls.SCHEMA_VERSION):
            raise ValueError(f"unsupported model policy schema_version {schema_version!r}")
        values = dict(payload)
        values.pop("schema_version", None)
        config_types = {
            "optimizer": OptimizeConfig,
            "contrarian": ContrarianConfig,
            "minutes": MinutesConfig,
            "availability": AvailabilityConfig,
            "game_script_minutes": GameScriptMinutesConfig,
            "game_script": GameScriptConfig,
        }
        try:
            for name, config_type in config_types.items():
                config_payload = values.get(name)
                if not isinstance(config_payload, Mapping):
                    raise ValueError(f"model policy field {name!r} must be an object")
                config_values = dict(config_payload)
                if name == "optimizer" and schema_version == cls.LEGACY_SCHEMA_VERSION:
                    incompatible = cls._V2_OPTIMIZER_FIELDS.intersection(config_values)
                    if incompatible:
                        names = ", ".join(sorted(incompatible))
                        raise ValueError(
                            "model policy schema_version 1 cannot contain v2 optimizer "
                            f"fields: {names}"
                        )
                values[name] = config_type(**config_values)
            slot_multipliers = values.get("slot_multipliers")
            if not isinstance(slot_multipliers, (list, tuple)):
                raise ValueError("model policy slot_multipliers must be an array")
            values["slot_multipliers"] = tuple(float(value) for value in slot_multipliers)
            return cls(**values, _payload_schema_version=schema_version)
        except TypeError as exc:
            raise ValueError(f"invalid model policy payload: {exc}") from exc

    @property
    def sha256(self) -> str:
        payload = json.dumps(
            self.to_payload(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
