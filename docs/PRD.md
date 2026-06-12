# Product Requirements Document — Dezider

_metadata: { "version": "3.17.0", "updated": "2026-06-12", "author": "engineering" }

## 1. Vision

Dezider is a decision-intelligence platform pairing personal decision tools
(PRR, Solution Matrix, Goal Setter…) with a civic feedback rail (Public
Pulse). v3.5 adds an **Accountability Trilogy** — Daily Time Log, Time
Dezider (Raja Guru), and Time Store — that together answer the question
"Am I investing time the way I planned, and can I buy back time?"

## 2. Personas

| Persona | Daily volume | Primary surfaces |
|---|---|---|
| Individual user | 5–20 sessions/week | PRR flow, Goal Setter, Journal, Solution Matrix, **Daily Time Log**, **Time Dezider**, **Time Store** |
| Org admin | 1–3 dashboards/day | Public Pulse Org dashboards, Sub-Portal config, **Time Store seller** |
| Govt department | Long horizon | Sub-Portal embedded on dept website, heatmaps |
| Internal admin | Continuous | ACM, audit logs, metrics, handbook |

## 3. Modules

### 3.1 Decision tools (unchanged)
PRR, Test123, Solution Finder, Solution Matrix (dual-mode 15/60 cell), Goal
Setter, Goal Manifestation, TEPFI, SWOT, Pros & Cons, CLD engine, AALA,
AAAA, Conflict Breaker, Emotional Gatekeeper, PNA, Lifestyle Designer /
Evaluator, GEM Flight / Goal, Time Dezider (legacy schedule), Unconditional
Happiness, Consciousness Diary, Meditation.

### 3.2 Solutions Store (unchanged)
9-language store of solution playbooks. **NEW**: optional time-save fields
(`time_save_per_day_min`, `time_save_per_week_min`) per solution so the
Time Store can filter eligible services.

### 3.3 Public Pulse (unchanged)
Phase 1+2 (intake + dashboards, k-anon gated) and Phase 3 (YoY analytics +
white-labelled Org sub-portals). AI clustering deferred on LLM budget.

### 3.4 Accountability Trilogy (NEW in v3.5)

**Daily Time Log** — one timeline per calendar date
- Manual time blocks + auto-rollup from CTT / Lifestyle Eval / Meditation / Journal
- 4 key timings per user: wake_up, bed_time, business_start, business_end
- Streaks (≥15 min logged counts the day)
- Weekly review: adherence-pct vs lifestyle plan, CTT / lifestyle / meditation totals, variance notes
- Endpoints at `/api/daily-time-log/*`, screens at `/tools/daily-time-log`, `/tools/weekly-review`

**Time Dezider — Raja Guru** (rule-based v1)
- 4 slots: Morning intent-setter, Midday recalibration, Evening retrospective, event-driven Next-Action
- Candidate picks scored across urgency × importance × energy-match × time-window × streak-risk × CLD-leverage
- Sources: user CTT tasks, Lifestyle plan, Solution Matrix, latest CLD
- Nudge cadence: morning / midday / evening / hourly / event-driven, each independently toggleable
- Accept / Defer / Skip feedback loop captured for future tuning
- Endpoints at `/api/raja-guru/*`, screen at `/tools/time-dezider`
- **AI overlay**: logged in backlog.md — reads CLD + journal + matrix narrative cells when LLM budget resets

**Time Store** (curated marketplace)
- Time Audit: scans user's CTT (low-priority + long), Lifestyle (social-media heavy), Matrix (cells keyed as mundane/routine/chore) and surfaces save opportunities tagged with TEPFI lever (People / Finance / Time)
- Services: filtered Solutions Store listings priced to save N min/day (buckets 30/60/120) or N min/week (buckets 180/300/600/900)
- Delegations: internal inbox for requests routed to Contacts / Org members / family
- Purchases: payment MOCKED pending Razorpay keys (docs: /app/memory/backlog.md)
- Endpoints at `/api/time-store/*`, screen at `/tools/time-store`

### 3.5 Cross-cutting (enhanced)
- **Auth**: unchanged
- **ACM**: 89 features (bumped seed to `2026-05-04-04`)
- **DPDP / GDPR**: full export / 7-day soft delete / cancel / admin-cron purge. User-facing screen at `/tools/privacy-data` (linked from Profile).
- **Voice nav**: 6 languages, 21 routes (includes daily-time-log, time-dezider, time-store)
- **Subscription**: unchanged (Razorpay test keys present; live keys pending)
- **Collaboration / Video / Notifications / Admin**: unchanged

