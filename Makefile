.PHONY: install test test-core test-wnba test-contract lint typecheck build check-boundaries

UV_RUN = uv run --no-editable

install:
	uv sync --all-packages --all-extras --no-editable

test: test-core test-wnba

test-core:
	$(UV_RUN) --package oracle-core --extra dev python -m pytest packages/oracle-core/tests -q

test-wnba:
	$(UV_RUN) --package wnba-oracle --extra dev python -m pytest wnba-oracle/tests -q

test-contract:
	$(UV_RUN) --package wnba-oracle --extra dev python -m pytest wnba-oracle/tests -m contract -v

lint:
	cd packages/oracle-core && $(UV_RUN) --package oracle-core --extra dev ruff check src tests
	cd wnba-oracle && $(UV_RUN) --package wnba-oracle --extra dev ruff check src tests scripts
	python3 scripts/check_import_boundaries.py

typecheck:
	$(UV_RUN) --package oracle-core --extra dev python -m mypy --config-file packages/oracle-core/pyproject.toml packages/oracle-core/src
	$(UV_RUN) --package wnba-oracle --extra dev python -m mypy --config-file wnba-oracle/pyproject.toml wnba-oracle/src

build:
	uv build --package oracle-core
	uv build --package wnba-oracle

check-boundaries:
	python3 scripts/check_import_boundaries.py
