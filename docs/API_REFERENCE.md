# REST API Reference — Dezider

_metadata: { "version": "3.15.0", "updated": "2026-05-18" }

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

| Method | Path | Description |
|---|---|---|
| GET | `/dpdp/export` | Download JSON bundle of user's personal data |
| POST | `/dpdp/delete-request` | Schedule account deletion (requires `confirmation="DELETE MY ACCOUNT"`) |
| POST | `/dpdp/cancel-delete` | Cancel pending deletion during cooling-off |
| GET | `/dpdp/status` | Current deletion status (pending / purge ETA / reason) |
| GET | `/dpdp/admin/audit-log` | Admin: filtered audit events |
| POST | `/dpdp/admin/purge-pending` | Admin: cron-callable purge of deletions past their grace window |

Front-end surface: `/tools/privacy-data` (linked from Profile tab).

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

## Time Store (auth) — NEW v3.5 (schema clarified v3.5.1)

| Method | Path | Description |
|---|---|---|
| GET | `/time-store/time-audit` | CTT+Lifestyle+Matrix save opportunities |
| GET | `/time-store/services?save_minutes_per_day=30\|60\|120` | eligible services (see note) |
| GET | `/time-store/services?save_minutes_per_week=180\|300\|600\|900` | per-week filter |
| POST | `/time-store/purchase` | buy a service (MOCKED payment) |
| GET | `/time-store/purchases` | my orders |
| POST | `/time-store/delegate` | delegate a task to contact / org / family |
| GET | `/time-store/delegations` | my delegation inbox |

Service response includes `org` branding (display_name, slug, brand_color) so the UI renders per-org cards.

**Visibility filter (v3.5.1)**: `/time-store/services` returns solutions where either `is_authorized=True` (system-seeded catalogue) OR (`visibility="PUBLIC"` AND `approval_status="approved"`). `status="active"` is always required. Bucket filters use `$gte: max(0, requested - 30)` (day) and `$gte: max(0, requested - 60)` (week) so partial matches are still surfaced.

**Solutions Store schema (time-save fields, v3.5.1)**:

| Field | Type | Description |
|---|---|---|
| `time_save_per_day_min` | int | Daily minutes reclaimed by using the service |
| `time_save_per_week_min` | int | Weekly minutes reclaimed |
| `time_save_rationale` | string | Short explanation for the user |
| `price_inr` | int | Currency-neutral price (INR) |
| `price_model` | string | `per_order \| per_visit \| monthly \| annual \| per_hour \| one_time` |
| `seed_key` | string | Stable key for idempotent re-seeding (system-only) |

Seed script: `backend/scripts/seed_time_store_services.py` — idempotent, safe to re-run.

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

---
## v3.14.0 — Tier Matrix · Customer Segments · Pricing  (added 2026-05-07)

### Public
| Method | Path | Description |
|---|---|---|
| GET | `/api/tiers` | 7-chakra tier metadata (Root → Crown, INR pricing) |
| GET | `/api/tier-matrix` | Public read of module/feature × tier grid |
| GET | `/api/customer-segments` | Public list of TG customer segments |
| GET | `/api/customer-segments/factors` | Predefined factor catalog (23 factors × 4 categories) |
| GET | `/api/pricing` | One-shot pricing payload (tiers + segments + matrix). 60s TTL cache. |

### Authenticated user
| Method | Path | Description |
|---|---|---|
| GET | `/api/me/tier-access` | Current user's tier + unlocked modules/features |

