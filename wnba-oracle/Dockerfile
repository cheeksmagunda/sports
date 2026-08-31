# WNBA Oracle backend image. Used by API and cron services.
# Build from the sports monorepo root with:
#   docker build -f wnba-oracle/Dockerfile .

FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.11.13 /uv /uvx /bin/

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /workspace
COPY pyproject.toml uv.lock ./
COPY packages/oracle-core/pyproject.toml packages/oracle-core/README.md ./packages/oracle-core/
COPY packages/oracle-core/src/ ./packages/oracle-core/src/
COPY wnba-oracle/pyproject.toml wnba-oracle/README.md ./wnba-oracle/
COPY wnba-oracle/src/ ./wnba-oracle/src/
COPY wnba-oracle/migrations/ ./wnba-oracle/migrations/
COPY wnba-oracle/alembic.ini ./wnba-oracle/

RUN uv sync --frozen --no-dev --package wnba-oracle --no-editable

ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
RUN /opt/venv/bin/playwright install chromium

FROM python:3.11-slim AS runtime

# Chromium runtime deps (jammy set from playwright docs minus test-only).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    tzdata \
    ca-certificates \
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcairo2 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libexpat1 \
    libgbm1 \
    libglib2.0-0 \
    libnspr4 \
    libnss3 \
    libpango-1.0-0 \
    libx11-6 \
    libxcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    && rm -rf /var/lib/apt/lists/*

ENV TZ=America/New_York \
    PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/playwright-browsers /opt/playwright-browsers
WORKDIR /app/wnba-oracle
COPY wnba-oracle/src/ ./src/
COPY wnba-oracle/migrations/ ./migrations/
COPY wnba-oracle/alembic.ini ./
COPY wnba-oracle/models/ ./models/
COPY wnba-oracle/data/ ./data/
COPY wnba-oracle/scripts/seed_storage_state.py ./scripts/seed_storage_state.py
COPY wnba-oracle/scripts/runtime_role_probe.py ./scripts/runtime_role_probe.py

ENV PYTHONPATH=/app/wnba-oracle/src \
    PORT=8000

RUN useradd --create-home --uid 10001 oracle \
    && mkdir -p /app/wnba-oracle/scraper \
    && chown -R oracle:oracle /app /opt/venv /opt/playwright-browsers
USER oracle

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/health', timeout=4)"]

# Default CMD is the API. Cron services override startCommand to:
#   sh -c "python /app/wnba-oracle/scripts/seed_storage_state.py && oracle-cron --job jobN"
# Always wrap with sh -c so ${PORT} expands. See mlb-oracle for the silent-cron
# regression that motivated this.
CMD ["sh", "-c", "echo BOOT_PHASE=migrate && alembic upgrade head && echo BOOT_PHASE=uvicorn PORT=${PORT:-8000} && exec uvicorn wnba_oracle.api.app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=* --log-level info"]
