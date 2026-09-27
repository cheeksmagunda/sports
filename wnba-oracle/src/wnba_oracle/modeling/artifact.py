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

    @property
    def pace_beta(self) -> float: ...

    @property
    def opp_pace_beta(self) -> float: ...

    @property
    def vegas_beta(self) -> float: ...

    @property
    def boost_beta(self) -> float: ...

    @property
    def league_pace(self) -> float: ...

    @property
    def league_opp_pace(self) -> float: ...

    @property
    def league_vegas(self) -> float: ...

    @property
    def league_boost(self) -> float: ...


class PickerArtifactLike(Protocol):
    @property
    def eb_baseline(self) -> EBBaselineLike | None: ...


def eb_predict_one(
    artifact: PickerArtifactLike | None,
    player_id: int,
    position: str,
    *,
    team_pace: float | None = None,
    opp_pace: float | None = None,
    vegas_total: float | None = None,
    card_boost: float | None = None,
    overall_rank: float | None = None,
    team_moneyline: float | None = None,
) -> float | None:
    """Return one empirical-Bayes prediction without loading external state.

    When pace / vegas / boost are provided (from serve-time ``head_features``
    or the Real Sports pool row), apply the fitted linear terms (#523). Older
    artifacts without the newer betas still work via ``getattr`` defaults.
    """
    if artifact is None or artifact.eb_baseline is None:
        return None
    baseline = artifact.eb_baseline
    if int(player_id) not in baseline.player_alpha:
        return None
    cohort = cohort_for_position(position)
    prediction = baseline.cohort_means.get(cohort, 0.0) + baseline.player_alpha[int(player_id)]
    pace_beta = float(getattr(baseline, "pace_beta", 0.0) or 0.0)
    league_pace = float(getattr(baseline, "league_pace", 0.0) or 0.0)
    if team_pace is not None and pace_beta:
        prediction += pace_beta * (float(team_pace) - league_pace)
    opp_beta = float(getattr(baseline, "opp_pace_beta", 0.0) or 0.0)
    league_opp = float(getattr(baseline, "league_opp_pace", 0.0) or 0.0)
    if opp_pace is not None and opp_beta:
        prediction += opp_beta * (float(opp_pace) - league_opp)
    vegas_beta = float(getattr(baseline, "vegas_beta", 0.0) or 0.0)
    league_vegas = float(getattr(baseline, "league_vegas", 0.0) or 0.0)
    if vegas_total is not None and vegas_beta:
        prediction += vegas_beta * (float(vegas_total) - league_vegas)
    boost_beta = float(getattr(baseline, "boost_beta", 0.0) or 0.0)
    league_boost = float(getattr(baseline, "league_boost", 0.0) or 0.0)
    if card_boost is not None and boost_beta:
        prediction += boost_beta * (float(card_boost) - league_boost)
    rank_beta = float(getattr(baseline, "overall_rank_beta", 0.0) or 0.0)
    league_rank = float(getattr(baseline, "league_overall_rank", 0.0) or 0.0)
    if overall_rank is not None and rank_beta:
        prediction += rank_beta * (float(overall_rank) - league_rank)
    ml_beta = float(getattr(baseline, "moneyline_beta", 0.0) or 0.0)
    league_ml = float(getattr(baseline, "league_moneyline", 0.0) or 0.0)
    if team_moneyline is not None and ml_beta:
        prediction += ml_beta * (float(team_moneyline) - league_ml)
    return max(0.5, float(prediction))
