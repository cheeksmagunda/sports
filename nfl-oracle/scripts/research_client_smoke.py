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
    "/research/provider/rules-offline",
    "/research/gates/entry",
    "/research/catalog/seasons",
    "/research/coverage/summary",
    "/research/schedule/summary",
    "/research/identity/density",
    "/research/health/readiness-score",
    "/research/shadow/contest-dry-run",
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
        "rank_orderings_ok": False,
        "draft_readiness": {},
        "posture": None,
        "coverage_density": {},
        "schedule_density": {},
        "provider_contract_gate_denied": False,
        "gates_hard_deny_ok": False,
        "contest_dry_run_ok": False,
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
        if path == "/research/provider/rules-offline":
            if body.get("submit_enabled") is not False:
                raise AssertionError("rules-offline submit_enabled must be false")
            if body.get("provider_contract_verified") is not False:
                raise AssertionError("rules-offline provider_contract_verified must be false")
            notes = body.get("offline_rule_notes") or {}
            rules = body.get("unknown_rules") or []
            if len(rules) < 7:
                raise AssertionError(f"expected >=7 unknown rules, got {len(rules)}")
            missing = [r for r in rules if r not in notes]
            if missing:
                raise AssertionError(f"offline notes missing for {missing}")
        if path == "/research/shadow/contest-dry-run":
            if body.get("dry_run") is not True:
                raise AssertionError("contest-dry-run dry_run must be true")
            if body.get("observation_only") is not True:
                raise AssertionError("contest-dry-run observation_only must be true")
            if body.get("mode") != "dry_run":
                raise AssertionError("contest-dry-run mode must be dry_run")
            if body.get("submit_proof", {}).get("submit_denied") is not True:
                raise AssertionError("contest-dry-run submit must be denied")
            results["contest_dry_run_ok"] = True
        if path == "/research/features/live-ok":
            live = body.get("live_ok") or []
            if len(live) < 20:
                raise AssertionError(f"live_ok too sparse: {len(live)}")
            if "injury_status" not in live or "opponent_adjusted_prior" not in live:
                raise AssertionError("expected injury/opponent-adjusted in live_ok")
            if "same_slate_final_value" in live:
                raise AssertionError("same_slate_final_value must not be live_ok")
        if path == "/research/gates/entry":
            if body.get("contest_entry") is not False:
                raise AssertionError("gates contest_entry must be false")
            deny = next(
                (g for g in body.get("gates", []) if g.get("key") == "package_submit_hard_deny"),
                None,
            )
            if deny is None or deny.get("ok") is not False:
                raise AssertionError("package_submit_hard_deny must be present and ok=false")
            contract = next(
                (g for g in body.get("gates", []) if g.get("key") == "provider_contract_verified"),
                None,
            )
            if contract is None or contract.get("ok") is not False:
                raise AssertionError(
                    "provider_contract_verified must be present and ok=false without #91 contract"
                )
            results["provider_contract_gate_denied"] = True
            results["gates_hard_deny_ok"] = True
        if path == "/research/coverage/summary":
            dens = body.get("density") or {}
            results["coverage_density"] = dens
            if dens.get("catalog_season_count", 0) < 14:
                raise AssertionError(
                    f"coverage density seasons too sparse: {dens.get('catalog_season_count')}"
                )
            if dens.get("matrix_game_id_count", 0) < 40:
                raise AssertionError(
                    f"coverage matrix games too sparse: {dens.get('matrix_game_id_count')}"
                )
            known = (dens.get("status_counts") or {}).get("known", 0)
            if known < 12:
                raise AssertionError(f"coverage known seasons too sparse: {known}")
            sched = body.get("schedule") or {}
            sdens = sched.get("density") or {}
            if sdens.get("season_count", 0) < 20:
                raise AssertionError(
                    f"coverage.summary schedule seasons too sparse: {sdens.get('season_count')}"
                )
            if sdens.get("game_count", 0) < 6000:
                raise AssertionError(
                    f"coverage.summary schedule games too sparse: {sdens.get('game_count')}"
                )
            if (sched.get("continuous_regular_season_count") or 0) < 20:
                raise AssertionError("coverage.summary continuous regular seasons too sparse")
        if path == "/research/schedule/summary":
            dens = body.get("density") or {}
            results["schedule_density"] = dens
            if dens.get("season_count", 0) < 20:
                raise AssertionError(
                    f"schedule density seasons too sparse: {dens.get('season_count')}"
                )
            if dens.get("game_count", 0) < 6000:
                raise AssertionError(f"schedule density games too sparse: {dens.get('game_count')}")
            if dens.get("week_count", 0) < 400:
                raise AssertionError(
                    f"schedule density week slots too sparse: {dens.get('week_count')}"
                )
            continuous = body.get("continuous_regular_season_count") or 0
            if continuous < 20:
                raise AssertionError(f"continuous regular seasons too sparse: {continuous}")
            if body.get("contest_entry") is not False:
                raise AssertionError("schedule summary contest_entry must be false")

    # Parametric slate resolve (not in GET_ROUTES — needs query string)
    if base_url:
        import httpx

        sresp = httpx.get(
            base_url.rstrip("/") + "/research/schedule/slate",
            params={"season": 2024, "week": 1},
            timeout=10.0,
        )
        if sresp.status_code != 200:
            raise AssertionError(f"schedule slate status={sresp.status_code}")
        sbody = sresp.json()
    else:
        assert client is not None
        sresp = client.get("/research/schedule/slate", params={"season": 2024, "week": 1})
        if sresp.status_code != 200:
            raise AssertionError(f"schedule slate status={sresp.status_code}")
        sbody = sresp.json()
    if sbody.get("contest_entry") is not False:
        raise AssertionError("schedule slate contest_entry must be false")
    if sbody.get("resolved") is not True:
        raise AssertionError("schedule slate must resolve")
    results["schedule_slate_ok"] = True
    results["routes_ok"].append("/research/schedule/slate?season=2024&week=1")

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

    rank_payload = {
        "player_ids": [1, 2, 3, 4, 5],
        "values_by_player": {"1": 10, "2": 5, "3": 4, "4": 3, "5": 2},
        "top_k": 5,
    }
    if base_url:
        import httpx

        rresp = httpx.post(
            base_url.rstrip("/") + "/research/shadow/rank-orderings",
            json=rank_payload,
            timeout=10.0,
        )
        if rresp.status_code != 200:
            raise AssertionError(f"rank-orderings status={rresp.status_code}")
        rbody = rresp.json()
    else:
        assert client is not None
        rresp = client.post("/research/shadow/rank-orderings", json=rank_payload)
        if rresp.status_code != 200:
            raise AssertionError(f"rank-orderings status={rresp.status_code}")
        rbody = rresp.json()
    if rbody.get("contest_entry") is not False:
        raise AssertionError("rank-orderings contest_entry must be false")
    if rbody.get("returned", 0) < 1:
        raise AssertionError("rank-orderings returned empty")
    results["rank_orderings_ok"] = True
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
        dens = summary.get("coverage_density") or {}
        sdens = summary.get("schedule_density") or {}
        print(
            "research_client_smoke OK: "
            f"routes={summary['routes_ok_count']} "
            f"posture={summary['posture']} "
            f"shadow_preview={summary['shadow_preview_ok']} "
            f"rank_orderings={summary['rank_orderings_ok']} "
            f"gates_hard_deny={summary.get('gates_hard_deny_ok')} "
            f"provider_contract_denied={summary.get('provider_contract_gate_denied')} "
            f"matrix_games={dens.get('matrix_game_id_count')} "
            f"known={((dens.get('status_counts') or {}).get('known'))} "
            f"schedule_seasons={sdens.get('season_count')} "
            f"schedule_games={sdens.get('game_count')} "
            f"submit_hard_denied="
            f"{summary['draft_readiness'].get('submit_hard_denied')} "
            f"contest_entry=false"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
