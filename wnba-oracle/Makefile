# wnba-oracle developer targets. Note: no `up` target. Railway CLI mutations
# do not work with this workspace token; use GraphQL or the Railway app.

.PHONY: help install test lint typecheck dev migrate deploy determinism-check rotation-check-help fmt

help:
	@echo "wnba-oracle developer targets:"
	@echo "  make install              - uv sync + playwright install"
	@echo "  make test                 - full pytest suite (excluding contract gate)"
	@echo "  make lint                 - ruff check"
	@echo "  make typecheck            - mypy"
	@echo "  make fmt                  - ruff format"
	@echo "  make dev                  - uvicorn on :8000 with reload"
	@echo "  make migrate              - alembic upgrade head"
	@echo "  make deploy               - emit deploy hint (go via use-railway skill)"
	@echo "  make determinism-check    - train twice, assert model CONTENT byte-equal"
	@echo "  make rotation-check-help  - print oracle-rotate-check usage"

install:
	uv sync --extra dev
	uv run playwright install chromium

test:
	uv run python -m pytest tests/ -q

test-contract:
	uv run python -m pytest tests/ -m contract -v

test-all:
	uv run python -m pytest tests/ -q
	uv run python -m pytest tests/ -m contract -v

lint:
	uv run ruff check src/ tests/ scripts/

typecheck:
	uv run mypy src/

fmt:
	uv run ruff format src/ tests/

dev:
	uv run uvicorn wnba_oracle.api.app:app --reload --host 0.0.0.0 --port 8000

migrate:
	uv run alembic upgrade head

deploy:
	@echo "Deploy via the use-railway skill or GraphQL push."
	@echo "Workspace-token CLI is not supported."

determinism-check:
	@D=$$(mktemp -d -t wnba_determ.XXXXXX); \
	  echo "Scratch dir: $$D"; \
	  echo "Run 1..."; \
	  OMP_NUM_THREADS=1 uv run oracle-train --commit determ01 \
	    --metrics-path $$D/run1.json | tail -3; \
	  PKL1=$$(find models -name "picker_determ01_*.pkl" | head -1); \
	  mv $$PKL1 $$D/run1.pkl; \
	  echo "Run 2..."; \
	  OMP_NUM_THREADS=1 uv run oracle-train --commit determ02 \
	    --metrics-path $$D/run2.json | tail -3; \
	  PKL2=$$(find models -name "picker_determ02_*.pkl" | head -1); \
	  mv $$PKL2 $$D/run2.pkl; \
	  echo "Comparing trained model CONTENT (not pickle bytes -- LightGBM"; \
	  echo "Boosters pickle non-deterministically even when content is equal)..."; \
	  uv run python scripts/compare_artifacts.py $$D/run1.pkl $$D/run2.pkl

rotation-check-help:
	uv run oracle-rotate-check --help
