.PHONY: install test test-core test-portfolio test-app test-wnba test-integration test-contract security lint typecheck build check-applications check-boundaries

UV_RUN = uv run --no-editable

install:
	uv sync --all-packages --all-extras --no-editable

test: test-core test-portfolio test-wnba

test-core:
	$(UV_RUN) --package oracle-core --extra dev python -m pytest packages/oracle-core/tests -q

test-portfolio:
	$(UV_RUN) --package oracle-core --extra dev python -m pytest scripts/tests -q

test-app:
	@test -n "$(APP)" || (echo "Usage: make test-app APP=<application>" >&2; exit 2)
	$(UV_RUN) --package $(APP) --extra dev python -m pytest $(APP)/tests -q

test-wnba:
	$(MAKE) test-app APP=wnba-oracle

test-integration:
	$(UV_RUN) --package wnba-oracle --extra dev python wnba-oracle/scripts/check_migrations.py
	cd wnba-oracle && $(UV_RUN) --package wnba-oracle --extra dev alembic upgrade head
	$(UV_RUN) --package wnba-oracle --extra dev python -m pytest wnba-oracle/tests/integration -m integration -q

test-contract:
	$(UV_RUN) --package wnba-oracle --extra dev python -m pytest wnba-oracle/tests -m contract -v

# Current audit exceptions cover Arrow's unexposed pre-buffer API and unused
# Starlette request, form, static-file, and endpoint surfaces. Revisit them when
# those runtime surfaces or dependencies change.
security:
	@set -eu; \
	  requirements=$$(mktemp -t sports-runtime-requirements.XXXXXX); \
	  trap 'rm -f "$$requirements"' EXIT; \
	  uv export --quiet --frozen --all-packages --no-dev --no-hashes --output-file "$$requirements"; \
	  $(UV_RUN) --package wnba-oracle --extra dev pip-audit --requirement "$$requirements" \
	    --ignore-vuln GHSA-rgxp-2hwp-jwgg \
	    --ignore-vuln GHSA-86qp-5c8j-p5mr \
	    --ignore-vuln GHSA-jp82-jpqv-5vv3 \
	    --ignore-vuln GHSA-82w8-qh3p-5jfq \
	    --ignore-vuln GHSA-wqp7-x3pw-xc5r \
	    --ignore-vuln GHSA-x746-7m8f-x49c
	$(UV_RUN) --package wnba-oracle --extra dev bandit -q -r wnba-oracle/src --severity-level medium --confidence-level medium

lint:
	cd packages/oracle-core && $(UV_RUN) --package oracle-core --extra dev ruff check src tests
	cd packages/oracle-core && $(UV_RUN) --package oracle-core --extra dev ruff format --check src tests
	cd wnba-oracle && $(UV_RUN) --package wnba-oracle --extra dev ruff check src tests scripts
	cd wnba-oracle && $(UV_RUN) --package wnba-oracle --extra dev ruff format --check src tests scripts

typecheck:
	$(UV_RUN) --package oracle-core --extra dev python -m mypy --config-file packages/oracle-core/pyproject.toml packages/oracle-core/src
	$(UV_RUN) --package wnba-oracle --extra dev python -m mypy --config-file wnba-oracle/pyproject.toml wnba-oracle/src

build:
	uv build --package oracle-core
	uv build --package wnba-oracle

check-boundaries:
	python3 scripts/check_import_boundaries.py

check-applications:
	python3 scripts/check_applications.py
