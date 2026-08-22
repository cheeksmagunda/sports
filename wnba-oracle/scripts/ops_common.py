"""Portable, fail-closed helpers for WNBA production checks.

The helpers use only the Python standard library and HTTPS. They deliberately
bound Railway log reads and require evidence for one declared role, slate, and
run window. Secrets come only from the process environment and are never put
in reports or exception text.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import pathlib
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Iterable, Mapping
from typing import Any

RAILWAY_GRAPHQL_URL = "https://backboard.railway.com/graphql/v2"
MAX_DEPLOYMENT_LIMIT = 5
MAX_LOG_LIMIT = 200
SUCCESSFUL_DEPLOYMENT_STATUSES = frozenset({"SUCCESS", "COMPLETED"})


class SafeRequestError(RuntimeError):
    """A network failure whose message is safe to publish in an issue."""


@dataclasses.dataclass(frozen=True)
class Check:
    name: str
    status: str
    summary: str

    def __post_init__(self) -> None:
        if self.status not in {"ok", "warn", "alert"}:
            raise ValueError(f"invalid check status: {self.status}")


@dataclasses.dataclass(frozen=True)
class RunWindow:
    """The exact expected execution interval for one cron role and slate."""

    role: str
    slate_date: str
    started_at: dt.datetime
    ended_at: dt.datetime

    def __post_init__(self) -> None:
        if not self.role.strip():
            raise ValueError("run role is required")
        try:
            dt.date.fromisoformat(self.slate_date)
        except ValueError as exc:
            raise ValueError("slate_date must be an ISO date") from exc
        if self.started_at.tzinfo is None or self.ended_at.tzinfo is None:
            raise ValueError("run window timestamps must include a timezone")
        if self.ended_at <= self.started_at:
            raise ValueError("run window must end after it starts")

    @classmethod
    def from_strings(
        cls, *, role: str, slate_date: str, started_at: str, ended_at: str
    ) -> RunWindow:
        start = parse_timestamp(started_at)
        end = parse_timestamp(ended_at)
        if start is None or end is None:
            raise ValueError("run window timestamps must be ISO-8601 values with a timezone")
        return cls(role=role, slate_date=slate_date, started_at=start, ended_at=end)

    def contains(self, value: dt.datetime | None) -> bool:
        if value is None:
            return False
        return self.started_at <= value <= self.ended_at

    def describe(self) -> str:
        start = self.started_at.astimezone(dt.UTC).replace(microsecond=0).isoformat()
        end = self.ended_at.astimezone(dt.UTC).replace(microsecond=0).isoformat()
        return f"{self.role} for {self.slate_date} from {start} to {end}"


@dataclasses.dataclass(frozen=True)
class RepairPolicy:
    """Bounded retry and observation policy for an explicit operator repair."""

    attempts: int = 2
    cooldown_seconds: float = 60.0
    postcheck_seconds: float = 20.0

    def __post_init__(self) -> None:
        if not 1 <= self.attempts <= 3:
            raise ValueError("repair attempts must be between 1 and 3")
        if not 0 <= self.cooldown_seconds <= 600:
            raise ValueError("repair cooldown must be between 0 and 600 seconds")
        if not 0 <= self.postcheck_seconds <= 300:
            raise ValueError("repair postcheck delay must be between 0 and 300 seconds")


@dataclasses.dataclass(frozen=True)
class RepairResult:
    attempts: int
    recovered: bool
    request_failures: int


def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def parse_timestamp(value: object) -> dt.datetime | None:
    """Return a UTC timestamp or ``None`` for absent or malformed input."""

    if isinstance(value, dt.datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        try:
            parsed = dt.datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(dt.UTC)


def normalized_status(value: object) -> str:
    """Normalize an external deployment status without assuming it is valid."""

    if value is None:
        return "UNKNOWN"
    rendered = str(value).strip().upper()
    return rendered or "UNKNOWN"


def deployment_status_check(name: str, deployments: Iterable[Mapping[str, Any]]) -> Check:
    """Only explicit terminal success is healthy; missing and unknown fail closed."""

    latest = next(iter(deployments), None)
    if latest is None:
        return Check(
            name, "alert", "No Railway deployment was returned for the requested run window."
        )
    status = normalized_status(latest.get("status"))
    if status in SUCCESSFUL_DEPLOYMENT_STATUSES:
        return Check(name, "ok", f"Railway deployment status is {status}.")
    return Check(name, "alert", f"Railway deployment status is {status}, not a terminal success.")


def get_json(url: str, *, timeout: float = 20.0) -> tuple[int, Any]:
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": "wnba-oracle-ops/2"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            raw = response.read()
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
        raw = exc.read()
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        raise SafeRequestError(f"HTTPS request failed ({type(exc).__name__})") from exc

    if not raw:
        return status, None
    try:
        return status, json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SafeRequestError(f"HTTPS response was not valid JSON (status {status})") from exc


def post_heartbeat(url: str, *, timeout: float = 10.0) -> None:
    """Post a positive monitor heartbeat without exposing the target URL."""

    request = urllib.request.Request(
        url,
        data=b"",
        method="POST",
        headers={"User-Agent": "wnba-oracle-ops/2", "Content-Length": "0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = int(response.status)
            response.read()
    except urllib.error.HTTPError as exc:
        exc.read()
        raise SafeRequestError(f"Heartbeat endpoint returned HTTP {exc.code}") from exc
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        raise SafeRequestError(f"Heartbeat request failed ({type(exc).__name__})") from exc
    if not 200 <= status < 300:
        raise SafeRequestError(f"Heartbeat endpoint returned HTTP {status}")


class RailwayClient:
    """Small Railway GraphQL client with value-safe, bounded queries."""

    def __init__(self, token: str, *, timeout: float = 25.0) -> None:
        if not token.strip():
            raise ValueError("RAILWAY_WORKSPACE_TOKEN is missing")
        self._token = token
        self._timeout = timeout

    def execute(self, query: str, variables: Mapping[str, Any]) -> dict[str, Any]:
        payload = json.dumps({"query": query, "variables": dict(variables)}).encode()
        request = urllib.request.Request(
            RAILWAY_GRAPHQL_URL,
            data=payload,
            method="POST",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}",
                "Content-Type": "application/json",
                "User-Agent": "wnba-oracle-ops/2",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout) as response:
                raw = response.read()
                status = int(response.status)
        except urllib.error.HTTPError as exc:
            exc.read()
            raise SafeRequestError(f"Railway API returned HTTP {exc.code}") from exc
        except (OSError, urllib.error.URLError, TimeoutError) as exc:
            raise SafeRequestError(f"Railway API request failed ({type(exc).__name__})") from exc
        if status != 200:
            raise SafeRequestError(f"Railway API returned HTTP {status}")
        try:
            decoded = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SafeRequestError("Railway API returned invalid JSON") from exc
        if not isinstance(decoded, dict) or decoded.get("errors"):
            raise SafeRequestError("Railway API returned GraphQL errors")
        data = decoded.get("data")
        if not isinstance(data, dict):
            raise SafeRequestError("Railway API response omitted data")
        return data

    def variables(self, project_id: str, environment_id: str, service_id: str) -> dict[str, str]:
        data = self.execute(
            """
            query variables($projectId: String!, $environmentId: String!, $serviceId: String) {
              variables(projectId: $projectId, environmentId: $environmentId, serviceId: $serviceId)
            }
            """,
            {
                "projectId": project_id,
                "environmentId": environment_id,
                "serviceId": service_id,
            },
        )
        values = data.get("variables")
        if not isinstance(values, dict):
            raise SafeRequestError("Railway variables response had an unexpected shape")
        return {str(key): str(value) for key, value in values.items()}

    def deployments(
        self, project_id: str, service_id: str, *, limit: int = MAX_DEPLOYMENT_LIMIT
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= MAX_DEPLOYMENT_LIMIT:
            raise ValueError(f"deployment limit must be between 1 and {MAX_DEPLOYMENT_LIMIT}")
        data = self.execute(
            """
            query deployments($input: DeploymentListInput!, $first: Int!) {
              deployments(input: $input, first: $first) {
                edges { node { id status createdAt } }
              }
            }
            """,
            {
                "input": {"projectId": project_id, "serviceId": service_id},
                "first": limit,
            },
        )
        connection = data.get("deployments")
        if not isinstance(connection, dict):
            raise SafeRequestError("Railway deployments response had an unexpected shape")
        edges = connection.get("edges")
        if not isinstance(edges, list):
            raise SafeRequestError("Railway deployments response omitted edges")
        return [
            edge["node"]
            for edge in edges
            if isinstance(edge, dict) and isinstance(edge.get("node"), dict)
        ]

    def deployment_logs(
        self, deployment_id: str, *, limit: int = MAX_LOG_LIMIT
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= MAX_LOG_LIMIT:
            raise ValueError(f"log limit must be between 1 and {MAX_LOG_LIMIT}")
        data = self.execute(
            """
            query deploymentLogs($deploymentId: String!, $limit: Int) {
              deploymentLogs(deploymentId: $deploymentId, limit: $limit) {
                timestamp
                message
                severity
              }
            }
            """,
            {"deploymentId": deployment_id, "limit": limit},
        )
        logs = data.get("deploymentLogs")
        if not isinstance(logs, list):
            raise SafeRequestError("Railway logs response had an unexpected shape")
        return [item for item in logs if isinstance(item, dict)]

    def evidence_for_window(
        self,
        project_id: str,
        service_id: str,
        window: RunWindow,
        *,
        deployment_limit: int = MAX_DEPLOYMENT_LIMIT,
        log_limit: int = MAX_LOG_LIMIT,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Return only deployments and logs attributable to one declared run."""

        deployments = self.deployments(project_id, service_id, limit=deployment_limit)
        matched = [
            deployment
            for deployment in deployments
            if window.contains(parse_timestamp(deployment.get("createdAt")))
        ]
        if not matched:
            return [], []
        selected = max(
            matched,
            key=lambda item: (
                parse_timestamp(item.get("createdAt")) or dt.datetime.min.replace(tzinfo=dt.UTC)
            ),
        )
        deployment_id = selected.get("id")
        if not isinstance(deployment_id, str) or not deployment_id:
            return [selected], []
        logs = self.deployment_logs(deployment_id, limit=log_limit)
        return [selected], [
            item for item in logs if window.contains(parse_timestamp(item.get("timestamp")))
        ]

    def deploy_service(self, service_id: str, environment_id: str) -> str:
        data = self.execute(
            """
            mutation serviceInstanceDeployV2($serviceId: String!, $environmentId: String!) {
              serviceInstanceDeployV2(serviceId: $serviceId, environmentId: $environmentId)
            }
            """,
            {"serviceId": service_id, "environmentId": environment_id},
        )
        deployment_id = data.get("serviceInstanceDeployV2")
        return str(deployment_id or "requested")


