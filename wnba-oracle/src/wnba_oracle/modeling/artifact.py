"""Pure prediction helpers over an already-loaded model artifact."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from wnba_oracle.features.spec import cohort_for_position


class EBBaselineLike(Protocol):
    @property
    def cohort_means(self) -> Mapping[str, float]: ...

    @property
    def player_alpha(self) -> Mapping[int, float]: ...


class PickerArtifactLike(Protocol):
    @property
    def eb_baseline(self) -> EBBaselineLike | None: ...


def eb_predict_one(
    artifact: PickerArtifactLike | None,
    player_id: int,
    position: str,
) -> float | None:
    """Return one empirical-Bayes prediction without loading external state."""
    if artifact is None or artifact.eb_baseline is None:
        return None
    baseline = artifact.eb_baseline
    if int(player_id) not in baseline.player_alpha:
        return None
    cohort = cohort_for_position(position)
    prediction = baseline.cohort_means.get(cohort, 0.0) + baseline.player_alpha[int(player_id)]
    return max(0.5, float(prediction))
