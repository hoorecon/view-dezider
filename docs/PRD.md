# Product Requirements Document — Dezider

_metadata: { "version": "3.15.0", "updated": "2026-05-18", "author": "engineering" }

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
