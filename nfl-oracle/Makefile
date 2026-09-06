# NFL Oracle developer targets. The parent workspace owns dependency locking.

.PHONY: help setup install test lint typecheck fmt baselines daily-shadow strategy-schema hydrate-identity provider-status auth-presence research-serve research-smoke

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
	@echo "  make provider-status - Real auth/provider readiness (no secrets)"
	@echo "  make auth-presence - env/path presence check (no secret values)"
	@echo "  make strategy-schema - emit strategy schema JSON"
	@echo "  make hydrate-identity - offline identity fixture summary"
	@echo "  make research-serve - local read-only research HTTP (127.0.0.1:8088)"
	@echo "  make research-smoke - offline TestClient smoke (hard-deny; SMOKE_ARGS=--json)"

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

strategy-schema:
	$(UV_RUN) nfl-strategy-schema --schema-only

hydrate-identity:
	$(UV_RUN) python scripts/hydrate_identity_fixtures.py

provider-status:
	$(UV_RUN) nfl-provider-status --json

auth-presence:
	$(UV_RUN) python scripts/auth_presence_check.py

research-serve:
	$(UV_RUN) --extra serve nfl-research-serve --host 127.0.0.1 --port 8088

# Offline-only by default: strip live DB/redis env like `make test`.
# Gates stay hard-deny (contest_entry=false). Override flags via SMOKE_ARGS.
research-smoke:
	env -u DATABASE_URL -u DATABASE_PUBLIC_URL -u REDIS_URL \
		$(UV_RUN) --extra dev python scripts/research_client_smoke.py $(SMOKE_ARGS)
