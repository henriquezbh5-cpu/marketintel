# ADR 0001 — Django as the backend framework

**Status**: Accepted · 2026-04-24

## Context

We need a Python backend that hosts both the API layer and the application
glue around our pipelines (admin, auth, ORM-backed services). Realistic
candidates: Django, FastAPI, Flask + ad-hoc components.

## Decision

We use **Django 5 + DRF** as the primary backend. Pipelines (Celery, Dagster)
import Django models directly to read/write the same database.

## Rationale

- **Batteries included**: ORM, migrations, admin, auth, sessions. Time saved
  on plumbing goes into pipelines instead.
- **DRF**: mature REST patterns (viewsets, throttle, filter, OpenAPI schema)
  beat anything we'd build over FastAPI in the time available.
- **ORM consistency**: pipelines and API share the same models — no duplicated
  SQLAlchemy/Django split.
- **Admin**: free CRUD UI for ops on dimensions (Sources, Instruments) without
  building a console.
- **Maturity**: deployment patterns, security defaults, ecosystem.

## Trade-offs

- Django's ORM is sync-first. Async views are limited; for the low-latency
  endpoints we plan to use Postgres connection pooling and aggressive caching
  rather than going async-first.
- Heavy compute (correlation matrices, backtests) doesn't run in Django — it
  runs in DuckDB embedded in workers. Django stays focused on serving + writes.
- Lock-in: hard to swap to FastAPI later without rewriting auth/permissions.
  We accept it; the productivity gain outweighs the option value.

## Alternatives considered

- **FastAPI + SQLAlchemy**: faster async path but every cross-cutting concern
  (auth, admin, migrations) becomes a separate decision. More velocity now,
  more decisions later. Ruled out.
- **Flask**: too thin; we'd reinvent half of Django.
