#!/usr/bin/env bash
# Expose the running stack publicly via Cloudflare Quick Tunnels.
#
# Usage:
#   ./scripts/expose_public.sh           # API + Dagster
#   ./scripts/expose_public.sh api       # only API
#   ./scripts/expose_public.sh dagster   # only Dagster
#
# Prereqs: cloudflared in PATH (pre-installed at ~/bin/cloudflared.exe on this box).
# The tunnel URLs are ephemeral: a fresh https://*.trycloudflare.com hostname
# every time, no signup, no rate limit. Stop with Ctrl+C.
#
# Hardening for public exposure:
#   - EXPOSE_ADMIN=false   → /admin is unmounted
#   - EXPOSE_METRICS=false → /metrics is unmounted
# Set these in .env before running, then `docker compose restart web`.
set -euo pipefail

CLOUDFLARED="${CLOUDFLARED:-cloudflared}"
if ! command -v "$CLOUDFLARED" >/dev/null 2>&1; then
    if [[ -x /c/Users/benit/bin/cloudflared.exe ]]; then
        CLOUDFLARED="/c/Users/benit/bin/cloudflared.exe"
    else
        echo "cloudflared not found. Download:" >&2
        echo "  curl -sL -o ~/bin/cloudflared.exe \\" >&2
        echo "    https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe" >&2
        exit 1
    fi
fi

target="${1:-both}"

run_tunnel() {
    local name="$1" url="$2"
    echo "==> Starting tunnel for $name → $url"
    "$CLOUDFLARED" tunnel --no-autoupdate --url "$url" 2>&1 \
        | tee "/tmp/cf-${name}.log" \
        | grep --line-buffered -E "trycloudflare|ERR" &
}

case "$target" in
    api)      run_tunnel api     http://localhost:8000 ;;
    dagster)  run_tunnel dagster http://localhost:3100 ;;
    both)
        run_tunnel api     http://localhost:8000
        run_tunnel dagster http://localhost:3100
        ;;
    *) echo "usage: $0 [api|dagster|both]"; exit 1 ;;
esac

echo ""
echo "Tunnels are starting. Public URLs will print above shortly."
echo "Press Ctrl+C to stop."
wait
