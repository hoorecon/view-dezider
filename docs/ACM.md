# Access Control Matrix (ACM) — Dezider

_metadata: { "version": "3.4", "updated": "2026-05-04", "seed_version": "2026-05-04-03" }

## Concept

Every feature in Dezider is gated by an entry in the `acm_features` collection.
A feature has:

- **`feature_id`** — stable string ID (used in code via `checkFeature(id)`).
- **`feature_name`** — human-readable label.
- **`release_stage`** — the lifecycle bucket (see below).
- **`access`** — a per-tier dict declaring `full` / `locked` / `hidden` plus optional quota.

## Release stages

| Stage | Visible to |
|---|---|
| `internal_only` | unit_tester, integration_tester (admin) |
| `alpha` | + alpha members |
| `beta` | + beta members |
| `ga_free` | everyone (including free) |
| `ga_paid` | trial + every paid tier |
| `ga_enterprise` | enterprise + api |
| `deprecated` | hidden everywhere new, still works for grandfathered users |

## Tier ladder

```
unit_tester < integration_tester < alpha < beta < free < trial
           < paid_starter < paid_pro < paid_enterprise < paid_api
```

## Access verbs

| Verb | Meaning | UI behaviour |
|---|---|---|
| `full` | usable, optionally with `quota` | normal control |
| `locked` | visible but click → upgrade prompt | greyed + lock icon |
| `hidden` | not even rendered | n/a |

## Module-feature counts (v3.4 seed)

```
Total modules: 32
Total features: 89
Seed version: 2026-05-04-03
```

### Notable additions in v3.4

- `solution_matrix_orgtype_individual` (ga_free, full for all)
- `solution_matrix_orgtype_org` (ga_paid, locked on free)
- `solution_matrix_orgtype_govt` (ga_paid, locked on free + starter)
- `solution_matrix_orgtype_nature` (ga_paid, locked on free + starter)
- `solution_matrix_pdf_export` (ga_paid; trial = 5/month, starter = 10/month, pro+ = unlimited)
- `solution_matrix_templates` (ga_free, full for all)

## How features get checked

### Backend
```python
from core.acm_engine import user_can_access
allowed = await user_can_access(user_id, "solution_matrix_pdf_export")
```

### Frontend
```ts
import { useACM } from '@/hooks/useACM';
const { checkFeature } = useACM();
const pdf = checkFeature('solution_matrix_pdf_export');
// pdf.access_level === 'full' | 'locked' | 'hidden'
```

## Re-seeding

The seed runs **automatically on boot** if `ACM_SEED_VERSION` in
`acm_seed_data.py` differs from the latest record in `acm_state`. To
force a re-seed without bumping the version, hit:

```bash
curl -X POST -H "Authorization: Bearer <admin-token>" \
  http://localhost:8001/api/acm/seed?force=true
```

## Adding a new feature

1. Open `backend/data/acm_seed_data.py`.
2. Find the relevant module section (or add a new module entry to `MODULES`).
3. Append a feature dict with `feature_id`, `feature_name`, `release_stage`, `quota_unit`, `quota_resets`, and `access` (one entry per tier).
4. Bump `ACM_SEED_VERSION` (date-based, eg `2026-05-04-04`).
5. Restart the backend → auto-reseed runs.
6. Verify with `GET /api/acm/my-access`.

## Quota helpers

For monthly-quota features, the per-tier `_full(N)` helper produces
`{"access": "full", "quota": N}`. The runtime tracks usage in
`acm_quota_counters` keyed by user + feature + month.
