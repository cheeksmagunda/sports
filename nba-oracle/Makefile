# NBA Oracle developer targets. The parent workspace owns dependency locking.

.PHONY: help setup install test lint typecheck fmt

UV_RUN = uv run --frozen --package nba-oracle

help:
	@echo "nba-oracle developer targets:"
	@echo "  make setup       - locked workspace setup"
	@echo "  make install     - locked workspace dependencies"
	@echo "  make test        - default offline test suite"
	@echo "  make lint        - ruff check"
	@echo "  make typecheck   - mypy"
	@echo "  make fmt         - ruff format"

setup:
	$(MAKE) -C .. setup

install:
	$(MAKE) -C .. install

test:
	env -u DATABASE_URL -u DATABASE_PUBLIC_URL -u REDIS_URL $(UV_RUN) --extra dev python -m pytest tests/ -q

lint:
	$(UV_RUN) --extra dev ruff check src/ tests/
	$(UV_RUN) --extra dev ruff format --check src/ tests/

typecheck:
	$(UV_RUN) --extra dev python -m mypy src/

fmt:
	$(UV_RUN) --extra dev ruff format src/ tests/
