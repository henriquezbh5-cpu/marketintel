#!/usr/bin/env bash
# Bootstrap a fresh dev environment.
#   - Build images, start the stack, run migrations, load seeds, ensure buckets.
# Usage: ./scripts/bootstrap.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Copying .env.example to .env (if missing)"
[[ -f .env ]] || cp .env.example .env

echo "==> Starting stack"
docker compose up -d

echo "==> Waiting for postgres"
until docker compose exec -T postgres pg_isready -U marketintel >/dev/null 2>&1; do
    sleep 1
done

echo "==> Running migrations"
docker compose exec -T web python manage.py migrate --noinput

echo "==> Loading seeds"
docker compose exec -T web python manage.py loaddata seeds/sources.json seeds/instruments.json

echo "==> Ensuring future partitions"
docker compose exec -T web python manage.py shell -c \
    "from pipelines.tasks.maintenance import ensure_future_partitions; ensure_future_partitions.apply()"

echo "==> Done."
echo "Web:     http://localhost:8000"
echo "Swagger: http://localhost:8000/api/docs/"
echo "Dagster: http://localhost:3000"
echo "Flower:  http://localhost:5555"
echo "MinIO:   http://localhost:9001 (minioadmin/minioadmin)"
