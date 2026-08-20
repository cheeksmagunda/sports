"""Generic job registration, lifecycle, role validation, and execution."""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum, StrEnum
from typing import Any, Protocol
from uuid import uuid4

from oracle_core.logging import StructuredLogger, get_logger
from oracle_core.storage import Lease, LeaseStore

Clock = Callable[[], datetime]
JobHandler = Callable[["JobContext"], "JobResult | None"]
_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


class JobExitCode(IntEnum):
    """Stable process exit codes for generic job outcomes."""

    SUCCESS = 0
    FAILURE = 1
    DEGRADED = 2
    USAGE = 64
    RETRYABLE = 75


class JobStatus(StrEnum):
    SUCCESS = "success"
    SKIPPED = "skipped"
    DEGRADED = "degraded"
    RETRYABLE_FAILURE = "retryable_failure"
    FAILED = "failed"


@dataclass(frozen=True)
class JobResult:
    """A structured job outcome with deterministic process semantics."""

    status: JobStatus = JobStatus.SUCCESS
    message: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)

    @property
    def exit_code(self) -> int:
        return int(
            {
                JobStatus.SUCCESS: JobExitCode.SUCCESS,
                JobStatus.SKIPPED: JobExitCode.SUCCESS,
                JobStatus.DEGRADED: JobExitCode.DEGRADED,
                JobStatus.RETRYABLE_FAILURE: JobExitCode.RETRYABLE,
                JobStatus.FAILED: JobExitCode.FAILURE,
            }[self.status]
        )

    @classmethod
    def success(cls, message: str = "", **details: Any) -> JobResult:
        return cls(JobStatus.SUCCESS, message, details)

    @classmethod
    def skipped(cls, message: str = "", **details: Any) -> JobResult:
        return cls(JobStatus.SKIPPED, message, details)

    @classmethod
    def degraded(cls, message: str = "", **details: Any) -> JobResult:
        return cls(JobStatus.DEGRADED, message, details)

    @classmethod
    def retryable_failure(cls, message: str = "", **details: Any) -> JobResult:
        return cls(JobStatus.RETRYABLE_FAILURE, message, details)

    @classmethod
    def failed(cls, message: str = "", **details: Any) -> JobResult:
        return cls(JobStatus.FAILED, message, details)


@dataclass(frozen=True)
class JobSpec:
    """Technical registration data for one application-owned job."""

    name: str
    handler: JobHandler
    roles: frozenset[str] = field(default_factory=frozenset)
    lease_key: str | None = None
    lease_ttl_seconds: int = 300
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not _NAME_PATTERN.fullmatch(self.name):
            raise ValueError("Job name must use lowercase letters, digits, underscores, or hyphens")
        if self.lease_key is not None and self.lease_ttl_seconds <= 0:
            raise ValueError("lease_ttl_seconds must be positive")
        invalid_roles = [role for role in self.roles if not role.strip()]
        if invalid_roles:
            raise ValueError("Job roles cannot be empty")


JobDefinition = JobSpec


@dataclass(frozen=True)
class JobContext:
    """Per-run technical context passed to an application job handler."""

    job_name: str
    role: str
    run_id: str
    started_at: datetime
    clock: Clock
    logger: StructuredLogger
    metadata: Mapping[str, Any] = field(default_factory=dict)
    lease: Lease | None = None

    def now(self) -> datetime:
        """Read the injected clock."""

        return self.clock()


class JobLifecycleHook(Protocol):
    """Observer capability for generic job lifecycle events."""

    def on_start(self, context: JobContext) -> None: ...

    def on_complete(self, context: JobContext, result: JobResult) -> None: ...

    def on_error(self, context: JobContext, error: BaseException) -> None: ...


class RoleMismatchError(ValueError):
    """Raised when a process role cannot execute a registered job."""

    def __init__(self, job_name: str, role: str, allowed: frozenset[str]) -> None:
        self.job_name = job_name
        self.role = role
        self.allowed = allowed
        allowed_names = ", ".join(sorted(allowed))
        super().__init__(
            f"Role {role!r} cannot run job {job_name!r}; allowed roles: {allowed_names}"
        )


def validate_role(spec: JobSpec, role: str) -> None:
    """Validate an application-selected role against a job registration."""

    if spec.roles and role not in spec.roles:
        raise RoleMismatchError(spec.name, role, spec.roles)


