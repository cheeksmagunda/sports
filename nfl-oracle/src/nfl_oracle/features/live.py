"""Map captured pre-lock evidence onto FeatureSpec names.

Two evidence paths already exist in this application and are the only inputs
here:

- Real Sports cards expose ``injuryStatus`` (``contests.parse`` keeps it on
  ``EntryLineupPick``; ``recommendations.provider`` keeps it on ``Candidate``).
- NWS forecasts are captured by ``recommendations.sources`` and reduced to
  ``weather_*`` numbers by ``forecast_features``.

Nothing is invented. When a capture is absent the value stays ``None`` and the
matching ``*_available`` flag stays ``False``; an indoor venue is reported the
same way, because no forecast was observed rather than because a magnitude was
guessed.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Final

INJURY_CATEGORIES: Final[tuple[str, ...]] = (
    "active",
    "questionable",
    "doubtful",
    "out",
    "inactive",
    "ir",
    "suspended",
    "limited",
    "dnp",
    "full",
    "unknown",
)

_INJURY_ALIASES: Final[dict[str, str]] = {
    "q": "questionable",
    "questionable": "questionable",
    "d": "doubtful",
    "doubtful": "doubtful",
    "o": "out",
    "out": "out",
    "active": "active",
    "available": "active",
    "inactive": "inactive",
    "ir": "ir",
    "injuredreserve": "ir",
    "suspended": "suspended",
    "limited": "limited",
    "dnp": "dnp",
    "didnotparticipate": "dnp",
    "full": "full",
    "fullparticipation": "full",
}

WEATHER_FEATURE_NAMES: Final[tuple[str, ...]] = (
    "weather_temp_f",
    "weather_wind_mph",
    "weather_precip_prob",
)


def injury_category(value: str | None) -> str:
    """Coarse, probability-free availability category for a raw designation."""

    normalized = re.sub(r"[^a-z]", "", (value or "").lower())
    return _INJURY_ALIASES.get(normalized, "unknown")


def injury_observed(value: str | None) -> bool:
    """True when the provider actually carried a designation on the card.

    An unrecognized string is still an observation; it only means the coarse
    category is ``unknown``. Absence of the field is the non-observation.
    """

    return value is not None and str(value).strip() != ""


def injury_features(value: str | None) -> dict[str, Any]:
    """FeatureSpec-named injury row: category plus its availability flag."""

    observed = injury_observed(value)
    return {
        "injury_status": injury_category(value) if observed else None,
        "injury_status_available": observed,
    }


def injury_indicator_features(value: str | None) -> dict[str, float]:
    """One-hot ``injury_<category>`` floats plus the availability float.

    Float-only so it can be merged straight into a model context vector.
    """

    category = injury_category(value)
    row = {f"injury_{name}": float(category == name) for name in INJURY_CATEGORIES}
    row["injury_status_available"] = float(injury_observed(value))
    return row


def weather_features(
    forecast: Mapping[str, float] | None, *, indoor: bool = False
) -> dict[str, Any]:
    """FeatureSpec-named weather row from an already-reduced NWS forecast.

    ``forecast`` is the mapping ``recommendations.sources.forecast_features``
    returns. Indoor venues and missing captures both yield nulls with
    ``weather_available`` False.
    """

    captured = {} if indoor or not forecast else dict(forecast)
    row: dict[str, Any] = {name: captured.get(name) for name in WEATHER_FEATURE_NAMES}
    row["weather_available"] = any(row[name] is not None for name in WEATHER_FEATURE_NAMES)
    return row


def weather_availability_flag(vector: Mapping[str, float]) -> float:
    """Availability float for a context vector already carrying weather keys."""

    return float(any(name in vector for name in WEATHER_FEATURE_NAMES))


def canonical_live_context_feature_names() -> tuple[str, ...]:
    """Injury one-hots + weather magnitudes always reserved in RatingModel (#418).

    Union these with keys observed in training so live card/NWS evidence can
    move predictions even when historical injury/weather coverage was sparse.
    """

    injury_keys = tuple(f"injury_{name}" for name in INJURY_CATEGORIES)
    return injury_keys + ("injury_status_available",) + WEATHER_FEATURE_NAMES + ("weather_available",)
