"""NFL T-40 watchdog crons cover EDT Saturday and name the WNBA mono API (#599)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_saturday_watchdog_starts_at_hour_16_utc() -> None:
    text = (ROOT / ".github/workflows/nfl-t40-watchdog.yml").read_text(encoding="utf-8")
    assert 'cron: "*/15 16-22 * * 6"' in text
    assert "17:20Z" in text
    assert "16:20Z" in text


def test_wnba_actions_probe_the_mono_api() -> None:
    mono = "https://wnba-api-wnba-production.up.railway.app"
    legacy = "https://api-production-7033.up.railway.app"
    workflows = (
        ".github/workflows/watchdog-monitor.yml",
        ".github/workflows/wnba-pre-freeze-guard.yml",
        ".github/workflows/wnba-dayclose-verify.yml",
        ".github/workflows/wnba-backfill-enrichment.yml",
    )
    for relative in workflows:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert f"WNBA_API_BASE: {mono}" in text
        assert f"WNBA_API_BASE: {legacy}" not in text
