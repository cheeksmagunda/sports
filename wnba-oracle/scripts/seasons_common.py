"""Shared --seasons parsing for WNBA research and race-corpus scripts."""

from __future__ import annotations

import argparse

DEFAULT_SEASONS = "2025,2026"
_MIN_YEAR = 2000
_MAX_YEAR = 2099


def parse_seasons(raw: str) -> list[str]:
    """Parse a comma-separated season list into sorted unique calendar years."""

    if not raw or not str(raw).strip():
        raise ValueError("seasons must include at least one year")
    years: list[str] = []
    for part in str(raw).split(","):
        token = part.strip()
        if not token:
            continue
        if not token.isdigit() or len(token) != 4:
            raise ValueError(f"Invalid season year: {token!r}")
        year = int(token)
        if year < _MIN_YEAR or year > _MAX_YEAR:
            raise ValueError(f"Invalid season year: {token!r}")
        years.append(token)
    if not years:
        raise ValueError("seasons must include at least one year")
    return sorted(set(years))


def in_seasons(slate_date: str, seasons: list[str]) -> bool:
    """True when ``slate_date`` (YYYY-MM-DD) falls in one of ``seasons``."""

    if len(slate_date) < 4:
        return False
    return slate_date[:4] in seasons


def add_seasons_argument(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--seasons",
        default=DEFAULT_SEASONS,
        help=f"Comma-separated calendar years to include (default: {DEFAULT_SEASONS})",
    )
