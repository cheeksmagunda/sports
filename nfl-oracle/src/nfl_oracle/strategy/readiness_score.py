"""Observation-only research readiness score (0–100). Never authorizes entry.

Scores offline research density (catalog, schedule, identity, features, provider
rule notes) plus auth presence. Contest entry remains hard-denied regardless of
band — this is a research health signal for operators, not an entry gate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

Band = Literal["thin", "usable_offline", "dense_offline", "research_strong"]

# Targets tuned to current offline fixture density (#89 scaffold).
TARGET_SEED_GAMES = 70
TARGET_KNOWN_RATIO = 0.85
TARGET_SCHEDULE_GAMES = 4000
TARGET_CONTINUOUS_SEASONS = 16
TARGET_IDENTITY_N = 100
TARGET_IDENTITY_COMPLETE_RATIO = 0.85
TARGET_LIVE_OK_FEATURES = 12


@dataclass(frozen=True)
class ReadinessComponent:
    key: str
    weight: float
    unit_score: float  # 0.0–1.0
    detail: str

    @property
    def weighted(self) -> float:
        return self.weight * max(0.0, min(1.0, self.unit_score))


@dataclass(frozen=True)
class ResearchReadinessScore:
    score: float
    band: Band
    components: tuple[ReadinessComponent, ...]
    contest_entry: bool = False
    observation_only: bool = True

    def to_json_obj(self) -> dict[str, Any]:
        return {
            "name": "nfl_research_readiness_score",
            "version": 1,
            "contest_entry": False,
            "observation_only": True,
            "entry_authorized": False,
            "policy": "deny_by_default_entry_gates",
            "score": round(self.score, 2),
            "max_score": 100.0,
            "band": self.band,
            "components": [
                {
                    "key": c.key,
                    "weight": c.weight,
                    "unit_score": round(c.unit_score, 4),
                    "weighted": round(c.weighted, 2),
                    "detail": c.detail,
                }
                for c in self.components
            ],
            "note": (
                "Research density signal only. High score does not enable "
                "submit, inventory fetch, or contest entry."
            ),
        }


def _clamp01(value: float) -> float:
    if value != value:  # NaN
        return 0.0
    return max(0.0, min(1.0, float(value)))


def band_for_score(score: float) -> Band:
    if score >= 90.0:
        return "research_strong"
    if score >= 70.0:
        return "dense_offline"
    if score >= 40.0:
        return "usable_offline"
    return "thin"


def compute_research_readiness_score(
    *,
    seed_game_count: int = 0,
    known_ratio: float = 0.0,
    schedule_game_count: int = 0,
    continuous_regular_season_count: int = 0,
    identity_n: int = 0,
    identity_complete_ratio: float = 0.0,
    live_ok_feature_count: int = 0,
    unknown_provider_rule_count: int = 0,
    offline_rule_note_count: int = 0,
    auth_usable: bool = False,
) -> ResearchReadinessScore:
    """Pure scorer — callers supply already-loaded offline summaries."""

    catalog_unit = _clamp01(seed_game_count / TARGET_SEED_GAMES)
    coverage_unit = _clamp01(known_ratio / TARGET_KNOWN_RATIO)
    schedule_games_unit = _clamp01(schedule_game_count / TARGET_SCHEDULE_GAMES)
    continuous_unit = _clamp01(
        continuous_regular_season_count / TARGET_CONTINUOUS_SEASONS
    )
    schedule_unit = 0.6 * schedule_games_unit + 0.4 * continuous_unit
    identity_n_unit = _clamp01(identity_n / TARGET_IDENTITY_N)
    identity_complete_unit = _clamp01(
        identity_complete_ratio / TARGET_IDENTITY_COMPLETE_RATIO
    )
    identity_unit = 0.5 * identity_n_unit + 0.5 * identity_complete_unit
    features_unit = _clamp01(live_ok_feature_count / TARGET_LIVE_OK_FEATURES)
    if unknown_provider_rule_count <= 0:
        rules_unit = 0.0
    else:
        rules_unit = _clamp01(offline_rule_note_count / unknown_provider_rule_count)
    auth_unit = 1.0 if auth_usable else 0.0

    components = (
        ReadinessComponent(
            key="catalog_seeds",
            weight=15.0,
            unit_score=catalog_unit,
            detail=f"seed_game_count={seed_game_count}/{TARGET_SEED_GAMES}",
        ),
        ReadinessComponent(
            key="coverage_known",
            weight=10.0,
            unit_score=coverage_unit,
            detail=f"known_ratio={known_ratio:.3f} target={TARGET_KNOWN_RATIO}",
        ),
        ReadinessComponent(
            key="schedule_density",
            weight=20.0,
            unit_score=schedule_unit,
            detail=(
                f"schedule_games={schedule_game_count}/{TARGET_SCHEDULE_GAMES};"
                f" continuous={continuous_regular_season_count}/"
                f"{TARGET_CONTINUOUS_SEASONS}"
            ),
        ),
        ReadinessComponent(
            key="identity_density",
            weight=15.0,
            unit_score=identity_unit,
            detail=(
                f"n={identity_n}/{TARGET_IDENTITY_N};"
                f" complete_ratio={identity_complete_ratio:.3f}"
            ),
        ),
        ReadinessComponent(
            key="live_ok_features",
            weight=15.0,
            unit_score=features_unit,
            detail=f"live_ok={live_ok_feature_count}/{TARGET_LIVE_OK_FEATURES}",
        ),
        ReadinessComponent(
            key="provider_rules_offline",
            weight=15.0,
            unit_score=rules_unit,
            detail=(
                f"offline_notes={offline_rule_note_count}/"
                f"{unknown_provider_rule_count}"
            ),
        ),
        ReadinessComponent(
            key="realsports_auth",
            weight=10.0,
            unit_score=auth_unit,
            detail="auth_usable" if auth_usable else "auth_missing_research_ok",
        ),
    )
    score = sum(c.weighted for c in components)
    return ResearchReadinessScore(
        score=score,
        band=band_for_score(score),
        components=components,
    )


def readiness_score_from_summaries(
    *,
    data_summary: dict[str, Any],
    identity_summary: dict[str, Any] | None = None,
    live_ok_feature_count: int = 0,
    unknown_provider_rule_count: int = 0,
    offline_rule_note_count: int = 0,
    auth_usable: bool = False,
) -> ResearchReadinessScore:
    """Build score from research_data_summary / identity payloads."""

    catalog = data_summary.get("catalog") or {}
    density = data_summary.get("density") or {}
    schedule = data_summary.get("schedule") or {}
    schedule_density = schedule.get("density") or {}
    identity = identity_summary or data_summary.get("identity") or {}
    id_density = identity.get("density") or {}

    known_ratio = float(density.get("known_ratio") or 0.0)
    seed_count = int(
        catalog.get("seed_game_count")
        or density.get("catalog_seed_game_count")
        or 0
    )
    schedule_games = int(
        schedule_density.get("game_count") or schedule.get("game_count") or 0
    )
    continuous = int(schedule.get("continuous_regular_season_count") or 0)
    identity_n = int(identity.get("n_identities") or 0)
    complete_ratio = float(id_density.get("complete_ratio") or 0.0) if id_density else 0.0

    return compute_research_readiness_score(
        seed_game_count=seed_count,
        known_ratio=known_ratio,
        schedule_game_count=schedule_games,
        continuous_regular_season_count=continuous,
        identity_n=identity_n,
        identity_complete_ratio=complete_ratio,
        live_ok_feature_count=live_ok_feature_count,
        unknown_provider_rule_count=unknown_provider_rule_count,
        offline_rule_note_count=offline_rule_note_count,
        auth_usable=auth_usable,
    )
