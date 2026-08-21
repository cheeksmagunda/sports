# WNBA Oracle developer targets. The parent workspace owns dependency locking.
# Railway mutations go through documented HTTPS or CLI operations.

.PHONY: help install test test-contract test-all lint typecheck dev migrate deploy determinism-check rotation-check-help fmt

UV_RUN = uv run --no-editable --package wnba-oracle

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
	uv sync --no-editable --package wnba-oracle --extra dev
	$(UV_RUN) playwright install chromium

test:
	$(UV_RUN) --extra dev python -m pytest tests/ -q

test-contract:
	$(UV_RUN) --extra dev python -m pytest tests/ -m contract -v

test-all:
	$(UV_RUN) --extra dev python -m pytest tests/ -q
	$(UV_RUN) --extra dev python -m pytest tests/ -m contract -v

lint:
	$(UV_RUN) --extra dev ruff check src/ tests/ scripts/

typecheck:
	$(UV_RUN) --extra dev python -m mypy src/

fmt:
	$(UV_RUN) --extra dev ruff format src/ tests/

dev:
	$(UV_RUN) uvicorn wnba_oracle.api.app:app --reload --host 0.0.0.0 --port 8000

migrate:
	$(UV_RUN) alembic upgrade head

deploy:
	@echo "Deploy through the documented Railway CLI or HTTPS workflow."

determinism-check:
	@D=$$(mktemp -d -t wnba_determ.XXXXXX); \
	  echo "Scratch dir: $$D"; \
	  echo "Run 1..."; \
	  OMP_NUM_THREADS=1 $(UV_RUN) oracle-train --commit determ01 \
	    --metrics-path $$D/run1.json | tail -3; \
	  PKL1=$$(find models -name "picker_determ01_*.pkl" | head -1); \
	  mv $$PKL1 $$D/run1.pkl; \
	  echo "Run 2..."; \
	  OMP_NUM_THREADS=1 $(UV_RUN) oracle-train --commit determ02 \
	    --metrics-path $$D/run2.json | tail -3; \
	  PKL2=$$(find models -name "picker_determ02_*.pkl" | head -1); \
	  mv $$PKL2 $$D/run2.pkl; \
	  echo "Comparing trained model content"; \
	  $(UV_RUN) python scripts/compare_artifacts.py $$D/run1.pkl $$D/run2.pkl

rotation-check-help:
	$(UV_RUN) oracle-rotate-check --help
