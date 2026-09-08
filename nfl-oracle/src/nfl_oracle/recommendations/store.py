"""NFL-owned append-only decisions on the shared transaction infrastructure."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from typing import Any

from oracle_core.storage import TransactionManager
from sqlalchemy import (
    JSON,
    Column,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    select,
    text,
)
from sqlalchemy.engine import Connection, Engine

from .schema import Slate, fingerprint, utc

metadata = MetaData()
freezes = Table(
    "nfl_recommendation_freezes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("day", String(10), nullable=False),
    Column("contest_id", Integer, nullable=False),
    Column("sequence", Integer, nullable=False),
    Column("digest", String(64), nullable=False, unique=True),
    Column("payload", JSON, nullable=False),
    UniqueConstraint("day", "sequence"),
)
runs = Table(
    "nfl_recommendation_runs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("day", String(10), nullable=False),
    Column("payload", JSON, nullable=False),
)
artifacts = Table(
    "nfl_recommendation_artifacts",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("sha256", String(64), nullable=False, unique=True),
    Column("kind", String(120), nullable=False),
    Column("payload", JSON, nullable=False),
    Column("created_at", String(32), nullable=False),
)


def migrate(engine: Engine) -> None:
    """Explicit migration, never invoked by a reader or ordinary writer startup."""
    metadata.create_all(engine)
    with engine.begin() as conn:
        for table in (freezes, runs, artifacts):
            name = table.name
            if engine.dialect.name == "sqlite":
                for action in ("UPDATE", "DELETE"):
                    conn.execute(
                        text(
                            f"CREATE TRIGGER IF NOT EXISTS {name}_{action.lower()} "
                            f"BEFORE {action} ON {name} BEGIN "
                            "SELECT RAISE(ABORT, 'append_only'); END"
                        )
                    )
            elif engine.dialect.name == "postgresql":
                conn.execute(
                    text("""
                    CREATE OR REPLACE FUNCTION nfl_recommendation_append_only()
                    RETURNS trigger LANGUAGE plpgsql AS $$
                    BEGIN RAISE EXCEPTION 'append_only'; END $$
                """)
                )
                conn.execute(text(f"DROP TRIGGER IF EXISTS append_only ON {name}"))
                conn.execute(
                    text(
                        f"CREATE TRIGGER append_only BEFORE UPDATE OR DELETE ON {name} "
                        "FOR EACH ROW EXECUTE FUNCTION nfl_recommendation_append_only()"
                    )
                )


class RecommendationStore:
    def __init__(
        self,
        engine: Engine,
        *,
        writable: bool = False,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.engine = engine
        self.transactions = TransactionManager(engine)
        self.writable = writable
        self.clock = clock

    def _writer(self) -> None:
        if not self.writable:
            raise PermissionError("reader_cannot_write")

    def _now(self, conn: Connection) -> datetime:
        if self.engine.dialect.name == "postgresql":
            return utc(conn.execute(text("SELECT clock_timestamp()")).scalar_one())
        return utc(self.clock())

    def freeze(
        self,
        slate: Slate,
        lineup: dict[str, Any],
        *,
        model_fingerprint: str,
        input_fingerprint: str,
        decision_at: datetime,
    ) -> dict[str, Any]:
        self._writer()
        decision_at = utc(decision_at)
        slate.assert_prelock(decision_at)
        picks = lineup.get("picks")
        if not isinstance(picks, list) or len(picks) != 5:
            raise ValueError("five_picks_required")
        if any(not isinstance(pick, dict) for pick in picks):
            raise ValueError("invalid_pick")
        candidates = {p.player_id: p for p in slate.candidates}
        ids = [p.get("player_id") for p in picks]
        if (
            any(type(player_id) is not int or player_id <= 0 for player_id in ids)
            or len(set(ids)) != 5
            or any(player_id not in candidates for player_id in ids)
        ):
            raise ValueError("invalid_pick_identity")
        if not model_fingerprint or not input_fingerprint:
            raise ValueError("fingerprints_required")
        # JSON copy prevents caller mutation after validation.
        public_lineup = json.loads(json.dumps(lineup, allow_nan=False))
        if public_lineup.get("contest_entry") is True:
            raise ValueError("contest_entry_forbidden")
        public_lineup["contest_entry"] = False
        for slot, pick in enumerate(public_lineup["picks"], 1):
            candidate = candidates[pick["player_id"]]
            pick.update(
                slot=slot,
                name=candidate.name,
                position=candidate.position,
                team=candidate.team,
                opponent=candidate.opponent,
                team_id=candidate.team_id,
                game_id=candidate.game_id,
                card_boost=candidate.card_boost,
                slot_multiplier=slate.contest.slot_multipliers[slot - 1],
            )
        day = slate.contest.day.isoformat()
        request = {
            "slate": slate.model_dump(mode="json"),
            "lineup": public_lineup,
            "model_fingerprint": model_fingerprint,
            "input_fingerprint": input_fingerprint,
            "decision_at": decision_at.isoformat(),
        }
        request_hash = fingerprint(request)
        with self.transactions.transaction() as conn:
            if self.engine.dialect.name == "postgresql":
                conn.execute(
                    text("SELECT pg_advisory_xact_lock(:key)"), {"key": int(day.replace("-", ""))}
                )
            elif self.engine.dialect.name == "sqlite":
                conn.execute(text("BEGIN IMMEDIATE"))
            previous = conn.execute(
                select(freezes.c.payload)
                .where(freezes.c.day == day)
                .order_by(freezes.c.sequence.desc())
                .limit(1)
            ).scalar_one_or_none()
            now = self._now(conn)
            if previous is not None:
                self._verify(previous)
                if previous["request_hash"] == request_hash:
                    return dict(previous)
                if now >= datetime.fromisoformat(previous["cutoff_at"]):
                    raise ValueError("slate_locked")
            if decision_at > now:
                raise ValueError("future_decision")
            slate.assert_prelock(now)
            record = {
                **request,
                "schema_version": 1,
                "slate_date": day,
                "contest_id": slate.contest.contest_id,
                "sequence": 1 if previous is None else previous["sequence"] + 1,
                "previous_digest": None if previous is None else previous["digest"],
                "request_hash": request_hash,
                "frozen_at": now.isoformat(),
                "cutoff_at": slate.cutoff().isoformat(),
                "contest_entry": False,
            }
            record["digest"] = fingerprint(record)
            # Recheck server clock after serialization, immediately before the insert.
            if self._now(conn) >= slate.cutoff():
                raise ValueError("slate_locked")
            conn.execute(
                freezes.insert().values(
                    day=day,
                    contest_id=slate.contest.contest_id,
                    sequence=record["sequence"],
                    digest=record["digest"],
                    payload=record,
                )
            )
            return record

    @staticmethod
    def _verify(record: dict[str, Any]) -> None:
        body = {k: v for k, v in record.items() if k != "digest"}
        if fingerprint(body) != record.get("digest"):
            raise ValueError("frozen_record_integrity_failure")

    def latest(self, day: date) -> dict[str, Any] | None:
        records = self.history(day, limit=1)
        return records[0] if records else None

    def history(self, day: date | None = None, *, limit: int = 50) -> list[dict[str, Any]]:
        if not 1 <= limit <= 500:
            raise ValueError("invalid_history_limit")
        query = select(freezes.c.payload).order_by(freezes.c.id.desc()).limit(limit)
        if day is not None:
            query = query.where(freezes.c.day == day.isoformat())
        with self.engine.connect() as conn:
            records = [dict(value) for value in conn.execute(query).scalars()]
        for record in records:
            self._verify(record)
        return records

    def export_records(self) -> dict[str, Any]:
        with self.engine.connect() as conn:
            records = [
                dict(v)
                for v in conn.execute(select(freezes.c.payload).order_by(freezes.c.id)).scalars()
            ]
        previous: dict[str, str] = {}
        for record in records:
            self._verify(record)
            day = record["slate_date"]
            if record["previous_digest"] != previous.get(day):
                raise ValueError("frozen_history_chain_failure")
            previous[day] = record["digest"]
        return {"schema_version": 1, "records": records, "digest": fingerprint(records)}

    def export_backup(self) -> dict[str, Any]:
        """Export freezes, run status, and worker artifacts as one checked bundle."""
        freeze_export = self.export_records()
        with self.engine.connect() as conn:
            run_rows = [
                {"day": row.day, "payload": row.payload}
                for row in conn.execute(select(runs.c.day, runs.c.payload).order_by(runs.c.id))
            ]
            artifact_rows = [
                {
                    "sha256": row.sha256,
                    "kind": row.kind,
                    "payload": row.payload,
                    "created_at": row.created_at,
                }
                for row in conn.execute(
                    select(
                        artifacts.c.sha256,
                        artifacts.c.kind,
                        artifacts.c.payload,
                        artifacts.c.created_at,
                    ).order_by(artifacts.c.id)
                )
            ]
        body = {
            "schema_version": 1,
            "freezes": freeze_export["records"],
            "runs": run_rows,
            "artifacts": artifact_rows,
        }
        return {**body, "digest": fingerprint(body)}

    def restore_backup(self, backup: Mapping[str, Any]) -> None:
        """Restore a complete export into an empty writable database."""
        self._writer()
        if set(backup) != {"schema_version", "freezes", "runs", "artifacts", "digest"}:
            raise ValueError("invalid_backup_record")
        if backup.get("schema_version") != 1:
            raise ValueError("unsupported_backup_schema")
        body = {key: backup.get(key) for key in ("schema_version", "freezes", "runs", "artifacts")}
        if backup.get("digest") != fingerprint(body):
            raise ValueError("backup_integrity_failure")
        freezes_rows = self._freeze_rows(backup.get("freezes"))
        runs_data = backup.get("runs")
        artifacts_data = backup.get("artifacts")
        if not isinstance(runs_data, list) or not isinstance(artifacts_data, list):
            raise ValueError("invalid_backup_record")
        run_rows: list[dict[str, Any]] = []
        for row in runs_data:
            if not isinstance(row, dict) or not isinstance(row.get("day"), str):
                raise ValueError("invalid_backup_record")
            if not isinstance(row.get("payload"), dict):
                raise ValueError("invalid_backup_record")
            run_rows.append({"day": row["day"], "payload": row["payload"]})
        artifact_rows: list[dict[str, Any]] = []
        for row in artifacts_data:
            if not isinstance(row, dict) or not isinstance(row.get("sha256"), str):
                raise ValueError("invalid_backup_record")
            payload = row.get("payload")
            if row.get("sha256") != fingerprint(payload):
                raise ValueError("artifact_integrity_failure")
            if not isinstance(row.get("kind"), str) or not isinstance(row.get("created_at"), str):
                raise ValueError("invalid_backup_record")
            artifact_rows.append(
                {
                    "sha256": row["sha256"],
                    "kind": row["kind"],
                    "payload": payload,
                    "created_at": row["created_at"],
                }
            )
        with self.transactions.transaction() as conn:
            if any(
                conn.execute(select(table.c.id).limit(1)).first() is not None
                for table in (freezes, runs, artifacts)
            ):
                raise ValueError("restore_requires_empty")
            if freezes_rows:
                conn.execute(freezes.insert(), freezes_rows)
            if run_rows:
                conn.execute(runs.insert(), run_rows)
            if artifact_rows:
                conn.execute(artifacts.insert(), artifact_rows)

    @staticmethod
    def _freeze_rows(records: Any) -> list[dict[str, Any]]:
        if not isinstance(records, list):
            raise ValueError("invalid_backup_record")
        previous: dict[str, str | None] = {}
        rows: list[dict[str, Any]] = []
        for record in records:
            if not isinstance(record, dict):
                raise ValueError("invalid_backup_record")
            RecommendationStore._verify(record)
            day = record.get("slate_date")
            sequence = record.get("sequence")
            if not isinstance(day, str) or not isinstance(sequence, int) or sequence < 1:
                raise ValueError("invalid_backup_record")
            if record.get("previous_digest") != previous.get(day):
                raise ValueError("frozen_history_chain_failure")
            if sequence != sum(1 for row in rows if row["day"] == day) + 1:
                raise ValueError("frozen_history_sequence_failure")
            previous[day] = record.get("digest")
            rows.append(
                {
                    "day": day,
                    "contest_id": record.get("contest_id"),
                    "sequence": sequence,
                    "digest": record.get("digest"),
                    "payload": record,
                }
            )
        return rows

    def restore_records(self, backup: Mapping[str, Any]) -> None:
        """Restore a validated freeze export into an empty writable database.

        Restore is intentionally explicit and never runs during reader startup. The
        export digest and every per-day hash chain are checked before any insert.
        """
        self._writer()
        if backup.get("schema_version") != 1:
            raise ValueError("unsupported_backup_schema")
        records = backup.get("records")
        if not isinstance(records, list) or backup.get("digest") != fingerprint(records):
            raise ValueError("backup_integrity_failure")
        rows = self._freeze_rows(records)
        with self.transactions.transaction() as conn:
            if conn.execute(select(freezes.c.id).limit(1)).first() is not None:
                raise ValueError("restore_requires_empty")
            if rows:
                conn.execute(freezes.insert(), rows)

    def record_run(
        self,
        day: date,
        *,
        status: str,
        detail_code: str,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        self._writer()
        if status not in {"no_slate", "blocked", "ready", "waiting", "locked", "error"}:
            raise ValueError("invalid_run_status")
        if not detail_code or any(
            c not in "abcdefghijklmnopqrstuvwxyz_0123456789" for c in detail_code
        ):
            raise ValueError("unsafe_detail_code")
        try:
            safe_details = json.loads(json.dumps(dict(details or {}), allow_nan=False))
        except (TypeError, ValueError):
            raise ValueError("invalid_run_details") from None
        with self.transactions.transaction() as conn:
            conn.execute(
                runs.insert().values(
                    day=day.isoformat(),
                    payload={
                        "status": status,
                        "detail_code": detail_code,
                        "checked_at": self._now(conn).isoformat(),
                        "details": safe_details,
                    },
                )
            )

    def put_artifact(self, kind: str, payload: Any) -> str:
        """Persist a content-addressed worker artifact exactly once."""
        self._writer()
        if (
            not kind
            or len(kind) > 120
            or any(
                c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.:-"
                for c in kind
            )
        ):
            raise ValueError("unsafe_artifact_kind")
        sha256 = fingerprint(payload)
        with self.transactions.transaction() as conn:
            if self.engine.dialect.name == "postgresql":
                conn.execute(
                    text("SELECT pg_advisory_xact_lock(:key)"),
                    {"key": int(sha256[:16], 16) % (2**63 - 1)},
                )
            elif self.engine.dialect.name == "sqlite":
                conn.execute(text("BEGIN IMMEDIATE"))
            existing = conn.execute(
                select(artifacts.c.kind, artifacts.c.payload).where(artifacts.c.sha256 == sha256)
            ).first()
            if existing is not None:
                if existing.kind != kind or fingerprint(existing.payload) != sha256:
                    raise ValueError("artifact_integrity_failure")
                return sha256
            conn.execute(
                artifacts.insert().values(
                    sha256=sha256,
                    kind=kind,
                    payload=json.loads(json.dumps(payload, allow_nan=False)),
                    created_at=self._now(conn).isoformat(),
                )
            )
        return sha256

    def get_artifact(self, sha256: str) -> dict[str, Any] | None:
        if len(sha256) != 64:
            raise ValueError("invalid_artifact_sha256")
        with self.engine.connect() as conn:
            row = conn.execute(
                select(
                    artifacts.c.sha256,
                    artifacts.c.kind,
                    artifacts.c.payload,
                    artifacts.c.created_at,
                ).where(artifacts.c.sha256 == sha256)
            ).first()
        if row is None:
            return None
        if fingerprint(row.payload) != row.sha256:
            raise ValueError("artifact_integrity_failure")
        return {
            "sha256": row.sha256,
            "kind": row.kind,
            "payload": row.payload,
            "created_at": row.created_at,
        }

    def latest_artifact(self, kind: str) -> dict[str, Any] | None:
        if not kind:
            raise ValueError("artifact_kind_required")
        with self.engine.connect() as conn:
            row = conn.execute(
                select(
                    artifacts.c.sha256,
                    artifacts.c.kind,
                    artifacts.c.payload,
                    artifacts.c.created_at,
                )
                .where(artifacts.c.kind == kind)
                .order_by(artifacts.c.id.desc())
                .limit(1)
            ).first()
        if row is None:
            return None
        if fingerprint(row.payload) != row.sha256:
            raise ValueError("artifact_integrity_failure")
        return {
            "sha256": row.sha256,
            "kind": row.kind,
            "payload": row.payload,
            "created_at": row.created_at,
        }

    def latest_run(self, day: date) -> dict[str, Any] | None:
        with self.engine.connect() as conn:
            result = conn.execute(
                select(runs.c.payload)
                .where(runs.c.day == day.isoformat())
                .order_by(runs.c.id.desc())
                .limit(1)
            ).scalar_one_or_none()
        return dict(result) if result is not None else None

    def healthy(self) -> bool:
        with self.engine.connect() as conn:
            conn.execute(select(freezes.c.id).limit(1))
            conn.execute(select(runs.c.id).limit(1))
            conn.execute(select(artifacts.c.id).limit(1))
        return True
