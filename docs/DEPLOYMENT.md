# Deployment runbook — Dezider

_metadata: { "version": "3.16.0", "updated": "2026-06-12" }

Three supported deploy targets:

1. **Emergent managed runtime** (current, alpha) — zero-config, push and go.
2. **Single-node Docker Compose** (stage / pre-prod) — `deploy/docker-compose.yml`.
3. **Kubernetes on AWS / GCP** (prod target) — `deploy/k8s/dezider-api.yaml`.

---

## 1) Emergent managed runtime

- Backend: supervisord auto-restarts uvicorn on file changes.
- Frontend: `expo start` with metro bundler; preview URL surfaced by the platform.
- Env: edit `backend/.env` for backend, `frontend/.env` for FE — reload happens automatically.
- DO NOT modify `MONGO_URL`, `EXPO_PACKAGER_PROXY_URL`, `EXPO_PACKAGER_HOSTNAME`.
- Logs: `tail -f /var/log/supervisor/backend.err.log`.
- DB backups: managed by Emergent.

For APK / IPA / app-store publishing use the Emergent **Publish** button (top-right). Don't try to set up your own EAS account.

## 2) Docker Compose (single host)

```bash
cp deploy/.env.example backend/.env       # tweak values
cd /app
docker compose -f deploy/docker-compose.yml up -d --build
curl http://localhost:8001/api/health/live
docker compose -f deploy/docker-compose.yml logs -f api
```

Mongo data persists in the named volume `mongo_data`.

Backup:
```bash
docker exec -t deploy-mongo-1 mongodump --archive=/tmp/dump.gz --gzip
docker cp deploy-mongo-1:/tmp/dump.gz ./backups/$(date +%Y-%m-%d).gz
```

## 3) Kubernetes (AWS EKS / GCP GKE)

### Pre-reqs
- A managed MongoDB (Atlas M30+ recommended).
- An ingress controller (NGINX or AWS ALB).
- A container registry (ECR / GAR).

### Deploy
```bash
cd /app/deploy/k8s

# 1. Replace SECRETS in dezider-api.yaml (MONGO_URL, EMERGENT_LLM_KEY, ...)
# 2. Build + push the image
docker build -t <REGISTRY>/dezider/backend:v3.4 -f /app/backend/Dockerfile /app/backend
docker push <REGISTRY>/dezider/backend:v3.4

# 3. Update the image tag in dezider-api.yaml and apply
kubectl apply -f dezider-api.yaml
kubectl -n dezider rollout status deploy/dezider-api
```

### Scaling
- Baseline 4 pods, HPA scales to 40 on CPU > 65% / mem > 75%.
- PodDisruptionBudget keeps 75% of pods running during upgrades.
- Mongo Atlas autoscale: tier M30 → M40 once steady-state IOPS > 70%.

### Probes
- **Readiness**: `/api/health/ready` (checks Mongo).
- **Liveness**: `/api/health/live` (no DB; pure process health).
- **Startup**: 150 s budget for first request.

### Cron jobs
- `dezider-dpdp-purge` runs hourly: `POST /api/dpdp/admin/purge-pending`.

### Observability
- `/api/metrics` is scraped by Prometheus (annotations are pre-set).
- Suggested Grafana dashboards: "http_requests_total", "http_5xx_total", "http_request_duration_ms".
- Set `SLOW_REQUEST_MS=800` to surface slow lines (pull from `kubectl logs` or your log shipper).

## DR / RTO / RPO

| Metric | Target | How |
|---|---|---|
| RTO | 30 min | k8s reconcile + Atlas point-in-time restore |
| RPO | 5 min | Atlas oplog continuous backup |
| Cold start | < 30 s | StartupProbe budget; ACM seed is incremental |

## Rollback

```bash
kubectl -n dezider rollout undo deploy/dezider-api
```

For data: restore Atlas snapshot via the Atlas UI; flip Mongo URL secret;
restart pods. (Tested on stage every quarter.)

