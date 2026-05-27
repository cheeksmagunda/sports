"""Database URL helpers. One place to keep the postgres scheme normalization."""

from __future__ import annotations


def normalize_postgres_url(url: str) -> str:
    """Coerce a Heroku-style or bare postgres:// URL into the
    `postgresql+psycopg://` form SQLAlchemy 2 + psycopg 3 expect.

    Returns the input unchanged if it already uses an explicit driver suffix
    or is non-postgres.
    """
    if not url:
        return url
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url