### Admin (require_admin)
| Method | Path | Description |
|---|---|---|
| GET | `/api/admin/tier-matrix` | Read full matrix (auto-seeds if empty) |
| POST | `/api/admin/tier-matrix/seed` | Idempotent smart-seed |
| POST | `/api/admin/tier-matrix/reset` | Wipe + reseed defaults |
| PUT | `/api/admin/tier-matrix/cell` | Toggle one cell (cascade-up + module-dominates) |
| POST | `/api/admin/tier-matrix/bulk` | Bulk save many cells |
| PUT | `/api/admin/users/{user_id}/tier` | Assign user a chakra tier |
| GET | `/api/admin/customer-segments` | List all TG segments |
| POST | `/api/admin/customer-segments` | Create segment (auto-seeds 23 factors + 7 INR pricings) |
| GET | `/api/admin/customer-segments/{sid}` | Read one |
| PUT | `/api/admin/customer-segments/{sid}` | Update |
| DELETE | `/api/admin/customer-segments/{sid}` | Delete |
| POST | `/api/admin/customer-segments/{sid}/factor` | Add custom factor (any category) |
| DELETE | `/api/admin/customer-segments/{sid}/factor/{key}` | Remove custom factor |
| POST | `/api/admin/customer-segments/{sid}/ai-research` | LLM-fill one factor's value (graceful fallback dict if budget capped) |
| PUT | `/api/admin/customer-segments/{sid}/pricing` | Upsert multi-currency multi-country tier pricings |

**Cascade rules (server-side):** Toggle ON cascades to higher tiers; toggle OFF stays local. Module=N forces all features=N at that tier. Feature toggle ON auto-enables parent module at same tier.

---

## v3.15.0 — 8-Step Pros & Cons / SWOT Decision Framework (2026-05-18)

The same 18-route set is exposed under `/api/pros-cons/{id}/*` **and** `/api/swot/{id}/*`.
Auth: Bearer. Per-user scoped data. All payloads JSON.

### Factors  (Step #1, #4, #5, #6)
| Method | Path | Body |
|---|---|---|
| POST | `/pros-cons/{id}/factors` | `{ name, expected_value?, unit?, parent_id? }` |
| PUT  | `/pros-cons/{id}/factors/{fid}` | any of: `name, expected_value, unit, parent_id, notation, priority_rank, std_rating, factor_type, improvable, my_expectation, others_expectations, market_standard, realistic_gap_pct, realistic_gap_value, notes` |
| DELETE | `/pros-cons/{id}/factors/{fid}` | — |
| POST | `/pros-cons/{id}/factors/reorder` | `{ ordered_ids: [fid, ...] }` |

### Options + Pros/Cons per option  (Step #2)
| Method | Path | Body |
|---|---|---|
| POST | `/pros-cons/{id}/options` | `{ name, description? }` |
| PUT  | `/pros-cons/{id}/options/{oid}` | `{ name?, description?, pros?, cons? }` |
| DELETE | `/pros-cons/{id}/options/{oid}` | — |
| POST | `/pros-cons/{id}/options/{oid}/pros` | `{ text, description?, importance? }` |
| POST | `/pros-cons/{id}/options/{oid}/cons` | `{ text, description?, importance? }` |
| DELETE | `/pros-cons/{id}/options/{oid}/pros/{item_id}` | — |
| DELETE | `/pros-cons/{id}/options/{oid}/cons/{item_id}` | — |

### Promote → Factors  (Step #3.1)
| Method | Path | Notes |
|---|---|---|
| POST | `/pros-cons/{id}/promote-pros-cons` | Idempotent. Cons get `"SHOULD NOT - "` prefix. |

### Config  (Step #6.2 + #8.9)
| Method | Path | Body |
|---|---|---|
| PUT | `/pros-cons/{id}/config` | `{ mandatory_threshold_pct?, max_improvement_period_months?, std_gap? }` |

### Assessment cells  (Step #7 + #8)
| Method | Path | Body |
|---|---|---|
| PUT | `/pros-cons/{id}/assessments/{oid}/{fid}` | `{ assessment_pct?, actual_value?, satisfaction_pct?, improvement_pct?, notes? }` (server derives `cell_value`, `satisfaction_value`) |

### Aggregate / rollup  (Step #7.4 + #8.10 + Final Guidelines)
| Method | Path | Returns |
|---|---|---|
| GET | `/pros-cons/{id}/aggregate` | `{ rollups[], factors[], options[], config, final_decision_guidelines[] }` |

### Wizard step bookmark
| Method | Path | Body |
|---|---|---|
| POST | `/pros-cons/{id}/step` | `{ step: 1..8 }` |

> Replace `/pros-cons/` with `/swot/` for the same 18 routes on the SWOT module.