def structured_events(
    logs: Iterable[Mapping[str, Any]], event_name: str, *, window: RunWindow | None = None
) -> list[dict[str, Any]]:
    """Decode structured log events, excluding logs outside the declared interval."""

    found: list[dict[str, Any]] = []
    for item in logs:
        if window is not None and not window.contains(parse_timestamp(item.get("timestamp"))):
            continue
        message = item.get("message")
        if not isinstance(message, str) or event_name not in message:
            continue
        try:
            payload = json.loads(message)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("event") == event_name or payload.get("message") == event_name:
            found.append(payload)
    return found


def role_evidence(logs: Iterable[Mapping[str, Any]], window: RunWindow) -> bool:
    """Verify the process self-reported the expected cron role in this run."""

    return any(
        event.get("job") == window.role and event.get("role") == window.role
        for event in structured_events(logs, "cron_dispatch", window=window)
    )


def slate_event_evidence(
    logs: Iterable[Mapping[str, Any]], *, event_name: str, window: RunWindow
) -> bool:
    """Verify a completion event explicitly names the declared slate date."""

    return any(
        str(event.get("slate_date", "")) == window.slate_date
        for event in structured_events(logs, event_name, window=window)
    )


def log_messages(logs: Iterable[Mapping[str, Any]]) -> list[str]:
    return [str(item.get("message", "")) for item in logs]


