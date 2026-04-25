# Deployment

Three deploy paths, ordered by effort:

1. **Render** — easiest. No credit card. ~5 min via the dashboard. The `render.yaml`
   blueprint provisions Postgres, Redis, web service and worker automatically.
2. **Railway** — pay-as-you-go after free trial credits. Cleaner DX, faster builds.
3. **Cloudflare Quick Tunnel** — share the local stack with a temporary public
   HTTPS URL. Useful for live demos during interviews.

> **Pre-flight (any deploy path)**: the GitHub repo must be visible to the
> deploy provider. Either make it public or grant the deploy app access to
> the private repo.

---

## 1. Render (recommended for a free permanent demo)

### One-time setup

1. Go to **https://render.com** and sign up with the GitHub account that owns
   the repo.
2. Connect the `marketintel` repo (Account Settings → GitHub → Configure → grant access).
3. Click **New → Blueprint**.
4. Pick the `marketintel` repository and the `main` branch.
5. Render reads `render.yaml`, lists 4 resources to create:
   - `marketintel-postgres` (free Postgres database)
   - `marketintel-redis` (free Redis)
   - `marketintel-web` (Docker web service)
   - `marketintel-worker` (Docker background worker, includes `--beat`)
6. Click **Apply**. First build takes 5–8 min.

### After the first deploy

Open the **marketintel-web** service → **Shell** tab and run:

```bash
python manage.py loaddata seeds/sources.json seeds/instruments.json
python manage.py createsuperuser
```

Trigger an initial ingest (Beat will keep refreshing every minute afterwards):

```bash
python manage.py shell -c "from pipelines.tasks.yahoo import ingest_yahoo_spot_for_active as t; print(t.apply().get())"
```

Open the URL Render assigned (e.g. `https://marketintel-web.onrender.com`).

### Free-tier caveats

- **Cold starts**: the web service sleeps after 15 min of inactivity. First hit
  after a sleep takes ~30 s. Upgrade to **Starter ($7/mo)** for keep-alive.
- **No bronze**: free tier has no S3-compatible storage. Leave `S3_*` env vars
  blank — bronze writes are skipped, silver still works fine. To enable, point
  `S3_ENDPOINT_URL` at AWS S3 / Backblaze B2 / Cloudflare R2.
- **No Dagster UI**: Dagster is not deployed; it's a separate service that
  requires a persistent volume. Run it locally against the prod database when
  needed.
- **`DJANGO_SECRET_KEY` mismatch**: the worker has `sync: false` for the secret
  so Render does not auto-generate one. After web is up, copy its
  `DJANGO_SECRET_KEY` value into the worker service env vars.

---

## 2. Railway

Railway has a generous free trial ($5 of credits) and a faster build pipeline.

### One-time setup

1. Go to **https://railway.app** and sign up.
2. **New Project → Deploy from GitHub repo → marketintel**. Railway picks up
   `railway.toml` and starts a build.
3. **+ New → Database → PostgreSQL**. Railway injects `DATABASE_URL` automatically.
4. **+ New → Database → Redis**. Sets `REDIS_URL` / `REDISURL`.
5. Add a worker service:
   - **+ New → GitHub Repo → marketintel** (same repo, second service).
   - In its settings, set **Custom start command**:
     ```
     celery -A config worker -l INFO -Q default,ingest,transform,dlq -c 2 --beat
     ```
6. On both services, set env vars:
   - `DJANGO_SETTINGS_MODULE=config.settings.prod`
   - `DJANGO_SECRET_KEY` (one shared value across both services)
   - `DJANGO_ALLOWED_HOSTS=*.railway.app,*.up.railway.app`
   - `EXPOSE_ADMIN=False`, `EXPOSE_METRICS=False`
   - The Postgres + Redis URLs Railway injected.

### After the first deploy

Open the web service → **Settings → Generate Domain** to get a public URL.
Then in the **Deploy** tab use the one-shot run feature to seed:

```bash
python manage.py loaddata seeds/sources.json seeds/instruments.json
python manage.py createsuperuser
```

---

## 3. Cloudflare Quick Tunnel (live local demo)

Best for sharing a running local stack temporarily — useful during interviews.

```bash
# 1. Make sure the local stack is up
docker compose up -d

# 2. Harden public exposure (admin / metrics off)
sed -i 's/^EXPOSE_ADMIN=.*/EXPOSE_ADMIN=False/' .env
sed -i 's/^EXPOSE_METRICS=.*/EXPOSE_METRICS=False/' .env
docker compose restart web

# 3. Launch tunnels (uses ~/bin/cloudflared.exe on Windows)
./scripts/expose_public.sh
```

`cloudflared` prints two `https://*.trycloudflare.com` URLs — one for the API
at `:8000`, one for Dagster at `:3100`. Tunnels die when you stop the script,
so the PC must stay on.

---

## 4. Kubernetes (production)

Manifests in `infra/k8s/`. See [`infra/k8s/base/kustomization.yaml`](../infra/k8s/base/kustomization.yaml).

```bash
# Staging
kubectl apply -k infra/k8s/overlays/staging

# Production
kubectl apply -k infra/k8s/overlays/production
```

Includes Deployments + Services + HPA + PDB + NetworkPolicy + Ingress (cert-manager)
+ a migrations Job. Postgres and Redis are statefulsets in `base/` — fine for
staging. Production should swap them for managed (RDS / CloudSQL / ElastiCache)
by removing those manifests from the kustomization.
