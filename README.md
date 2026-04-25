# MarketIntel

Scalable market data platform. Ingests, normalises and serves data from
third-party providers (Yahoo Finance for equities; Binance, CoinGecko, CryptoPanic
available as alternative connectors) through distributed pipelines, stores it in a
dimensional model with time partitioning, and exposes a REST API plus an
interactive web dashboard.

Built as a working demo for a **Senior Data / Backend Engineer** role on a
market intelligence platform.

**Live demo**: see "Production deploy" below.
**Source**: https://github.com/henriquezbh5-cpu/marketintel

---

## How the role spec maps to this project

| Role bullet | How MarketIntel covers it |
|---|---|
| Scalable Python/Django backend | Django 5 + DRF, environment-split settings, scoped throttling, cursor pagination for time-series |
| Third-party ingestion pipelines | Connectors in `pipelines/connectors/` with retries, rate limiting, circuit breakers, idempotent UPSERTs |
| Data modelling & schema design | Medallion layout (bronze/silver/gold), SCD Type 2 dimensions, monthly Postgres partitioning |
| Async / distributed processing | Celery + Redis (4 queues, beat, DLQ table), Dagster for the asset graph |
| Orchestration / storage / warehousing | Dagster (assets, schedules, sensors), MinIO (S3) for bronze, PostgreSQL for silver, DuckDB for analytics |
| Application layer | REST API with DRF + interactive dashboard with Tailwind + Alpine + Chart.js |
| Technical strategy | 7 ADRs in `docs/adr/`, runbook in `docs/RUNBOOK.md` |

A live mapping is also available at `/coverage/` once the stack is up.

---

## Stack

- **Language**: Python 3.12
- **Backend**: Django 5.0, Django REST Framework
- **Async**: Celery 5 + Redis (broker + result backend)
- **Orchestration**: Dagster (assets, sensors, schedules)
- **Storage**: PostgreSQL 16 (OLTP + silver), MinIO (S3-compatible bronze), DuckDB (analytics)
- **HTTP**: httpx
- **Observability**: structlog + OpenTelemetry hooks, Prometheus metrics, Grafana dashboards
- **Testing**: pytest, pytest-django, factory-boy, respx (HTTP mocks)
- **Infra**: Docker Compose for dev, multi-stage Dockerfile for prod, K8s manifests with kustomize

---

## Architecture in one page

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Third-party    │    │   Bronze (raw)  │    │  Silver (clean) │
│   APIs          │───>│   MinIO/JSONL   │───>│   PostgreSQL    │
│ Yahoo Finance   │    │   immutable     │    │   normalised    │
└─────────────────┘    └─────────────────┘    └────────┬────────┘
                                                       │
                              ┌────────────────────────┼─────────────┐
                              │                        │             │
                       ┌──────v──────┐          ┌──────v──────┐  ┌───v────┐
                       │   Gold      │          │   API REST  │  │ DuckDB │
                       │ aggregates  │          │ + dashboard │  │analytic│
                       │  (matviews) │          │   Django    │  │  layer │
                       └─────────────┘          └─────────────┘  └────────┘
```

Dagster orchestrates the asset graph: ingest → normalise → quality → publish.
Celery runs the parallel work (per-symbol fan-out, transformations, refreshes).

Full detail in [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Quickstart

```bash
# 1. Bring the full stack up
cp .env.example .env
docker compose up -d

# 2. Migrations and seed data
docker compose exec web python manage.py migrate
docker compose exec web python manage.py apply_post_migrate
docker compose exec web python manage.py loaddata seeds/sources.json seeds/instruments.json

# 3. Pull a first batch of equity quotes
docker compose exec web python manage.py shell -c \
  "from pipelines.tasks.yahoo import ingest_yahoo_spot_for_active; print(ingest_yahoo_spot_for_active.apply().get())"

# 4. Open the dashboard
open http://localhost:8000/

# 5. Open the Dagster UI
open http://localhost:3000/
```

---

## Repo layout

```
MarketIntel/
├── config/                 # Django project settings (base / dev / prod / test)
├── apps/
│   ├── core/               # Shared models (DLQ), middleware, health probes
│   ├── instruments/        # Source + Instrument (SCD Type 2 dimension)
│   ├── prices/             # Partitioned candle fact + spot quote table
│   ├── news/               # News articles with sentiment + full-text index
│   ├── api/                # DRF: serializers, viewsets, routers, throttle
│   └── dashboard/          # Interactive web dashboard (server-rendered)
├── pipelines/
│   ├── connectors/         # HTTP clients for third-party APIs
│   ├── tasks/              # Celery tasks (idempotent, retried, DLQ-backed)
│   └── orchestration/      # Dagster assets, jobs, schedules, sensors
├── warehouse/              # DuckDB analytics layer + sample SQL queries
├── docs/
│   ├── adr/                # Architecture Decision Records (7)
│   ├── data-model.md       # Schema reference
│   ├── pipelines.md        # Pipeline cadence + idempotency contract
│   ├── DEPLOY.md           # Tunnel / Railway / Kubernetes deploy paths
│   ├── RUNBOOK.md          # On-call playbook (alerts, common ops)
│   └── CONTRIBUTING.md     # Setup + workflow
├── tests/                  # Unit + integration (27 tests)
├── infra/
│   ├── postgres/           # Init SQL + post-migrate gold marts
│   ├── k8s/                # Kustomize base + staging/production overlays
│   ├── grafana/            # Dashboards + datasource provisioning
│   └── prometheus/         # Scrape config + alert rules
├── scripts/                # ops scripts (bootstrap, backfill, dlq, expose)
├── seeds/                  # Initial Source + Instrument data
├── manage.py
├── pyproject.toml
├── Dockerfile              # Multi-stage (dev + prod targets)
├── docker-compose.yml
├── railway.toml            # Railway deploy config
└── Makefile
```

---

## Production deploy

The platform is deploy-ready for three targets — see [`docs/DEPLOY.md`](docs/DEPLOY.md):

1. **Cloudflare quick tunnel** — share the local stack with a temporary HTTPS URL
   (`./scripts/expose_public.sh`).
2. **Railway** — managed deploy with persistent URL. `railway.toml` is committed.
3. **Kubernetes** — production-grade manifests in `infra/k8s/` (kustomize base
   + staging / production overlays).

---

## Status

Working portfolio demo:

- Real third-party connector against Yahoo Finance (no API key required for the
  public chart endpoint).
- 18 instruments tracked: 15 blue-chip US equities + 2 indices (S&P 500, NASDAQ
  Composite) + 1 ETF (SPY).
- 27 tests green (unit + integration with HTTP mocks via respx).
- Celery beat refreshes quotes every minute; gold matviews refresh every 5 min.
- Dagster materialises bronze → silver assets end-to-end (verified live).
- DLQ table with admin requeue action; partition health monitored on `/system/`.
