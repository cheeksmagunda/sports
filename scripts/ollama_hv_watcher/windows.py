"""Domain-free T-40 → slate-close window math for the HV watcher (#574).

No sport imports. Each slate supplies freeze/kickoff and close instants;
the portfolio day plan arms at the earliest T-40 and releases at the latest
close. Session identity is ``{sport}:{slate_id}``.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from ollama_hv_watcher.live import LiveDataRequiredError, require_live

DEFAULT_T40_MINUTES = 40


def parse_iso_utc(value: str) -> datetime:
    """Parse an ISO-8601 timestamp into an aware UTC datetime."""

    raw = require_live(value, "timestamp")
    assert isinstance(raw, str)
    raw = raw.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        raise LiveDataRequiredError(
            "timestamp_timezone",
            context=f"value={value!r}; refuse naive placeholders",
        )
    return dt.astimezone(UTC)


@dataclass(frozen=True)
class SlateWindow:
    """One sport slate's arm/release window relative to freeze/kickoff."""

    sport: str
    slate_id: str
    freeze_or_kickoff_at: datetime
    close_at: datetime
    lead_minutes: int = DEFAULT_T40_MINUTES

    def __post_init__(self) -> None:
        if self.freeze_or_kickoff_at.tzinfo is None:
            raise ValueError("freeze_or_kickoff_at_must_be_timezone_aware")
        if self.close_at.tzinfo is None:
            raise ValueError("close_at_must_be_timezone_aware")
        if self.lead_minutes < 0:
            raise ValueError("lead_minutes_must_be_non_negative")
        if self.close_at < self.freeze_or_kickoff_at:
            raise ValueError("close_at_before_freeze_or_kickoff")
        if not self.sport.strip():
            raise ValueError("sport_required")
        if not self.slate_id.strip():
            raise ValueError("slate_id_required")

    @property
    def session_id(self) -> str:
        return f"{self.sport}:{self.slate_id}"

    @property
    def t40_at(self) -> datetime:
        return self.freeze_or_kickoff_at - timedelta(minutes=self.lead_minutes)

    @property
    def arm_at(self) -> datetime:
        return self.t40_at

    def is_armed(self, now: datetime) -> bool:
        if now.tzinfo is None:
            raise ValueError("now_must_be_timezone_aware")
        return self.arm_at <= now < self.close_at

    def is_active(self, now: datetime) -> bool:
        if now.tzinfo is None:
            raise ValueError("now_must_be_timezone_aware")
        return self.arm_at <= now <= self.close_at

    def is_before_arm(self, now: datetime) -> bool:
        if now.tzinfo is None:
            raise ValueError("now_must_be_timezone_aware")
        return now < self.arm_at

    def is_closed(self, now: datetime) -> bool:
        if now.tzinfo is None:
            raise ValueError("now_must_be_timezone_aware")
        return now >= self.close_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "sport": self.sport,
            "slate_id": self.slate_id,
            "session_id": self.session_id,
            "freeze_or_kickoff_at": self.freeze_or_kickoff_at.isoformat().replace(
                "+00:00", "Z"
            ),
            "close_at": self.close_at.isoformat().replace("+00:00", "Z"),
            "arm_at": self.arm_at.isoformat().replace("+00:00", "Z"),
            "t40_at": self.t40_at.isoformat().replace("+00:00", "Z"),
            "lead_minutes": self.lead_minutes,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> SlateWindow:
        if not isinstance(payload, dict):
            raise LiveDataRequiredError("slate_row", context="not_a_dict")
        missing = [
            key
            for key in ("sport", "slate_id", "freeze_or_kickoff_at", "close_at")
            if key not in payload or payload[key] in (None, "")
        ]
        if missing:
            raise LiveDataRequiredError(
                ",".join(missing),
                context="slate_window; refuse invented kickoff/close",
            )
        if "lead_minutes" in payload and payload["lead_minutes"] is None:
            raise LiveDataRequiredError(
                "lead_minutes",
                context="explicit null is ambiguous; omit key for T-40 default",
            )
        lead = (
            int(payload["lead_minutes"])
            if "lead_minutes" in payload
            else DEFAULT_T40_MINUTES
        )
        return cls(
            sport=str(require_live(payload["sport"], "sport")),
            slate_id=str(require_live(payload["slate_id"], "slate_id")),
            freeze_or_kickoff_at=parse_iso_utc(
                str(payload["freeze_or_kickoff_at"])
            ),
            close_at=parse_iso_utc(str(payload["close_at"])),
            lead_minutes=lead,
        )


