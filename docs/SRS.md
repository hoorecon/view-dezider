# System Requirements Specification — Dezider

_metadata: { "version": "3.4", "updated": "2026-05-04" }

## 1. System architecture

```
          +------------------+      +-------------------+
  Mobile  |   Expo (RN)      | --→  | NGINX / Ingress   | --→ [api pods (FastAPI)]
  Web     |   /app/frontend  |      | (terminates TLS,  |        |
  Org/Govt|   widget iframe  |      |  /api -> 8001)    |        v
  iframe  +------------------+      +-------------------+    [MongoDB]
                                                              ↑
                                                          [auto-snapshot]
```

- **Frontend**: Expo Router (RN), single codebase for iOS + Android + web preview.
- **Backend**: FastAPI on uvicorn (uvloop + httptools), behind NGINX. 4 worker pods baseline (HPA 4–40).
- **Database**: MongoDB 7 replica-set (3 nodes prod). Single node ok for dev/stage.
- **Job runner**: synchronous for now (no Celery). DPDP purge cron is a k8s `CronJob` hitting `/api/dpdp/admin/purge-pending` hourly.

## 2. Tech stack

| Layer | Tech | Version |
|---|---|---|
| Mobile / web | Expo | SDK 53 |
|  | React Native | 0.79 |
|  | expo-router | 5.x |
|  | expo-speech-recognition | latest |
|  | nativewind | 4 |
|  | zustand / react-hook-form | latest |
| API | FastAPI | 0.118 |
|  | uvicorn | 0.30 (uvloop) |
|  | motor (mongo async) | 3.7 |
|  | pydantic | 2.x |
|  | slowapi (rate-limit) | 0.1 |
|  | reportlab (PDF) | 4.4 |
|  | LiteLLM via Emergent universal key | latest |
| Storage | MongoDB | 7 |
| Observability | Internal counters + Prometheus text format | n/a |
| Container | Python 3.11 slim | n/a |

## 3. Module-to-collection map

(High-traffic collections only. Full list in WOWO.md.)

- `users`, `user_sessions`, `user_subscriptions`, `user_wallets`
- `decisions`, `factors`, `options`, `option_scores`
- `solution_finders`, `solution_matrices`
- `goal_setter_entries`, `goal_manifestations`, `unconditional_happiness`, `aala_entries`, `pna_entries`
- `clds`, `cld_simulations`
- `tepfi_matrices`, `swot_analyses`, `pros_cons_lists`
- `journal_entries`, `consciousness_diary_entries`, `meditation_sessions`
- `notifications`, `audit_log`, `idempotency_keys`
- `acm_modules`, `acm_features`, `acm_state`
- `pp_consents`, `pp_demographic_profiles`, `pp_tool_sessions`, `pp_feedback_items`, `pp_orgs`, `pp_org_memberships`, `pp_portal_config`

## 4. Index plan (top of mind)

200 indexes installed at boot via `core/database.ensure_indexes()`. Examples:

- `users.email` UNIQUE
- `user_sessions.session_token` UNIQUE
- `audit_log.actor_id, ts -1`
- `pp_tool_sessions.tool_slug, started_at`
- `pp_orgs.slug` UNIQUE
- `idempotency_keys.expires_at` (TTL)

## 5. Hardening posture

| Concern | Mitigation | Implementation |
|---|---|---|
| Brute-force login | Rate limit 10/min/user | `core/rate_limiting.py` |
| Memory-bomb requests | 10 MB body cap | `BodySizeLimitMiddleware` |
| XSS via response | CSP + X-Content-Type | `SecurityHeadersMiddleware` |
| Clickjacking | X-Frame-Options SAMEORIGIN (override per-route) | same |
| MITM | HSTS 2y in prod | same |
| PII leakage in logs | Email/phone/Aadhaar/PAN regex redaction | `redact_pii` filter |
| Replay/dup mutations | Idempotency-Key dedupe (24h TTL) | `core/hardening.get_idempotent_response` |
| LLM cost burst | 10/min AI cap + 503 fallback | `core/llm_errors.py` |
| Outbound deps flake | Circuit breaker + retry-with-jitter | `core.hardening.with_retry` |
| Data subject rights | DPDP export/delete/cancel + 7-day grace + admin purge | `routes/dpdp.py` |
| Audit visibility | Append-only `audit_log` collection | `core.hardening.write_audit` |
| Slow ops | `> 800ms` lines logged separately | `SlowRequestLoggerMiddleware` |
| Disaster recovery | Daily mongodump + 5-min replica oplog | runbook `DEPLOYMENT.md` |

## 6. Performance targets vs. measured

| Endpoint family | Target p95 | Measured (synthetic) |
|---|---|---|
| Auth (`/auth/*`) | 200 ms | 80–150 ms |
| Reads (`GET /tools/...`) | 250 ms | 30–80 ms |
| Writes (`POST /tools/...`) | 350 ms | 50–120 ms |
| Public Pulse dashboards | 500 ms | 80–300 ms (k-anon-friendly aggregations) |
| YoY analytics | 600 ms | 120–350 ms |
| Solution Matrix PDF | 1.5 s | 0.5–1.0 s for 60-cell |
| AI endpoints | 8 s | bypassed (503 due to budget) |

## 7. Capacity model

- 1 M total users, 1% DAU = 10 K daily active.
- Peak hour 25% of daily → 2,500 users/hour, ~3 req/min/user → 7,500 req/min.
- 4 pods × 4 workers × 1k req/min/worker = 16,000 req/min headroom.
- Mongo M30 (3 nodes) handles 6k ops/sec read + 2k write — well above projected.

Scale-out trigger: CPU > 65% for 60 s (HPA), memory > 75% for 60 s.

## 8. Failure modes

| Failure | Impact | Recovery |
|---|---|---|
| Mongo primary failover | 5–15 s of 503s | replica auto-promotes, motor reconnects |
| LLM budget exhausted | All AI endpoints 503 | retry queue (planned); read-only degraded mode active |
| Slowapi key store overflows | n/a (in-memory; reset on restart) | bounded by per-user cap |
| API pod OOM | k8s restarts; HPA may add pod | LivenessProbe |
| Bad migration | Restore last snapshot (≤5 min RPO) | `mongorestore` runbook |
