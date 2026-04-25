# Pipelines

> How data flows from third-party sources to the API. For the *why* of each
> piece see the ADRs in [`adr/`](adr/).

---

## End-to-end flow

```
┌──────────────┐  schedule   ┌───────────────┐  fan-out   ┌──────────────┐
│  Dagster     │────────────>│ asset:        │───────────>│ Celery group │
│  schedule    │             │ silver_*      │            │ ingest_*     │
└──────────────┘             └───────────────┘            └───────┬──────┘
                                                                  │
                                                                  v
                                                       ┌──────────────────┐
                                                       │ Connector        │
                                                       │ (httpx + RL +    │
                                                       │  circuit breaker)│
                                                       └────────┬─────────┘
                                                                │
                                  ┌─────────────────────────────┴───┐
                                  │                                 │
                          ┌───────v────────┐                ┌───────v───────┐
                          │ Bronze (MinIO) │                │ Silver        │
                          │ JSONL.gz       │                │ Postgres UPSERT│
                          └────────────────┘                └───────────────┘
```

---

## Cadences

| Pipeline | Cadence | Trigger |
|---|---|---|
| `sync_coingecko_catalog` | Daily at 03:00 UTC | Beat |
| `ingest_prices_for_active_instruments` | Every minute | Beat |
| `ingest_news_recent` | Every 5 minutes | Beat |
| `ingest_binance_klines` (per symbol) | On asset materialisation | Dagster job |
| `refresh_gold_marts` | Every 5 minutes | Beat |
| `ensure_future_partitions` | 25th of month, 00:00 UTC | Beat |

---

## Idempotency contract

Every ingestion task obeys these rules:

1. **Natural key first**: writes are `INSERT ... ON CONFLICT DO UPDATE` keyed
   on the upstream's id, not on autoincrement.
2. **Replay-safe**: re-running a task with the same args is identical to running
   it once. Re-running over an overlapping window updates rows in place.
3. **No side effects beyond DB / object storage**: tasks don't email, don't
   call out to Slack, don't do anything you'd regret on retry.
4. **Bounded**: `soft_time_limit < time_limit`. If a task can't finish in N
   seconds it's a bug, not a long-running job.

---

## Failure handling

```
upstream error / timeout
        │
        v
   typed exception (RateLimited, ConnectorError, CircuitOpen)
        │
        v
   Celery retries with exponential backoff + jitter (max 5)
        │
        v failed
   on_failure → DLQ + structured log + Prometheus counter
        │
        v
   ops inspects Flower / Grafana / DLQ table
        │
        v
   manual requeue with same args (idempotent, see above)
```

---

## Observability

Every task emits at minimum two log records:
- `task_start` with `task_id`, `task_name`, `run_id`, `kwargs`
- `task_done` (or `task_error`) on completion

Plus Prometheus counters (via `django-prometheus`):
- `celery_task_count{state, queue}`
- `connector_request_count{source, status}`
- `pipeline_rows_written{layer, table}`

OpenTelemetry traces (when `OTEL_EXPORTER_OTLP_ENDPOINT` is set) cover
HTTP requests across services.

---

## Backfills

Run a Dagster job with explicit partitions:

```bash
dagster asset materialize \
    --select silver_price_candles \
    --partition 2026-04-15
```

Or for a range:

```bash
for d in $(seq 0 30); do
    date_iso=$(date -u -d "2026-04-01 +$d days" +%Y-%m-%d)
    dagster asset materialize --select silver_price_candles --partition $date_iso
done
```

The asset's underlying Celery task is idempotent, so re-running over already-
ingested partitions is safe.

---

## Adding a new source

1. Create a `BaseConnector` subclass under `pipelines/connectors/`.
2. Add a `Source` row (fixture or migration).
3. Write the ingestion task under `pipelines/tasks/ingest.py`.
4. Wire a Dagster asset (bronze, then silver) under `pipelines/orchestration/assets.py`.
5. Add tests with `vcrpy` fixtures of upstream responses.
6. Document in this file.
