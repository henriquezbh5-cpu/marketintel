# MarketIntel — Architecture

> Decisions, trade-offs and architecture diagrams. For point-in-time decisions
> with their historical context see [`docs/adr/`](docs/adr/).

---

## 1. Non-functional objectives

| Attribute | Target |
|---|---|
| Ingestion throughput | 5K instruments × 1 min cadence sustained |
| API latency (p95) | < 200 ms for symbol+range queries |
| Data freshness | < 60 s from upstream for spot prices |
| Idempotency | 100% — re-running any window does not produce duplicates |
| Recovery | Manual backfill of any historical range via Dagster |
| Observability | Structured logs, Prometheus metrics, OTel traces |

---

## 2. Data layers (Medallion)

### Bronze — raw
- **Storage**: MinIO (S3-compatible) as gzip-compressed JSON Lines
- **Layout**: `s3://bronze/<source>/<entity>/dt=YYYY-MM-DD/hh=HH/<run_id>.jsonl.gz`
- **Immutable**: nothing is overwritten. The run_id distinguishes runs.
- **Why**: deterministic replay, audit, debugging of transformations.

### Silver — clean & normalised
- **Storage**: PostgreSQL 16
- **Schema**: separated from gold materialised views
- **Rules**: correct types, FKs to dimensions, deduplication, validation.
- **Loading**: `INSERT ... ON CONFLICT DO UPDATE` keyed on (source, external_id, ts).

### Gold — aggregates & marts
- **Storage**: PostgreSQL materialised views + DuckDB for heavy analytics
- **Refresh**: Dagster schedules / Celery beat (1m / 5m / 1h depending on the mart)
- **Why**: API queries < 200 ms without hitting the per-minute partitioned fact.

---

## 3. Dimensional model

```
                     ┌─────────────────┐
                     │   dim_source    │   (Yahoo Finance, Binance, ...)
                     └────────┬────────┘
                              │
                     ┌────────v────────┐
                     │ dim_instrument  │   SCD Type 2: tracks ticker change,
                     │ valid_from/to   │   rebrand, listing/delisting
                     │ is_current      │
                     └────────┬────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
       ┌──────v─────┐  ┌──────v─────┐  ┌──────v─────┐
       │ fact_price │  │ fact_trade │  │ fact_news  │
       │ partitioned│  │ partitioned│  │            │
       │ by month   │  │ by day     │  │            │
       └────────────┘  └────────────┘  └────────────┘
```

**Partitioning** (PostgreSQL declarative partitioning):
- `fact_price_candle` partitioned by `RANGE (ts)` monthly. Future partitions
  auto-created by a Celery maintenance task on the 25th of every month.
- BRIN index on `ts` (much cheaper than B-tree for append-only time-series).
- Composite B-tree on `(instrument_id, ts DESC)` for per-symbol queries.

**SCD Type 2 on `dim_instrument`**:
- `valid_from`, `valid_to`, `is_current` (partial unique index where `is_current = TRUE`).
- The service layer closes the previous version when a tracked attribute changes.

See [`docs/data-model.md`](docs/data-model.md) for full DDL.

---

## 4. Distributed processing

### Why Celery + Dagster (not just one)

These tools serve different purposes and complement each other:

| | Dagster | Celery |
|---|---|---|
| Model | Asset graph (declarative) | Task queue (imperative) |
| Granularity | Pipeline / dataset | Function / unit of work |
| Schedules / sensors | Yes, native | Beat (more limited) |
| Lineage / metadata | Yes, first-class | No |
| Massive parallelism | Limited | Unlimited (horizontal workers) |

**Pattern**: Dagster owns the asset DAG (`raw_prices` → `clean_prices` → `price_marts`).
Any asset that needs heavy fan-out (e.g. fetch 5K symbols) **delegates to Celery**
via `chord` / `group`. Dagster waits for the result and publishes the asset.

```python
# pipelines/orchestration/assets.py
@asset(partitions_def=DailyPartitionsDefinition(start_date="2024-01-01"))
def raw_prices(context):
    symbols = list_active_symbols()
    # Parallel fan-out via Celery
    results = group(
        fetch_prices_task.s(sym, context.partition_key)
        for sym in symbols
    ).apply_async()
    return results.get(timeout=600)
```

