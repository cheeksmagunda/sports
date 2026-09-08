# NFL Oracle local research image — observation-only HTTP API.
# NOT for Railway / production deploy. No secrets required or injected.
#
# Build from the sports monorepo root:
#   docker build -f nfl-oracle/Dockerfile -t nfl-oracle-local .
# Or:
#   make -C nfl-oracle docker-research-smoke

FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.13 /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

WORKDIR /workspace
COPY pyproject.toml uv.lock ./
COPY packages/oracle-core/pyproject.toml packages/oracle-core/README.md ./packages/oracle-core/
COPY packages/oracle-core/src/ ./packages/oracle-core/src/
COPY nfl-oracle/pyproject.toml nfl-oracle/README.md ./nfl-oracle/
COPY nfl-oracle/frontend/ ./nfl-oracle/frontend/
COPY nfl-oracle/src/ ./nfl-oracle/src/

# Research serve extra only. Do not install Playwright browsers.
RUN uv sync --frozen --no-dev --extra serve --package nfl-oracle --no-editable

FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    NFL_ORACLE_MODE=research_local

COPY --from=builder /opt/venv /opt/venv

# Layout keeps resolve_project_root discoverable via cwd (src/nfl_oracle present).
WORKDIR /app/nfl-oracle
COPY nfl-oracle/src/ ./src/
COPY nfl-oracle/data/catalog/ ./data/catalog/
COPY nfl-oracle/data/schedule/ ./data/schedule/
COPY nfl-oracle/data/raw/.gitkeep ./data/raw/.gitkeep
RUN mkdir -p data/cache data/artifacts \
    && mkdir -m 700 scraper

EXPOSE 8088

# Observation only: contest_entry stays false; no storage_state / Railway secrets.
CMD ["nfl-research-serve", "--host", "0.0.0.0", "--port", "8088"]
