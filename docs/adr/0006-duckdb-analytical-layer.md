# ADR 0006 — DuckDB as embedded analytical layer

**Status**: Accepted · 2026-04-24

## Context

Some queries we want to answer (correlation matrices over months of candles,
factor exposures across hundreds of symbols, ad-hoc analyses) are textbook
OLAP scans. Running them on Postgres works but starves the OLTP path: the
same connection pool serves the API and the analyst, the same buffer cache
gets thrashed.

## Decision

Use **DuckDB embedded inside worker processes** for analytical workloads.
DuckDB reads Postgres tables via the `postgres_scanner` extension and
pushes filters down so partition pruning still applies.

Analyst-facing access pattern:

```python
from warehouse import analytical_db, register_views

with analytical_db() as conn:
    register_views(conn)
    df = conn.execute(open("warehouse/queries/correlation_matrix.sql").read(),
                      {"resolution": "1h", "since": ..., "symbols": (...)}
                     ).fetchdf()
```

## Rationale

- **Isolation**: heavy scans don't run in the OLTP server. They run in a
  worker with its own memory budget.
- **Speed**: DuckDB is a vectorised columnar engine. For analytical scans
  it's 10–100x faster than Postgres on the same data.
- **No infra**: it's a library. No second cluster to operate.
- **Postgres scanner**: we keep the canonical data in Postgres, DuckDB reads
  it on demand. No ETL into a separate warehouse for this scale.

## Trade-offs

- DuckDB is single-node. If our analytical workload grows beyond what one
  worker can handle we'd graduate to a real warehouse (Snowflake/BigQuery
  via CDC).
- Cross-connection consistency: DuckDB sees Postgres at query time, not as
  a transactional snapshot tied to other queries. Acceptable for analytics.
- Yet another tool. We mitigate by keeping all DuckDB usage in `warehouse/`
  with a single helper.

## Alternatives considered

- **A real warehouse (Snowflake/BigQuery)**: overkill at our scale, and adds
  a CDC pipeline.
- **ClickHouse**: tempting (we'd love columnar storage for candles) but adds
  another database to operate.
- **Run analytical queries on Postgres**: works to a point, but OLTP and
  analytics share resources. Bad day on the analyst's notebook = bad day
  for the API. Deal-breaker.