## 4. Non-functional requirements (v3.5)

Unchanged from v3.4 (1M users / 10K concurrent, p95 < 300 ms cache-hot).

New hot paths:
- `/api/daily-time-log/{date}` with auto-rollup: 4 collection scans + aggregate → target p95 400 ms
- `/api/raja-guru/day-plan`: 4 collection reads + in-memory scoring → target p95 300 ms
- `/api/time-store/time-audit`: 3 collection reads + string search → target p95 400 ms

## 5. Out of scope (v3.5)

- Push notifications for Raja Guru nudges (logged in backlog)
- Real-time delegation inbox routing (v3.6)
- Time Store live payments (awaiting Razorpay keys)
- Native iOS / Android builds (still on Expo OTA)

## 6. Open / blocked

| Item | Owner | Status |
|---|---|---|
| DigiLocker eKYC | Backend | BLOCKED on API Setu keys |
| Exotel SMS OTP | Backend | BLOCKED on DLT template approval |
| LLM budget reset | Platform | BLOCKED — AI endpoints serve 503 |
| Raja Guru AI overlay | Backend | DEFERRED until LLM budget resets |
| Time Store live payments | Backend | DEFERRED until Razorpay live keys |

## 7. Changelog

- **3.5.1 (2026-05-04)**: Added `/tools/privacy-data` screen (DPDP user UX — export / delete-request / cancel / status). `/tools/time-store/services` query relaxed to honour `is_authorized=True` system-seeded catalogue + `approval_status=approved` user-submitted items. Seed-time-store-services migration (`backend/scripts/seed_time_store_services.py`) patched 7 existing items and inserted 8 new time-saver SKUs (BigBasket, Urban Company, UClean, ClearTax, GetFriday VA, FreshMenu, DriveU, Zoho Books). Fixed purchase-endpoint collection mismatch (`solutions_store_solutions` → `solutions_store`).
- **3.5 (2026-05-04)**: Accountability Trilogy (Daily Time Log + Time Dezider Raja Guru + Time Store). 5 seeded time-save services in Solutions Store. ACM seed v04. 156/156 backend tests.
- **3.4 (2026-05-04)**: Production hardening (sec headers, body cap, gzip, metrics, audit log, DPDP, idempotency), 11 admin docs, deployment scaffolding, in-app docs viewer at `/admin/handbook`.
- **3.3 (2026-04-15)**: Solution Matrix OrgType nested schema, PP Phase 2.5.
- **3.2 (2026-03-30)**: PP Phase 2 dashboards.
- **3.1 (2026-03-10)**: PP Phase 1 + 4 research tools.
- **3.0 (2026-02-20)**: ACM v2 (89-feature matrix).

---
## v3.14.0 — Subscription Tier Matrix · Customer Segment Master · Public Pricing (2026-05-07)

### Problem
Sales team had no way to map our 32 ACM modules + 89 features to the 7 aspirational customer tiers (Freelancer → Fortune Venture). Pricing was hardcoded INR-only. No formal target-group profiles existed for go-to-market.

### Solution
Three integrated modules:
1. **Tier Matrix** (already existed) — admin-grid mapping modules/features × 7 chakra tiers with cascade-up + module-dominates rules
2. **Customer Segment Master** (NEW) — admin-managed TG profiles capturing demography, psychography, behavioural, firmographic factors with AI-research per factor
3. **Public Pricing Page** (NEW) — `/pricing` route consuming both, with Monthly/Annual toggle, 8-country currency picker, expandable feature comparison

### Acceptance criteria — all met ✅
- Admin can create segments with predefined + custom factors
- Per-factor AI-research fills value via Emergent LLM key with graceful fallback
- Each segment supports tier pricing in 8 currencies (INR/USD/GBP/EUR/AED/SGD/AUD/CAD)
- Public pricing page renders 7 tier cards + comparison table
- 60s TTL cache on hot path; auto-invalidated on admin writes
- Indexed for production scale (`segment_id` unique, `created_at` sort)

---
## v3.15.0 — 8-Step Pros & Cons / SWOT Decision Framework (2026-05-18)

### Problem
The standalone Pros & Cons module captured a single flat list of pros and cons per analysis with no concept of multiple options, no factor consolidation, no per-option assessment, and no overall satisfaction scoring. Same gap existed on the SWOT module (4-quadrant flat list only). The user's reference workbook (`REFERENCE Career Consultation to Dr Raj.xlsx`) formalised an 8-step framework that elevates Pros & Cons / SWOT from "brainstorm list" into a structured multi-option consulting tool with knock-out rules, prioritisation and weighted satisfaction scoring.

