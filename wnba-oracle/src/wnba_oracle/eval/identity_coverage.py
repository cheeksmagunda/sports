"""Identity-aware prediction-to-outcome joins with explicit coverage reporting."""

from __future__ import annotations

import unicodedata
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True, slots=True)
class IdentityCoverageReport:
    total_predictions: int
    canonical_identity_resolved: int
    canonical_outcome_matches: int
    fallback_outcome_matches: int
    unresolved_canonical_predictions: int
    fully_unmatched_predictions: int

    @property
    def canonical_outcome_match_rate(self) -> float:
        return (
            self.canonical_outcome_matches / self.total_predictions
            if self.total_predictions
            else 0.0
        )

    @property
    def fallback_outcome_match_rate(self) -> float:
        return (
            self.fallback_outcome_matches / self.total_predictions
            if self.total_predictions
            else 0.0
        )

    @property
    def unresolved_canonical_rate(self) -> float:
        return (
            self.unresolved_canonical_predictions / self.total_predictions
            if self.total_predictions
            else 0.0
        )


def join_predictions_to_outcomes(
    *,
    predictions: pd.DataFrame,
    outcomes: pd.DataFrame,
    canonical_mapping: pd.DataFrame,
    prediction_date_col: str,
    prediction_player_id_col: str,
    prediction_name_col: str,
    prediction_team_col: str,
    outcome_date_col: str,
    outcome_player_id_col: str,
    outcome_name_col: str,
    outcome_team_col: str,
    fallback_team_alias: Callable[[object], str] | None = None,
) -> tuple[pd.DataFrame, IdentityCoverageReport]:
    team_alias = fallback_team_alias or (lambda value: str(value or "").upper())
    pred = predictions.copy()
    out = outcomes.copy()
    canon = canonical_mapping.copy()

    pred["__prediction_row_id"] = range(len(pred))
    pred["__prediction_rs_id"] = pred[prediction_player_id_col].map(lambda value: str(int(value)))

    canon["__mapping_rs_id"] = canon["real_sports_player_id"].map(lambda value: str(value))
    out = out[out["min"] > 0].copy()
    out["__fallback_initial"] = out[outcome_name_col].map(lambda name: _norm(name)[:1])
    out["__fallback_last"] = out[outcome_name_col].map(_last_name)
    out["__fallback_team"] = out[outcome_team_col].map(team_alias)

    merged = pred.merge(
        canon[["__mapping_rs_id", "wnba_player_id", "provenance"]],
        left_on="__prediction_rs_id",
        right_on="__mapping_rs_id",
        how="left",
    )
    merged["__canonical_resolved"] = merged["wnba_player_id"].notna()

    canonical_joined = merged.merge(
        out,
        left_on=[prediction_date_col, "wnba_player_id"],
        right_on=[outcome_date_col, outcome_player_id_col],
        how="left",
        suffixes=("", "_outcome"),
    )
    canonical_joined["__matched_via_canonical"] = canonical_joined["min"].notna()

    unresolved = canonical_joined.loc[
        ~canonical_joined["__canonical_resolved"],
        [
            "__prediction_row_id",
            prediction_date_col,
            prediction_player_id_col,
            prediction_name_col,
            prediction_team_col,
        ],
    ].copy()
    unresolved["__fallback_initial"] = unresolved[prediction_name_col].map(
        lambda name: _norm(name)[:1]
    )
    unresolved["__fallback_last"] = unresolved[prediction_name_col].map(_last_name)
    unresolved["__fallback_team"] = unresolved[prediction_team_col].map(team_alias)
    fallback_joined = unresolved.merge(
        out,
        left_on=[prediction_date_col, "__fallback_initial", "__fallback_last"],
        right_on=[outcome_date_col, "__fallback_initial", "__fallback_last"],
        how="left",
        suffixes=("", "_outcome"),
    )
    fallback_joined["__team_match"] = (
        fallback_joined["__fallback_team"] == fallback_joined["__fallback_team_outcome"]
    ).fillna(False)
    fallback_joined = fallback_joined.sort_values("__team_match", ascending=False).drop_duplicates(
        subset="__prediction_row_id", keep="first"
    )
    fallback_joined["__matched_via_fallback"] = fallback_joined["min"].notna()

    fallback_by_row = fallback_joined.set_index("__prediction_row_id")
    combined = canonical_joined.set_index("__prediction_row_id")
    fallback_rows = combined.index.intersection(fallback_by_row.index)
    for column in out.columns:
        combined.loc[fallback_rows, column] = combined.loc[fallback_rows, column].where(
            combined.loc[fallback_rows, "__matched_via_canonical"],
            fallback_by_row.loc[fallback_rows, column],
        )
    combined["__matched_via_fallback"] = False
    combined.loc[fallback_rows, "__matched_via_fallback"] = (
        ~combined.loc[fallback_rows, "__matched_via_canonical"]
        & fallback_by_row.loc[fallback_rows, "__matched_via_fallback"]
    )

    report = IdentityCoverageReport(
        total_predictions=len(combined),
        canonical_identity_resolved=int(combined["__canonical_resolved"].sum()),
        canonical_outcome_matches=int(combined["__matched_via_canonical"].sum()),
        fallback_outcome_matches=int(combined["__matched_via_fallback"].sum()),
        unresolved_canonical_predictions=int((~combined["__canonical_resolved"]).sum()),
        fully_unmatched_predictions=int(
            (~combined["__matched_via_canonical"] & ~combined["__matched_via_fallback"]).sum()
        ),
    )
    return combined.reset_index(drop=True), report


def _norm(value: object) -> str:
    raw = unicodedata.normalize("NFKD", str(value or ""))
    ascii_only = "".join(char for char in raw if not unicodedata.combining(char))
    return "".join(char for char in ascii_only.lower() if char.isalnum() or char.isspace()).strip()


def _last_name(value: object) -> str:
    parts = _norm(value).split()
    return parts[-1] if parts else ""
