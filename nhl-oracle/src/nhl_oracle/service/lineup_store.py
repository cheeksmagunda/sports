"""Postgres store for T-40 lineups written by the worker and read by the API (#675).

One row per (slate day, contest id). ``preview`` rows are replaced each cycle.
A ``frozen`` row is never replaced: the upsert only fires while the stored
status is not ``frozen``.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import Any

from oracle_core.storage import PoolOptions, create_postgres_engine
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine

metadata = MetaData()

lineups = Table(
    "nhl_t40_lineups",
    metadata,
    Column("slate_day", String(10), primary_key=True),
    Column("contest_id", Integer, primary_key=True),
    Column("status", String(16), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
)


def database_url() -> str | None:
    for key in ("NHL_DATABASE_URL", "DATABASE_URL"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


def engine_from_env() -> Engine | None:
    url = database_url()
    if url is None:
        return None
    return create_postgres_engine(
        url,
        pool=PoolOptions(pool_size=2, max_overflow=1, pool_timeout=15.0, pool_recycle=900),
    )


def ensure_schema(engine: Engine) -> None:
    metadata.create_all(engine, checkfirst=True)


def save_outcome(engine: Engine, payload: dict[str, Any]) -> str:
    """Upsert unless the stored row is frozen. Returns the stored status."""

    now = datetime.now(UTC)
    row = {
        "slate_day": payload["day"],
        "contest_id": int(payload["contest_id"]),
        "status": payload["status"],
        "payload": payload,
        "updated_at": now,
    }
    statement = pg_insert(lineups).values(**row)
    statement = statement.on_conflict_do_update(
        index_elements=[lineups.c.slate_day, lineups.c.contest_id],
        set_={
            "status": statement.excluded.status,
            "payload": statement.excluded.payload,
            "updated_at": statement.excluded.updated_at,
        },
        where=lineups.c.status != "frozen",
    )
    with engine.begin() as connection:
        connection.execute(statement)
        stored = connection.execute(
            select(lineups.c.status).where(
                lineups.c.slate_day == row["slate_day"],
                lineups.c.contest_id == row["contest_id"],
            )
        ).scalar_one()
    return str(stored)


def is_frozen(engine: Engine, slate_day: str) -> bool:
    with engine.connect() as connection:
        found = connection.execute(
            select(lineups.c.status).where(
                lineups.c.slate_day == slate_day, lineups.c.status == "frozen"
            )
        ).first()
    return found is not None


def load_day(engine: Engine, slate_day: str) -> dict[str, Any] | None:
    """Frozen row first, otherwise the latest preview for that day."""

    with engine.connect() as connection:
        rows = connection.execute(
            select(lineups.c.status, lineups.c.payload, lineups.c.updated_at)
            .where(lineups.c.slate_day == slate_day)
            .order_by(lineups.c.updated_at.desc())
        ).all()
    if not rows:
        return None
    frozen = [row for row in rows if row.status == "frozen"]
    chosen = frozen[0] if frozen else rows[0]
    return dict(chosen.payload)


def load_latest(engine: Engine) -> dict[str, Any] | None:
    with engine.connect() as connection:
        row = connection.execute(
            select(lineups.c.payload).order_by(lineups.c.updated_at.desc()).limit(1)
        ).first()
    return None if row is None else dict(row.payload)
