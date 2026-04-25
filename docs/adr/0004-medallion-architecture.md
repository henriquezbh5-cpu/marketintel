# ADR 0004 — Medallion (bronze / silver / gold) data layout

**Status**: Accepted · 2026-04-24

## Context

We ingest data from multiple third-party sources with their own quirks
(rate limits, schema changes, occasional bad rows). We need a layout that
lets us:
1. Reproduce any historical state from raw inputs.
2. Serve clean, normalised data to the API and downstream consumers.
3. Pre-aggregate hot queries without coupling them to OLTP load.

## Decision

We adopt a Medallion architecture:

| Layer | Storage | Purpose | Mutability |
|---|---|---|---|
| Bronze | MinIO/S3 (JSONL.gz) | Raw upstream payloads, immutable | Append-only |
| Silver | PostgreSQL | Normalised, deduplicated, FK-validated | UPSERT idempotent |
| Gold | PostgreSQL matviews + DuckDB | Aggregations, marts, analytics | Refreshed on schedule |

## Rationale

- **Bronze as the source of truth**: any silver row is reproducible from
  bronze if we ever change a transformation. Replays are deterministic
  thanks to the run_id + partition layout.
- **Silver in Postgres**: API queries need joins, indexes, transactions.
  Postgres is the right place. Idempotent UPSERTs handle out-of-order /
  late data.
- **Gold matviews**: hot dashboard queries (top movers, volume leaders) hit
  refreshed matviews so the OLTP path stays cool. DuckDB handles the heavy
  cross-table analytical queries (correlation matrices, factor exposures).

## Trade-offs

- Three layers means three places to evolve when we change a column. Mitigated
  by versioning transformations and keeping bronze immutable.
- MinIO/S3 round-trips add latency; we don't read bronze on the API path.
- Gold matviews need UNIQUE indexes for `REFRESH CONCURRENTLY` — minor friction.

## Alternatives considered

- **Skip bronze, write straight to silver**: cheap, but loses the replay
  property. We've been bitten by upstream silently mutating their `id`
  semantics — bronze is the difference between recovering in 10 minutes
  and rewriting a connector.
- **Lakehouse (Iceberg/Delta)**: overkill for our volume today. We can graduate
  bronze to Iceberg later if scan patterns demand it.
