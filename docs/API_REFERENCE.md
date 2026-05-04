# REST API Reference — Dezider

_metadata: { "version": "3.4", "updated": "2026-05-04" }

Base URL: `/api`. Auth: `Authorization: Bearer <session_token>` (from `/auth/login`).
Response headers from every endpoint:
- `X-Request-ID` (12-char hex; quote when reporting bugs)
- `X-Response-Time-MS` (server-measured)
- `X-RateLimit-*` (when slowapi headers enabled)

---

## Public / no-auth endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness (returns ok) |
| GET | `/health/ready` | Mongo reachability probe (200/503) |
| GET | `/health/live` | k8s liveness probe (no DB) |
| GET | `/health/version` | Build version + commit + env |
| GET | `/metrics` | Prometheus text (Bearer-token gated if `METRICS_TOKEN` set) |
| GET | `/metrics/json` | Admin-only JSON metric snapshot |
| GET | `/p/{slug}` | Org sub-portal branding/about |
| GET | `/p/{slug}/feedback/public` | Resolved feedback for an org |
| POST | `/p/{slug}/feedback` | Submit feedback (auth optional) |
| GET | `/embed/{slug}` | Iframe-safe widget (HTML) |
| GET | `/embed/{slug}/widget.js` | Auto-iframe injector JS |
| GET | `/public-pulse/dashboards/{key}` | k-anon insights |
| GET | `/public-pulse/analytics/yoy/overall` | YoY all sessions |
| GET | `/public-pulse/analytics/yoy/feedback` | YoY feedback items |
| GET | `/public-pulse/analytics/yoy/tool/{slug}` | YoY by tool |
| GET | `/feature-flags/public` | Public feature flag dump |

## Auth

| Method | Path | Description |
|---|---|---|
| POST | `/auth/register` | Email + password + name |
| POST | `/auth/login` | Returns `session_token` |
| POST | `/auth/logout` | Invalidates token |
| POST | `/auth/refresh` | Rotates token |
| GET | `/auth/me` | Current user |
| POST | `/auth/forgot-password` | Send reset email (rate-limited) |
| POST | `/auth/reset-password` | Apply reset token |
| POST | `/auth/change-password` | Auth required |

## DPDP / GDPR (auth)

| Method | Path | Description |
|---|---|---|
| GET | `/dpdp/export` | Download all my data as JSON |
| POST | `/dpdp/delete-request` | Mark account for delete (7-day grace) |
| POST | `/dpdp/cancel-delete` | Cancel within grace window |
| GET | `/dpdp/status` | My deletion status |
| GET | `/dpdp/admin/audit-log` | Admin only: query audit log |
| POST | `/dpdp/admin/purge-pending` | Admin/cron: hard-delete past grace |

## Solution Matrix (auth)

| Method | Path | Description |
|---|---|---|
| GET | `/solution-matrices/templates` | List 4 starter templates |
| GET | `/solution-matrices/templates/{id}` | Get one template payload |
| POST | `/solution-matrices` | Create entry |
| GET | `/solution-matrices` | List my entries |
| GET | `/solution-matrices/{id}` | Get one |
| PUT | `/solution-matrices/{id}` | Update one |
| DELETE | `/solution-matrices/{id}` | Delete one |
| GET | `/solution-matrices/{id}/pdf` | Landscape A4 PDF (mode-aware) |

### Solution Matrix payload schema (key fields)

```json
{
  "matrix_mode": "standard|accurate",
  "matrix_self": {
    "aggregate":  { /* used in standard mode */ },
    "individual": { "time":"", "energy":"", "people":"", "finance":"", "infrastructure":"",
                    "summary":"", "knowledge_skills":"",
                    "influences": { "time": {"positive":"", "negative":""}, ... } },
    "org":   { ... },
    "govt":  { ... },
    "nature": { ... }
  },
  "matrix_micro": { ... },
  "matrix_macro": { ... }
}
```

## Solution Finder (auth) — `/solution-finders/*`
Similar 5 endpoints (POST/GET/PUT/DELETE/list).

## Public Pulse — Org admin (auth + role)

| Method | Path | Description |
|---|---|---|
| POST | `/public-pulse/orgs/apply` | Submit org application |
| GET | `/public-pulse/orgs/{org_id}/dashboard` | Org dashboard |
| GET | `/public-pulse/orgs/{org_id}/feedback` | Inbound feedback list |
| PUT | `/public-pulse/orgs/{org_id}/feedback/{fid}` | Update status / response |
| PUT | `/p/{slug}/config` | Admin: portal config (allow domains, CTA label…) |
| POST | `/public-pulse/orgs/{org_id}/members/invite` | Invite a member |

## Tools (auth) — by route prefix

- `/goal-setter/*`, `/goal-manifestation/*`
- `/aala/*`, `/aaaa/*`, `/pna/*`
- `/cld/*` (LLM-backed)
- `/tepfi/*`, `/swot/*`, `/pros-cons/*`
- `/conflict-breaker/*`, `/emotional-gatekeeper/*`
- `/lifestyle/*`, `/lifestyle-eval/*`, `/lifestyle-designer/*`
- `/gem-flight/*`, `/gem-goal/*`, `/time-dezider/*`
- `/consciousness-diary/*`, `/meditation/*`, `/unconditional-happiness/*`
- `/ctt/*`, `/ctt-tasks/*`
- `/ai-assistant/*` (LLM-backed; 503 when budget exhausted)

Full route list: see Postman collection.

## ACM (auth)

| Method | Path | Description |
|---|---|---|
| GET | `/acm/my-access` | All features visible/locked/full for current user |
| GET | `/acm/feature/{id}` | Single feature meta |
| POST | `/acm/seed?force=true` | Admin: re-seed ACM (idempotent) |

## Conventions

- All POST/PUT bodies are JSON.
- Date-times are ISO 8601 (`2026-05-04T14:33:00Z`).
- `entry_id` / `feedback_id` are server-issued UUIDs (do not assume formats).
- Pagination: `?limit=NN&skip=NN` (default `limit=100`, `skip=0`, max `limit=500`).
- Error envelope: `{ "detail": "<message>", "request_id": "..." }`.
