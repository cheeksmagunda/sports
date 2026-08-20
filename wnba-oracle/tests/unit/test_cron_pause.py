"""cron.py: PICKS_PAUSE_START/END skips job1/job1late/job2, never dayclose."""

from __future__ import annotations

import datetime as dt
from unittest.mock import patch

import pytest

from wnba_oracle.common.clock import slate_date
from wnba_oracle.common.settings import Settings
from wnba_oracle.scheduler import cron

_TODAY = slate_date()
PAUSED = Settings(
    PICKS_PAUSE_START=(_TODAY - dt.timedelta(days=1)).isoformat(),
    PICKS_PAUSE_END=(_TODAY + dt.timedelta(days=1)).isoformat(),
)
NOT_PAUSED = Settings()


@pytest.mark.parametrize("job", ["job1", "job1late", "job2"])
def test_paused_skips_picking_jobs(job: str) -> None:
    with (
        patch("sys.argv", ["oracle-cron", "--job", job]),
        patch("wnba_oracle.scheduler.cron.get_settings", return_value=PAUSED),
        patch("wnba_oracle.scheduler.job1.main") as job1_main,
        patch("wnba_oracle.scheduler.job1.main_lite") as job1_main_lite,
        patch("wnba_oracle.scheduler.job2.main") as job2_main,
    ):
        rc = cron.main()
    assert rc == 0
    job1_main.assert_not_called()
    job1_main_lite.assert_not_called()
    job2_main.assert_not_called()


def test_paused_does_not_skip_dayclose() -> None:
    with (
        patch("sys.argv", ["oracle-cron", "--job", "dayclose"]),
        patch("wnba_oracle.scheduler.cron.get_settings", return_value=PAUSED),
        patch("wnba_oracle.scheduler.job_dayclose.main", return_value=0) as dayclose_main,
    ):
        rc = cron.main()
    assert rc == 0
    dayclose_main.assert_called_once()


def test_not_paused_dispatches_job1late() -> None:
    with (
        patch("sys.argv", ["oracle-cron", "--job", "job1late"]),
        patch("wnba_oracle.scheduler.cron.get_settings", return_value=NOT_PAUSED),
        patch("wnba_oracle.scheduler.job1.main_lite", return_value=0) as job1_main_lite,
    ):
        rc = cron.main()
    assert rc == 0
    job1_main_lite.assert_called_once()


def test_pause_window_does_not_cover_today() -> None:
    # A pause window entirely in the past (or future) should not skip.
    stale = Settings(PICKS_PAUSE_START="2020-01-01", PICKS_PAUSE_END="2020-01-02")
    with (
        patch("sys.argv", ["oracle-cron", "--job", "job1late"]),
        patch("wnba_oracle.scheduler.cron.get_settings", return_value=stale),
        patch("wnba_oracle.scheduler.job1.main_lite", return_value=0) as job1_main_lite,
    ):
        rc = cron.main()
    assert rc == 0
    job1_main_lite.assert_called_once()