def contains_any(messages: Iterable[str], needles: Iterable[str]) -> bool:
    lowered = "\n".join(messages).lower()
    return any(needle.lower() in lowered for needle in needles)


def run_evidence_checks(
    *,
    deployment_name: str,
    completion_name: str,
    completion_event: str,
    deployments: Iterable[Mapping[str, Any]],
    logs: Iterable[Mapping[str, Any]],
    window: RunWindow,
    require_slate_event: bool = True,
) -> list[Check]:
    """Return fail-closed deployment, role, and completion evidence checks."""

    checks = [deployment_status_check(deployment_name, deployments)]
    if role_evidence(logs, window):
        checks.append(
            Check(
                f"{completion_name} role",
                "ok",
                f"Observed {window.role} in the requested run window.",
            )
        )
    else:
        checks.append(
            Check(
                f"{completion_name} role",
                "alert",
                f"No cron_dispatch event proved {window.describe()}.",
            )
        )
    if require_slate_event:
        if slate_event_evidence(logs, event_name=completion_event, window=window):
            checks.append(
                Check(
                    completion_name,
                    "ok",
                    f"Observed {completion_event} for slate {window.slate_date} in the requested run window.",
                )
            )
        else:
            checks.append(
                Check(
                    completion_name,
                    "alert",
                    f"No {completion_event} event proved slate {window.slate_date} in the requested run window.",
                )
            )
    return checks


