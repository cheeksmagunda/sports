"""Loud fail-closed errors when live slate/board fields are missing (#574).

Never invent placeholder calendars, players, values, or scores. If the field
the app needs is absent or ambiguous, raise - do not guess.
"""

from __future__ import annotations


class LiveDataRequiredError(ValueError):
    """Raised when a required live field is missing or ambiguous."""

    def __init__(self, field: str, *, context: str = "") -> None:
        self.field = field
        self.context = context
        where = f" context={context}" if context else ""
        super().__init__(
            f"LIVE_DATA_REQUIRED: missing_or_ambiguous field={field}{where}. "
            "Do not invent placeholders; supply live Real Sports / calendar "
            "data or stop."
        )


def require_live(value: object, field: str, *, context: str = "") -> object:
    """Return value or raise when None / blank string / empty container."""

    if value is None:
        raise LiveDataRequiredError(field, context=context)
    if isinstance(value, str) and not value.strip():
        raise LiveDataRequiredError(field, context=context)
    if isinstance(value, (list, tuple, dict)) and len(value) == 0:
        raise LiveDataRequiredError(field, context=context)
    return value
