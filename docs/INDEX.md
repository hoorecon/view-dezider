# Dezider — Admin Documentation

_metadata: { "version": "3.23.1", "updated": "2026-07-19", "author": "engineering" }

Maintained by the engineering team. Last refreshed: **2026-07-19 · v3.23.1** (FRAME monetization: AdMaker sponsored auction + AdTaker publisher widgets + 10M-scale Option-Bank Finder with async jobs; full KT refresh across SRS / API_REFERENCE / SYSTEM_KT §10 / ADMIN_USER_GUIDE "Ad Programs" / PRD appendix / ACM; Postman collection **fully regenerated from live OpenAPI — 126 folders, 1,316 requests, 100% endpoint coverage** with a repeatable generator script).

The documents below are the source of truth for product scope, system
behaviour, and operational posture. They are authored as plain markdown
in this folder, then rendered in-app at `/admin/docs/[slug]` for the
admin team to read on mobile.

## Index

| Slug | Title | Audience |
|---|---|---|
| `SYSTEM_KT` | System KT — block diagram & flow charts | Everyone (start here) |
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
| `PRODUCTION_DEPLOYMENT` | Production deployment runbook (live infra: Cloudflare + EC2 + sync.sh) | DevOps |
| `ADMIN_USER_GUIDE` | Admin User Guide — every admin screen, how-to & workflows (Functional KT) | Admins / support |

Every doc has a `_metadata` section at the top with version + last-update.
If you edit a doc, **bump the version number and add a CHANGELOG line.**

## Changelog of this doc bundle (2026-07-19)
v3.22.0–v3.23.0 refresh (Iter 193–194, FRAME):
- **SRS** — two new sections: *v3.22.0 FRAME* (Filter→Rank→Auction→Merge→Embed: organic-is-sacred ranking, Min-Cutoff % quality gate inherited through the Central Catalog, AdRank×GSP auction with region/time-slot bids, AdTaker widget spec) and *v3.23.0 FRAME @ Scale* (Option-Bank architecture S0–S4, 3 ingestion rails, measured benchmarks 200K→2.65s, identity ladder AdMaker/AdTaker/OrgLogin).
- **API_REFERENCE** — full endpoint tables for `/admaker/*` (bids CRUD, CPC track, resolve-config, advertiser `my/*`), `/adtaker/*` (publishers, rotate-keys, self-serve key-auth trio, org portal, public widget/embed/track), Option Bank rails, async finder jobs, catalog + ai-wallet config keys.
- **Postman_Collection.json** — **fully regenerated from live OpenAPI: 126 folders · 1,316 requests · 100% endpoint coverage** (was 58 folders/1,021 requests with ~300 newer endpoints missing and a 419-request "Other" bucket). Module taxonomy (`backend/prompts/admin_docs_taxonomy.py`) overhauled to name every folder; new repeatable generator `backend/scripts/generate_postman_collection.py`; AdTaker self-serve requests carry `X-Adtaker-Key/-Secret` headers automatically. `POSTMAN.md` documents regeneration + the collection vars (`adtakerKey/adtakerSecret/trackerId/finderJobId`).
- **SYSTEM_KT** — new §10: FRAME block diagram (both scales), data stores, identity ladder, debugging cheat-sheet rows.
- **ADMIN_USER_GUIDE** — new "Ad Programs" section: `/admin/ad-programs` 3-tab guide (bids incl. GSP/budget semantics, publishers incl. one-time secret + rotate + org link, cutoffs & slots), Decider-Store Catalog/Bank actions, and the two end-user surfaces (AdMaker Studio ACM gating + ownership rule, Publisher Portal org gate).
- **PRD** — appendix: business narrative for Sponsored Solutions, embeddable apps, and the Option-Bank scale story.
- **ACM** — module `ad_programs` / feature `admaker_program` matrix + seed 2026-07-19-01.

## Changelog of this doc bundle (2026-07-13)
v3.21.0 refresh:
- **NEW `SYSTEM_KT`** — quick-KT doc: whole-system block diagram, end-to-end flow charts (auth, PRR, AI-metered-chat, Stripe, Zoho, OCR import, deploy pipeline), data stores, integrations, and a screen-by-screen visual reference. In-app viewer now also renders images (`![alt](url)`).
- **Stripe** — new `/api/stripe/*` (checkout · status · webhook · health): USD/INR card checkout for AI-wallet top-ups + subscriptions, alongside Razorpay. Idempotent fulfillment. (Prod needs a real `STRIPE_API_KEY` — pod value is a placeholder.)
- **AI Assistant** — now defaults to Anthropic **Claude (claude-sonnet-4-6)** via the metered wallet; on quota-exceeded it falls back to `gpt-4.1-mini`.
- **Auth** — `/auth/register` + `/auth/google/session` now honour `skip_whatsapp_gate` (fix: new sign-ups were wrongly forced to OTP).
- **MyDezider** — operators are now common to both Quantitative & Qualitative factors (value-driven default: numeric→"≥", text→"Contains"; user-overridable).
- **Ops** — deploy build fix (`opencv-python==4.11.0.86` numpy conflict); `SECRET_KEY` + `CORS_ORIGINS` added to backend env.
- Docs refreshed to v3.21.0: `PRD, SRS, API_REFERENCE, ADMIN_USER_GUIDE, DEPLOYMENT, PRODUCTION_DEPLOYMENT, SECURITY, INDEX` + new `SYSTEM_KT`.

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