### Solution
A new 8-step framework available on **both** Pros & Cons and SWOT modules. PRR / MyDezider core flow is **untouched** — this is a parallel consulting layer for the simpler P&C and SWOT screens.

The eight steps are:
1. **List Direct Factors** — name + optional expected value & unit
2. **List Options + per-option Pros & Cons** — capture P&C scoped to each option
3. **Promote P&C → Factors** — one-tap auto-promotion; Cons are prefixed with `"SHOULD NOT - "`; source provenance retained
4. **De-duplicate / Group as sub-factors** — manual parent picker (AI suggestion reserved for WOWO tier)
5. **Review factor tree** — collapsible parent/child view (sub-factor-level ratings reserved)
6. **Notation (Mandatory/Optional) + knock-out threshold** — admin-set or per-decision threshold % below which mandatory mismatch disqualifies the option
7. **Prioritisation + Std Rating + Assessment %** — drag-reorder; `Cell Value = Assessment% × Std Rating`
8. **Detailed Assessment** — Subjective/Objective × Improvable (n/y/y_bf) × My-expectation / Others' / Market-standard × Realistic gap% & value → Realistic Rating, then per option: Actual value, Satisfaction %, Improvement %, **Satisfaction Value** + per-option **Overall Satisfaction %** + auto rank #

### Final Decision Guidelines
12 reference tie-breaker rules surfaced as a modal at the end of Step #8 (timing, effective time, worth-considering, expected value, primary/secondary classification, prioritisation, realistic gap, actual value, assessment %, primary-vs-secondary matching, positive sequencing scenarios 2A/2B).

### Acceptance criteria — all met ✅
- Existing legacy Pros & Cons + SWOT flat lists preserved (zero-regression)
- Backend persists factors, options, P&C-per-option, assessments, config in same document
- Promote step is idempotent + prefixes Cons with `"SHOULD NOT - "`
- Server-side knock-out detection on Mandatory factors when threshold set
- Per-option Joint Score, Overall Satisfaction %, Rank, Disqualified flag computed
- Final Decision Guidelines available via dedicated modal & Step 8 CTA
- Single wizard UI (`/tools/pros-cons-wizard`) drives both modules via `?module=swot|pros-cons`
- "Open 8-step framework" CTA added to both module detail screens

### Out of scope (deferred)
- AI suggestion for Step #4 de-dup / group → WOWO tier (LLM credits)
- Sub-factor level rating + roll-up — Step #5 enhancement
- Step #7 dual rankings (low-to-high column)
- Step #4 fuzzy-match similarity helper

---
## v3.16.0 — PostHog Web Replays · Revenue Recon · Import-URL v3 · AI Wallet (2026-06-12)

