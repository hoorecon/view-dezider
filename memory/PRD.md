# View Dezider - Product Requirements Document

## Overview
Multi-user Decision Making App based on a 10-step Proactive Risk Response (PRR) framework with AI-driven features, Solution Tools, and Multi-tenant SaaS capabilities.

## Core Features

### 1. 10-Step PRR Decision Flow
- Modular step components (Step2-Step10)
- DecisionContext for centralized state
- Factor Grouping (Quantitative/Qualitative) with data source config (Webhook/AI/Web Surf)

### 2. Solution Tools (P0 - NEW)
#### Simple Solution Finder
- 5-step structured problem-solving worksheet
- Steps: Life Area & Goal → Concerns → Influence & Solutions → Risk Management → Action Plan
- Fields: area_of_life, smart_goal, milestones, concerns, capabilities, resources, solutions, external help, risk management, action items

#### Advanced Solution Matrix
- 7-step extended analysis tool
- Self/Micro/Macro matrix layers with 7 sub-areas each (Summary, Knowledge & Skills, Capacity, Time, People, Finance, Infrastructure)
- 8 Solution Categories: Completely Solvable, Partially Solvable, Not Solvable, Patience Period, Accept & Let Go, Surrender & Trust, Surrender & Ignore, Surrender & Involve
- 5 Solution Sources: Self, Well-wisher, Experienced, On-Demand Expert, Regular Coach

### 3. WOWO Feature Flags (P0 - NEW)
- Admin-controlled Wire On/Wire Off system
- Toggle Solution Finder and Solution Matrix visibility
- Admin UI in Settings page with Switch toggles
- Dashboard conditionally renders Solution Tools section

### 4. Admin Settings (P1)
- Video Call Duration Configuration (5-120 min configurable)
- Feature Flags management
- Organization Branding management

### 5. Multi-tenant SaaS
- Organization model with slug-based login
- Per-org data isolation
- Org-specific branding (logo, colors, tagline)
- Org registration support on signup page

### 6. AI Features
- TEPFI Auto-mapping (via Emergent LLM)
- CLD (Causal Loop Diagram) generation with visual editing
- Factor Data Auto-fetch (Webhook/AI/Web Surf)
- Web Surf uses real DuckDuckGo search + LLM synthesis

### 7. Expert Video Calls
- Jitsi Meet embedded video calls
- Admin-configurable duration limits
- Screen sharing support

### 8. CLD Visual Editing (P2 - NEW)
- Edit mode toggle on CLD diagram
- Select and remove nodes
- Add/remove links between nodes
- Toggle link types (Reinforcing/Balancing)
- Interactive link list management

### 9. Org-Level Admin Hierarchy (P0 - NEW)
- Roles: org_super_admin, org_co_admin, org_admin, org_member
- Role-based permissions for managing org members
- Promotion/demotion with hierarchy enforcement

### 10. CTT - Centralized Task Tracker (P0 - NEW)
- Full task CRUD with all fields from Excel spec: Task ID, Company, Division, Team, Project, Logged By, Task/Sub-Task, Status, Remarks, Priority, Deadline, Task Owner, Dependencies (ID/ED/IH/EH), Duration, From/To Time, Day-wise Status
- Auto-aggregation: Pull action items from Decisions (Step 10), Solution Finders, and Solution Matrices into CTT
- Two modes: One-time tasks + Routine tasks (Frequency: Hourly/Daily/Weekly/Fortnightly/Monthly)
- Group/filter by Life Area and Decision Type (Problem/Need/Aspiration)
- Day-wise status grid (tap to cycle through statuses per date)
- Google Calendar URL generation for task scheduling
- Dashboard stats with counts by status, priority, life area, source
- 3 view modes: List, Board (grouped by Life Area), Day Grid (weekly calendar view)
- Navigation from Home dashboard + Profile screen

### 11. GEM - Goals Execution Manager (P1 - Boilerplate)
- Goals across 10 Life Areas, typed as Problem/Need/Aspiration
- Link goals to Decisions, Solution Finders, Solution Matrices
- Progress tracking per goal
- Dashboard with aggregated stats by area, type, status

