# Access Control Matrix (ACM) — Dezider

_metadata: { "version": "3.5.1", "updated": "2026-05-04", "seed_version": "2026-05-04-04" }

## Concept
Every feature gated by a row in `acm_features`. Feature has `feature_id`,
`feature_name`, `release_stage`, and per-tier `access` (`full` | `locked` | `hidden`,
optional `quota`).

## Tier ladder
`unit_tester < integration_tester < alpha < beta < free < trial < paid_starter < paid_pro < paid_enterprise < paid_api`

## Release stages
`internal_only | alpha | beta | ga_free | ga_paid | ga_enterprise | deprecated`

## Counts (v3.5.1)
```
Total modules: 32
Total features: 89
Seed version: 2026-05-04-04
```

## Notable features by release stage

### ga_free (everyone)
- `solution_matrix_orgtype_individual`
- `solution_matrix_templates`
- `daily_time_log` (implicit via /api route, no explicit feature_id yet)
- `time_dezider_guidance`
- `privacy_data_export` / `privacy_data_delete` — DPDP rights; no quota

### ga_paid (trial + paid)
- `solution_matrix_orgtype_org / govt / nature`
- `solution_matrix_pdf_export` (trial = 5/month, starter = 10/month, pro+ unlimited)
- `solution_matrix` (7-step advanced)

### Cross-module ACM hooks
- `pp_org_portal` — gates the white-label sub-portal
- `pp_dashboards_yoy` — gates the Phase 3 YoY tab
- `handbook_viewer` (admin only)

## Runtime API
```
GET  /api/acm/my-access            → { features: { id: {access_level, quota, quota_used} } }
GET  /api/acm/feature/{feature_id} → single feature meta
POST /api/acm/seed?force=true      → admin re-seed (idempotent)
```

## Frontend check
```ts
const { checkFeature } = useACM();
const pdf = checkFeature('solution_matrix_pdf_export');
if (pdf.access_level === 'locked') { ... }
```

## How to add a feature (playbook)
1. Edit `backend/data/acm_seed_data.py` — find module section.
2. Append a feature dict with `feature_id`, `feature_name`, `release_stage`, `quota_unit`, `quota_resets`, `access`.
3. Bump `ACM_SEED_VERSION` (date-based).
4. Restart backend — auto-reseed runs.
5. Verify with `GET /api/acm/my-access`.

## Quota helpers
`_full(N)` → `{access:'full', quota:N}`. Usage tracked in `acm_quota_counters` keyed by (user, feature, month).
