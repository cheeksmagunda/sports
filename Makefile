.PHONY: install test test-core test-wnba test-contract lint typecheck build check-boundaries

install:
	uv sync --all-packages --all-extras

test: test-core test-wnba

test-core:
	uv run --package oracle-core --extra dev python -m pytest packages/oracle-core/tests -q

test-wnba:
	uv run --package wnba-oracle --extra dev python -m pytest wnba-oracle/tests -q

test-contract:
	uv run --package wnba-oracle --extra dev python -m pytest wnba-oracle/tests -m contract -v

lint:
	cd packages/oracle-core && uv run --package oracle-core --extra dev ruff check src tests
	cd wnba-oracle && uv run --package wnba-oracle --extra dev ruff check src tests scripts
	python3 scripts/check_import_boundaries.py

typecheck:
	uv run --package oracle-core --extra dev python -m mypy --config-file packages/oracle-core/pyproject.toml packages/oracle-core/src
	uv run --package wnba-oracle --extra dev python -m mypy --config-file wnba-oracle/pyproject.toml wnba-oracle/src

build:
	uv build --package oracle-core
	uv build --package wnba-oracle

check-boundaries:
	python3 scripts/check_import_boundaries.py
