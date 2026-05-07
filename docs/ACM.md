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

---
## v3.14.0 — Tier Matrix integration  (2026-05-07)

The ACM remains the **fine-grained access control** layer (user_type × subscription_plan → quotas + allowed actions per feature). Layered above ACM is now the **7-Chakra Subscription Tier Matrix** which performs the **marketing-tier feature gate**:

| Layer | Purpose | Source |
|---|---|---|
| **Tier Matrix** (NEW) | Maps each ACM module + feature to a chakra tier (Root → Crown). Marketing/pricing layer. | `db.tier_matrix` |
| **ACM** | Per-tier-allowed module's quota + role gating + action-level allowed_actions | `db.acm_modules`, `db.acm_features` |

**Resolution order at runtime**: tier-matrix(allowed?) → ACM(quota + role check). Both must pass.

**Cascade rules**: Toggle ON at tier T → all higher tiers ON automatically. Module=N at tier T → all features under it forced N at tier T (lock icon shown).

**Admin UI**: `/admin/tier-matrix` (32 modules × 7 chakras grid).

## v3.14.0 — Customer Segments TG Master

Companion to ACM/tier-matrix: defines **non-technical** target-group profiles (demography, psychography, behavioural, firmographic) per segment. Each segment maps to:
- Chakra tier (recommended)
- Multi-currency multi-country pricing per tier
- Optional market-research module association

**Admin UI**: `/admin/customer-segments`.
