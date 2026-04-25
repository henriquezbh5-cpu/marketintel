# ADR 0003 — Dagster for asset-based orchestration

**Status**: Accepted · 2026-04-24

## Context

We need orchestration for the bronze → silver → gold pipeline graph: defining
dependencies, scheduling, sensing external state, retrying, partitioning by
time, and observing lineage. Candidates: Airflow, Prefect, Dagster, custom.

## Decision

**Dagster** for orchestration, used alongside Celery for fan-out (see ADR 0002).

## Rationale

- **Asset-based model**: we think in datasets, not tasks. Dagster's `@asset`
  matches that shape directly. Lineage and metadata are first-class.
- **Partitions**: built-in time partitioning (daily, monthly) — exactly what
  we need for backfills.
- **Sensors**: external-state-driven runs (e.g. partition_sensor) without
  cron polling.
- **Dev experience**: `dagster dev` ships a UI you can run locally to inspect
  asset materialisations and lineage.
- **Type-checked I/O**: Dagster's I/O managers + asset types catch class
  mismatches that Airflow would silently pass.

## Trade-offs

- Younger than Airflow; smaller community. We accept the trade-off because
  the asset model fits us better than DAG-of-tasks.
- Dagster can run massive parallelism with executors but it's not designed
  for thousands of tiny tasks per minute. We delegate that to Celery (the
  asset uses `group()` of Celery signatures).
- Two systems to operate (Dagster + Celery). We split responsibilities
  cleanly: Dagster owns the graph, Celery owns the workers.

## Alternatives considered

- **Airflow**: industry default. Heavy, task-centric not asset-centric, weaker
  developer ergonomics. Ruled out.
- **Prefect 2**: similar to Dagster. Slightly weaker partitioning and lineage
  story. Close call; Dagster won on the asset model.
- **Custom (Celery Beat + DB-tracked DAG)**: tempting at first, but reinvents
  scheduling, retries, observability. Not justified.
