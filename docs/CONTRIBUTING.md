# Contributing

## Setup

```bash
git clone <repo>
cd MarketIntel
make install-dev
make up
make migrate
make seed
```

Stack:
- Web:     http://localhost:8000
- Swagger: http://localhost:8000/api/docs/
- Dagster: http://localhost:3000
- Flower:  http://localhost:5555
- MinIO:   http://localhost:9001 (`minioadmin`/`minioadmin`)

## Workflow

1. Branch off `main`: `git checkout -b feat/your-thing`.
2. Code. Pre-commit runs ruff + format + secrets scan on every commit.
3. Add or update tests. CI requires `pytest` to pass.
4. Update [`docs/data-model.md`](data-model.md) if you touched a model.
5. If the change deserves a record → add an ADR under [`docs/adr/`](adr/).
6. Open a PR using the template. CODEOWNERS gates schema-touching changes.

## Testing

```bash
make test               # everything
make test-unit          # fast, no DB
make test-integration   # needs Postgres + Redis
```

Integration tests run against the dockerised Postgres in CI. Locally you can
either run `make up` first, or rely on `pytest`'s autocreated test DB.

## Adding a new connector

See [`docs/pipelines.md`](pipelines.md#adding-a-new-source). Recap:

1. New file under `pipelines/connectors/<name>.py` extending `BaseConnector`.
2. New Source row (fixture under `seeds/`).
3. Ingestion task under `pipelines/tasks/ingest.py`.
4. Asset under `pipelines/orchestration/assets.py`.
5. Tests under `tests/test_connector_<name>.py` using `respx` or `vcrpy`.
6. Document in `docs/pipelines.md`.

## Performance changes

If you change anything in the API hot path or pipeline write path, attach
benchmark numbers (before/after) to the PR. EXPLAIN ANALYZE for SQL changes.

## Commit style

Conventional commits in English (`feat:`, `fix:`, `chore:`, `docs:`, `refactor:`, `test:`).
Include the relevant scope when it helps: `feat(prices): partition fact table`.
