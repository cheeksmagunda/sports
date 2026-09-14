"""A published slate is terminal: freeze once, then stop.

The freeze is a decision a person acts on. Re-running the pipeline after it is
on the page can replace a lineup the operator has already entered, and each
re-run is another full provider sweep. Production wrote 19 freezes on
2026-09-09 and 20 on 2026-09-10, one distinct lineup each.

The guard must never cost a first freeze, so it fails open on anything it
cannot answer.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from nfl_oracle.recommendations.cli import _already_frozen

DAY = date(2026, 9, 14)


class _Store:
    """Minimal stand-in for the parts of the store the guard touches."""

    def __init__(self, frozen: Any = None, *, raises: bool = False) -> None:
        self._frozen = frozen
        self._raises = raises
        self.calls = 0

    def latest(self, day: date) -> Any:
        self.calls += 1
        if self._raises:
            raise RuntimeError("database unavailable")
        return self._frozen


def _freeze(cutoff: datetime) -> dict[str, str]:
    return {"cutoff_at": cutoff.isoformat()}


def test_skips_when_a_lineup_is_already_published_and_the_slate_is_open() -> None:
    cutoff = datetime.now(UTC) + timedelta(minutes=30)
    assert _already_frozen(_Store(_freeze(cutoff)), DAY) is True


def test_does_not_skip_before_the_first_freeze() -> None:
    assert _already_frozen(_Store(None), DAY) is False


def test_does_not_skip_once_the_slate_cutoff_has_passed() -> None:
    """Past cutoff, publish() already refuses; let it record "locked"."""

    cutoff = datetime.now(UTC) - timedelta(minutes=1)
    assert _already_frozen(_Store(_freeze(cutoff)), DAY) is False


def test_fails_open_when_the_store_raises() -> None:
    store = _Store(raises=True)
    assert _already_frozen(store, DAY) is False
    assert store.calls == 1


def test_fails_open_on_a_malformed_freeze_record() -> None:
    for broken in ({}, {"cutoff_at": None}, {"cutoff_at": "not-a-timestamp"}):
        assert _already_frozen(_Store(broken), DAY) is False
