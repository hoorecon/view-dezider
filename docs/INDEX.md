# Dezider — Admin Documentation

Maintained by the engineering team. Last refreshed: **2026-06-12 · v3.18.0** (Generic Notification Engine — CRUD trigger events → Email + WhatsApp · Import-URL Intelligence + AI Auto-Tune · PostHog Web Session Replays · Revenue Reconciliation · AI Wallet Config — 979 endpoints across 53 folders).

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
