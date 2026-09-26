"""Guard the nfl-t40-watchdog schedule against holiday kickoff regressions."""

from __future__ import annotations

import re
from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "nfl-t40-watchdog.yml"

# Weekly grid (Sunday + TNF/SNF/MNF evenings).
WEEKLY_CRONS = (
    "*/15 13-14 * * 0",
    "*/15 16-21 * * 0",
    "*/15 23 * * 0,1,4",
    "*/15 0 * * 1,2,5",
)

# Holiday gaps: Thanksgiving afternoon, Dec Saturday (e.g. 12-19), Christmas.
HOLIDAY_CRONS = (
    "*/15 17-21 * 11 4",  # Thanksgiving Thu afternoon (November)
    "*/15 21-23 * 12 6",  # Late-season Saturday (December, e.g. 12-19)
    "*/15 0 * 12 0",  # Saturday nightcap spill into Sunday 00 UTC
    "*/15 17-21 25 12 *",  # Christmas Day afternoon
    "*/15 0 26 12 *",  # Christmas nightcap spill into 12-26 00 UTC
)


def _scheduled_crons(text: str) -> set[str]:
    return set(re.findall(r'^\s*-\s*cron:\s*"([^"]+)"', text, flags=re.MULTILINE))


def test_t40_watchdog_workflow_keeps_weekly_and_holiday_crons() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    crons = _scheduled_crons(text)

    for expression in WEEKLY_CRONS:
        assert expression in crons, f"missing weekly cron: {expression}"
    for expression in HOLIDAY_CRONS:
        assert expression in crons, f"missing holiday cron: {expression}"

    assert "Thanksgiving" in text
    assert "12-19" in text
    assert "Christmas" in text