def perform_repair(
    request_repair: Callable[[], object],
    postcheck: Callable[[], bool],
    *,
    policy: RepairPolicy,
    sleep: Callable[[float], None] = time.sleep,
) -> RepairResult:
    """Run a bounded explicit repair, with a cooldown and a health postcheck."""

    request_failures = 0
    for attempt in range(1, policy.attempts + 1):
        try:
            request_repair()
        except Exception:
            request_failures += 1
        else:
            if policy.postcheck_seconds:
                sleep(policy.postcheck_seconds)
            try:
                if postcheck():
                    return RepairResult(attempt, recovered=True, request_failures=request_failures)
            except Exception:
                pass
        if attempt < policy.attempts and policy.cooldown_seconds:
            sleep(policy.cooldown_seconds)
    return RepairResult(policy.attempts, recovered=False, request_failures=request_failures)


def summarize_status(checks: Iterable[Check]) -> str:
    statuses = {check.status for check in checks}
    if "alert" in statuses:
        return "alert"
    if "warn" in statuses:
        return "warn"
    return "ok"


def write_report(
    path: str | pathlib.Path, title: str, checks: list[Check], *, notes: list[str] | None = None
) -> None:
    generated = utc_now().replace(microsecond=0).isoformat()
    overall = summarize_status(checks)
    lines = [f"## {title}", "", f"Status: **{overall.upper()}**", f"Checked: {generated}", ""]
    lines.extend(f"- `{check.status.upper()}` {check.name}: {check.summary}" for check in checks)
    if notes:
        lines.extend(["", "Notes:"])
        lines.extend(f"- {note}" for note in notes)
    pathlib.Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_github_output(path: str | pathlib.Path | None, **values: str) -> None:
    if path is None:
        return
    with pathlib.Path(path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            if "\n" in value:
                raise ValueError(f"multiline GitHub output is not supported: {key}")
            handle.write(f"{key}={value}\n")


def safe_sha(value: str | None) -> str:
    cleaned = (value or "").strip().lower()
    return cleaned[:12] if cleaned else "unset"
