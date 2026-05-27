# WNBA Oracle backend image. Used by api and cron services.
# Multi-stage: builder installs deps via uv; runtime adds Chromium for
# Playwright Real Sports re-auth.

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

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini ./

RUN uv sync --frozen --no-dev --no-editable

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
WORKDIR /app
COPY src/ ./src/
COPY migrations/ ./migrations/
COPY alembic.ini ./
COPY models/ ./models/
COPY data/ ./data/
COPY scripts/seed_storage_state.py ./scripts/seed_storage_state.py

ENV PYTHONPATH=/app/src \
    PORT=8000

RUN useradd --create-home --uid 10001 oracle \
    && mkdir -p /app/scraper \
    && chown -R oracle:oracle /app /opt/venv /opt/playwright-browsers
USER oracle

EXPOSE 8000

# Default CMD is the API. Cron services override startCommand to:
#   sh -c "python /app/scripts/seed_storage_state.py && oracle-cron --job jobN"
# Always wrap with sh -c so ${PORT} expands. See mlb-oracle for the silent-cron
# regression that motivated this.
CMD ["sh", "-c", "echo BOOT_PHASE=migrate && alembic upgrade head && echo BOOT_PHASE=uvicorn PORT=${PORT:-8000} && exec uvicorn wnba_oracle.api.app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips=* --log-level info"]