### Guarantees of every Celery task

Each `pipelines.tasks.*` task obeys:
1. **Idempotent**: natural key + `ON CONFLICT`. Re-running is safe.
2. **Retries with jitter**: `autoretry_for=(httpx.HTTPError,)`, `retry_backoff=True`,
   `retry_jitter=True`, `max_retries=5`.
3. **Time-bounded**: `soft_time_limit` always less than `time_limit`.
4. **Observable**: structlog with `task_id`, `source`, `symbol`, `partition`.
5. **Dead-letter**: when retries are exhausted, the failure is persisted to the
   `core_dead_letter_task` table for manual review / requeue.

---

## 5. Third-party connectors

### Design

```
pipelines/connectors/base.py            — Protocol + base with retries, rate limit, metrics
pipelines/connectors/yahoo_finance.py   — Equity quotes & OHLCV (no API key)
pipelines/connectors/binance.py         — Crypto OHLCV (alternate)
pipelines/connectors/coingecko.py       — Crypto spot prices (alternate)
pipelines/connectors/cryptopanic.py     — News with sentiment (alternate)
```

Every connector implements `BaseConnector` and provides:
- Endpoint methods that return typed dataclasses (no leaky upstream JSON in callers)
- Token-bucket rate limiting per instance
- Circuit breaker (closed / open / half-open with probe)
- Structured logs + Prometheus metrics on every request

### Why not vendor SDKs

- Full control over retries, rate limiting, observability
- Some SDKs are sync-only and block the event loop
- Versioning: the contract is ours, not the provider's. If Yahoo changes an
  endpoint, only the adapter touches it

---

## 6. API layer

### Stack
- DRF with `ModelViewSet` and `ReadOnlyModelViewSet`
- `django-filter` for typed query parameters
- `drf-spectacular` for OpenAPI 3.1 schema
- Authentication: API key with scope (read / write / admin); session auth for the admin

### Throttling
- Per API key, scoped per endpoint group
- Burst + sustained limits (`apps.api.throttling.APIKeyScopedThrottle`)

### Caching
- Redis backend with short TTL (60 s) for spot prices
- ETag / `Last-Modified` on time-series endpoints for incremental clients

### Pagination
- Cursor pagination for time-series (candles, news) — keyset-friendly
- Limit/offset for catalogue endpoints (instruments, sources)

---

## 7. Web dashboard

`apps/dashboard/` — server-rendered with Django templates, hydrated with
Alpine.js + Chart.js. Direct ORM access (no internal HTTP roundtrip), polling
JSON endpoints for live updates.

Pages:
- `/` Overview with KPIs, featured chart, top movers, watchlist, news, status
- `/markets/` All instruments table with live prices and inline sparklines
- `/markets/<symbol>/` Multi-resolution candle chart with 8 computed stats
- `/news/` Sentiment-filtered news feed
- `/system/` Pipeline health: freshness, DLQ, partitions, sources
- `/coverage/` Bullet-by-bullet mapping back to the role spec

---

## 8. Decisions taken (summary)

| ADR | Decision |
|---|---|
| 0001 | Django as backend, not FastAPI standalone |
| 0002 | Celery, not RQ or arq |
| 0003 | Dagster, not Airflow or Prefect |
| 0004 | Medallion bronze / silver / gold |
| 0005 | PostgreSQL declarative partitioning, not Citus or Timescale |
| 0006 | DuckDB as embedded analytical layer |
| 0007 | structlog + OTel, not stdlib logging directly |

---

## 9. What's missing for production

Honest about scope:

- [ ] Real auth (OIDC / SSO), today it's a simple API key
- [ ] Automated Postgres backups (pgBackRest or managed)
- [ ] Multi-tenancy (today it's single-tenant)
- [ ] CDC to sync to an external warehouse (Snowflake / BigQuery)
- [ ] Grafana alerting policies (latency, error rate, freshness)
- [ ] Embeddings + vector search pipeline for news (sketched, not implemented)
- [ ] Migrations gating in staging before production rollout
