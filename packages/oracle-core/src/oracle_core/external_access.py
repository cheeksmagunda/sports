"""Provider-neutral coordination for scarce external account access."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import text
from sqlalchemy.engine import Engine


class ExternalAccessConfigurationError(RuntimeError):
    """Raised when durable external-access coordination cannot run safely."""


@dataclass(frozen=True, slots=True)
class AccessPolicy:
    """Account-wide spacing and daily ceiling for collection windows."""

    min_interval: timedelta
    max_windows_per_day: int
    timezone: str = "UTC"

    def __post_init__(self) -> None:
        if self.min_interval < timedelta(0):
            raise ValueError("min_interval cannot be negative")
        if self.max_windows_per_day < 1:
            raise ValueError("max_windows_per_day must be at least 1")
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"unknown timezone: {self.timezone}") from exc


@dataclass(frozen=True, slots=True)
class AccessGrant:
    """Result of atomically attempting to reserve one account access window."""

    granted: bool
    reason: str
    window_id: int | None = None
    next_eligible_at: datetime | None = None
    windows_today: int = 0


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return value.astimezone(UTC)


def _day_bounds(now: datetime, timezone: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone)
    local_day = now.astimezone(zone).date()
    start = datetime.combine(local_day, time.min, tzinfo=zone).astimezone(UTC)
    end = datetime.combine(local_day + timedelta(days=1), time.min, tzinfo=zone).astimezone(UTC)
    return start, end


def _lock_key(scope: str) -> int:
    digest = hashlib.blake2b(scope.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)


def evaluate_access(
    *,
    policy: AccessPolicy,
    now: datetime,
    last_started_at: datetime | None,
    windows_today: int,
) -> AccessGrant:
    """Pure policy decision used by the durable coordinator and unit tests."""

    current = _require_aware(now)
    if windows_today >= policy.max_windows_per_day:
        return AccessGrant(False, "daily_limit", windows_today=windows_today)
    if last_started_at is not None:
        last = _require_aware(last_started_at)
        next_eligible = last + policy.min_interval
        if current < next_eligible:
            return AccessGrant(
                False,
                "cooldown",
                next_eligible_at=next_eligible,
                windows_today=windows_today,
            )
    return AccessGrant(True, "granted", windows_today=windows_today)


def try_acquire_access_window(
    engine: Engine,
    *,
    scope: str,
    consumer: str,
    policy: AccessPolicy,
    slate_date: date | None = None,
    now: datetime | None = None,
) -> AccessGrant:
    """Atomically reserve a durable access window across processes and apps."""

    if not scope.strip() or not consumer.strip():
        raise ValueError("scope and consumer must be non-empty")
    if engine.dialect.name != "postgresql":
        raise ExternalAccessConfigurationError(
            "external access coordination requires PostgreSQL advisory locks"
        )

    current = _require_aware(now or datetime.now(UTC))
    day_start, day_end = _day_bounds(current, policy.timezone)
    with engine.begin() as connection:
        connection.execute(
            text("SELECT pg_advisory_xact_lock(:lock_key)"),
            {"lock_key": _lock_key(scope)},
        )
        last_started_at = connection.execute(
            text(
                "SELECT started_at FROM external_access_windows "
                "WHERE scope = :scope ORDER BY started_at DESC LIMIT 1"
            ),
            {"scope": scope},
        ).scalar_one_or_none()
        windows_today = int(
            connection.execute(
                text(
                    "SELECT count(*) FROM external_access_windows "
                    "WHERE scope = :scope AND started_at >= :day_start "
                    "AND started_at < :day_end"
                ),
                {"scope": scope, "day_start": day_start, "day_end": day_end},
            ).scalar_one()
        )
        decision = evaluate_access(
            policy=policy,
            now=current,
            last_started_at=last_started_at,
            windows_today=windows_today,
        )
        if not decision.granted:
            return decision
        window_id = int(
            connection.execute(
                text(
                    "INSERT INTO external_access_windows "
                    "(scope, consumer, slate_date, started_at) "
                    "VALUES (:scope, :consumer, :slate_date, :started_at) "
                    "RETURNING id"
                ),
                {
                    "scope": scope,
                    "consumer": consumer,
                    "slate_date": slate_date,
                    "started_at": current,
                },
            ).scalar_one()
        )
    return AccessGrant(
        True,
        "granted",
        window_id=window_id,
        windows_today=windows_today + 1,
    )


def finish_access_window(
    engine: Engine,
    window_id: int,
    *,
    outcome: str,
    completed_at: datetime | None = None,
) -> None:
    """Close a granted window without changing its already-consumed budget."""

    if not outcome.strip():
        raise ValueError("outcome must be non-empty")
    current = _require_aware(completed_at or datetime.now(UTC))
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE external_access_windows SET completed_at = :completed_at, "
                "outcome = :outcome WHERE id = :window_id"
            ),
            {
                "window_id": window_id,
                "completed_at": current,
                "outcome": outcome[:32],
            },
        )
