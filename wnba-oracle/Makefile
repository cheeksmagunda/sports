# WNBA Oracle developer targets. The parent workspace owns dependency locking.
# Railway mutations go through documented HTTPS or CLI operations.

.PHONY: help install test test-contract test-all lint typecheck dev migrate deploy determinism-check rotation-check-help fmt

help:
	@echo "wnba-oracle developer targets:"
	@echo "  make install              - uv sync + playwright install"
	@echo "  make test                 - full pytest suite (excluding contract gate)"
	@echo "  make test-contract        - external provider contract tests"
	@echo "  make lint                 - ruff check"
	@echo "  make typecheck            - mypy"
	@echo "  make fmt                  - ruff format"
	@echo "  make dev                  - uvicorn on :8000 with reload"
	@echo "  make migrate              - alembic upgrade head"
	@echo "  make deploy               - emit deploy hint"
	@echo "  make determinism-check    - train twice, compare model content"
	@echo "  make rotation-check-help  - print oracle-rotate-check usage"

install:
	uv sync --package wnba-oracle --extra dev
	uv run --package wnba-oracle playwright install chromium

test:
	uv run --package wnba-oracle --extra dev python -m pytest tests/ -q

test-contract:
	uv run --package wnba-oracle --extra dev python -m pytest tests/ -m contract -v

test-all:
	uv run --package wnba-oracle --extra dev python -m pytest tests/ -q
	uv run --package wnba-oracle --extra dev python -m pytest tests/ -m contract -v

lint:
	uv run --package wnba-oracle --extra dev ruff check src/ tests/ scripts/

typecheck:
	uv run --package wnba-oracle --extra dev python -m mypy src/

fmt:
	uv run --package wnba-oracle --extra dev ruff format src/ tests/

dev:
	uv run --package wnba-oracle uvicorn wnba_oracle.api.app:app --reload --host 0.0.0.0 --port 8000

migrate:
	uv run --package wnba-oracle alembic upgrade head

deploy:
	@echo "Deploy through the documented Railway CLI or HTTPS workflow."

determinism-check:
	@D=$$(mktemp -d -t wnba_determ.XXXXXX); \
	  echo "Scratch dir: $$D"; \
	  echo "Run 1..."; \
	  OMP_NUM_THREADS=1 uv run --package wnba-oracle oracle-train --commit determ01 \
	    --metrics-path $$D/run1.json | tail -3; \
	  PKL1=$$(find models -name "picker_determ01_*.pkl" | head -1); \
	  mv $$PKL1 $$D/run1.pkl; \
	  echo "Run 2..."; \
	  OMP_NUM_THREADS=1 uv run --package wnba-oracle oracle-train --commit determ02 \
	    --metrics-path $$D/run2.json | tail -3; \
	  PKL2=$$(find models -name "picker_determ02_*.pkl" | head -1); \
	  mv $$PKL2 $$D/run2.pkl; \
	  echo "Comparing trained model content"; \
	  uv run --package wnba-oracle python scripts/compare_artifacts.py $$D/run1.pkl $$D/run2.pkl

rotation-check-help:
	uv run --package wnba-oracle oracle-rotate-check --help
