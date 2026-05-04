# Deployment runbook — Dezider

_metadata: { "version": "3.4", "updated": "2026-05-04" }

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