@dataclass(frozen=True)
class DayWatchPlan:
    """Portfolio watch plan across one or more distinct slate sessions."""

    slates: tuple[SlateWindow, ...]

    def __post_init__(self) -> None:
        if not self.slates:
            raise ValueError("day_plan_requires_at_least_one_slate")
        seen: set[str] = set()
        for slate in self.slates:
            if slate.session_id in seen:
                raise ValueError(f"duplicate_session_id:{slate.session_id}")
            seen.add(slate.session_id)

    @property
    def arm_at(self) -> datetime:
        return min(s.arm_at for s in self.slates)

    @property
    def release_at(self) -> datetime:
        return max(s.close_at for s in self.slates)

    @property
    def close_at(self) -> datetime:
        return self.release_at

    def active_sessions(self, now: datetime) -> tuple[SlateWindow, ...]:
        return tuple(s for s in self.slates if s.is_armed(now))

    def active_slates(self, now: datetime) -> tuple[SlateWindow, ...]:
        return tuple(s for s in self.slates if s.is_active(now))

    def pending_sessions(self, now: datetime) -> tuple[SlateWindow, ...]:
        return tuple(s for s in self.slates if s.is_before_arm(now))

    def closed_sessions(self, now: datetime) -> tuple[SlateWindow, ...]:
        return tuple(s for s in self.slates if s.is_closed(now))

    def should_run(self, now: datetime) -> bool:
        if now.tzinfo is None:
            raise ValueError("now_must_be_timezone_aware")
        return self.arm_at <= now < self.release_at

    def is_active(self, now: datetime) -> bool:
        if now.tzinfo is None:
            raise ValueError("now_must_be_timezone_aware")
        return self.arm_at <= now <= self.release_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "arm_at": self.arm_at.isoformat().replace("+00:00", "Z"),
            "release_at": self.release_at.isoformat().replace("+00:00", "Z"),
            "close_at": self.close_at.isoformat().replace("+00:00", "Z"),
            "slate_count": len(self.slates),
            "session_ids": [s.session_id for s in self.slates],
            "slates": [s.to_dict() for s in self.slates],
        }


def build_day_plan(
    slates: Sequence[SlateWindow] | Iterable[SlateWindow],
) -> DayWatchPlan:
    ordered = tuple(sorted(slates, key=lambda s: (s.arm_at, s.sport, s.slate_id)))
    return DayWatchPlan(slates=ordered)


def portfolio_window(
    slates: Sequence[SlateWindow] | Iterable[SlateWindow],
) -> DayWatchPlan | None:
    material = list(slates)
    if not material:
        return None
    return build_day_plan(material)


build_portfolio_window = portfolio_window
PortfolioWindow = DayWatchPlan


def load_windows_payload(payload: dict[str, Any] | list[Any]) -> DayWatchPlan:
    if isinstance(payload, list):
        rows = payload
    else:
        rows = payload.get("slates")
        if not isinstance(rows, list):
            raise LiveDataRequiredError(
                "slates",
                context="windows_json_requires_slates_list",
            )
    windows: list[SlateWindow] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise LiveDataRequiredError(
                f"slates[{index}]",
                context="row_must_be_object; refuse silent skip",
            )
        windows.append(SlateWindow.from_dict(row))
    plan = portfolio_window(windows)
    if plan is None:
        raise LiveDataRequiredError("slates", context="windows_json_empty")
    return plan
