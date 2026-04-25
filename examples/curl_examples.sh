#!/usr/bin/env bash
# Example cURL calls against MarketIntel.
# Set BASE and API_KEY before running.
set -euo pipefail

BASE="${BASE:-http://localhost:8000}"
API_KEY="${API_KEY:?set API_KEY}"
H="X-API-Key: $API_KEY"

echo "=== Sources ==="
curl -fsSL -H "$H" "$BASE/api/v1/sources/" | jq .

echo "=== Instruments (top 5) ==="
curl -fsSL -H "$H" "$BASE/api/v1/instruments/?page_size=5" | jq .

echo "=== Candles for BTC (last hour, 1m) ==="
TS_FROM=$(date -u -d '-1 hour' +%Y-%m-%dT%H:%M:%SZ)
curl -fsSL -H "$H" \
    "$BASE/api/v1/candles/?symbol=BTC&resolution=1m&ts_from=$TS_FROM&page_size=10" | jq .

echo "=== Spot for BTC ==="
curl -fsSL -H "$H" "$BASE/api/v1/spot/BTC/" | jq .

echo "=== Negative news on BTC ==="
curl -fsSL -H "$H" "$BASE/api/v1/news/?symbol=BTC&sentiment=negative&page_size=5" | jq .

echo "=== OpenAPI schema ==="
curl -fsSL "$BASE/api/schema/" | head -50
