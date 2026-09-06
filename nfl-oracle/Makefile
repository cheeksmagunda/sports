# NFL Oracle developer targets. The parent workspace owns dependency locking.

.PHONY: help setup install test lint typecheck fmt baselines daily-shadow

UV_RUN = uv run --frozen --package nfl-oracle

help:
	@echo "nfl-oracle developer targets:"
	@echo "  make setup       - locked workspace setup"
	@echo "  make install     - locked workspace dependencies"
	@echo "  make test        - default offline test suite"
	@echo "  make lint        - ruff check"
	@echo "  make typecheck   - mypy"
	@echo "  make fmt         - ruff format"
	@echo "  make baselines   - offline Real value walk-forward baselines"
	@echo "  make daily-shadow - coverage→baselines→status artifact (#91 shadow)"

setup:
	$(MAKE) -C .. setup

install:
	$(MAKE) -C .. install

test:
	env -u DATABASE_URL -u DATABASE_PUBLIC_URL -u REDIS_URL $(UV_RUN) --extra dev python -m pytest tests/ -q

lint:
	$(UV_RUN) --extra dev ruff check src/ tests/ scripts/
	$(UV_RUN) --extra dev ruff format --check src/ tests/ scripts/

typecheck:
	$(UV_RUN) --extra dev python -m mypy src/

fmt:
	$(UV_RUN) --extra dev ruff format src/ tests/ scripts/

baselines:
	$(UV_RUN) nfl-value-baselines --json

daily-shadow:
	$(UV_RUN) python scripts/daily_shadow.py
