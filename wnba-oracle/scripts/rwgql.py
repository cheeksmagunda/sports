#!/usr/bin/env python3
"""Call Railway GraphQL with ambient auth and optional variables on stdin.

Railway issues two token kinds and they authenticate differently
(https://docs.railway.com/integrations/api):

- ``RAILWAY_API_TOKEN``: account or workspace token, sent as
  ``Authorization: Bearer``.
- ``RAILWAY_TOKEN``: project token scoped to one environment, sent as
  ``Project-Access-Token``.

Exactly one must be set; the Railway CLI also refuses both at once.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Mapping
from typing import Any
from urllib import error, request

ENDPOINT = "https://backboard.railway.com/graphql/v2"
# Railway's edge answers 403 text/plain to urllib's default "Python-urllib/x.y"
# User-Agent, before any auth check. An explicit product UA gets through.
USER_AGENT = "sports-oracle-rwgql/1 (+https://github.com/cheeksmagunda/sports)"
USAGE = "Usage: scripts/rwgql.sh '<graphql query>' [--variables-stdin]"
AUTH_HELP = (
    "rwgql: set exactly one of RAILWAY_API_TOKEN (account/workspace) or RAILWAY_TOKEN (project)"
)
SENSITIVE_NAME = re.compile(
    r"(?:auth|credential|key|password|secret|state|token|url)", re.IGNORECASE
)
SENSITIVE_ENV_NAMES = {
    "DATABASE_PUBLIC_URL",
    "DATABASE_URL",
    "GITHUB_TOKEN",
    "ODDS_API_KEY",
    "RAILWAY_API_TOKEN",
    "RAILWAY_TOKEN",
    "REALSPORTS_STORAGE_STATE_B64GZ",
    "REAL_SPORTS_PASSWORD",
    "REAL_SPORTS_USERNAME",
    "REDIS_URL",
    "WATCHDOG_PING_URL",
}


def collect_redactions(variables: object) -> set[str]:
    redactions = {
        value for name in SENSITIVE_ENV_NAMES if len(value := os.environ.get(name, "")) >= 4
    }

    def walk(value: object) -> None:
        if isinstance(value, dict):
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, str) and len(value) >= 4:
            redactions.add(value)

    walk(variables)
    return redactions


def redact_text(text: str, values: set[str]) -> str:
    for value in sorted(values, key=len, reverse=True):
        text = text.replace(value, "[REDACTED]")
    return text


def redact_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if SENSITIVE_NAME.search(str(key)) else redact_fields(child)
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [redact_fields(child) for child in value]
    return value


def resolve_auth(environ: Mapping[str, str]) -> dict[str, str] | None:
    """Pick the Railway auth header for whichever token kind is configured.

    Returns None when neither or both tokens are present, because a project
    token sent as Bearer (or vice versa) fails with an opaque 401 that is
    indistinguishable from a revoked token.
    """
    api_token = environ.get("RAILWAY_API_TOKEN", "").strip()
    project_token = environ.get("RAILWAY_TOKEN", "").strip()
    if bool(api_token) == bool(project_token):
        return None
    if api_token:
        return {"Authorization": f"Bearer {api_token}"}
    return {"Project-Access-Token": project_token}


def build_headers(auth: Mapping[str, str]) -> dict[str, str]:
    return {**auth, "Content-Type": "application/json", "User-Agent": USER_AGENT}


def emit_response(body: bytes, redactions: set[str]) -> bool:
    text = redact_text(body.decode("utf-8", errors="replace"), redactions)
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        print("rwgql: Railway returned a non-JSON response", file=sys.stderr)
        return False
    safe = redact_fields(payload)
    print(json.dumps(safe, separators=(",", ":")))
    return not (isinstance(payload, dict) and payload.get("errors"))


def main() -> int:
    if len(sys.argv) not in {2, 3} or (len(sys.argv) == 3 and sys.argv[2] != "--variables-stdin"):
        print(USAGE, file=sys.stderr)
        return 64
    query = sys.argv[1].strip()
    if not query:
        print("rwgql: GraphQL query is required", file=sys.stderr)
        return 64
    auth = resolve_auth(os.environ)
    if auth is None:
        print(AUTH_HELP, file=sys.stderr)
        return 78

    variables: object = {}
    if len(sys.argv) == 3:
        try:
            variables = json.load(sys.stdin)
        except json.JSONDecodeError:
            print("rwgql: variables stdin is not valid JSON", file=sys.stderr)
            return 65
        if not isinstance(variables, dict):
            print("rwgql: variables stdin must contain a JSON object", file=sys.stderr)
            return 65

    redactions = collect_redactions(variables)
    payload = json.dumps({"query": query, "variables": variables}).encode()
    req = request.Request(
        ENDPOINT,
        data=payload,
        method="POST",
        headers=build_headers(auth),
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            body = response.read()
    except error.HTTPError as exc:
        body = exc.read()
        emit_response(body, redactions)
        print(f"rwgql: Railway returned HTTP {exc.code}", file=sys.stderr)
        return 1
    except (error.URLError, TimeoutError):
        print("rwgql: Railway request failed", file=sys.stderr)
        return 1
    return 0 if emit_response(body, redactions) else 1


if __name__ == "__main__":
    raise SystemExit(main())
