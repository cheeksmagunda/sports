# WNBA Oracle developer targets. The parent workspace owns dependency locking.
# Railway mutations go through documented HTTPS or CLI operations.

.PHONY: help setup install install-browser test test-integration test-contract test-all lint typecheck dev migrate deploy determinism-check rotation-check-help fmt

UV_RUN = uv run --frozen --package wnba-oracle

help:
	@echo "wnba-oracle developer targets:"
	@echo "  make setup                - locked workspace setup and smoke check"
	@echo "  make install              - locked workspace dependencies"
	@echo "  make install-browser      - optional Chromium for provider work"
	@echo "  make test                 - default test suite (unit and offline acceptance)"
	@echo "  make test-integration     - PostgreSQL, Redis, and migration acceptance"
	@echo "  make test-contract        - external provider contract tests"
	@echo "  make test-all             - default, integration, and contract suites"
	@echo "  make lint                 - ruff check"
	@echo "  make typecheck            - mypy"
	@echo "  make fmt                  - ruff format"
	@echo "  make dev                  - uvicorn on :8000 with reload"
	@echo "  make migrate              - alembic upgrade head"
	@echo "  make deploy               - emit deploy hint"
	@echo "  make determinism-check    - train twice, compare model content"
	@echo "  make rotation-check-help  - print oracle-rotate-check usage"

setup:
	$(MAKE) -C .. setup

install:
	$(MAKE) -C .. install

install-browser: install
	$(UV_RUN) playwright install chromium

test:
	env -u DATABASE_URL -u DATABASE_PUBLIC_URL -u REDIS_URL $(UV_RUN) --extra dev python -m pytest tests/ -q

test-integration:
	$(UV_RUN) --extra dev python scripts/check_migrations.py
	$(UV_RUN) --extra dev alembic upgrade head
	$(UV_RUN) --extra dev python -m pytest tests/integration -m integration -q

test-contract:
	$(UV_RUN) --extra dev python -m pytest tests/ -m contract -v

test-all: test test-integration test-contract

lint:
	$(UV_RUN) --extra dev ruff check src/ tests/ scripts/
	$(UV_RUN) --extra dev ruff format --check src/ tests/ scripts/

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
	@set -eu; \
	  D=$$(mktemp -d -t wnba_determ.XXXXXX); \
	  trap 'rm -rf "$$D"' EXIT; \
	  echo "Scratch dir: $$D"; \
	  echo "Snapshotting immutable training inputs..."; \
	  $(UV_RUN) python scripts/snapshot_training_inputs.py --output-dir "$$D"; \
	  echo "Run 1..."; \
	  OMP_NUM_THREADS=1 POLARS_MAX_THREADS=1 PYTHONHASHSEED=0 \
	    $(UV_RUN) oracle-train --commit determ01 \
	    --corpus "$$D/labels.parquet" --heads-corpus "$$D/heads.parquet" \
	    --artifact-dir "$$D" --metrics-path "$$D/run1.json" >"$$D/run1.log"; \
	  tail -3 "$$D/run1.log"; \
	  PKL1=$$(find "$$D" -maxdepth 1 -name "picker_determ01_*.pkl" -print -quit); \
	  test -n "$$PKL1"; \
	  echo "Run 2..."; \
	  OMP_NUM_THREADS=1 POLARS_MAX_THREADS=1 PYTHONHASHSEED=0 \
	    $(UV_RUN) oracle-train --commit determ02 \
	    --corpus "$$D/labels.parquet" --heads-corpus "$$D/heads.parquet" \
	    --artifact-dir "$$D" --metrics-path "$$D/run2.json" >"$$D/run2.log"; \
	  tail -3 "$$D/run2.log"; \
	  PKL2=$$(find "$$D" -maxdepth 1 -name "picker_determ02_*.pkl" -print -quit); \
	  test -n "$$PKL2"; \
	  echo "Comparing trained model content"; \
	  $(UV_RUN) python scripts/compare_artifacts.py "$$PKL1" "$$PKL2"

rotation-check-help:
	$(UV_RUN) oracle-rotate-check --help
