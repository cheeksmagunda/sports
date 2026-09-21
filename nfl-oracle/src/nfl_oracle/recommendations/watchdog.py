"""NFL T-40 freeze watchdog.

Scheduled GitHub Actions runs this module against the recommendation database to
answer one operational question: did today's slate freeze by a small grace
window after T-40? The worker already records the freeze itself; this module is
the read-only alerting layer that notices when no freeze happened in time.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from nfl_oracle.calendar.week_close import WeekGame, kickoff_eastern


@dataclass(frozen=True)
class T40WatchdogReport:
    day: date
    status: str
    reason: str
    checked_at: datetime
    earliest_kickoff_at: datetime | None
    freeze_due_at: datetime | None
    alert_deadline_at: datetime | None
    frozen_at: datetime | None
    latest_run: dict[str, Any] | None

    @property
    def is_alert(self) -> bool:
        return self.status == "alert"


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(UTC)


def _freeze_deadline(day_games: list[WeekGame]) -> datetime | None:
    kickoffs = [kickoff_eastern(game) for game in day_games]
    resolved = [kick.astimezone(UTC) for kick in kickoffs if kick is not None]
    if not resolved:
        return None
    return min(resolved) - timedelta(minutes=40)


def evaluate_t40_deadline(
    *,
    day: date,
    games: list[WeekGame],
    frozen: dict[str, Any] | None,
    latest_run: dict[str, Any] | None,
    checked_at: datetime,
    grace_minutes: int = 10,
) -> T40WatchdogReport:
    """Read-only deadline evaluation for one slate day."""
    now = checked_at.astimezone(UTC)
    day_games = [game for game in games if game.gameday == day]
    if not day_games:
        return T40WatchdogReport(
            day=day,
            status="no_slate",
            reason="no_scheduled_games",
            checked_at=now,
            earliest_kickoff_at=None,
            freeze_due_at=None,
            alert_deadline_at=None,
            frozen_at=_parse_timestamp((frozen or {}).get("frozen_at")),
            latest_run=latest_run,
        )
    freeze_due_at = _freeze_deadline(day_games)
    frozen_at = _parse_timestamp((frozen or {}).get("frozen_at"))
    if freeze_due_at is None:
        return T40WatchdogReport(
            day=day,
            status="unresolved",
            reason="schedule_missing_gametime",
            checked_at=now,
            earliest_kickoff_at=None,
            freeze_due_at=None,
            alert_deadline_at=None,
            frozen_at=frozen_at,
            latest_run=latest_run,
        )
    earliest_kickoff_at = freeze_due_at + timedelta(minutes=40)
    alert_deadline_at = freeze_due_at + timedelta(minutes=grace_minutes)
    if frozen_at is not None and frozen_at <= alert_deadline_at:
        return T40WatchdogReport(
            day=day,
            status="ok",
            reason="freeze_on_time",
            checked_at=now,
            earliest_kickoff_at=earliest_kickoff_at,
            freeze_due_at=freeze_due_at,
            alert_deadline_at=alert_deadline_at,
            frozen_at=frozen_at,
            latest_run=latest_run,
        )
    if now < alert_deadline_at:
        return T40WatchdogReport(
            day=day,
            status="pending",
            reason="deadline_not_elapsed",
            checked_at=now,
            earliest_kickoff_at=earliest_kickoff_at,
            freeze_due_at=freeze_due_at,
            alert_deadline_at=alert_deadline_at,
            frozen_at=frozen_at,
            latest_run=latest_run,
        )
    return T40WatchdogReport(
        day=day,
        status="alert",
        reason="freeze_missed_deadline" if frozen_at is not None else "no_freeze_by_deadline",
        checked_at=now,
        earliest_kickoff_at=earliest_kickoff_at,
        freeze_due_at=freeze_due_at,
        alert_deadline_at=alert_deadline_at,
        frozen_at=frozen_at,
        latest_run=latest_run,
    )


def render_markdown(report: T40WatchdogReport) -> str:
    kickoff = report.earliest_kickoff_at.isoformat() if report.earliest_kickoff_at else "-"
    freeze_due = report.freeze_due_at.isoformat() if report.freeze_due_at else "-"
    alert_deadline = report.alert_deadline_at.isoformat() if report.alert_deadline_at else "-"
    frozen_at = report.frozen_at.isoformat() if report.frozen_at else "-"
    lines = [
        f"# NFL T-40 watchdog ({report.checked_at.strftime('%Y-%m-%dT%H:%MZ')})",
        "",
        f"- status: `{report.status}`",
        f"- reason: `{report.reason}`",
        f"- slate_date: `{report.day.isoformat()}`",
        f"- earliest_kickoff_at: `{kickoff}`",
        f"- freeze_due_at: `{freeze_due}`",
        f"- alert_deadline_at: `{alert_deadline}`",
        f"- frozen_at: `{frozen_at}`",
    ]
    if report.latest_run is not None:
        lines.extend(
            [
                "",
                "## Latest worker run",
                "",
                "```json",
                json.dumps(report.latest_run, sort_keys=True, separators=(",", ":")),
                "```",
            ]
        )
    return "\n".join(lines) + "\n"