class JobRegistry:
    """Deterministic registry that rejects duplicate job names."""

    def __init__(self, specs: Sequence[JobSpec] = ()) -> None:
        self._specs: dict[str, JobSpec] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: JobSpec) -> JobSpec:
        if spec.name in self._specs:
            raise ValueError(f"Job {spec.name!r} is already registered")
        self._specs[spec.name] = spec
        return spec

    def get(self, name: str) -> JobSpec:
        try:
            return self._specs[name]
        except KeyError as error:
            raise KeyError(f"Unknown job {name!r}") from error

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._specs))

    def __contains__(self, name: object) -> bool:
        return name in self._specs


def utc_now() -> datetime:
    return datetime.now(UTC)


class JobRunner:
    """Run registered jobs with structured events and optional distributed leases."""

    def __init__(
        self,
        registry: JobRegistry,
        *,
        lease_store: LeaseStore | None = None,
        clock: Clock = utc_now,
        logger: StructuredLogger | None = None,
        hooks: Sequence[JobLifecycleHook] = (),
    ) -> None:
        self.registry = registry
        self.lease_store = lease_store
        self.clock = clock
        self.logger = logger or get_logger("oracle_core.jobs")
        self.hooks = tuple(hooks)

    def run(
        self,
        job_name: str,
        *,
        role: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> JobResult:
        spec = self.registry.get(job_name)
        validate_role(spec, role)
        lease = self._acquire_lease(spec)
        context = self._context(spec, role, lease, metadata)
        self._emit_start(context)
        if spec.lease_key is not None and lease is None:
            result = JobResult.skipped(
                "distributed lease is already held", lease_key=spec.lease_key
            )
            self._emit_complete(context, result)
            return result

        try:
            result = spec.handler(context) or JobResult.success()
            if not isinstance(result, JobResult):
                raise TypeError("Job handlers must return JobResult or None")
        except Exception as error:
            self._emit_error(context, error)
            result = JobResult.failed("job raised an exception", error_type=type(error).__name__)
        finally:
            if lease is not None and self.lease_store is not None:
                try:
                    released = self.lease_store.release(lease)
                except Exception:
                    released = False
                    self.logger.exception(
                        "job_lease_release_failed",
                        job=job_name,
                        run_id=context.run_id,
                        lease_key=lease.key,
                    )
                if not released:
                    self.logger.warning(
                        "job_lease_release_missed",
                        job=job_name,
                        run_id=context.run_id,
                        lease_key=lease.key,
                    )

        self._emit_complete(context, result)
        return result

    def run_exit_code(self, job_name: str, *, role: str) -> int:
        """Run a job and return its stable process exit code."""

        try:
            return self.run(job_name, role=role).exit_code
        except (KeyError, RoleMismatchError, ValueError):
            return int(JobExitCode.USAGE)

    def _acquire_lease(self, spec: JobSpec) -> Lease | None:
        if spec.lease_key is None:
            return None
        if self.lease_store is None:
            raise RuntimeError(f"Job {spec.name!r} requires a lease store")
        return self.lease_store.acquire(spec.lease_key, ttl_seconds=spec.lease_ttl_seconds)

    def _context(
        self,
        spec: JobSpec,
        role: str,
        lease: Lease | None,
        metadata: Mapping[str, Any] | None,
    ) -> JobContext:
        started_at = self.clock()
        run_id = uuid4().hex
        merged = {**spec.metadata, **dict(metadata or {})}
        logger = self.logger.bind(job=spec.name, role=role, run_id=run_id)
        return JobContext(
            job_name=spec.name,
            role=role,
            run_id=run_id,
            started_at=started_at,
            clock=self.clock,
            logger=logger,
            metadata=merged,
            lease=lease,
        )

    def _emit_start(self, context: JobContext) -> None:
        context.logger.info("job_started", started_at=context.started_at.isoformat())
        for hook in self.hooks:
            hook.on_start(context)

    def _emit_complete(self, context: JobContext, result: JobResult) -> None:
        duration = max(0.0, (self.clock() - context.started_at).total_seconds())
        context.logger.info(
            "job_completed",
            status=result.status.value,
            exit_code=result.exit_code,
            duration_seconds=duration,
            result_details=result.details,
        )
        for hook in self.hooks:
            hook.on_complete(context, result)

    def _emit_error(self, context: JobContext, error: BaseException) -> None:
        context.logger.exception("job_failed", error_type=type(error).__name__)
        for hook in self.hooks:
            hook.on_error(context, error)
