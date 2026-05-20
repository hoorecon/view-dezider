# Regression Suite Authoring Guide

Every new feature, bug-fix, or flow change must add or extend a regression
suite. This guide shows how — it takes 5 minutes per case.

## Where Suites Live

```
backend/core/regression/
├── registry.py        # central registry (don't touch)
├── runner.py          # async runner (don't touch)
├── scheduler.py       # weekly run (don't touch)
├── models.py          # Suite, TestCase, RunResult schemas
└── seed_suites.py     # ← add your suite here
```

For a brand-new feature you may also create a sibling module like
`seed_suites_my_feature.py` and import it from `__init__.py`.

## Anatomy of a Suite

```python
from core.regression import registry
from core.regression.models import Suite, TestCase


async def _case_list_works(ctx):
    """Async test body. Returns dict {passed, message, ...}."""
    r = await ctx.http.get(
        "/api/my-feature/items",
        headers=ctx.auth_headers(admin=True),
    )
    if r.status_code != 200:
        return {"passed": False, "message": f"status={r.status_code}"}
    items = r.json()
    if len(items) < 3:
        return {"passed": False, "message": f"count={len(items)} expected ≥ 3"}
    return {"passed": True, "message": f"count={len(items)}"}


registry.register_suite(Suite(
    id="my_feature_api",          # globally unique, snake_case
    feature="My Feature",         # group label shown in Admin UI
    module="my_feature",          # internal module key
    kind="api",                   # "api" or "ui"
    title="My Feature — API surface",
    description="GET / POST smoke + integration cases",
    owner_file=__file__,
    cases=[
        TestCase("mf_list_smoke",    "GET /items returns ≥3",  "smoke",      _case_list_works),
        TestCase("mf_create_funct",  "POST then GET roundtrip", "functional", _case_create_and_read),
    ],
))
```

### TestContext

Every case body receives a `TestContext`:

| Attribute | Use |
|---|---|
| `ctx.http` | `httpx.AsyncClient` with `base_url` preset |
| `ctx.admin_token` | session token for `admin@test.com` (set on boot) |
| `ctx.user_token` | session token for the regular test user |
| `ctx.auth_headers(admin=True)` | shortcut → `{"Authorization": "Bearer <token>"}` |
| `ctx.scratch` | dict shared between cases in the same suite (rarely needed) |

### Level

| Level | When to use |
|---|---|
| `smoke` | Fast endpoint reachability + basic schema check (≤ 1s each). Always include at least one smoke case per feature. |
| `functional` | End-to-end behaviour, create+read+update cycles, edge cases. Heavier. Runs in weekly. |

### Kind

| Kind | Behaviour |
|---|---|
| `api` | Runs inline inside the FastAPI process via httpx. |
| `ui` | Currently declarative-only — produces a `manual_pending` result. Once the Playwright sidecar lands (Phase B.2) the runner will dispatch UI specs to it. Until then, store the spec as a markdown file under `docs/regression/ui/<feature>.md` and set `ui_spec_path` on the Suite. |

## Reusable Case Factories

For trivial GET assertions, use `_make_get` / `_make_list_min` (already in
`seed_suites.py`). Don't duplicate them — extend with your own helpers in
the same file if a new pattern emerges.

## Where Results Go

- All runs persisted in `db.regression_runs` (one document per run).
- Runs older than 7 days are auto-pruned on every new run.
- Weekly auto-run: Sundays 02:00 UTC.
- Admin Panel page: `/admin/regression-tests` — list, filter, run, view history.
- Latest status badge per suite: `GET /api/admin/regression/latest`.

## Checklist Before You Commit a New Feature

- [ ] Suite registered with stable `id` and useful `feature` + `description`
- [ ] At least one `smoke` case (must complete in < 1s, hit the live endpoint)
- [ ] One or more `functional` cases for the happy-path flow
- [ ] If the feature has a UI, add a UI suite + Playwright spec at `docs/regression/ui/<feature>.md`
- [ ] Locally verified: `python -c "import asyncio; from core.regression import runner, seed_suites; print(asyncio.run(runner.run(level='smoke', kind='api', suite_ids=['my_feature_api'])).to_dict())"`

## Phase B.2 (Roadmap)

- Playwright sidecar container with `mcr.microsoft.com/playwright:v1.x-jammy`
  → runs UI specs on every manual/weekly trigger
- SMTP-based weekly report email (zipped JSON + HTML summary) using
  credentials from the Settings Hub
- HTML diff report compared to last week's run
