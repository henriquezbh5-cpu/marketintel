# MarketIntel

Plataforma de datos de mercado escalable. Ingiere, normaliza y sirve datos de proveedores
externos (CoinGecko, Binance, CryptoPanic) a través de pipelines distribuidos, almacena
en un modelo dimensional con particionamiento temporal, y expone una API REST para
producto y consumo analítico.

Construida como demostración del rol de **Senior Data / Backend Engineer** en una
plataforma de inteligencia de mercado.

---

## Capacidades

| Bullet del rol | Cómo se cubre en MarketIntel |
|---|---|
| Backend Python/Django escalable | Django 5 + DRF, settings por entorno, async views donde aplica |
| Pipelines de ingesta de terceros | Conectores en `pipelines/connectors/` con retries, rate-limiting, idempotencia |
| Modelado y diseño de esquemas | Modelo Medallion (bronze/silver/gold), SCD2 en dimensiones, partitioning por tiempo en hechos |
| Procesamiento async / distribuido | Celery + Redis (workers, beat, prioridades, dead-letter), task graph en Dagster |
| Orquestación / storage / warehousing | Dagster (assets, schedules, sensors), MinIO (S3) para raw, PostgreSQL para serving, DuckDB para analítica |
| Capa de aplicación | API REST con DRF, autenticación por API key, paginación, filtering, throttling |
| Estrategia y arquitectura técnica | ADRs en `docs/adr/`, diagramas en `docs/architecture/` |

---

## Stack

- **Lenguaje**: Python 3.12
- **Backend**: Django 5.0, Django REST Framework
- **Async**: Celery 5 + Redis (broker + result backend)
- **Orquestación**: Dagster (assets, sensors, schedules)
- **Storage**: PostgreSQL 16 (OLTP + serving), MinIO (raw S3), DuckDB (analytics)
- **HTTP**: httpx (async-first)
- **Observabilidad**: structlog + OpenTelemetry hooks, Prometheus metrics
- **Testing**: pytest, pytest-django, factory-boy, vcrpy para fixtures de APIs externas
- **Infra**: Docker Compose para dev, Dockerfile multi-stage para prod

---

## Arquitectura en una página

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Third-party    │    │   Bronze (raw)  │    │  Silver (clean) │
│   APIs          │───>│   MinIO/JSONL   │───>│   PostgreSQL    │
│ CoinGecko, etc. │    │   immutable     │    │   normalized    │
└─────────────────┘    └─────────────────┘    └────────┬────────┘
                                                       │
                              ┌────────────────────────┼─────────────┐
                              │                        │             │
                       ┌──────v──────┐          ┌──────v──────┐  ┌───v────┐
                       │   Gold      │          │   API REST  │  │ DuckDB │
                       │ aggregates  │          │   Django    │  │analytic│
                       │  (matviews) │          │    DRF      │  │  layer │
                       └─────────────┘          └─────────────┘  └────────┘
```

Orquestador (Dagster) coordina: ingest → normalize → quality → publish.
Worker pool (Celery) ejecuta tareas paralelas por símbolo/instrumento.

Ver detalle en [`ARCHITECTURE.md`](ARCHITECTURE.md).

---

## Quickstart

```bash
# 1. Levantar stack completo
cp .env.example .env
docker compose up -d

# 2. Migraciones y seed
docker compose exec web python manage.py migrate
docker compose exec web python manage.py loaddata seeds/instruments.json

# 3. Disparar primera ingesta
docker compose exec web python manage.py ingest --source coingecko --symbols BTC,ETH

# 4. Ver Dagster UI
open http://localhost:3000

# 5. Ver API
curl http://localhost:8000/api/v1/instruments/
```

---

## Estructura

```
MarketIntel/
├── config/                # Django project settings (base/dev/prod)
├── apps/
│   ├── core/              # Modelos compartidos, mixins, abstract bases
│   ├── instruments/       # Catálogo de instrumentos (dim, SCD2)
│   ├── prices/            # Time-series de precios (fact, partitioned)
│   ├── news/              # Noticias y sentimiento
│   └── api/               # DRF: serializers, viewsets, routers, throttle
├── pipelines/
│   ├── connectors/        # Clientes HTTP a APIs externas
│   ├── tasks/             # Celery tasks (idempotentes)
│   ├── orchestration/     # Dagster assets, jobs, schedules, sensors
│   └── transformations/   # SQL/Python de normalización
├── warehouse/             # DuckDB models + queries analíticas
├── docs/
│   ├── adr/               # Architecture Decision Records
│   ├── architecture/      # Diagramas
│   ├── data-model.md
│   └── pipelines.md
├── tests/                 # Unit + integration + e2e
├── infra/                 # docker-compose, Dockerfile, k8s manifests
├── manage.py
├── pyproject.toml
└── docker-compose.yml
```

---

## Estado del proyecto

Portfolio funcional. Conectores reales contra APIs públicas (sin keys requeridas
para CoinGecko free tier). Dagster orquesta el grafo completo. Celery procesa
ingestas paralelas con backoff y deduplicación.

Pruebas: unit + integration con fixtures grabadas (vcrpy) para los conectores.
