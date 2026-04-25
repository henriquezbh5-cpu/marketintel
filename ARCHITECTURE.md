# MarketIntel — Architecture

> Decisiones, trade-offs y diagramas de arquitectura. Para decisiones puntuales
> con su contexto histórico ver [`docs/adr/`](docs/adr/).

---

## 1. Objetivos no funcionales

| Atributo | Target |
|---|---|
| Throughput de ingesta | 5K instrumentos × 1 min cadence sostenida |
| Latencia API (p95) | < 200 ms para queries por símbolo y rango |
| Frescura de datos | < 60 s desde fuente para precios spot |
| Idempotencia | 100% — re-ejecutar cualquier ventana no genera duplicados |
| Recuperación | Backfill manual de cualquier rango histórico via Dagster |
| Observabilidad | Logs estructurados, métricas Prometheus, traces OTel |

---

## 2. Capas de datos (Medallion)

### Bronze — raw
- **Storage**: MinIO (S3-compat) en JSON Lines comprimido (gzip)
- **Layout**: `s3://bronze/<source>/<entity>/dt=YYYY-MM-DD/hh=HH/<run_id>.jsonl.gz`
- **Inmutable**: nada se sobrescribe. El run_id distingue ejecuciones.
- **Razón**: replay determinista, auditoría, debugging de transformaciones.

### Silver — clean & normalized
- **Storage**: PostgreSQL 16
- **Schema**: `silver` (separado de `public` que sirve API)
- **Reglas**: tipos correctos, FKs a dimensiones, deduplicación, validación.
- **Carga**: `INSERT ... ON CONFLICT DO UPDATE` con clave natural por (source, external_id, ts).

### Gold — aggregates & marts
- **Storage**: PostgreSQL materialized views + DuckDB para analítica pesada
- **Refresh**: Dagster schedules (1m / 5m / 1h dependiendo del mart)
- **Razón**: consultas API < 200 ms sin pegarle al fact partitionado por minuto.

---

## 3. Modelo dimensional

```
                     ┌─────────────────┐
                     │   dim_source    │   (CoinGecko, Binance, ...)
                     └────────┬────────┘
                              │
                     ┌────────v────────┐
                     │ dim_instrument  │   SCD2: tracks rebrand, ticker
                     │ valid_from/to   │   change, listing/delisting
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

**Particionamiento** (PostgreSQL declarative partitioning):
- `fact_price` particionada por `RANGE (ts)` mensual. Auto-creación de particiones
  vía Dagster sensor que corre el día 25 de cada mes.
- Índices BRIN sobre `ts` (mucho más baratos que B-tree para append-only time-series).
- B-tree compuesto sobre `(instrument_id, ts DESC)` para queries por símbolo.

**SCD2 en dim_instrument**:
- `valid_from`, `valid_to`, `is_current` (parcial-indexado donde `is_current=true`).
- Trigger que cierra el registro previo al insertar uno nuevo con la misma natural key.

Ver [`docs/data-model.md`](docs/data-model.md) para DDL completo.

---

## 4. Procesamiento distribuido

### Por qué Celery + Dagster (no uno solo)

Son herramientas con propósitos distintos que se complementan:

| | Dagster | Celery |
|---|---|---|
| Modelo | Asset graph (declarativo) | Task queue (imperativo) |
| Granularidad | Pipeline / dataset | Función / unidad de trabajo |
| Schedules / sensors | Sí, nativo | Beat (más limitado) |
| Lineage / metadata | Sí, first-class | No |
| Paralelismo masivo | Limitado | Ilimitado (workers horizontales) |

**Patrón**: Dagster define el DAG de assets (`raw_prices` → `clean_prices` → `price_marts`).
Cada asset que requiere paralelismo masivo (ej. fetch de 5K símbolos) **delega a
Celery** vía `chord`/`group`. Dagster espera el resultado y publica el asset.

```python
# pipelines/orchestration/assets.py
@asset(partitions_def=DailyPartitionsDefinition(start_date="2024-01-01"))
def raw_prices(context):
    symbols = list_active_symbols()
    # Fan-out paralelo via Celery
    results = group(
        fetch_prices_task.s(sym, context.partition_key)
        for sym in symbols
    ).apply_async()
    return results.get(timeout=600)
```

### Garantías de las tasks Celery

Cada `pipelines.tasks.*` cumple:
1. **Idempotente**: clave natural + `ON CONFLICT`. Re-ejecutar es seguro.
2. **Retries con jitter**: `autoretry_for=(httpx.HTTPError,)`, `retry_backoff=True`,
   `retry_jitter=True`, `max_retries=5`.
3. **Time-bounded**: `soft_time_limit` siempre menor que `time_limit`.
4. **Observable**: structlog con `task_id`, `source`, `symbol`, `partition`.
5. **Dead-letter**: si excede retries, va a queue `dlq` para inspección manual.

---

## 5. Conectores a terceros

### Diseño

```
pipelines/connectors/base.py        — Protocol + base con retries, rate limit, OTel
pipelines/connectors/coingecko.py   — Adapter
pipelines/connectors/binance.py     — Adapter
pipelines/connectors/cryptopanic.py — Adapter
```

Cada conector implementa `BaseConnector` con:
- `fetch(entity, params) -> AsyncIterator[dict]` — streaming de raw rows
- `normalize(raw) -> NormalizedRecord` — pydantic model con schema validado
- `rate_limit` — token bucket por API (configurable por env)
- `circuit_breaker` — abre tras N fallos consecutivos, half-open con probe

### Por qué no SDK oficiales

- Control total sobre retries, rate limit, observabilidad.
- Algunos SDKs no son async; bloquean event loop.
- Versionado: el contrato es nuestro, no del proveedor. Si CoinGecko cambia un
  endpoint solo tocamos el adapter.

---

## 6. API layer

### Stack
- DRF con `ModelViewSet` para CRUD básicos.
- `django-filter` para query params tipados.
- `drf-spectacular` para OpenAPI 3.1 schema.
- Autenticación: API key con scope (read vs write). JWT futuro si llega frontend.

### Throttling
- Por API key, configurable por scope.
- Burst + sustained (DRF `ScopedRateThrottle`).

### Cacheo
- `cache_page` en endpoints de catálogo (instrumentos, sources).
- Redis backend con TTL corto (60s) para precios spot.
- ETag/`Last-Modified` en endpoints time-series para clientes incrementales.

---

## 7. Decisiones tomadas (resumen)

| ADR | Decisión |
|---|---|
| 0001 | Django como backend, no FastAPI standalone |
| 0002 | Celery, no RQ ni arq |
| 0003 | Dagster, no Airflow ni Prefect |
| 0004 | Medallion bronze/silver/gold |
| 0005 | PostgreSQL declarative partitioning, no Citus ni Timescale |
| 0006 | DuckDB como capa analítica embebida |
| 0007 | structlog + OTel, no logging stdlib directo |

---

## 8. Lo que falta para producción

Honestidad sobre el alcance:

- [ ] Auth real (OIDC / SSO), hoy es API key simple.
- [ ] Backups automatizados de Postgres (pgBackRest).
- [ ] Multi-tenancy (hoy es single-tenant).
- [ ] CDC para sincronizar a un warehouse externo (Snowflake/BigQuery).
- [ ] Alerting policies en Grafana (latencia, error rate, freshness).
- [ ] Pipeline de embeddings + vector search para news (esbozado, no implementado).
- [ ] CI/CD completo con migrations gating en staging.
