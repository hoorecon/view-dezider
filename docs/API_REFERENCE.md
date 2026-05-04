# REST API Reference — Dezider

_metadata: { "version": "3.5", "updated": "2026-05-04" }

Base URL: `/api`. Auth: `Authorization: Bearer <session_token>` from `/auth/login`.
Every response carries `X-Request-ID`, `X-Response-Time-MS`, security headers.

---

## Health & observability (public)

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Basic ok |
| GET | `/health/ready` | Mongo reachability |
| GET | `/health/live` | Pure process health (no DB) |
| GET | `/health/version` | Build version + commit + env |
| GET | `/metrics` | Prometheus text (Bearer-gated if `METRICS_TOKEN` set) |
| GET | `/metrics/json` | Admin JSON snapshot |

## Auth
Same as v3.4 — register / login / logout / refresh / me / forgot / reset / change.

## DPDP / GDPR (auth)
export / delete-request / cancel-delete / status / admin/audit-log / admin/purge-pending.

## Solution Matrix (auth)
CRUD + templates list/detail + PDF export. See `/docs/PRD.md` §3.3.

## Public Pulse
Consent / feedback / sessions / dashboards. YoY analytics at `/public-pulse/analytics/yoy/{overall|feedback|tool/{slug}}`.

## Public Sub-Portal (no auth)
`/p/{slug}`, `/p/{slug}/feedback/public`, `POST /p/{slug}/feedback`, `/embed/{slug}`, `/embed/{slug}/widget.js`.

## Daily Time Log (auth) — NEW v3.5

| Method | Path | Description |
|---|---|---|
| GET | `/daily-time-log/preferences` | 4 key timings + nudge cadence |
| POST | `/daily-time-log/preferences` | upsert above |
| POST | `/daily-time-log` | upsert day (manual blocks + auto-merge) |
| GET | `/daily-time-log/{YYYY-MM-DD}` | fetch one day (auto-rollup included) |
| POST | `/daily-time-log/{date}/refresh-rollup` | force re-scan source modules |
| GET | `/daily-time-log/week?start_date=YYYY-MM-DD` | 7-day strip |
| GET | `/daily-time-log/streaks` | current + longest + last_log_date |
| GET | `/daily-time-log/weekly-review?start_date=` | adherence + variance + category totals |

### Payload shape
```json
{
  "log_date": "2026-05-04",
  "key_timings": {"wake_up":"06:30","bed_time":"22:30","business_start":"09:30","business_end":"18:30"},
  "blocks": [
    {"start":"06:00","end":"07:00","category":"lifestyle","label":"Morning run"},
    {"start":"09:30","end":"11:00","category":"ctt","ref_type":"ctt_task","ref_id":"task-123","label":"Deep work"}
  ],
  "overall_mood": 4, "overall_energy": 4, "reflection": "good start",
  "run_auto_rollup": true
}
```

Block categories: `lifestyle | ctt | meditation | journal | sleep | break | learning | other`. `auto_sourced=true` for auto-rollup blocks.

## Time Dezider — Raja Guru (auth) — NEW v3.5

| Method | Path | Description |
|---|---|---|
| GET | `/raja-guru/day-plan` | morning intent-setter |
| GET | `/raja-guru/midday-check` | midday recalibration |
| GET | `/raja-guru/evening-retro` | evening retro (wins + gaps) |
| GET | `/raja-guru/next-action` | event-driven "what now?" |
| GET | `/raja-guru/preferences` | nudge cadence flags |
| POST | `/raja-guru/preferences` | toggle nudge flags |
| POST | `/raja-guru/feedback` | record accept/defer/skip |

Response shape (day-plan):
```json
{
  "intro": "Good morning, Raja. ...",
  "key_timings": {...},
  "total_planned_minutes": 240,
  "picks": [
    {"kind":"ctt_task","ref_id":"t-1","title":"Ship investor deck","estimated_minutes":90,"score":34.5,"reason":"Urgent + high importance"},
    {"kind":"lifestyle_area","ref_id":"fitness","title":"Fitness","estimated_minutes":45,"score":21.0,"reason":"Best window for this is now — morning compounds."}
  ],
  "raja_note": "Accept 2-3 non-negotiables. Defer the rest with dignity."
}
```

## Time Store (auth) — NEW v3.5

| Method | Path | Description |
|---|---|---|
| GET | `/time-store/time-audit` | CTT+Lifestyle+Matrix save opportunities |
| GET | `/time-store/services?save_minutes_per_day=30\|60\|120` | eligible services |
| GET | `/time-store/services?save_minutes_per_week=180\|300\|600\|900` | per-week filter |
| POST | `/time-store/purchase` | buy a service (MOCKED payment) |
| GET | `/time-store/purchases` | my orders |
| POST | `/time-store/delegate` | delegate a task to contact / org / family |
| GET | `/time-store/delegations` | my delegation inbox |

Service response includes `org` branding (display_name, slug, brand_color) so the UI renders per-org cards.

## Admin Docs (admin auth)

| Method | Path | Description |
|---|---|---|
| GET | `/admin-docs` | list all 12 handbook docs with version + updated |
| GET | `/admin-docs/{slug}` | fetch one doc (markdown body + parsed metadata) |

Slugs: `INDEX, PRD, SRS, API_REFERENCE, POSTMAN, REGRESSION, UAT, ACM, WOWO, CLD, SECURITY, DEPLOYMENT`.

## Conventions
- All dates: ISO 8601 (`2026-05-04` or `2026-05-04T14:33:00Z`).
- Pagination: `?limit=NN&skip=NN`.
- Errors: `{ "detail": "message", "request_id": "..." }`.
- UIDs: server-issued UUIDs — don't assume format.
