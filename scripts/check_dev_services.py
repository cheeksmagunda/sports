"""Read-only, bounded probes of the explicitly configured development services."""

from __future__ import annotations

import os
from collections.abc import Mapping

from redis import Redis
from sqlalchemy import text

from oracle_core.storage import create_postgres_engine


def probe_postgres(url: str) -> None:
    engine = create_postgres_engine(
        url,
        connect_args={
            "connect_timeout": 3,
            "options": "-c statement_timeout=3000 -c default_transaction_read_only=on",
        },
    )
    try:
        with engine.connect() as connection:
            if connection.execute(text("SELECT 1")).scalar_one() != 1:
                raise RuntimeError("unexpected database probe result")
    finally:
        engine.dispose()


def probe_redis(url: str) -> None:
    with Redis.from_url(url, socket_connect_timeout=3, socket_timeout=3) as client:
        if not client.ping():
            raise RuntimeError("unexpected Redis probe result")


def main(environ: Mapping[str, str] | None = None) -> int:
    environ = os.environ if environ is None else environ
    for name, probe in (("DATABASE_URL", probe_postgres), ("REDIS_URL", probe_redis)):
        value = environ.get(name, "")
        if not value:
            print(f"{name}: missing; start the project devcontainer")
            return 1
        try:
            probe(value)
        except Exception:
            # Driver exceptions can contain passwords or connection URLs.
            print(f"{name}: unreachable; check the development service")
            return 1
        print(f"{name}: reachable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