## Secret rotation

Quarterly. Update `dezider-api-secrets`, then:
```bash
kubectl -n dezider rollout restart deploy/dezider-api
```

## Post-deploy smoke test

```bash
curl https://api.dezider.app/api/health/live
curl https://api.dezider.app/api/health/version
curl https://api.dezider.app/api/metrics -H "Authorization: Bearer $METRICS_TOKEN"
```

## Tier 0 incidents

1. Health/ready returns 503: page on-call, check Mongo Atlas dashboard.
2. p95 > 1.5 s: scale up + grep slow_request lines.
3. /api/metrics shows http_5xx_total spike > 1%: roll back deploy.

---

## Self-host (your own domain) — Quick checklist (v3.15.0)

The same Docker + K8s pipeline above applies — these are the **action items**
distilled for a custom-domain deployment (e.g. `app.viewdezider.com`,
`api.viewdezider.com`).

### A. Prerequisites you provide
- [ ] A Linux host (VPS/EC2/GCE) **or** a managed K8s cluster (EKS / GKE / AKS)
- [ ] A MongoDB instance — **MongoDB Atlas M30+ recommended** (auto-backup, point-in-time restore); self-hosted only for staging
- [ ] A registered domain + DNS access (Cloudflare / Route53 / etc.)
- [ ] A container registry (Docker Hub / ECR / GAR / GHCR)
- [ ] TLS certificates — easiest via Let's Encrypt + certbot, or load-balancer-managed (ALB / GLB / Cloudflare)
- [ ] Required 3rd-party API keys (only the ones you actually use):
      `EMERGENT_LLM_KEY`, `GOOGLE_CLIENT_ID/SECRET`, `RAZORPAY_KEY_ID/SECRET`,
      `ULTRAMSG_TOKEN`, `EXOTEL_API_KEY`, `DIGILOCKER_CLIENT_ID/SECRET`,
      `SMTP_HOST/PORT/USER/PASS`

### B. DNS layout (recommended split)
| Sub-domain | Points to | Purpose |
|---|---|---|
| `api.yourdomain.com` | Backend load balancer / NGINX | FastAPI on port 8001 (TLS terminates at LB) |
| `app.yourdomain.com` | Static host / CDN | Expo web build (`npx expo export -p web`) |
| `admin.yourdomain.com` (optional) | Same as `app` | Same SPA, just nicer bookmark |
| `pulse.yourdomain.com` (optional) | Same as `app` | Public Pulse landing |

### C. Backend deploy (3 options)
1. **Docker Compose (single VPS)** — fastest path:
   ```bash
   git clone <your-fork> && cd app
   cp deploy/.env.example backend/.env       # paste in your keys
   docker compose -f deploy/docker-compose.yml up -d --build
   ```
   Put NGINX in front, terminate TLS, proxy `api.yourdomain.com → 127.0.0.1:8001`.

2. **Kubernetes (production)** — see Section 3 above. Edit
   `deploy/k8s/dezider-api.yaml`:  set `image`, `MONGO_URL`, secrets,
   ingress host, then `kubectl apply -f`.

3. **PaaS (Render / Railway / Fly.io)** — point at `backend/Dockerfile`, set
   the env vars from `.env.example`, expose port 8001. Add MongoDB as an
   addon / external Atlas URL.

### D. Frontend deploy (Expo web → static)
The frontend is an Expo Router app — for production web you ship static files:
```bash
cd frontend
# Point at your live API
echo "EXPO_PUBLIC_BACKEND_URL=https://api.yourdomain.com" > .env.production
npx expo export -p web                          # outputs to ./dist
```
Host `frontend/dist` on **any static host**:
- **Cloudflare Pages / Vercel / Netlify** — just upload (`dist`) or connect repo
- **S3 + CloudFront** — `aws s3 sync dist/ s3://your-bucket --delete`
- **NGINX on the same VPS** — copy `dist/` to `/var/www/app` and add a server block

