"""Exercise NFL recommendation storage against a temporary local PostgreSQL."""

from __future__ import annotations

import argparse
import subprocess
import time
from datetime import UTC, datetime

from oracle_core.storage import create_postgres_engine
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from nfl_oracle.recommendations.store import RecommendationStore, migrate


def command(*args: str) -> str:
    return subprocess.run(args, check=True, text=True, capture_output=True).stdout.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", default="postgres:16-alpine")
    args = parser.parse_args()
    if subprocess.run(["docker", "version"], capture_output=True).returncode != 0:
        print("docker unavailable; PostgreSQL store smoke skipped")
        return 0

    name = f"nfl-postgres-smoke-{int(time.time())}"
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-d",
            "--name",
            name,
            "-e",
            "POSTGRES_PASSWORD=postgres",
            "-e",
            "POSTGRES_DB=nfl",
            "-p",
            "127.0.0.1::5432",
            args.image,
        ],
        check=True,
        text=True,
        capture_output=True,
    ).stdout.strip()
    try:
        published = command("docker", "port", name, "5432/tcp")
        port = published.rsplit(":", 1)[-1]
        url = f"postgresql://postgres:postgres@127.0.0.1:{port}/nfl"
        engine = create_postgres_engine(url)
        for _ in range(30):
            try:
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                break
            except Exception:
                time.sleep(1)
        else:
            raise RuntimeError("temporary PostgreSQL did not become ready")

        migrate(engine)
        store = RecommendationStore(engine, writable=True)
        store.record_run(
            datetime.now(UTC).date(),
            status="waiting",
            detail_code="postgres_smoke",
        )
        sha = store.put_artifact("smoke", {"source": "postgres_store_smoke", "version": 1})
        backup = store.export_backup()
        assert store.get_artifact(sha) is not None
        try:
            with engine.begin() as conn:
                conn.execute(text("DELETE FROM nfl_recommendation_artifacts"))
        except DBAPIError:
            pass
        else:
            raise AssertionError("append-only artifact trigger did not reject DELETE")

        with engine.begin() as conn:
            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))
        migrate(engine)
        restored = RecommendationStore(engine, writable=True)
        restored.restore_backup(backup)
        assert restored.export_backup() == backup
        print("NFL PostgreSQL store smoke OK")
        return 0
    finally:
        subprocess.run(["docker", "rm", "-f", name], check=False, capture_output=True)


if __name__ == "__main__":
    raise SystemExit(main())
