#!/usr/bin/env python3
"""Offline research FastAPI client smoke (observation only; no contest entry).

Uses TestClient against create_app(project_root=offline fixtures) by default so
CI / box stays network-free. Optional --base-url hits a live nfl-research-serve.
Never prints secrets. Exit 0 on pass, 1 on assertion failure.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "offline_research"

GET_ROUTES = (
    "/",
    "/health",
    "/research/schemas/labels",
    "/research/schemas/strategy",
    "/research/schemas/features",
    "/research/schemas/scoring",
    "/research/features/live-ok",
    "/research/provider/status",
    "/research/gates/entry",
    "/research/catalog/seasons",
    "/research/coverage/summary",
    "/research/identity/density",
    "/research/status",
)


def _client(fixture_root: Path):
    from fastapi.testclient import TestClient

    from nfl_oracle.service.app import create_app

    return TestClient(create_app(project_root=fixture_root))


def _get(client: Any, path: str) -> dict[str, Any]:
    resp = client.get(path)
    if resp.status_code != 200:
        raise AssertionError(f"{path} status={resp.status_code} body={resp.text[:200]}")
    body = resp.json()
    if isinstance(body, dict) and body.get("contest_entry") is True:
        raise AssertionError(f"{path} returned contest_entry=true")
    return body if isinstance(body, dict) else {"_raw": body}


def _httpx_get(base_url: str, path: str) -> dict[str, Any]:
    import httpx

    url = base_url.rstrip("/") + path
    resp = httpx.get(url, timeout=10.0)
    if resp.status_code != 200:
        raise AssertionError(f"{path} status={resp.status_code}")
    body = resp.json()
    if isinstance(body, dict) and body.get("contest_entry") is True:
        raise AssertionError(f"{path} returned contest_entry=true")
    return body if isinstance(body, dict) else {"_raw": body}


def run_smoke(*, fixture_root: Path, base_url: str | None) -> dict[str, Any]:
    results: dict[str, Any] = {
        "role": "research_client_smoke",
        "contest_entry": False,
        "observation_only": True,
        "mode": "live_http" if base_url else "testclient_offline",
        "routes_ok": [],
        "shadow_preview_ok": False,
        "draft_readiness": {},
        "posture": None,
    }

    def getter(path: str) -> dict[str, Any]:
        if base_url:
            return _httpx_get(base_url, path)
        assert client is not None
        return _get(client, path)

    client = None if base_url else _client(fixture_root)

    for path in GET_ROUTES:
        body = getter(path)
        results["routes_ok"].append(path)
        if path == "/research/status":
            results["posture"] = body.get("posture")
            results["draft_readiness"] = body.get("draft_readiness") or {}
            if results["draft_readiness"].get("submit_hard_denied") is not True:
                raise AssertionError("draft_readiness.submit_hard_denied must be true")
            if results["draft_readiness"].get("contest_entry") is not False:
                raise AssertionError("draft_readiness.contest_entry must be false")
        if path == "/research/gates/entry":
            if body.get("contest_entry") is not False:
                raise AssertionError("gates contest_entry must be false")
            deny = next(
                (g for g in body.get("gates", []) if g.get("key") == "package_submit_hard_deny"),
                None,
            )
            if deny is None or deny.get("ok") is not False:
                raise AssertionError("package_submit_hard_deny must be present and ok=false")

    preview_payload = {
        "player_ids": [1, 2, 3, 4, 5],
        "values_by_player": {"1": 10, "2": 5, "3": 4, "4": 3, "5": 2},
        "use_contest_algebra": True,
        "include_best_ordering": True,
    }
    if base_url:
        import httpx

        resp = httpx.post(
            base_url.rstrip("/") + "/research/shadow/preview",
            json=preview_payload,
            timeout=10.0,
        )
        if resp.status_code != 200:
            raise AssertionError(f"shadow preview status={resp.status_code}")
        pbody = resp.json()
    else:
        assert client is not None
        resp = client.post("/research/shadow/preview", json=preview_payload)
        if resp.status_code != 200:
            raise AssertionError(f"shadow preview status={resp.status_code}")
        pbody = resp.json()
    if pbody.get("contest_entry") is not False:
        raise AssertionError("shadow preview contest_entry must be false")
    if "contest_shadow_score" not in pbody:
        raise AssertionError("shadow preview missing contest_shadow_score")
    results["shadow_preview_ok"] = True
    results["routes_ok_count"] = len(results["routes_ok"])
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--fixture-root",
        type=Path,
        default=DEFAULT_FIXTURE_ROOT,
        help="offline research project root (default: tests/fixtures/offline_research)",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="optional live research server base URL (otherwise TestClient offline)",
    )
    parser.add_argument("--json", action="store_true", help="print JSON summary")
    args = parser.parse_args(argv)

    try:
        summary = run_smoke(fixture_root=args.fixture_root, base_url=args.base_url)
    except Exception as exc:  # noqa: BLE001 — smoke boundary
        print(f"research_client_smoke FAIL: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(
            "research_client_smoke OK: "
            f"routes={summary['routes_ok_count']} "
            f"posture={summary['posture']} "
            f"shadow_preview={summary['shadow_preview_ok']} "
            f"submit_hard_denied="
            f"{summary['draft_readiness'].get('submit_hard_denied')} "
            f"contest_entry=false"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
