# MarketIntel — common development commands.
#
# Use `make` (no args) to see what's available.

.DEFAULT_GOAL := help
.PHONY: help install install-dev up down logs migrate seed test test-unit test-integration \
        lint fmt typecheck clean shell ingest backfill prod-build prod-shell

PYTHON ?= python
COMPOSE ?= docker compose

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install runtime deps
	$(PYTHON) -m pip install --upgrade pip uv
	uv pip install -e .

install-dev: ## Install dev deps (test, lint, type-check)
	$(PYTHON) -m pip install --upgrade pip uv
	uv pip install -e ".[dev]"
	pre-commit install || true

# ─── Stack lifecycle ────────────────────────────────────────────
up: ## Start the full local stack
	$(COMPOSE) up -d
	@echo "Waiting for postgres..."
	@$(COMPOSE) exec -T postgres bash -c 'until pg_isready -U marketintel; do sleep 1; done' >/dev/null
	@echo "Stack ready. Web: http://localhost:8000  Dagster: http://localhost:3000  Flower: http://localhost:5555"

down: ## Stop the local stack
	$(COMPOSE) down

logs: ## Tail logs from all services
	$(COMPOSE) logs -f --tail=100

shell: ## Django shell inside the web container
	$(COMPOSE) exec web python manage.py shell

# ─── Database ───────────────────────────────────────────────────
migrate: ## Apply Django migrations
	$(COMPOSE) exec web python manage.py migrate --noinput

seed: ## Load initial fixtures (sources + instruments)
	$(COMPOSE) exec web python manage.py loaddata seeds/sources.json seeds/instruments.json

# ─── Pipeline ops ───────────────────────────────────────────────
ingest: ## Trigger a Yahoo Finance quote ingest for all active instruments
	$(COMPOSE) exec web python -c "from pipelines.tasks.yahoo import ingest_yahoo_spot_for_active; print(ingest_yahoo_spot_for_active.apply().get())"

backfill: ## Backfill OHLCV bars (override SYMBOLS=AAPL,MSFT,NVDA)
	$(COMPOSE) exec web python -c "from pipelines.tasks.yahoo import ingest_yahoo_candles; \
[ingest_yahoo_candles.apply(args=(s,), kwargs={'resolution': r}) \
 for s in '$${SYMBOLS:-AAPL,MSFT,NVDA,SPY}'.split(',') \
 for r in ('1m','5m','15m','1h','1d')]"

# ─── Tests ──────────────────────────────────────────────────────
test: ## Run the full test suite
	$(COMPOSE) exec web pytest

test-unit: ## Run unit tests only (no DB / Redis required)
	$(COMPOSE) exec web pytest -m unit

test-integration: ## Run integration tests
	$(COMPOSE) exec web pytest -m integration

# ─── Quality ────────────────────────────────────────────────────
lint: ## Run ruff
	ruff check apps pipelines warehouse config tests
	ruff format --check apps pipelines warehouse config tests

fmt: ## Apply ruff fixes + format
	ruff check --fix apps pipelines warehouse config tests
	ruff format apps pipelines warehouse config tests

typecheck: ## Run mypy
	mypy apps pipelines warehouse config

# ─── Production image ───────────────────────────────────────────
prod-build: ## Build the production image
	docker build --target prod -t marketintel:prod .

prod-shell: ## Shell into the prod image (debug only)
	docker run --rm -it --entrypoint /bin/bash marketintel:prod

# ─── Cleanup ────────────────────────────────────────────────────
clean: ## Remove build artefacts and caches
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	rm -rf build dist *.egg-info .coverage htmlcov coverage.xml
