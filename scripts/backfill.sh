#!/usr/bin/env bash
# Backfill candles via Dagster across a date range.
# Usage: ./scripts/backfill.sh 2026-04-01 2026-04-15
set -euo pipefail

START="${1:-}"
END="${2:-}"

if [[ -z "$START" || -z "$END" ]]; then
    echo "usage: $0 <YYYY-MM-DD> <YYYY-MM-DD>" >&2
    exit 1
fi

current="$START"
while [[ "$current" < "$END" || "$current" == "$END" ]]; do
    echo "==> Materialising silver_price_candles for $current"
    docker compose exec -T dagster dagster asset materialize \
        --select silver_price_candles \
        --partition "$current"
    current=$(date -u -d "$current + 1 day" +%Y-%m-%d)
done

echo "==> Backfill done."
