# Deployment

Three deployment paths, ordered by effort:

1. **Quick Tunnel** — share a temporary public URL (5 minutes, free, no signup)
2. **Railway** — managed deploy, persistent URL (15 minutes, free trial)
3. **Kubernetes** — production-grade (manifests in `infra/k8s/`)

---

## 1. Quick Tunnel via Cloudflare

Best when: you want to demo the running local stack without committing to a host.

```bash
# 1. Make sure the local stack is up
docker compose up -d

# 2. Harden public exposure (admin/metrics off)
echo "EXPOSE_ADMIN=false" >> .env
echo "EXPOSE_METRICS=false" >> .env
docker compose restart web

# 3. Launch tunnels
./scripts/expose_public.sh
```

`cloudflared` prints two `https://*.trycloudflare.com` URLs — one for the
API at `:8000`, one for Dagster at `:3100`. Hostnames are ephemeral; a new
one is minted every run.

Limits: tunnel dies when you Ctrl+C. The PC must stay on. Not for
production. Fine for sharing a link with a recruiter for 30 minutes.

---

## 2. Railway

Best when: you want a persistent URL with one-click rollbacks, no infra to
manage. Railway free trial covers this stack comfortably.

### One-time setup

1. Push this repo to GitHub (private or public).
2. Sign up at https://railway.app and connect your GitHub.
3. New Project → Deploy from GitHub repo → pick `marketintel`.
4. Railway reads `railway.toml`, builds the image, runs migrations + seeds.

### Plugins

Add as managed plugins in the same project:

- **Postgres**: `+ New → Database → PostgreSQL`. Inject `DATABASE_URL` into
  `web` and `worker` services.
- **Redis**: `+ New → Database → Redis`. Inject `REDIS_URL`, `CELERY_BROKER_URL`,
  `CELERY_RESULT_BACKEND`.

### Worker service

Add a second service from the same repo with a different start command:

```
celery -A config worker -l INFO -Q default,ingest,transform,dlq -c 2 --beat
```

(`--beat` folds the scheduler into the worker so we stay under the free-tier
service count. For real production, run beat as its own singleton.)

### Environment variables

Pulled from `railway.toml`:
- `DJANGO_SETTINGS_MODULE=config.settings.prod`
- `EXPOSE_ADMIN=false`
- `EXPOSE_METRICS=false`

You must add manually:
- `DJANGO_SECRET_KEY` — generate with `python -c 'import secrets; print(secrets.token_urlsafe(50))'`
- `DJANGO_ALLOWED_HOSTS=marketintel-production.up.railway.app` (your domain)

### What's missing on Railway free tier

- **MinIO**: bronze writes will fail. Either skip bronze in the gold path, or
  point S3 settings at AWS S3 / Backblaze B2 free tier.
- **Dagster UI**: needs its own service + persistent volume; out of scope for
  free tier. Run Dagster locally against the prod Postgres if needed.

These limitations are documented but acceptable for a portfolio demo —
the API + ingestion path works end-to-end.

---

## 3. Kubernetes

Production. Manifests in `infra/k8s/`. See [`infra/k8s/base/kustomization.yaml`](../infra/k8s/base/kustomization.yaml).

```bash
# Staging
kubectl apply -k infra/k8s/overlays/staging

# Production
kubectl apply -k infra/k8s/overlays/production
```

Includes: Deployments + Services + HPA + PDB + NetworkPolicy + Ingress (cert-manager) + a migrations Job.

Postgres and Redis are statefulsets in `base/` — fine for staging. Production
should swap them for managed (RDS/CloudSQL/ElastiCache) by removing those
manifests from the kustomization.