### 12. Social Learning Engine (P0 - DONE)
- 3-Tier Knowledge Pyramid: Personal → Admin-Authorized → AI-Synthesized
- Input: Text, URL scraping, File (PDF/DOCX/Image OCR), Audio/Video
- AI classification via GPT-4.1-mini: Region, OrgType, Life Area, Scenario mapping
- Factor extraction with P1-P10 priority, mandatory/optional, expected values
- Risk extraction with probability, impact, mitigation, contingency
- 3-tier integration into My Dezider (Step 2) and Solution Finder (Q4)
- Refactored into modular package (11 files) from 1800-line monolith

## Architecture
```
/app
├── backend/
│   ├── server.py (Main app ~3100 lines)
│   ├── core/ (Shared utilities)
│   │   ├── database.py
│   │   └── auth.py
│   └── routes/ (Modular endpoints)
│       ├── tools.py (Solution Finder + Matrix)
│       ├── admin.py (Feature Flags + Call Config)
│       ├── ctt_gem.py (CTT Task Tracker + GEM Goals)
│       └── social_learning/ (Refactored package)
│           ├── __init__.py (Router aggregation)
│           ├── constants.py, models.py, helpers.py
│           ├── ai_engine.py, file_extraction.py, stt_engine.py
│           ├── upload_routes.py, template_routes.py
│           ├── admin_routes.py, integration_routes.py, stats_routes.py
├── frontend/
│   ├── app/
│   │   ├── (tabs)/ (index, profile, prr)
│   │   ├── admin/ (experts, templates, settings, org-members)
│   │   ├── auth/ (login, register)
│   │   ├── tools/ (ctt, ctt-task, gem, gem-goal, solution-finder, solution-matrix, etc.)
│   │   └── prr/[id].tsx
│   └── src/
│       ├── components/ (steps/, CLDViewer, ExpertCallModal)
│       ├── context/ (DecisionContext)
│       └── store/ (authStore)
```

## API Endpoints
### CTT Endpoints (NEW)
- `POST/GET /api/ctt/tasks` - Task CRUD (list with filters: status, life_area, decision_type, priority, is_routine, source_type)
- `GET/PUT/DELETE /api/ctt/tasks/{id}` - Single task operations
- `PUT /api/ctt/tasks/{id}/day-status` - Day-wise status updates
- `POST /api/ctt/aggregate` - Import action items from Decisions, Solution Finders, Matrices
- `GET /api/ctt/stats` - Dashboard statistics
- `GET /api/ctt/tasks/{id}/calendar-url` - Google Calendar URL

### GEM Endpoints (NEW)
- `POST/GET /api/gem/goals` - Goal CRUD with filters
- `GET/PUT/DELETE /api/gem/goals/{id}` - Single goal operations
- `POST /api/gem/goals/{id}/link` - Link to decisions/finders/matrices
- `GET /api/gem/dashboard` - Dashboard stats

### Other Endpoints
- `GET/PUT /api/admin/feature-flags` - WOWO toggle
- `GET /api/feature-flags` - Get flags (auth)
- `GET /api/feature-flags/public` - Get flags (no auth)
- `POST/GET/PUT/DELETE /api/solution-finders` - Solution Finder CRUD
- `POST/GET/PUT/DELETE /api/solution-matrices` - Solution Matrix CRUD
- `GET/PUT /api/admin/call-config` - Video call settings


---

# Decision Reports & Intake Track (added 3 Jun 2026)

## User feedback captured
1. PDF formatting/branding — DONE (text wrap, "JELCOS AI").
2. Pros & Cons report completeness — DONE (single "Satisfaction %" = assessment %,
   worth-based ranking, life-area/decision-type labels, app-flow section order,
   MPPS analysis + Standard & Final Recommendation).
3. Timezone: "Generated" time in user's local zone (Profile/Self-contact `country`,
   default IST) — DONE (Phase 1).
4. Show initial intake info (For/Individual, Life Area, Need, Sub-area, Scenario, Title,
   Description) in PDF + list-detail.
5. Apply full treatment (intake + detailed %, Standard Rec, MPPS, Final Rec) to
   My Dezider, SWOT, Solution Finder reports (not just Pros & Cons).
