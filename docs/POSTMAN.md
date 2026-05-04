# Postman / Insomnia collection — Dezider API

_metadata: { "version": "3.4", "updated": "2026-05-04" }

The canonical importable JSON lives at `/app/docs/Postman_Collection.json`
(sibling to this doc). Below is the human-readable index of what's in it.

Import into Postman: File → Import → select `Postman_Collection.json`.
Set the **`baseUrl`** environment variable to `http://localhost:8001` for
dev or `https://YOUR-DOMAIN.com` for stage/prod.

The collection ships with two pre-configured environments:

- **Dezider Local Dev** (`baseUrl` = http://localhost:8001)
- **Dezider Stage** (`baseUrl` = https://stage.dezider.app)

## Folder layout

1. **0. Auth** — register / login / logout / me / refresh / forgot / reset / change
2. **1. Health & Metrics** — health/ready/live/version, /metrics, /metrics/json
3. **2. DPDP** — export / delete-request / cancel / status / admin/audit-log / admin/purge-pending
4. **3. Solution Matrix** — templates list/detail, CRUD, PDF export
5. **4. Solution Finder** — CRUD
6. **5. Public Pulse** — consent / feedback / sessions / dashboards / YoY analytics
7. **6. Public Pulse Org** — apply / dashboard / feedback / members
8. **7. Public Sub-Portal** — /p/{slug}, /embed/{slug}, widget.js
9. **8. ACM** — my-access, feature, admin/seed
10. **9. Tools (sample)** — goal-setter, AALA, CLD, conflict-breaker, lifestyle-eval

## Auth flow tip

The collection's pre-request scripts read `session_token` from the
environment. After running **Auth → Login**, the test script copies
`session_token` from the response into the env automatically; subsequent
requests pick it up.

## Smoke test sequence (CI)

1. `POST /auth/register` (random email)
2. `POST /auth/login`
3. `GET /auth/me`
4. `GET /solution-matrices/templates`
5. `POST /solution-matrices` (with template payload)
6. `GET /solution-matrices/{id}/pdf`
7. `GET /dpdp/status`
8. `GET /public-pulse/analytics/yoy/overall`
9. `GET /p/coimbatore-skills-foundation-5b9c19`
10. `POST /auth/logout`
