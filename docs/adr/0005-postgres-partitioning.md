# ADR 0005 — Postgres declarative partitioning for time-series facts

**Status**: Accepted · 2026-04-24

## Context

`fact_price_candle` grows by ~5K rows/min × resolutions × symbols. Within a
year we'd be in the multi-billion-row range. We need a strategy that keeps
typical queries (last-N candles for symbol X over a day or week) fast and
operations (vacuum, drop old data, backfill) tractable.

## Decision

Use **Postgres 16 declarative partitioning** with `PARTITION BY RANGE (ts)`,
monthly granularity. Partition creation managed by a Celery maintenance task
(`ensure_future_partitions`) running on the 25th of every month.

Index strategy on each partition:
- BRIN on `ts` (massively cheaper than B-tree for append-only time-series).
- B-tree on `(instrument_id, ts DESC)` for the dominant query pattern.
- Unique constraint on `(instrument_id, source_id, resolution, ts)` for dedup.

## Rationale

- **Pruning**: queries with `ts BETWEEN ... AND ...` only touch relevant
  partitions. We measured: month-long candle scans drop from O(seconds) to
  O(ms) once ranges fit a single partition.
- **Drop = unlink**: archiving last year's data is `DETACH PARTITION` + drop,
  no DELETE. Storage management at the file level.
- **No extra extension required**: pure stock Postgres. We avoid TimescaleDB's
  licensing footnotes and Citus's distribution complexity.
- **BRIN over B-tree on ts**: ~100x smaller, ideal for the strictly-sorted
  insert pattern of time-series. We pay a small cost on out-of-order writes
  (rare in our case).

## Trade-offs

- Maintenance burden: partitions must be pre-created. We automate via
  `ensure_future_partitions`, but if it fails silently we'd start dropping
  inserts. Monitoring covers this with a synthetic check (write probe row,
  verify it lands).
- Foreign keys to partitioned tables are not supported. We accept this; the
  `instrument_id` reference is to a regular table, the FK lives there.
- Can't use Django's `unique_together` with the partition key portably.
  We declare the unique constraint by hand in the partition migration.

## Alternatives considered

- **TimescaleDB**: better automation (compression, continuous aggregates),
  but adds an extension dependency. License is fine for our use today;
  re-evaluate if compression becomes worth it.
- **Citus distributed**: solves a problem we don't have yet (multi-node
  scale-out). Premature.
- **No partitioning, big indexes**: works to ~500M rows, then index
  maintenance becomes the bottleneck. Not future-proof.
