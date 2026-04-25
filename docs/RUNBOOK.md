# MarketIntel — Operations Runbook

Quick reference for on-call. For background see [`ARCHITECTURE.md`](../ARCHITECTURE.md).

---

## Top alerts

### `APIHighErrorRate`
The API is returning >5% 5xx for 10 minutes.

1. Check `/health/ready/` → if degraded, look at `checks` payload to find which dep failed.
2. Inspect Sentry for the dominant exception class.
3. Recent deploys? `kubectl rollout history deploy/web -n marketintel`.
4. If a deploy correlates → `kubectl rollout undo deploy/web -n marketintel`.
5. If postgres is the culprit → check `pg_stat_activity` for long queries; the
   serving path should be sub-second.

### `PipelineFreshnessStale`
No successful CoinGecko ingest in 5+ minutes.

1. Flower (`/flower`) → are workers consuming `ingest`?
2. Check Beat is alive: `kubectl logs deploy/beat -n marketintel`.
3. Connector tripped? Look for `connector_breaker_open_total` spikes in
   Grafana → if open, identify upstream issue (status page) and decide whether
   to keep it open or reset.
4. If everything looks healthy and the gauge is stale, the worker may be
   throwing silently. `kubectl logs -l component=worker --tail=200`.

### `DLQGrowing`
\>10 tasks dead-lettered in 15 min.

1. `python scripts/dlq_inspect.py list --limit 20` — what's failing?
2. Cluster by exception. If they're all the same upstream error, the issue
   is external; pause the schedule and wait, then requeue.
3. Genuine bug → fix forward, then `python scripts/dlq_inspect.py requeue <id>`
   in batches.

---

## Common ops

### Pause a schedule

```bash
kubectl exec deploy/beat -n marketintel -- \
    python manage.py shell -c \
    "from django_celery_beat.models import PeriodicTask; \
     PeriodicTask.objects.filter(name='ingest-prices-1m').update(enabled=False)"
```

### Backfill a date range

```bash
./scripts/backfill.sh 2026-04-01 2026-04-15
```

The underlying assets are idempotent so re-running over already-ingested
partitions is safe.

### Connect to Postgres

```bash
kubectl exec -it postgres-0 -n marketintel -- \
    psql -U marketintel -d marketintel
```

### Refresh a gold mart manually

```sql
REFRESH MATERIALIZED VIEW CONCURRENTLY gold.mv_top_movers_24h;
```

### Issue an API key

```bash
kubectl exec -it deploy/web -n marketintel -- \
    python scripts/issue_api_key.py <username> --scope read
```

### Add a new monthly partition manually

```bash
kubectl exec deploy/web -n marketintel -- python manage.py shell -c \
    "from pipelines.tasks.maintenance import ensure_future_partitions; \
     print(ensure_future_partitions.apply().get())"
```

---

## Recovery

### Lost a partition table

Bronze data is the recovery source.

```bash
# 1. Recreate the partition
ensure_future_partitions(months_ahead=1)

# 2. Replay the affected day from bronze (Dagster)
dagster asset materialize --select silver_price_candles --partition 2026-04-15
```

### Corrupted matview

```sql
DROP MATERIALIZED VIEW gold.mv_top_movers_24h;
```

Re-run `infra/postgres/init/03_gold_marts.sql` and trigger
`refresh_gold_marts`.

---

## Useful queries

### Latest ingest per source

```sql
SELECT source.code, max(spot.ts) AS last_seen
FROM fact_price_spot spot
JOIN instruments_source source ON source.id = spot.source_id
GROUP BY source.code;
```

### Slowest API endpoints (last hour)

```sql
SELECT view, count(*), avg(duration_ms)
FROM (
    -- replace with your APM data; placeholder
    SELECT 'view' AS view, 100 AS duration_ms
) x
GROUP BY view
ORDER BY avg(duration_ms) DESC
LIMIT 10;
```

### Partition sizes

```sql
SELECT
    relname AS partition,
    pg_size_pretty(pg_total_relation_size(c.oid)) AS size
FROM pg_class c
JOIN pg_inherits i ON i.inhrelid = c.oid
JOIN pg_class p ON p.oid = i.inhparent
WHERE p.relname = 'fact_price_candle'
ORDER BY pg_total_relation_size(c.oid) DESC;
```
