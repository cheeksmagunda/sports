"""Database URL helpers. One place to keep the postgres scheme normalization."""

from __future__ import annotations

import re
from pathlib import Path

from oracle_core.storage import normalize_postgres_url as _normalize_postgres_url

_SSLROOTCERT = re.compile(r"(sslrootcert=)([^&\s]+)")


def normalize_postgres_url(url: str) -> str:
    """Retain the WNBA pass-through contract over the strict core helper."""
    if not url or not url.startswith(("postgres://", "postgresql://", "postgresql+")):
        return url
    return _normalize_postgres_url(url)


def repair_local_sslrootcert(url: str, repo_root: Path) -> str:
    """Re-point an `sslrootcert` that names a path which no longer exists.

    Local DB access goes through the Railway TCP proxy with verify-ca, so
    DATABASE_PUBLIC_URL carries an ABSOLUTE `sslrootcert` path into the repo's
    own .pgssl directory. Move or rename the checkout and every local script
    dies on "root certificate file ... does not exist", with the stale path in
    the message pointing at a directory that is simply gone. That happened when
    this repo moved to ~/Desktop/sports/wnba-oracle on 2026-08-19.

    Rewrites only when the referenced file is missing AND a file of the same
    name exists under ``repo_root/.pgssl``, so a correct URL is never touched
    and a genuinely absent cert still fails loudly. On Railway there is no
    .pgssl directory, so this is inert in production.
    """
    if not url:
        return url

    def _swap(match: re.Match[str]) -> str:
        current = Path(match.group(2))
        if current.exists():
            return match.group(0)
        candidate = repo_root / ".pgssl" / current.name
        return f"{match.group(1)}{candidate}" if candidate.exists() else match.group(0)

    return _SSLROOTCERT.sub(_swap, url)