6. Add Solution Finder items into Solution Box listing.
7. My Dezider MPPS must be enabled for ALL options (not just Rank #1) → re-rank by MPPS.
8. Back-fill existing items: Title/Life-area/Type only (Sub-area/Scenario unrecoverable).
9. Show "For: Individual/Org/Govt" acting-as line. 10. Solution Box intake persist+display.

## Open earlier request
- Share report by email (SendGrid/Resend) to non-registered (email) + registered
  (in-app "Shared with me"); free recipient access; "Shared by <facilitator>".

## Phases
- Phase 1 (DONE, tested): timezone in all PDFs; shared `_decision_overview_section`
  used by Pros&Cons/Dezider/SWOT; persist intake on Pros&Cons create
  (backend `ProsConsCreate` + `new-decision.tsx`); life-area/decision-type labels.
- Phase 2 (NEXT): list-detail intake display (Pros&Cons/Solution Box/Dezider/SWOT);
  Solution Box intake persist; add Solution Finder items to Solution Box; back-fill.
- Phase 3: My Dezider report parity (detailed %, ranking, Standard/MPPS/Final Rec).
- Phase 4: My Dezider MPPS for ALL options (engine + UI + re-rank).
- Phase 5: SWOT & Solution Finder report parity.
- Phase 6: Share report by email.

## Technical notes
- Pros&Cons MPPS = Step-8 `improvement_pct` delta; effective% = clamp(0..100,
  assessment%+improvement%); worth = joint_score / Σ std_rating × 100.
- My Dezider MPPS on `decisions` doc (`mpps_*`); worth via `calculateDynamicWorth`
  (`frontend/src/utils/decisionHelpers.ts`).
- Life-area canonical ids in models/decisions_models.py (DB may store `la_`-prefixed).
- Self-contact (`db.contacts`, is_self=True) `country` = Profile country → timezone.
- Report builder: `/app/backend/routes/decision_reports.py`.


---

# Decision Embed Framework (PMSBazaar pitch) — P0–P4 (built earlier this initiative)
- Multi-tenant partner embed config CRUD (`partner_embed.py`), white-label iframe widget + JS loader
  (`partner_embed_widget.py`), cross-origin pre-seeding, Bulk Screener engine (`screener.py`,
  `ScreenerPanel.tsx`) with flat-credit billing, and Admin Embed Console (`app/admin/embed-partners.tsx`).
- Demo org `pmsbazaar-demo` (frictionless). Re-seed: `python -m scripts.seed_embed_partner_demo`.

## Fork session — 8 Jun 2026 (verified, testing iteration_89)
- ✅ Issue 1 (legacy, was untested): My Dezider Step 10 "Complete Decision" button works (confirm →
  status=completed → redirect); ActionItemEditor → CTT / → LifeStyle port buttons clickable & navigate;
  Add Action Item modal inputs render as muted placeholders (not pre-filled). Verified end-to-end.
- ✅ Issue 2 (P2): Added 36 `embed-*` testIDs to embed-partners.tsx and 17 `screener-*` testIDs to
  ScreenerPanel.tsx. No logic change. Screener CSV→factors→quote→run flow re-verified.
- NOTE: newly added testIDs needed `sudo supervisorctl restart expo` for Metro to surface them.

## AI Assess gap-fill + Screener P3b — 8 Jun 2026 (tested, iteration_90)
- ✅ Screener P3b (AI assessment for qualitative TEXT factors on finalists) was ALREADY built
  (`screener.py::_ai_assess_finalists`, `use_ai` flag, `screener_ai_assess` meter) — verified working.
- ✅ My Dezider "AI Assess All" gap-fill: previously skipped cells missing Expected/Actual. Now the
  bulk dialog offers Cancel / Ready only / AI-fill all when gaps exist. AI-fill sends `force_fill=true`;
  backend `core/ai_assess.ai_assess_factor(force_fill=True)` runs an extra metered LLM call
  (`_forcefill_generate`, feature `ai_assess_fill`) to set a STANDARD Expected (+operator/unit) and a
  realistic estimated Actual, then scores %. Generated Expected/Operator/Unit are PERSISTED onto the
  factor (route `decisions/assessment.py` `$set` now writes `factors` too — bug fixed in iter90).
  Higher credits come naturally from the heavier token usage. Files: `core/ai_assess.py`,
  `routes/decisions/assessment.py`, `frontend/src/components/steps/Step7.tsx`.
- NOTE: dev LiteLLM proxy has a low budget cap ($0.4) that can 502 repeated live AI calls in sandbox.
- Test: `/app/backend/tests/test_ai_assess_force_fill.py`.

## URL Analyse + Screener→Decision bridge + Consent gate — 8 Jun 2026 (tested, iteration_91)
Full plan (Phases A–D) approved by user; all 11 backend tests + frontend e2e PASS.
- **Phase A — Screener → decision bridge**: `POST /api/embed/screener/run/{run_id}/to-decision`
  and `/to-pros-cons` convert a saved run into a MyDezider decision / Pros & Cons analysis
  (finalists→options, factors→ratings, per-factor pct→assessments). UI: "Send to MyDezider" /
  "Send to Pros & Cons" buttons on Screener results (`ScreenerPanel.tsx`).
- **Phase B — Standalone "Analyse a URL"**: new screen `app/tools/analyse-url.tsx` (+ entry in the
  prr New menu, testID `new-menu-analyse-url`). Crawls a comparison page, derives weighted factors,
  proportionally scores items, and auto-creates a decision (lands on Step 7). Backend:
  `routes/url_analyze.py` + shared `core/url_crawl.py` (fetch→HTML table→AI fallback) +
  `core/decision_builder.py` (shared by screener bridge & url-analyze).
- **Phase C — Legal/consent gate**: `UrlAccessConsentModal.tsx` — mandatory access-eligibility type
  (Own / Partner / Free-Public / Custom) + disclaimer acceptance before ANY pasted URL is processed
  (used by both Analyse-a-URL and the Screener paste-URL mode). Auditable consent stored in
  `db.url_access_consents` (user, url, eligibility_type, ip, ua, disclaimer_version, ts).
- **Phase D — PMSBazaar ranking demo**: `GET /api/embed/demo-host/pmsbazaar-demo?flow=screener`
  now shows ranking-engine framing ("Rank these for me").
- NOTE: dev LiteLLM budget cap can 502 the AI table-less extraction path; the HTML-table path needs
  no AI. Test: `/app/backend/tests/test_iter91_url_analyse_screener.py`.

## PROD BUG FIX — "AI Assess All" 405 burst → chunked batch — 8 Jun 2026 (tested, iteration_92)
- Symptom (jelcos.ai): "AI Assess All" → "Assessed 0 cells • N failed"; console showed 405 (Method
  Not Allowed) on every `/api/decisions/{id}/factors/{fid}/ai-assess` call, while the single-cell ✨AI
  button worked. Root cause: the bulk runner fired one POST PER CELL (47+ rapid requests) — a burst the
  production edge/CDN rejects with 405. Dev never reproduces (returns 502 not 405). Not a rate limit
  (0 succeeded; a limiter would let the first few through).
- Fix: new backend `POST /api/decisions/{decision_id}/ai-assess-batch` (≤12 cells/request) sharing a
  `_apply_assessment()` helper with the single-cell route. Frontend `Step7.tsx` `runBulkAssess` now
  chunks all empty cells (CHUNK=6) and calls the batch endpoint via the shared axios `api` instance
  (assessCellSilent removed). ~48 cells → ~8 requests instead of 48, on the proven single-POST path.
- Verified: backend 5/5 (`test_iter92_ai_assess_batch.py`); frontend network shows 2× batch calls for
  12 cells, 0 per-cell calls, no 405s; single-cell ✨AI regression intact.
- ⚠️ ACTION: user must REDEPLOY to jelcos.ai for the fix to take effect. Dev LiteLLM has a $0.4 budget
  cap that can still make "AI-fill all" cells fail inside the batch (not a code issue).

## Three UX changes: Step-2 URL import, Instant Dezider rename, Profile admin cleanup — 8 Jun 2026 (tested, iteration_93)
- **#1 Step 2 "Import from URL"** (MyDezider): new card in `Step2.tsx` → consent gate → `POST
  /api/url-analyze/decision/{id}/import` crawls a comparison page and MERGES factors (with suggested
  Expected values + operators), options (Step 6) and partial assessments (Step 7). Backend: new
  `merge_into_mydezider()` in `core/decision_builder.py` (name-matches to avoid dup factors/options).
  Reuses `crawl_candidates` + `_derive_factors_and_scores`. Curl + e2e verified.
- **#2 Rename "Test 123" → "Instant Dezider"** across New menu (now FIRST, before Decider), home
  "Decision Kickstarters" (first card), filter chips, list/new screens, voice parser, and
  `app/_layout.tsx` headerTitle. Internal route `/test123` + backend unchanged.
- **#3 Profile admin cleanup**: removed 387 lines (9 admin-module sections) from `app/(tabs)/profile.tsx`;
  replaced with a single admin-only "Admin Console" shortcut (testID `profile-open-admin-console`) →
  `/admin`. All those modules already live in the `/admin` console (ADMIN_NAV). Non-admin/user
  settings untouched. Gating `userRole !== 'user'` (hidden for regular users).
- NOTE: URL-import expected_value defaults to column max (cost-style "lower-is-better" factors may need
  the user to flip — out of scope, editable in Step 2). Dev LiteLLM budget cap still applies to AI paths.

## URL-import direction-awareness — 8 Jun 2026 (tested)
- `routes/url_analyze.py::_derive_factors_and_scores` now auto-detects "lower-is-better" columns
  (cost/fee/expense/price/charge/premium/risk/drawdown/debt/loss/latency/.../churn) via
  `_is_lower_better()`. Those factors get operator `<=`, Expected = column MIN, and inverted
  proportional scores (lowest value → 100%). Higher-is-better columns keep `>=`/MAX as before.
- Applies to BOTH standalone "Analyse a URL" and Step-2 "Import from URL". Verified e2e (Expense Ratio
  → `<=` 0.85, Alpha 100% / Gamma 0%) + unit test `tests/test_url_import_direction.py` (2 passed).

## Remaining backlog (post-fork)
- P1: CLD Engine Phase B & C (Rules Engine + AI Suggestions)
- P1: PRR Enhancement #4 & #5 (configurable timing fields + decision-linking bypass)
- P1: DigiLocker eKYC Integration (needs sandbox credentials or mock-first)
- P2: Webhook API Integration; Org-Type Master Migration

## Fork session — 8 Jun 2026 (verification + 2 fixes)
- ✅ Regression verified on fork: URL-crawl→MyDezider/ProsCons (iter91 11/11, with a recreated
  local fixture `tests/fixtures/funds.html` served on :9777), AI-assess-batch (iter92), URL-import
  direction, force-fill — all green. "Instant Dezider" rename + profile admin cleanup confirmed shipped.
- ✅ UI FIX (Step2.tsx): moved the **Type (Quantitative/Qualitative)** selector ABOVE the
  Operator/Expected/Unit criteria (was below). Data Source toggle split into its own row to stay
  adjacent to its collapsible config panel. Pure layout reorder, lint clean.
- ✅ BUG FIX (`core/url_crawl.py`): "Import from URL" failed with HTTP 503 on Amazon. Root cause: the
  crawler sent a **bot User-Agent** (`ViewDeziderBot`) → retail/CDN sites reject with 403/503. Fix:
  realistic desktop-Chrome headers (UA + Accept/Accept-Language), 3 attempts with backoff on
  403/429/503, and specific error copy distinguishing bot-block vs JS-rendered vs not-found. Verified:
  Amazon no longer 503s (now 200; still JS-rendered so needs AI extraction), fixture table → 4 candidates,
  13/13 tests pass. NOTE: removed `br` from Accept-Encoding (brotli not installed → would garble HTML).
  ⚠️ Known limit: JS-heavy retail giants (Amazon/Flipkart/Google) load lists via JS we can't render —
  feature works best on comparison/aggregator pages with real HTML tables or JSON, or Screener CSV upload.
  A headless-browser/scraping-API integration would be required to reliably scrape those (not yet wired).
  ⚠️ Prod (jelcos.ai) must REDEPLOY for this fix to take effect.