### E. Post-deploy smoke (5 commands)
```bash
curl https://api.yourdomain.com/api/health/live              # → {"status":"ok"}
curl https://api.yourdomain.com/api/health/ready             # → mongo reachability
curl https://api.yourdomain.com/api/health/version           # → build + commit
curl -X POST https://api.yourdomain.com/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"email":"admin@test.com","password":"AdminPass2026!"}'
open https://app.yourdomain.com                              # SPA loads
```

### F. Seed ACM (one-time, idempotent)
```bash
TOKEN=$(curl -s -X POST https://api.yourdomain.com/api/auth/login \
        -H "Content-Type: application/json" \
        -d '{"email":"admin@test.com","password":"AdminPass2026!"}' | jq -r .session_token)
curl -X POST "https://api.yourdomain.com/api/acm/seed?force=true" \
     -H "Authorization: Bearer $TOKEN"
```

### G. Custom-domain CORS (one env var)
Add to `backend/.env`:
```
ALLOWED_ORIGINS=https://app.yourdomain.com,https://admin.yourdomain.com,https://pulse.yourdomain.com
```
(Wildcards are allowed during early testing — tighten before launch.)

### H. Mobile build (separate from web hosting)
APK / IPA must use the Emergent **Publish** button or your own EAS account.
Self-hosting only covers the web app + API + DB.

### I. What's *not* in this delta but you may need at launch
- [ ] Razorpay live keys (sandbox keys included in `.env.example` placeholders)
- [ ] DigiLocker production approval from API Setu
- [ ] Exotel DLT template approval
- [ ] LLM budget (Emergent LLM Key currently capped — AI flows degrade gracefully via 503)
- [ ] CDN cache rules for `/api/pricing` (60 s TTL already in app)
- [ ] Backup cron for self-hosted Mongo (or rely on Atlas continuous backup)
- [ ] Uptime monitoring on `/api/health/ready` (UptimeRobot / Better Stack / Datadog)

---
## v3.16.0 — Deployment notes (2026-06-12)

### Env additions
```
# PostHog — web replay (frontend, build-time)
EXPO_PUBLIC_POSTHOG_HOST=https://eu.i.posthog.com
EXPO_PUBLIC_POSTHOG_KEY=phc_xxxxxxxxxxxxxxxx

# PostHog — server-side events (backend)
POSTHOG_HOST=https://eu.i.posthog.com
POSTHOG_API_KEY=phc_xxxxxxxxxxxxxxxx

# ScraperAPI (URL Import v3 rendered HTML)
SCRAPER_API_KEY=...

# Emergent Universal Key (Claude precise tier)
EMERGENT_LLM_KEY=...

# Revenue Reconciliation — GCP Billing Export (super-admin uploads in UI; no env var)
```

### Cloudflare Pages (frontend web build)
- `EXPO_PUBLIC_POSTHOG_HOST` + `EXPO_PUBLIC_POSTHOG_KEY` must be set BEFORE `npx expo export -p web` because `posthog-js` is bundled at build time.
- After redeploy, hard refresh the preview tab and confirm `window.posthog.__loaded === true`.

### EC2 / Docker backend
- After upgrade: `pip install -r backend/requirements.txt` (adds `google-cloud-bigquery==3.41.0`, `posthog`).
- Restart: `sudo supervisorctl restart backend`.
- One-time post-deploy: super-admin uploads GCP Service-Account JSON via `/admin/recon` → Configure GCP form. Validate via `POST /admin/recon/sync`.

### Smoke test additions (v3.16)
```bash
# After login as super-admin
curl -X POST $BASE/api/url-analyze/decision/{id}/import \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"url":"https://example.com/product","ai_tier":"fast"}'

curl $BASE/api/admin/ai-wallet/config -H "Authorization: Bearer $TOKEN"
curl $BASE/api/admin/recon/summary    -H "Authorization: Bearer $TOKEN"
```
