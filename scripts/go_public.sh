#!/usr/bin/env bash
# One-shot: publish to GitHub + harden + expose via Cloudflare tunnel.
#
# Run from the repo root:
#     bash scripts/go_public.sh
#
# What it does:
#   1. Push this repo to github.com/<user>/marketintel as PUBLIC
#   2. Toggle EXPOSE_ADMIN/EXPOSE_METRICS off in .env (safety)
#   3. Restart web with the hardened flags
#   4. Launch two Cloudflare quick tunnels (API + Dagster)
#
# Stop the tunnels with Ctrl+C. The PC must stay on for them to keep working.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# ─── 1. GitHub ─────────────────────────────────────────────────
if ! gh repo view marketintel >/dev/null 2>&1; then
    echo "==> Creating public GitHub repo and pushing..."
    gh repo create marketintel --public --source=. --push \
        --description "Market intelligence data platform — Django + Celery + Dagster + Postgres partitioning + DuckDB. Senior Data/Backend Engineer portfolio."
    echo "==> Repo: $(gh repo view --json url --jq .url)"
else
    echo "==> Repo already exists: $(gh repo view --json url --jq .url)"
    git push -u origin main 2>&1 | tail -3 || true
fi

# ─── 2. Harden .env ────────────────────────────────────────────
echo "==> Hardening: EXPOSE_ADMIN=False, EXPOSE_METRICS=False"
sed -i 's/^EXPOSE_ADMIN=.*/EXPOSE_ADMIN=False/' .env
sed -i 's/^EXPOSE_METRICS=.*/EXPOSE_METRICS=False/' .env
grep -q "^EXPOSE_ADMIN=" .env || echo "EXPOSE_ADMIN=False" >> .env
grep -q "^EXPOSE_METRICS=" .env || echo "EXPOSE_METRICS=False" >> .env

# ─── 3. Restart web with new flags ─────────────────────────────
echo "==> Restarting web container..."
docker compose restart web >/dev/null
sleep 8
echo "==> /admin/ should now be 404:"
curl -sS -o /dev/null -w "    HTTP %{http_code}\n" http://localhost:8000/admin/
echo "==> /api/v1/sources/ should still respond:"
curl -sS -o /dev/null -w "    HTTP %{http_code}\n" \
    -H "X-API-Key: dummy" http://localhost:8000/api/v1/sources/

# ─── 4. Launch tunnels ─────────────────────────────────────────
CLOUDFLARED="${CLOUDFLARED:-/c/Users/benit/bin/cloudflared.exe}"
if [[ ! -x "$CLOUDFLARED" ]]; then
    echo "==> cloudflared not at $CLOUDFLARED — install with:"
    echo "    curl -sL -o ~/bin/cloudflared.exe \\"
    echo "      https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo " Launching public tunnels. Public URLs will print below."
echo " Stop with Ctrl+C. Share the trycloudflare.com links."
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Run both tunnels in foreground with prefixed output so URLs are easy to spot.
"$CLOUDFLARED" tunnel --no-autoupdate --url http://localhost:8000 \
    2>&1 | sed -u 's/^/[API ]      /' &
API_PID=$!

"$CLOUDFLARED" tunnel --no-autoupdate --url http://localhost:3100 \
    2>&1 | sed -u 's/^/[DAGSTER]   /' &
DAGSTER_PID=$!

trap 'kill $API_PID $DAGSTER_PID 2>/dev/null; exit 0' INT TERM
wait
