"""Offline research_client_smoke script."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
FIXTURE_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "offline_research"


def test_research_client_smoke_offline() -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        mod = importlib.import_module("research_client_smoke")
        mod = importlib.reload(mod)
        summary = mod.run_smoke(fixture_root=FIXTURE_ROOT, base_url=None)
        assert summary["contest_entry"] is False
        assert summary["shadow_preview_ok"] is True
        assert summary["rank_orderings_ok"] is True
        assert summary["routes_ok_count"] >= 14
        assert summary["draft_readiness"]["submit_hard_denied"] is True
        assert summary["gates_hard_deny_ok"] is True
        assert summary["provider_contract_gate_denied"] is True
        assert summary["schedule_density"]["season_count"] >= 20
        assert summary["schedule_density"]["game_count"] >= 6000
        assert summary["coverage_density"]["catalog_season_count"] >= 14
        assert summary["coverage_density"]["matrix_game_id_count"] >= 40
        assert summary["coverage_density"]["status_counts"]["known"] >= 12
        assert summary["posture"] in {
            "blocked",
            "shadow_only",
            "ready_pending_contract",
            "capture_only",
        }
        assert mod.main(["--fixture-root", str(FIXTURE_ROOT)]) == 0
    finally:
        if str(SCRIPTS) in sys.path:
            sys.path.remove(str(SCRIPTS))
