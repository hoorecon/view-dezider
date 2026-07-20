# REST API Reference — Dezider

_metadata: { "version": "3.23.1", "updated": "2026-07-19" }

> **Postman parity (v3.23.1):** the committed collection `/app/docs/Postman_Collection.json` now covers **every** live endpoint — **126 folders · 1,316 requests** — regenerated via `backend/scripts/generate_postman_collection.py` (see `POSTMAN.md`).

> **v3.22.0–v3.23.0 (2026-07-19) additions —** **FRAME monetization + scale**: `/admaker/*` (Sponsored-Solutions bid CRUD, AdRank×GSP auction hooks, CPC click billing, advertiser self-serve `my/*`), `/adtaker/*` (publisher CRUD with tracker IDs + API Key/Secret, public `widget.js`/`embed`/`track`, self-serve header-auth API, org portal), **Option Bank** `/decider-store/{tid}/bank*` (3 ingestion rails + stats), **async Finder jobs** `/decisions/{id}/finder/jobs` + `/finder/jobs/{job_id}` (10M-scale pipeline with % progress), Catalog-node `finder_ad_config` overrides and 4 new `ai-wallet/config` keys. Full tables in the "AdMaker · AdTaker · Option Bank (v3.22–v3.23)" section at the end.

> **v3.21.0 (2026-07-13) additions —** **Stripe Payments** `/stripe/*`: `POST /stripe/checkout` `{kind: ai_wallet|subscription, currency: usd|inr, pack_id|plan_id, success_url}` → `{checkout_url, session_id}`; `GET /stripe/status/{session_id}` (polls + idempotently fulfils); `POST /stripe/webhook` (verified when `STRIPE_WEBHOOK_SECRET` set); `GET /stripe/health`. Amounts are computed server-side; fulfillment reuses `_credit_refill` (wallet) / `apply_charge` (subscription). **AI Assistant** `/ai-assistant/quick-ask` & `/ai-assistant/conversations/{id}/message` now return a `model` field and default to Claude `claude-sonnet-4-6` (metered), falling back to `gpt-4.1-mini` when wallet credits are exhausted. **Auth** `/auth/register` & `/auth/google/session` responses now reflect `effective_whatsapp_verified` (honour `skip_whatsapp_gate`).

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

### Handbook viewer (`/admin-docs`) — serves the markdown files in `/app/docs/`
| Method | Path | Description |
|---|---|---|
| GET | `/admin-docs` | list all 16 handbook docs with version + updated |
| GET | `/admin-docs/{slug}` | fetch one doc (markdown body + parsed metadata) |
| GET | `/admin-docs/{slug}/pdf` | download the doc rendered as a PDF |

Slugs: `INDEX, SYSTEM_KT, PRD, SRS, API_REFERENCE, POSTMAN, REGRESSION, UAT, ACM, WOWO, CLD, SECURITY, DEPLOYMENT, PRODUCTION_DEPLOYMENT, ADMIN_USER_GUIDE` (see `routes/admin_docs_viewer.py DOC_FILES`).

### Live API tooling (`/admin/docs`) — generated from the running OpenAPI schema
| Method | Path | Description |
|---|---|---|
| GET | `/admin/docs/api-catalog?channel=` | Full endpoint catalog with channel tags, categories, request/response samples |
| GET | `/admin/docs/postman-collection` | Download the Postman v2.1 collection (identical to the committed `/app/docs/Postman_Collection.json` — regen script: `backend/scripts/generate_postman_collection.py`) |
| GET | `/admin/docs/{doc_type}` | AI-generated doc (`prd, srs, regression_tests, uat_cases`) from Mongo |
| POST | `/admin/docs/refresh/{doc_type}` | Regenerate one AI doc |
| POST | `/admin/docs/refresh-all` | Regenerate all AI docs |

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

---

## v3.16.0 — URL Analyse · AI Wallet · Revenue Recon · Analytics (2026-06-12)

### URL Analyse (auth) — Import-from-URL v3
| Method | Path | Description |
|---|---|---|
| POST | `/url-analyze` | Generic page → candidate factor extraction (LLM tiered) |
| POST | `/url-analyze/decision/{id}/import` | Import factors + options into an existing decision (groups-aware, hints supported) |
| POST | `/url-analyze/decision/{id}/set-expectations` | Claude-powered AI to fill `expected_value + operator` on every leaf factor (422 until factors + options + ≥1 `unit_value` present) |