### Problem
v3.15 left four enterprise-grade gaps:
1. We had backend & frontend PostHog events but **no session replays** (RN SDK can't record on web).
2. No granular reconciliation between Razorpay collections, transfers/routes, and Gemini/Claude LLM costs — risk of structurally losing money on every paid AI call.
3. Import-from-URL v1/v2 mapped factors but conflated `data_type` (text/number) with `factor_type` (Quantitative undisputed-fact vs Qualitative judgment), and lacked page-defined grouping support, accuracy hints, or AI-assisted operator inference.
4. AI Wallet had no admin-facing pricing controls for the precise (Claude) tier nor a way to govern AI-grouping behaviour.

### Solution

**A. PostHog Web Session Replays**
- Platform-split `src/utils/analytics.ts`: web uses `posthog-js@1.386` (replay-capable), native keeps `posthog-react-native`.
- Privacy-hardened: `maskAllInputs: true`, `capture_performance: false` (no network bodies → zero JWT/PII leakage), `person_profiles: 'identified_only'`, manual `$pageview` per expo-router change.
- Server-side events via `core/posthog_client.py` (lazy-init, no-op without key): signup, payment_success, ai_credits_consumed, otp_sent, eg_session_completed.

**B. Revenue Reconciliation (Razorpay ⟷ BigQuery ⟷ Ledger)**
- `core/recon.py`: incremental Razorpay sync (payments / transfers / settlements with 5-day overlap), BigQuery Billing Export reader (2GB byte-cap guard), per-txn tally (collected − rzp_fee − routed_markup − earmarked_cost = buffer; `at_loss` flag), daily LLM-token ⟷ GCP-actual variance.
- `routes/admin_recon.py`: 7 endpoints, **super-admin gated** — `summary`, `transactions`, `daily`, `sync`, `gcp-config`, `transactions.csv`. Service-account JSON stored b64 in `recon_config`, never returned to browser.
- Frontend `/admin/recon`: verdict banner (at_risk / safe), 8 KPI cards, per-txn tally table, GCP setup form, sync-now, CSV export.

**C. Import-from-URL v3 — Factor-Type Doctrine + Hierarchy + Hints**
- **Factor-Type doctrine** persisted: `quantitative` = undisputed fact (incl. textual: Color=Blue, Furnishing=Semi); `qualitative` = subjective judgment (Comfort, Luxury Feel). `data_type` (text|number|date) remains a separate storage/format concept.
- **Page-defined groupings SACRED**: GSMArena BODY etc. preserved as-is. AI-grouping only when no page groups AND factor count > admin-configurable `import_group_threshold` (default 15).
- **Accuracy hints** (Step 2 UI, optional): `expected_factor_count`, `expected_option_count`, `first_factor_name`, `first_option_name` → server validates and performs ONE corrective self-heal retry.
- **Tiered LLMs**: Precise = Claude (claude-sonnet-4-6) via Emergent Universal Key first; fallback chain Claude → Gemini → OpenAI → Groq. Fast = Gemini → Groq.
- **"Set Expectations — By AI"** button at Step 2: Claude-powered, fills `expected_value` + `operator` on all 21 leaf factors (parents untouched), 422-gated until factors + options + ≥1 unit_value present.
- **Zero-tolerance** on option↔factor value mapping; unknown value keys DROPPED.

**D. AI Wallet Admin Config + Tiered Metering**
- `core/ai_wallet.py`: new fields `precise_model`, `precise_usd_per_mtok`, `import_group_threshold`. `charge(credit_multiplier=)` preserves zero-loss invariant.
- `core/ai_metering.py`: `metered_chat(tier=)` routes "precise" to Claude FIRST, charges at multiplier = `precise_usd_per_mtok / blended_usd_per_mtok`.
- Admin UI `/admin/ai-wallet-config`: live "Precise tier credit multiplier ×N" worked-example row.

### Acceptance criteria — all met ✅
- PostHog web replay: verified live in preview browser (sessionRecordingStarted=true, snapshots to `/s/`, events to `/e/`).
- Reconciliation: pytest 6/6 + live Razorpay sync (57 payments, 5 transfers, 26 settlements pulled in test env). Zero-loss invariant surfaced as the structural insight: with markup routed away, primary account nets `collected − fee − markup ≈ cost − fee`, so user must raise `markup_user_pct` if buffer must be ≥ 0 per-txn.
- Import-URL v3: 47/47 pytest; NoBroker live import → mode=detail, 20 factors with ALL user-listed values matched, 3 options (main + Dhamu + Golden Jublee), all text-facts correctly tagged `quantitative`. Set-Expectations 21/21 via Claude with `ai_provider=emergent_precise`.
- AI Wallet UI shows `import_group_threshold` field + multiplier row; admin can edit & persist.

### Out of scope (deferred)
- Empty "Draft" sessions cleanup on dashboard (P2, paused per user request).
- DigiLocker eKYC (BLOCKED on API Setu keys).
- Exotel SMS OTP (BLOCKED on DLT template approval).
- Push notifications (intentionally not built — requires user request).

### Status updates from v3.15 backlog
- ✅ **Emergent Universal Key topped up & VERIFIED working** (Profile → Universal Key → Add Balance). Claude precise tier now active. Previous backlog item "LLM budget reset" is **CLOSED**.
- ⚠️ Razorpay/markup zero-loss tuning: surface to ops for `markup_user_pct` increase before going live with paid AI.

### Documentation refreshed in this release
- `PRD.md` (this), `SRS.md`, `API_REFERENCE.md`, `POSTMAN.md`, `Postman_Collection.json` (auto-regenerated from live OpenAPI, 52 folders × 972 endpoints), `UAT.md`, `REGRESSION.md`, `SECURITY.md`, `WOWO.md`, `ACM.md`, `CLD.md`, `DEPLOYMENT.md`, `ADMIN_USER_GUIDE.md`.

---
## v3.16.1 — Import-URL: "Hints are Law" accuracy hotfix (2026-06-12)

### Problem (user-reported, critical)
Importing `carwale.com/new/best-electric-cars-under-10-lakh/` with 4 accuracy
hints (6 factors, first "All Brands", 4 options, first "Tata Tiago EV") and the
**Costly & Precise (Claude)** engine returned 2 irrelevant factors (PRICE,
MODEL). Root cause: the page embeds a tiny "Top 3" HTML table; the FREE
deterministic table parser matched it and returned immediately — **the paid AI
engine was never invoked and the hints were never validated**. Hints were only
wired into the single-listing "detail page" path. Bonus defect: deterministic
factors carried no `factor_type`, so PRICE rendered as "Qualitative".

### Solution
1. **Hints are law** — both endpoints (`POST /url-analyze`, `POST
   /url-analyze/decision/{id}/import`) now validate EVERY deterministic parse
   (hierarchical matrix + flat table/grid) against the user's hints; on
   mismatch the pipeline escalates to the hint-guided AI extraction.
2. **Hints injected up-front** — the extraction prompt now carries a
   "USER-VERIFIED PAGE FACTS" ground-truth block on the FIRST attempt (the
   self-healing corrective retry is retained).
3. **Comparison/listing pages extracted by AI** — the prompt no longer bails
   out with `{"page_type":"comparison"}`; listing/filter/best-of pages yield
   facet factors (Brand, Budget, Body Type, Fuel Type, Transmission, Seating
   Capacity…) + listed items as options (peers NOT force-scored 100).
4. **Precise tier honoured** — a "precise" request escalates thin (<3 factor)
   deterministic parses to Claude even without hints.
5. **Arbitration & fallback** — if AI output matches hints worse than the
   deterministic parse, the parse wins; if AI fails entirely, the parse is
   merged WITH explicit `hint_warnings` instead of failing the import.
6. `factor_type` now defaulted via nature-regex on deterministic flat imports.

### Verification
- Live e2e (preview): same URL + hints + precise → **6/6 expected factors, 4
  options ordered Tata Tiago EV first, `ai_provider=emergent_precise`,
  `hint_warnings=[]`, 57 s** (values + 0-100 scores filled for every car).
- `backend/tests/test_url_import_hints.py` — 11 new regression tests; full URL
  import suite 41 passed.

---
## v3.17.0 — Import-URL Intelligence: per-page-type prompts + accuracy analytics (2026-06-12)

### Why
Import-from-URL is the core accelerator of the decision flow. To keep raising
its accuracy we need (a) prompts engineered per page SHAPE, and (b) a granular
feedback/telemetry loop visible to admins — like PostHog, but with full
prompt-level drill-down.

### What shipped
1. **Always-on LLM page-type classification** (tiny fast-tier call) into 5
   types: `comparison_matrix` (GSMArena/versus), `listing_filter` (carwale
   case), `detail` (single product/property), `search_grid` (Amazon-style
   results), `article_roundup` ("Top 10 …" editorial). Heuristic fallback if
   the LLM is unavailable — classification can never block an import.
2. **Per-page-type prompt specialisation** — each type appends an engineered
   PAGE-TYPE GUIDANCE block to the extraction prompt (facet-factor rules for
   listing pages, card-only attributes for search grids, author-verdict factor
   for round-ups, sacred page groups for matrices, exhaustive specs for detail).
3. **Run telemetry (`url_import_runs`)** — every import/analyze run records:
   URL, the 4 accuracy hints, AI tier→provider, classified page type +
   confidence, pipeline route, factors/options added, hint warnings/pass,
   latency, ~tokens, corrective-retry flag, EXACT system prompt + raw LLM
   response (15 KB truncation, 90-day body purge with metadata retained), and
   status/error. Twin lightweight PostHog events: `url_import_completed`,
   `url_import_feedback`.
4. **👍/👎 user verdict** — 1-tap "Was this URL import accurate?" chip appears
   in Step 2 after an import; builds the labelled accuracy dataset.
5. **Admin dashboard `/admin/import-analytics`** (super-admin): KPI cards
   (runs, success, hint-pass, hint adoption, AI escalation, retry rate, 👍
   satisfaction, avg latency), breakdowns by page type / provider / route,
   filterable run list, drill-down modal incl. the exact prompt + raw response.
   Sidebar: Overview → "Import-URL Intel"; dashboard tile added.

### Verification
- pytest 47/47 (incl. new `tests/test_import_telemetry.py` — 7 tests).
- Live e2e: carwale import → classified `listing_filter` (conf 1.0, gemini),
  route `ai_extraction`, 6 facet factors / 4 options, prompt+response stored,
  feedback 👍 recorded, all admin endpoints + RBAC verified.
- Testing agent frontend run: 7/7 PASS (iteration_104.json).
