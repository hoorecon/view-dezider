# Postman / Insomnia collection — Dezider API

_metadata: { "version": "3.5.1", "updated": "2026-05-04" }

Collection JSON: `/app/docs/Postman_Collection.json` (updated for v3.5.1 with
Daily Time Log / Raja Guru / Time Store / DPDP folders).

## Environments
- **Local Dev** (`baseUrl` = http://localhost:8001)
- **Stage** (`baseUrl` = https://stage.dezider.app)

## Folders (v3.5)

1. **0. Auth** — register / login / me / logout
2. **1. Health & Metrics** — health, ready, live, version, metrics
3. **2. DPDP** — export, delete-request, cancel, status, admin/audit-log, admin/purge
4. **3. Solution Matrix** — templates list/detail, CRUD, PDF export
5. **4. Solution Finder** — CRUD
6. **5. Public Pulse** — consent, feedback, dashboards, YoY analytics
7. **6. Public Pulse Org** — apply, dashboard, feedback, members
8. **7. Public Sub-Portal** — /p/{slug}, /embed/{slug}, widget.js
9. **8. ACM** — my-access, feature, admin/seed
10. **9. Daily Time Log** (NEW) — preferences, upsert-day, get-day, refresh-rollup, week, streaks, weekly-review
11. **10. Time Dezider — Raja Guru** (NEW) — day-plan, midday-check, evening-retro, next-action, preferences, feedback
12. **11. Time Store** (NEW) — time-audit, services, purchase, purchases, delegate, delegations
13. **12. Tools (sample)** — goal-setter, AALA, CLD, conflict-breaker

## Auth flow tip
After **Auth → Login**, the test script copies `session_token` into the env
automatically. Other requests pick it up via the collection-level Bearer auth.

## Smoke test sequence (CI)

```
POST /auth/register           (random email)
POST /auth/login
GET  /auth/me
GET  /solution-matrices/templates
POST /solution-matrices       (accurate mode)
GET  /solution-matrices/{id}/pdf
GET  /dpdp/status
GET  /daily-time-log/preferences
POST /daily-time-log          (one day, 2 blocks)
GET  /daily-time-log/streaks
GET  /raja-guru/day-plan
GET  /time-store/time-audit
GET  /time-store/services?save_minutes_per_day=30
POST /auth/logout
```
