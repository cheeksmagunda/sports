# NFL Oracle developer targets. The parent workspace owns dependency locking.

.PHONY: help setup install test lint typecheck fmt baselines daily-shadow strategy-schema hydrate-identity provider-status auth-presence research-serve research-smoke cache-schedules contest-dry-run walk-forward-report docker-research-build docker-research-smoke docker-production-smoke postgres-store-smoke

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
	@echo "  make contest-dry-run - offline five-card shadow slate (dry_run; hard-deny submit)"
	@echo "  make walk-forward-report - baselines vs feature_ridge eval report (fixtures → artifacts/)"
	@echo "  make docker-research-smoke - build nfl-oracle-local research image if docker available (skip ok)"
	@echo "  make docker-production-smoke - build production image and verify CLI entrypoint (skip ok)"
	@echo "  make postgres-store-smoke - exercise migration, append-only, and backup on temporary PostgreSQL"

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

cache-schedules:
	$(UV_RUN) python scripts/cache_nflverse_schedules.py

contest-dry-run:
	$(UV_RUN) nfl-contest-dry-run --json

walk-forward-report:
	$(UV_RUN) nfl-walk-forward-report

# Local research Docker (observation-only). Skips cleanly when docker is absent.
# Does not touch WNBA Railway configs. No secrets required.
docker-research-build:
	@if ! docker --version >/dev/null 2>&1; then \
		echo "docker not available; skip nfl-oracle-local research build"; \
	else \
		docker compose -f docker-compose.yml build; \
	fi

docker-research-smoke: docker-research-build
	@if ! docker --version >/dev/null 2>&1; then \
		exit 0; \
	else \
		echo "nfl-oracle-local research image build OK (observation-only; no secrets)"; \
	fi

# Production image smoke. This builds locally and invokes only --help, so it
# never needs a database, provider session, or Railway credentials.
docker-production-smoke:
	@if ! docker --version >/dev/null 2>&1; then \
		echo "docker not available; skip nfl-oracle production image smoke"; \
	else \
		docker build -f Dockerfile.production -t nfl-oracle:production-smoke ..; \
		docker run --rm nfl-oracle:production-smoke nfl-pipeline --help; \
	fi

postgres-store-smoke:
	$(UV_RUN) python scripts/postgres_store_smoke.py
