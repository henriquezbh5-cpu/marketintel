#!/usr/bin/env bash
# End-to-end smoke test against a running stack.
# Usage: ./scripts/healthcheck.sh [base_url]
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"

check() {
    local name="$1"
    local url="$2"
    local expected="${3:-200}"
    local actual
    actual="$(curl -s -o /dev/null -w "%{http_code}" "$url" || echo "000")"
    if [[ "$actual" == "$expected" ]]; then
        printf "  \033[32m✔\033[0m %-30s %s (HTTP %s)\n" "$name" "$url" "$actual"
    else
        printf "  \033[31m✘\033[0m %-30s %s (HTTP %s, expected %s)\n" \
            "$name" "$url" "$actual" "$expected"
        exit 1
    fi
}

echo "Checking $BASE_URL..."
check "liveness"   "$BASE_URL/health/live/"
check "readiness"  "$BASE_URL/health/ready/"
check "metrics"    "$BASE_URL/metrics/"
check "openapi"    "$BASE_URL/api/schema/"
check "swagger"    "$BASE_URL/api/docs/"

echo "==> All checks passed."