**Request body (Import)** — all fields except `url` optional:
```json
{
  "url": "https://www.nobroker.in/property/...",
  "ai_tier": "precise",
  "expected_factor_count": 20,
  "expected_option_count": 4,
  "first_factor_name": "Rent",
  "first_option_name": "Main Listing"
}
```

**Response (Import)**:
```json
{
  "mode": "detail",
  "kind": "hier",
  "ai_provider": "emergent_precise",
  "structure": "hierarchical",
  "main_item": {...},
  "groups": [{"name":"Rent & Costs","source":"page","factors":[...]}],
  "items": [{"name":"Main Listing","values":{"Rent::Monthly":18000,...},"scores":{...}}],
  "hint_warnings": []
}
```

`ai_tier`:
- `fast` (default) — Gemini → Groq, wallet-billed at base multiplier.
- `precise` — Claude (claude-sonnet-4-6) via Emergent Universal Key first; fallback Claude → Gemini → OpenAI → Groq. Wallet-billed at admin-configurable multiplier.

Errors: `402 InsufficientCredits`, `422 missing prerequisites for set-expectations`, `503` when LLM budget capped.

### AI Wallet (auth)
| Method | Path | Description |
|---|---|---|
| GET | `/ai-wallet` | Current balance + thresholds |
| GET | `/ai-wallet/ledger?limit=` | Recent debits/credits |
| GET | `/ai-wallet/estimates` | Token-cost estimates per supported provider |
| GET | `/ai-wallet/provider-consent` | User's consent to use which providers |
| PUT | `/ai-wallet/provider-consent` | Update provider opt-ins |
| GET | `/ai-wallet/packs` | Available refill SKUs |
| POST | `/ai-wallet/refill/quote` | Quote a refill (returns price breakdown + GST) |
| POST | `/ai-wallet/refill/order` | Create Razorpay order |
| POST | `/ai-wallet/refill/verify` | Verify payment signature |
| POST | `/ai-wallet/refill/webhook` | Razorpay webhook (idempotent) |
| GET | `/ai-wallet/refill/checkout` | HTML checkout helper |

**AI Wallet — Admin (require_super_admin)**:
| Method | Path | Description |
|---|---|---|
| GET | `/admin/ai-wallet/config` | Read pricing & policy config |
| PUT | `/admin/ai-wallet/config` | Update — accepts `markup_user_pct`, `blended_usd_per_mtok`, `precise_model`, `precise_usd_per_mtok`, `import_group_threshold`, refill packs, etc. |
| POST | `/admin/ai-wallet/grant` | Grant credits to a user (dev/promo) |
| GET | `/admin/ai-wallet/users?limit=` | All-user wallet snapshot |

### Revenue Reconciliation — Super-Admin (require_super_admin)
| Method | Path | Description |
|---|---|---|
| GET | `/admin/recon/summary` | Verdict + 8 KPI cards (at_risk/safe, P&L) |
| GET | `/admin/recon/transactions?month=&limit=&skip=` | Per-txn tally rows |
| GET | `/admin/recon/transactions.csv?month=` | CSV export (PlainTextResponse stream) |
| GET | `/admin/recon/daily?days=` | LLM-token-derived ₹ vs BigQuery actual variance |
| POST | `/admin/recon/sync` | On-demand incremental Razorpay + GCP sync |
| GET | `/admin/recon/gcp-config` | Returns presence flag only — never the SA JSON itself |
| PUT | `/admin/recon/gcp-config` | Upload base64-encoded GCP Service-Account JSON + project_id |

**Tally formula** (per Razorpay payment):
```
buffer_inr = collected − rzp_fee − routed_markup_inr − earmarked_cost_inr
at_loss    = buffer_inr < 0
```
Structural note: Razorpay Route sends the entire markup to the linked account,
so primary account nets `collected − fee − markup ≈ cost − fee` — slightly below
earmarked LLM cost. Raise `markup_user_pct` in AI Wallet config if you need
`buffer_inr ≥ 0` per transaction.

