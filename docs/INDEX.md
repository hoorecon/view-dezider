# Dezider — Admin Documentation

Maintained by the engineering team. Last refreshed: **2026-06-28 · v3.20.0** (Life Goals — 7-level GEM-backed planner in "My 360° Life"; Import-from-File for MyDezider Step 2 with AI factor/option extraction + optional web-crawl enrichment; the 4 sub-types "Present Problem · Need · Future Risk · Aspiration" now consistent across MyDezider, Pros & Cons and Solution Finder).

The documents below are the source of truth for product scope, system
behaviour, and operational posture. They are authored as plain markdown
in this folder, then rendered in-app at `/admin/docs/[slug]` for the
admin team to read on mobile.

## Index

| Slug | Title | Audience |
|---|---|---|
| `PRD` | Product Requirements Document | Product / leadership |
| `SRS` | System Requirements Specification | Engineering / QA |
| `API_REFERENCE` | REST API Reference | Backend / partners |
| `POSTMAN` | Postman / Insomnia collection (JSON) | Backend / QA |
| `REGRESSION` | Regression Test Catalogue | QA / CI |
| `UAT` | User-Acceptance Test scenarios | QA / users |
| `ACM` | Access Control Matrix | Product / security |
| `WOWO` | Ways of Working / Out (module guide) | Engineering |
| `CLD` | Causal Loop Diagram engine spec | Product / engineering |
| `SECURITY` | Security posture + threat model | Security / compliance |
| `DEPLOYMENT` | Deployment runbooks (Emergent / Docker / AWS / GCP) | DevOps |

Every doc has a `_metadata` section at the top with version + last-update.
If you edit a doc, **bump the version number and add a CHANGELOG line.**

## Changelog of this doc bundle (2026-06-28)
v3.20.0 refresh (Iter 176):
- **PRD, API_REFERENCE, ADMIN_USER_GUIDE, POSTMAN** — appendix sections for **Life Goals** (7-level GEM-backed planner in "My 360° Life": `/api/life-goals/*`), **Import-from-File** (`/api/file-import/decision/{id}` — pdf/docx/txt/xlsx/csv/image → AI factors+options + optional metered web-crawl enrichment), and the **4 sub-types** "Present Problem · Need · Future Risk · Aspiration" now persisted via `decision_type` on Pros & Cons + Solution Finder.
- `Postman_Collection.json` adds the **"Life Goals (My 360° Life)"** and **"Import from File (MyDezider Step 2)"** folders: **55 folders**.

## Changelog of this doc bundle (2026-06-12)
v3.18.0 refresh:
- PRD, SRS, API_REFERENCE, UAT, REGRESSION, POSTMAN — appendix sections for the **Generic Notification Engine** (CRUD-able trigger events: `import-analytics` weekly digest + `import-run-failed` instant alert → Email/Resend + WhatsApp/UltraMsg with per-channel toggles, 60s scheduler, throttling, dispatch log).
- `Postman_Collection.json` adds the "Notification Engine (Admin)" folder: **53 folders, 979 endpoints**.
- `ADMIN_USER_GUIDE.md` adds the Notification Engine admin page guide.

Previous (v3.16.0/v3.17.x):
All 12 handbook files refreshed to **v3.16.0**:
- PRD, SRS, API_REFERENCE, POSTMAN, UAT, ACM, WOWO, CLD, SECURITY, REGRESSION, DEPLOYMENT — appendix sections added for PostHog Web Replays, Revenue Reconciliation, Import-URL v3 (Factor-Type doctrine + hints + Set Expectations), AI Wallet admin pricing/threshold config, and EMERGENT_LLM_KEY topped-up status.
- `Postman_Collection.json` regenerated from live OpenAPI: **52 folders, 972 endpoints** (~520 KB).
- `ADMIN_USER_GUIDE.md` adds the AI Wallet Config and Revenue Recon admin pages.
