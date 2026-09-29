# NHL Oracle staging image. The same image serves the read-only API and runs
# the separately configured worker. Railway service start commands select the
# role. No migrations, no contest entry, no secrets in the image.
#
# Build from the monorepo root:
#   docker build -f nhl-oracle/Dockerfile -t nhl-oracle:staging .

FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

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
COPY nhl-oracle/pyproject.toml nhl-oracle/README.md ./nhl-oracle/
COPY nhl-oracle/src/ ./nhl-oracle/src/

# Serve extra installs uvicorn. The T-40 worker captures Real request headers
# with the stored session through Chromium (#675), same as wnba-oracle.
RUN uv sync --frozen --no-dev --extra serve --package nhl-oracle --no-editable

ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
RUN env -u PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD /opt/venv/bin/playwright install chromium

FROM python:3.11-slim AS runtime

# Chromium runtime deps (same set as wnba-oracle).
RUN apt-get update && apt-get install -y --no-install-recommends \
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

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers \
    NHL_PIPELINE_ROLE=api \
    PORT=8000

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /opt/playwright-browsers /opt/playwright-browsers

WORKDIR /app/nhl-oracle
COPY nhl-oracle/src/ ./src/

RUN useradd --create-home --uid 10001 oracle \
    && mkdir -p /app/nhl-oracle \
    && chown -R oracle:oracle /app /opt/venv /opt/playwright-browsers
USER oracle

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD ["python", "-c", "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/health', timeout=4)"]

# API is the safe default. Railway's worker service overrides this command with
# `nhl-pipeline worker`. No migrate-on-startup (scaffold has no schema yet).
CMD ["sh", "-c", "exec nhl-pipeline serve --host 0.0.0.0 --port ${PORT:-8000}"]