### Analytics (PostHog server-side, internal)
PostHog events are emitted server-side via `core/posthog_client.py` — there is no
public REST surface. Frontend mirror lives in `src/utils/analytics.ts`.
Events: `signup`, `login{method}`, `decision_created`, `ai_assess_all_run`,
`payment_success`, `ai_credits_consumed`, `otp_sent`, `eg_session_completed`,
`screen` (frontend, every expo-router change), `tool_opened` (frontend, /tools/*).

Privacy posture: `identified_only` person profiles, `maskAllInputs:true`,
`capture_performance:false`, `user_id` only — never email/phone/PII.

### v3.16 endpoint count
**Total: 972 endpoints across 52 folders** (auto-generated Postman collection at
`/app/docs/Postman_Collection.json`, regenerated 2026-06-12 from live OpenAPI).

---
## v3.16.1 — Import-URL behaviour change (2026-06-12)

`POST /api/url-analyze` and `POST /api/url-analyze/decision/{id}/import`:
- Accuracy hints now GATE deterministic parses: a free table/matrix/grid parse
  that contradicts `expected_factor_count` / `expected_option_count` /
  `first_factor_name` / `first_option_name` is no longer returned — the
  pipeline escalates to the hint-guided AI extraction (hints embedded in the
  prompt as USER-VERIFIED PAGE FACTS + one corrective retry).
- The AI extractor now handles multi-item comparison/listing/filter pages
  (previously detail-pages only) — facets become factors, listed items become
  options.
- `ai_tier="precise"` escalates thin (<3 factor) deterministic parses to
  Claude even without hints.
- Response: `mode:"flat"` deterministic-fallback responses can now include
  `hint_warnings: string[]` (previously only `mode:"detail"` carried it).
  Responses are otherwise backward-compatible.

---
## v3.17.0 — Import-URL Intelligence endpoints (2026-06-12)

### Changed
- `POST /api/url-analyze` and `POST /api/url-analyze/decision/{id}/import`
  responses now include `run_id` (telemetry run identifier for feedback).
  Every run is LLM-classified by page type and recorded to `url_import_runs`.

### New
| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/url-analyze/runs/{run_id}/feedback` | user (owner) | 1-tap import accuracy verdict `{"verdict":"up"\|"down"}` |
| GET | `/api/admin/import-analytics/summary?days=30` | super-admin | KPIs + breakdowns by page_type / ai_provider / route |
| GET | `/api/admin/import-analytics/runs?days=&page_type=&route=&status=&feedback=&limit=&skip=` | super-admin | Run list (no prompt bodies); 400 on invalid page_type/route |
| GET | `/api/admin/import-analytics/runs/{run_id}` | super-admin | Full run incl. exact system prompt + raw LLM response (15 KB trunc, purged after 90 days) |

`page_type` ∈ comparison_matrix, listing_filter, detail, search_grid, article_roundup.
`route` ∈ deterministic_hier, deterministic_flat, ai_extraction, deterministic_fallback, llm_flat_fallback.
PostHog events: `url_import_completed`, `url_import_feedback`.

---
## v3.17.1 — AI Auto-Tune endpoints (2026-06-12)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/admin/import-analytics/tuning/generate?days=&page_type=` | super-admin | AI analysis of failing runs → proposed prompt edits (skips page types with no failures or pending suggestion) |
| GET | `/api/admin/import-analytics/tuning` | super-admin | `{suggestions[], active_overrides[]}` |
| POST | `/api/admin/import-analytics/tuning/{id}/approve` | super-admin | Activate override (LIVE immediately); 409 if already decided |
| POST | `/api/admin/import-analytics/tuning/{id}/reject` | super-admin | Archive suggestion |
| DELETE | `/api/admin/import-analytics/tuning/override/{page_type}` | super-admin | Revert to built-in default block |

---
## v3.18.0 — Notification Engine endpoints (2026-06-12)

Generic CRUD-able notification triggers (scheduled digests + event alerts) →
Email (Resend) + WhatsApp (UltraMsg) with per-channel on/off toggles.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/admin/notification-engine/registry` | super-admin | Catalogue of registered trigger-event keys (`import-analytics` scheduled, `import-run-failed` event) with kind + default schedule |
| GET | `/api/admin/notification-engine/triggers` | super-admin | All triggers incl. computed `schedule_label`, `next_run_at`, `last_status` |
| POST | `/api/admin/notification-engine/triggers` | super-admin | Create trigger `{event_key, name, schedule?, channels, throttle_minutes?}`; kind derived from registry; 400 on unknown event_key / invalid email / invalid phone / bad timezone |
| PUT | `/api/admin/notification-engine/triggers/{id}` | super-admin | Partial update (name, enabled, schedule, channels, throttle); recomputes `next_run_at` on schedule change; 400 if schedule set on event-kind |
| DELETE | `/api/admin/notification-engine/triggers/{id}` | super-admin | Remove trigger; 404 if missing |
| POST | `/api/admin/notification-engine/triggers/{id}/test` | super-admin | Send NOW to configured recipients (event-kind uses sample payload); returns per-channel delivery report; does NOT mutate schedule/throttle state |
| GET | `/api/admin/notification-engine/runs?trigger_id=&limit=50` | super-admin | Dispatch log (newest first, max 200) |

Trigger document: `{id, event_key, name, kind: scheduled|event, enabled, schedule:{frequency: daily|weekly|monthly, day_of_week, day_of_month(1-28), hour, minute, timezone}, channels:{email:{enabled, recipients[]}, whatsapp:{enabled, numbers[]}}, throttle_minutes (event-kind), next_run_at, last_run_at, last_status}`.
Run statuses: `sent` (≥1 delivery ok), `failed` (all attempted failed), `skipped_no_recipients`, `error` (builder/registry failure).
Scheduler: 60-second APScheduler tick (fcntl-singleton across workers, `NOTIFICATION_SCHEDULER_DISABLED=true` to disable). Boot seeds the default **Weekly Import Analytics Digest** (Mon 09:00 IST, email ON/empty, WhatsApp OFF) idempotently.
Event emission: `core.url_telemetry.record_run` fires `import-run-failed` (fire-and-forget, per-trigger `throttle_minutes` guard) whenever an import run errors.

---
## v3.20.0 — Life Goals + Import-from-File + Global Sub-types (2026-06-28)

### Life Goals — "My 360° Life" (stored in `db.gem_goals`; GEM is the central connector)
Sub-types are fixed in this exact order: **Present Problem · Need · Future Risk · Aspiration**.
7 levels: L1 Overall → L2 10yr → L3 5yr → L4 3yr → L5 1yr (Life Area) → L6 Quarterly (sub-type) → L7 Monthly.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/life-goals/meta` | auth | Config: `life_areas`, `sub_types` (ordered), `levels` (L1..L7), `horizons`, `statuses` |
| POST | `/api/life-goals` | auth | Create. `mode='timeline'` needs `{title, horizon∈[quarter,1yr,3yr,5yr,10yr], life_area}` (sub_type optional). `mode='tree'` needs `{title, level 1..7}`; L>1 needs `parent_id` of exactly level-1 (else 400); L1+parent → 400; L5 needs `life_area`; L6 needs `sub_type` |
| GET | `/api/life-goals` | auth | List; filters `?mode=&level=&parent_id=&life_area=` |
| GET | `/api/life-goals/tree` | auth | All tree goals flat + level config (client nests by `parent_id`) |
| GET | `/api/life-goals/{id}` | auth | One goal |
| PUT | `/api/life-goals/{id}` | auth | Update (title, description, status, life_area, sub_type, target_date, horizon, period_label, priority, progress 0-100). `status='done'` ⇒ progress 100 |
| DELETE | `/api/life-goals/{id}` | auth | Delete; **tree goals cascade-delete descendants** |

A Life Goal is a GEM goal carrying `lg_mode`, `lg_level`, `parent_id`, `horizon`, `sub_type`; it also appears in `GET /api/gem/goals` (`sub_type` mirrored into `goal_type`). Regular GEM goals have no `lg_mode`.

### Import from File — MyDezider Step 2
| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/api/file-import/decision/{decision_id}` | owner | Body `{filename, file_b64, ai_tier:'fast'|'precise', crawl_web:bool, context?}`. Parses pdf/docx/txt/xlsx/xls/csv/image(OCR) → AI extracts factors+options (metered via the AI wallet, same as URL import) → if `crawl_web`, DuckDuckGo + LLM enrich up to 8 options with factor values → `merge_into_mydezider`. Returns `{factors_added, options_added, enriched, enriched_count, factors[], options[]}`. Errors: unsupported ext / bad-empty base64 → 400, >8 MB → 413, unreadable / <20-char text → 422, no AI credits → 402 |

Post-import the client offers an opt-in to run the existing plan-capped **`POST /api/ai/suggest-factors`** ("Fetch My Best Factors", touchpoint `tp_best_factors`) to add missed-out factors.

### Sub-type field across the other modules
- **Pros & Cons** (`POST /api/pros-cons` + `PUT /api/pros-cons/{id}`) already persists `decision_type`.
- **Solution Finder** (`POST /api/solution-finders` + `PUT /api/solution-finders/{id}`) now accepts/persists `decision_type` (one of `problem|need|risk|aspiration`).


---

## AdMaker · AdTaker · Option Bank (v3.22–v3.23)

### Finder — run & async jobs
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/decisions/{id}/finder/config` | owner | Resolved defaults + `total_options` (embedded) + **`bank_options`** (Option-Bank size — UI auto-switches to job mode when > 0) |
| POST | `/api/decisions/{id}/finder/run` | owner | Sync run over embedded options. Response now also carries `sponsored[]` (auction winners, **no bid/price fields**), `ad_config {min_cutoff_pct, sponsored_n, region, eligible_above_cutoff}` |
| POST | `/api/decisions/{id}/finder/jobs` | owner | **Async Option-Bank run** (indexed S1 prune → streamed heap Top-K → auction). Body `{min_options?, max_options?, top_n?, match_rule?, region?, force?}`. Returns `{job_id, cached}` — identical expectations-hash within 10 min returns the cached job |
| GET | `/api/finder/jobs/{job_id}` | owner | Poll `{status: running|done|error, progress {pct,label}, result}`. Result: `{engine:'bank', stage, total_options, candidates, survivors, scanned, ranked(≤50), top, top_ids, sponsored, ad_config, duration_ms}` |

### AdMaker Program — admin bid management
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/admaker/bids?template_id=&status=` | admin | List (joined `template_title`; counters: impressions, clicks, spent_paise, last_price_paise) |
| POST | `/api/admaker/bids` | admin | Create. `{template_id, option_name, advertiser_name, bid_paise≥1, region('global'|cc), budget_paise(0=∞), slot_start/slot_end (ISO), daily_start_hour/daily_end_hour (0-23, overnight wrap ok), timezone(IANA), status}` |
| PUT | `/api/admaker/bids/{bid_id}` | admin | Partial update (same fields) |
| DELETE | `/api/admaker/bids/{bid_id}` | admin | Delete |
| POST | `/api/admaker/track` | user | Sponsored **click → CPC charge** at the stored GSP price. `{bid_id, decision_id?, option_id?}` → `{ok, charged_paise}`; auto-`exhausted` on budget |
| GET | `/api/admaker/resolve-config?node_id=&template_id=` | admin | Effective `{min_cutoff_pct, sponsored_n}` + the SOURCE of each value (template / CCM node / global) |

### AdMaker Studio — advertiser self-serve (same user login, ACM `admaker_program`)
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/admaker/my/eligible-options?template_id=` | user¹ | Options linked to the caller's own Solution-Store listings (incl. same-org creators + bank `store_bridge` refs) |
| GET | `/api/admaker/my/bids` | user¹ | Own bids (joined titles) |
| POST | `/api/admaker/my/bids` | user¹ | Create — **403 unless the option is owned** (ownership invariant) |
| PUT/DELETE | `/api/admaker/my/bids/{bid_id}` | user¹ | Own-only; `option_name` changes are stripped (needs fresh ownership check) |
| GET | `/api/admaker/my/dashboard` | user¹ | `{totals {bids, impressions, clicks, ctr_pct, spend_paise, avg_cpc_paise}, bids[+ctr_pct, avg_cpc_paise]}` |

¹ passes when: platform admin, OR `org_role ∈ {org_admin, advertiser}`, OR ACM `admaker_program` allowed (trial/paid_pro/paid_enterprise). Otherwise **403** with the ACM upgrade message.

### AdTaker Program — publishers, keys, widgets
| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/adtaker/publishers` | admin | List + lifetime totals per tracker. Never returns `api_secret_hash` |
| POST | `/api/adtaker/publishers` | admin | Create → mints `tracker_id (DZ-PUB-XXXXXXXX)` + `api_key (dzk_…)` + **`api_secret (dzs_…) returned ONCE`** (stored sha256-hashed). Optional `org_id` link, `revenue_share_pct` (default 68) |
| PUT | `/api/adtaker/publishers/{publisher_id}` | admin | Update name/site/share/status/`org_id` |
| POST | `/api/adtaker/publishers/{publisher_id}/rotate-keys` | admin | New key+secret (old pair dies instantly; secret returned once) |
| DELETE | `/api/adtaker/publishers/{publisher_id}` | admin | Delete |
| GET | `/api/adtaker/publishers/{publisher_id}/stats?days=30` | admin | Totals, CTR, daily series, `earnings_estimate_paise` (= conversions × bounty × share%) |
| GET | `/api/adtaker/self/profile` | key² | Publisher profile |
| GET | `/api/adtaker/self/stats?days=` | key² | Same stats payload, self-serve |
| GET | `/api/adtaker/self/apps` | key² | Live Decider Apps + a ready-to-paste `embed_snippet` per app |
| GET | `/api/adtaker/portal/me?days=` | org session | Publishers linked to the caller's `org_id` + stats (403 for non-org users) |
| GET | `/api/adtaker/widget.js?tracker=&app=` | public | Drop-in `<script>` loader → injects the embed iframe (cache 5 min) |
| GET | `/api/adtaker/embed/{template_id}?tracker=` | public | Self-contained HTML card (`frame-ancestors *`), logs an **impression**; CTA beacons a click + deep-links `/decider-store/{id}?ref={tracker}` |
| POST | `/api/adtaker/track` | public | Beacon `{tracker, template_id, event: impression|click|conversion}` (404 on unknown/paused tracker) |

² headers `X-Adtaker-Key: dzk_…` + `X-Adtaker-Secret: dzs_…` (401 invalid, 403 paused).

Conversion attribution: `POST /api/decider-store/{tid}/clone` accepts optional `ref` (tracker ID) → logs a `conversion` event.

### Option Bank — ingestion & management (all admin)
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/decider-store/{tid}/bank` | `{total, by_source}` |
| POST | `/api/decider-store/{tid}/bank/sync-template` | Rail 1a: template's embedded options → bank (idempotent) |
| POST | `/api/decider-store/{tid}/bank/ingest/solutions` | Rail 1b: bridged Solution-Store items (`quantitative_factors` keyed by sub-factor id) merged with ReviewNet `baseline_profile` |
| POST | `/api/decider-store/{tid}/bank/ingest/partner` | Rail 2: external JSON API. `{api_url, items_path?, name_key, value_map {sub_id: json_key}, headers?, limit?}` |
| POST | `/api/decider-store/{tid}/bank/ingest/bulk` | Rail 3: raw rows (Deep-Import/scripts). `{items:[{name, values:{sub_id: raw|{raw,num}}}], source}` (≤50K/call) |
| DELETE | `/api/decider-store/{tid}/bank?source=` | Clear all or one source |

### Config surfaces
- `PUT /api/catalog/nodes/{node_id}` now accepts `finder_min_cutoff_pct` (0-100) and `finder_sponsored_n` (0-20); **-1 clears** the override. Stored as `finder_ad_config`; inherited by ALL descendants (nearest configured ancestor wins).
- `PUT /api/admin/ai-wallet/config` new keys: `finder_min_cutoff_pct` (default 60), `finder_sponsored_n` (3), `adtaker_default_share_pct` (68), `adtaker_conversion_bounty_paise` (500).
- Decider-Store template create/update: `catalog_node_id` (Scenario mapping) + `finder_settings.{min_cutoff_pct, sponsored_n}` per-app overrides.
