# NBA Oracle health-scaffold image for sports-oracle / nba-staging.
# Build from the sports monorepo root:
#   docker build -f nba-oracle/Dockerfile -t nba-oracle .
#
# Serves GET /health only. No contest entry, providers, or domain routes.
# Builds MUST go through this Dockerfile (railway.toml builder=DOCKERFILE).
# Do not image-reuse-redeploy a RAILPACK-failed deployment (issue #279).

FROM python:3.11-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:0.11.13 /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /workspace
COPY pyproject.toml uv.lock ./
COPY packages/oracle-core/pyproject.toml packages/oracle-core/README.md ./packages/oracle-core/
COPY packages/oracle-core/src/ ./packages/oracle-core/src/
COPY nba-oracle/pyproject.toml nba-oracle/README.md ./nba-oracle/
COPY nba-oracle/src/ ./nba-oracle/src/

RUN uv sync --frozen --no-dev --package nba-oracle --no-editable

FROM python:3.11-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

COPY --from=builder /opt/venv /opt/venv
WORKDIR /app/nba-oracle
COPY nba-oracle/src/ ./src/

ENV PYTHONPATH=/app/nba-oracle/src

RUN useradd --create-home --uid 10001 oracle \
    && chown -R oracle:oracle /app /opt/venv
USER oracle

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/health', timeout=4)"]

# Always wrap with sh -c so ${PORT} expands.
CMD ["sh", "-c", "exec uvicorn nba_oracle.api.app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=* --log-level info"]
