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

## Comparison-MATRIX parsing fix (GSMArena etc.) — 8 Jun 2026 (tested)
- Symptom: pasting a GSMArena phone-compare URL fetched fine (UA fix worked) but produced
  garbage factors ("col2", "col3", Expected 850.0). Root cause: GSMArena is a TRANSPOSED matrix —
  compared items are COLUMNS (names in the page `<title>`) and specs are ROWS split across ~15
  per-category tables — but our parser assumed row-per-item.
- Fix (`core/url_crawl.py`): new `_comparison_matrix_candidates()` parses transposed matrices
  (items from `_names_from_title()` "Compare A vs. B vs. C"; attributes prefixed with their
  category section header → readable factor names like "Body · Weight", "Battery · Capacity").
  A `_is_low_quality()` gate (generic colN keys / <2 items) routes standard-parse misses into the
  matrix parser, then the AI fallback. Standard row-per-item tables (fixture funds.html) still use
  the original path.
- Fix (`routes/url_analyze.py`): new `_measure_num()` only treats CLEAN single measurements as
  numeric ("169 g (5.96 oz)", "3500 mAh") and REJECTS messy spec strings ("GSM 850 / 900",
  "2018, August", "256GB 12GB RAM") — killing the fake-850 numeric factors. Derive now also drops
  over-long columns (avg>60 chars) and tie-breaks toward tidier values; messy specs become
  qualitative factors instead of bogus numerics.
- Verified e2e on the live GSMArena URL: 3 phones → options; "Body · Weight" & "Battery · Capacity"
  numeric+scored; band/date/OS columns now qualitative. Offline regression `tests/test_url_matrix_parse.py`
  (5 passed) + iter91/direction still green (13 passed). Fixtures added: phone_compare.html, funds.html.
- ⚠️ Heuristic ceiling: free-text spec sites yield only a few clean numeric factors (rest qualitative).
  Truly clean factor extraction (Battery mAh, RAM, Price as numerics) would need LLM refinement
  (user's key) — offered as a follow-up. JS-rendered retail (Amazon) still needs a headless/scraping API.
- ⚠️ Prod (jelcos.ai) must REDEPLOY.

## FULL HIERARCHICAL URL import (GSMArena benchmark) — 8 Jun 2026 (tested iter94)
- Requirement: pasting a category-grouped comparison page (GSMArena phone-compare) into "Analyse a URL"
  must import the COMPLETE two-level structure into MyDezider Step 2 — each spec CATEGORY → a main/parent
  factor, each spec ROW → a sub-factor, compared items → options, all cells assessed.
- `core/url_crawl.py`: extracted shared `_fetch_html()` (browser headers + retry); added
  `parse_hierarchy()` / `crawl_hierarchy()` → {items (from <title>), groups:[{category, rows:[{label,values}]}]}.
  GSMArena → 15 categories (Network…EU LABEL), correct sub-specs (Body→Dimensions/Weight/Build/SIM).
- `core/decision_builder.py`: `create_hierarchical_mydezider()` builds 15 parent factors (rating 50) +
  sub-factors (parent_id, weights split to EXACTLY 100 via last-sub remainder) + options with LEAF
  assessments (percentage + raw value as unit_value). `_effective_pct()`/`_hier_worth()` mirror the
  frontend's weighted sub-factor rollup so stored worth matches the UI.
- `routes/url_analyze.py`: `_score_hierarchy_numeric()` (proportional, direction-aware) + `_ai_score_text_rows()`
  (ONE metered LLM call scoring all text specs 0-100, best-effort — graceful no-op if wallet empty).
  `analyze_url` auto-routes category-grouped matrices to the hierarchical builder; flat derive is the fallback.
- Verified (iter94, testing agent): Step 2 renders 15/15 parents + 55/55 sub-factors, expand/collapse + split UI
  working, 3 options (Oppo F9 / Find X9s Pro / Galaxy A57). Backend: `POST /api/url-analyze` → mode='hierarchical',
  category_count=15, item_count=3. Graceful degradation confirmed when LLM wallet is empty (structure + raw
  values still build; user can run "AI Assess All"). New tests: test_url_matrix_parse.py (incl. hierarchy),
  test_iter94_url_hierarchy_import.py. Fixed cosmetic weight-total 100.02% float display (Step2.tsx tolerance +
  builder exact-100 weights).
- ⚠️ AI cell-scoring consumes Emergent-LLM credits (one batched call per import). ⚠️ Redeploy jelcos.ai.
- Pending follow-up: option 3 = LLM factor refinement (done as part of this) + headless/scraping API for
  JS-rendered retail (Amazon) — NOT yet wired; needed only for non-static sites.

## Emotional Gatekeeper AI now METERED + per-session cost + session filters — 10 Jun 2026 (tested)
- **Was unmetered**: all EG AI (`ai_engine._call_llm`) hit the Emergent key directly — no wallet gate,
  no per-user charge, not on the free-first chain (→ hard 500s, no "charge wallet" prompt).
- **Part A — metering**: `ai_engine._call_llm/_call_llm_json` now route through `ai_metering.metered_chat`
  with `feature` (eg_trap_analyze / eg_loop_recommend / eg_loop_reframe / eg_limitation_classify /
  eg_limitation_reframe / eg_outlet_analyze / eg_aim_analyze / eg_breakthrough_report) + `session_id`.
  Threaded user_id+session_id through all 8 AI fns + their routes (trap/loop/limitation/outlet_aim/
  session-report). Errors mapped: `402 {code:insufficient_credits}`, `503 {code:ai_unavailable}`,
  `502 {code:ai_error}` (routes re-raise HTTPException instead of wrapping as 500).
- **Per-session cost**: `ai_wallet._ledger`/`charge` now store `session_id`; new `ai_wallet.session_cost()`.
  `GET /sessions/{id}` returns `ai_cost {credits, calls}`, shown as a chip on the session screen.
- **Part B — frontend prompts**: shared `src/utils/aiErrors.ts::handleAiError` wired into eg-trap/loop/
  limitation/aim/session — shows "Charge Wallet" (402), "Use OpenAI (share data)" consent + Top-up
  (503 ai_unavailable), or generic retry. Each passes a `retry` callback.
- **Part C — session history**: Recent Sessions expanded inline with filter chips (status: All/In
  progress/Completed, type: All/Trap/Loop/Limitation/Outlet/AIM) via `GET /sessions?status=&session_type=`.
- **Verified (curl)**: trap analyze 200 charges wallet (≈25 cr, provider gemini→groq), ledger tagged
  session_id+feature, `ai_cost` returned; 0 credits → 402 insufficient_credits; session filters return
  correct subsets. Frontend lint clean.
- ⚠️ Redeploy jelcos.ai + set GROQ_API_KEY/OPENAI_API_KEY in prod .env. ⚠️ OpenAI key out of quota (429).

## Voice transcription 500 fixed — Whisper (Groq→OpenAI) replaces Google STT — 10 Jun 2026 (tested)
- **Bug**: EG-Trap "Voice Input" → 500 ("Transcription failed"). Root cause reproduced in dev:
  the STT engine used Google's unofficial free STT (`SpeechRecognition`+`pydub`), which needs the
  `flac` CLI (missing → uncaught `OSError` → **500**) and `ffmpeg` for webm. Only `ValueError` was caught.
- **Fix** (`routes/social_learning/stt_engine.py`): `STTEngine.transcribe` now uses **litellm Whisper**
  — `groq/whisper-large-v3-turbo` (free) PRIMARY → OpenAI `whisper-1` FALLBACK. Accepts wav/webm/mp3/m4a
  **directly (no ffmpeg/flac/pydub)**. Raises `ValueError` (→ 400 "type instead") only when every provider
  fails — never an uncaught 500. Benefits all callers (EG-Trap voice + social-learning upload).
  Also hardened `trap_routes` content-type parsing to strip `;codecs=opus` and default to webm.
- **Verified**: round-trip + `tests/test_stt_whisper.py` 2/2 pass — real harvard.wav transcribes
  accurately via Groq free tier; no-provider → ValueError (not 500).
- ⚠️ The user's `OPENAI_API_KEY` is currently **out of quota (429)** — OpenAI fallback (chat & Whisper)
  won't work until they enable billing / the free data-sharing tier; Groq (free) is the working primary.
- ⚠️ Redeploy jelcos.ai + set `GROQ_API_KEY` in prod .env for this to take effect there.

## Free-first multi-provider LLM chain + batched AI scoring + OpenAI consent — 9 Jun 2026 (tested iter97 + pytest)
- **Why**: "AI Assess All" showed "0 cells • N failed" because the only LLM providers were
  Gemini (rate-limited/timeout in some envs) and the Emergent universal key (budget exhausted). Root
  cause confirmed in logs: `Budget has been exceeded`.
- **Provider chain (`core/ai_metering.py`)**: `metered_chat` now runs a FREE-FIRST fallback chain —
  **Gemini → Groq → OpenAI(consent) → Emergent** — with per-provider retry+back-off on 429 and a 30s
  timeout so a hung provider fails over fast. Only the first provider that returns text is charged.
  Keys: `GROQ_API_KEY`, `OPENAI_API_KEY` added to backend/.env. Models: Groq `llama-3.3-70b-versatile`,
  OpenAI `gpt-4o-mini`. Verified in dev: Gemini times out/503 → "advancing chain" → **Groq scores 200**.
- **Batched scoring (`core/ai_assess.batch_score_cells` + `POST /decisions/{id}/ai-assess-all-batched`)**:
  scores ~40 cells per LLM call instead of 1-2 calls/cell — a 192-cell decision goes from ~384 calls to
  ~5, keeping usage inside free quotas. Frontend `Step7.runBulkAssess` AND
  `DecisionContext.bulkAssessAllRemaining` (post-URL-import auto-score) both migrated to this endpoint.
  Old per-cell `/ai-assess-batch` retained but no longer the primary path.
- **OpenAI data-sharing consent (3c)**: `GET/PUT /api/ai-wallet/provider-consent` stores
  `users.ai_provider_consent {allow_openai, mode}`. AI Wallet screen has a Settings toggle + mode chips
  (Ask each time / Always). When free quotas exhaust mid-run, Step 7 shows an in-the-moment prompt:
  [Top up] / [Use OpenAI once] / [Always use OpenAI] (saves consent). OpenAI only enters the chain when
  the user consents (privacy: it shares decision data with OpenAI for the free tier).
- **Tests**: `tests/test_provider_chain_batched.py` 2/2 pass (consent round-trip + batched-via-Groq).
  iter97 frontend: consent toggle/chips persist (200 PUT/GET), Step-2 banner confirmed removed.
- ⚠️ Redeploy jelcos.ai + set `GROQ_API_KEY`/`OPENAI_API_KEY` in prod .env for this to take effect there.

## "AI Assess All — 0 cells • N failed" diagnosis + clearer message — 9 Jun 2026 (verified)
- **Root cause (confirmed via backend logs, funded wallet)**: the AI assessment LLM call fails with
  `litellm.BadRequestError: Budget has been exceeded! ... Max budget: 0.4` (Emergent Universal LLM key
  budget/balance exhausted). `ai_assess_factor` then raises 502 → the batch route marked each cell
  `status:error` → the UI showed the confusing "N failed". This is NOT the app's in-app AI-wallet (that
  path returns 402 → "Out of AI credits"); it's the underlying Universal LLM key balance.
  → User fix: **Profile → Universal Key → Add Balance** (or enable auto-topup), then retry. In dev/preview
  the sandbox key has a fixed $0.40 cap, so live AI calls 502 here regardless of in-app credits.
- **UX fix**: `routes/decisions/assessment.py::md_ai_assess_batch` now returns `ai_unavailable: true` and
  STOPS at the first 502 (no more burning through 30+ chunks with the same failure). `Step7.tsx`
  `runBulkAssess` shows "AI temporarily unavailable — Universal LLM key balance may be exhausted; add
  balance and retry (already-scored cells are saved)" instead of "N failed". Verified in dev: batch now
  returns `ai_unavailable:true, results:0` and the UI message is actionable.
- ⚠️ Redeploy jelcos.ai for the clearer message; the underlying remedy is topping up the Universal Key.

## Step-2 URL import → hierarchical + removed redundant assess banner — 9 Jun 2026 (curl-verified)
- **FIX (Step 2 "Import from URL" now hierarchical)**: previously it used the FLAT parser
  (`merge_into_mydezider`, capped at 8 factors) so GSMArena gave ~8 flat factors ("Body · Weight").
  Now `routes/url_analyze.py::import_url_into_decision` first tries `crawl_hierarchy`; for a
  category-grouped matrix (≥2 groups & ≥2 items) it scores (`_score_hierarchy_numeric` +
  `_ai_score_text_rows`) and calls the NEW `core/decision_builder.merge_hierarchical_into_mydezider()`
  — merges 15 PARENT factors + sub-factors (weights split to exactly 100) + options w/ leaf
  assessments into the EXISTING decision (name-dedup). Flat derive remains the fallback.
  Verified via curl on the user's GSMArena compare URL: mode=hierarchical, category_count=15,
  55 sub-factors, 3 options, per-parent weights sum=100.0.
- **REMOVED the "AI Assess All remaining" banner from Step 2** (`Step2.tsx`) — assessment belongs on
  Step 7 where "AI Assess All" already exists; the Step-2 banner was redundant. Dropped its handler,
  the `aar` styles, and now-unused `useAiWalletStore`/context imports.
- ⚠️ User tests on PROD (jelcos.ai) — these changes are in dev/preview; **redeploy required** for them
  to appear on jelcos.ai. ⚠️ AI text-row scoring may no-op in dev if the LLM wallet is empty (structure
  + raw values still build; run "AI Assess All" on Step 7 after top-up).

## Multi-source imports (Step 2 + Step 7 URL actuals) — 8 Jun 2026 (tested iter96)
- **Step 2 multi-source import (3-icon layout)**: `Step2.tsx` imports a comparison matrix into a NEW
  decision via XLS/CSV (`step2-import-xls`), Google Sheet (`step2-import-sheet`), or URL
  (`step2-import-url`) → consent gate. Adds factors (+suggested Expected), options, partial
  assessments. Backend: `routes/matrix_import.py` (`import-matrix-file`, `import-matrix-sheet`,
  `factor-matrix-template.xlsx`) + `core/matrix_import.py`.
- **Step 7 "Import from URL" (actuals mapper) — COMPLETED THIS SESSION**: added the missing UI in
  `Step7.tsx` — `md-import-actuals-url` button → URL input dialog (`md-actuals-url-input` /
  `md-actuals-url-continue`) → `UrlAccessConsentModal` (purple) → `POST /api/decisions/{id}/import-actuals-from-url`
  extracts ACTUAL values against the decision's EXISTING templatized factors, then AUTO-triggers
  `bulkAssessAllRemaining()` AI scoring. Graceful out-of-credits handling.
- Verified iter96: backend 7/7 pytest (`test_iter96_matrix_import.py`) — template/csv-import/sheet/
  actuals-from-url all 200 on happy path, 400/422 on bad input/consent gate. Frontend: all Step 2 icons
  render + URL→consent chain; Step 7 new button→dialog→consent→import API call all work.
- ⚠️ Recurring: `sudo supervisorctl restart expo` needed after FE source edits (Metro cache).
- ⚠️ AI scoring may report out-of-credits in dev (expected). ⚠️ Redeploy jelcos.ai + re-enter ScraperAPI key.

## Skip-WhatsApp-Gate flag + one-tap AI Assess + ScraperAPI — 8 Jun 2026 (tested iter95)
- **Skip WhatsApp Gate (testing)**: new global flag in `core/security_config.py`
  (`skip_whatsapp_gate`, default False). `effective_whatsapp_verified()` returns True for ALL users
  when ON, so the post-login `/whatsapp-verify` gate is bypassed (login/auth-me already return the
  effective value → no frontend gate change). Super-Admin toggle in Admin → Settings
  (testID `toggle-skip-whatsapp-gate`, red track). PUT `/admin/security-config` is super-admin-only.
  ⚠️ Currently ON in dev/preview for QA — turn OFF in production.
- **One-tap "AI Assess All remaining"**: `DecisionContext.bulkAssessAllRemaining()` + `countUnscoredCells()`
  score every un-scored LEAF cell via chunked `/ai-assess-batch` (force_fill), re-fetching per chunk so
  worth updates live; graceful 402/out-of-credits handling. Surfaced as a purple banner on Step 2
  (testID `ai-assess-all-remaining-btn`) shown when ≥2 options + un-scored cells exist — turns a raw
  import into a ranked recommendation in one tap.
- **ScraperAPI integration (optional)**: registered provider `scraperapi` in `/admin/integrations`
  (api_key + optional country_code). `core/integrations.resolve_scraperapi()` (Admin UI → env fallback).
  `core/url_crawl._fetch_html` routes JS-heavy domains (amazon/flipkart/google-shopping/myntra/ajio/…)
  through ScraperAPI render, and escalates to it when a direct fetch is bot-blocked; gracefully falls
  back to direct httpx when no key. NEEDS the user's ScraperAPI key to activate Amazon-class imports.
- Verified iter95 (7/7 pytest + frontend): gate bypass, admin toggle (super-admin-only), banner +
  graceful out-of-credits, scraperapi provider listed, no-key GSMArena fallback intact.
- ⚠️ Redeploy jelcos.ai for these to go live.

## ScraperAPI activated + Amazon product-grid import — 8 Jun 2026 (tested)
- User provided a ScraperAPI key; configured via `PUT /api/admin/integrations/scraperapi` (stored in
  db.integrations, masked). Verified: key valid (5,000 credits), ScraperAPI **renders Amazon** (1.67MB,
  product grid + prices) — bypasses the 503 that direct httpx hit.
- Added `core/url_crawl._product_grid_candidates()` — deterministic extractor for e-commerce SEARCH
  grids (Amazon `[data-asin]` cards / schema.org Product) → name + Price + Rating. Wired into
  `crawl_candidates` BEFORE the LLM fallback, so Amazon/Flipkart imports need **no AI**.
- Fixed `_MEASURE_RE` to accept a leading currency symbol (₹ $ € £ ¥) so "₹2,498" parses as numeric →
  Price becomes a numeric lower-better factor, Rating numeric higher-better.
- Verified e2e: `POST /api/url-analyze {amazon search url, target:mydezider}` → decision with 24 options,
  factors Price(<=)+Rating(>=), options ranked by worth (top ~97.5% = cheap + high-rated). New tests in
  test_url_matrix_parse.py (currency + product grid). GSMArena (no-key) unaffected.
- ⚠️ ScraperAPI key is in the PREVIEW db only — on PROD (jelcos.ai) after redeploy, re-enter the key in
  Admin → Integrations → ScraperAPI (the provider only appears post-redeploy).
- Note: 3 Screener-converter tests fail in dev solely due to a drained AI wallet (insufficient_credits),
  not code — they pass once the Emergent LLM wallet is topped up.

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

## Fork session — 10 Jun 2026 (EG AI credit estimate badges + >15cr confirm gate)
- ✅ COMPLETED & TESTED (iter98 PASS): Finished wiring per-action AI credit estimate badges
  ("· ~N cr") on every Emotional Gatekeeper AI button and the >15-credit confirmation gate.
  Backend `GET /api/ai-wallet/estimates` (tokens_per_credit=100, confirm_threshold_credits=15)
  and `src/utils/aiEstimates.ts` (useAiEstimate + confirmAiSpend) were pre-built; this session
  completed the frontend rollout across all 5 screens:
    - eg-trap: Get AI Awareness ~9cr
    - eg-loop: Get AI Recommendation ~7cr · Generate Reframe ~10cr
    - eg-limitation: Classify ~7cr · Generate Breakthrough ~10cr
    - eg-aim: Analyze & Get Insights ~14cr
    - eg-session: Generate AI Breakthrough Report ~20cr → ONLY this pops Alert.alert confirm (>15)
  - Fixed a corrupted trailing line in eg-session.tsx (duplicate `ight: 18 },`) that broke parsing.
  - Note: on react-native-web preview, Alert.alert is polyfilled; native iOS/Android shows real modal.
- Backlog unchanged below.

## Remaining backlog (post-fork, as of 10 Jun 2026)
- P1: CLD Engine Phase B & C (Rules Engine + AI Suggestions)
- P1: PRR Enhancement #4 & #5 (configurable timing fields + decision-linking bypass)
- P1: DigiLocker eKYC Integration (needs sandbox credentials or mock-first)
- P2: Webhook API Integration; Org-Type Master Migration
- Refactor (P2): extract shared AI-execution/error hook from duplicated eg-*.tsx logic

## Fork session — 10 Jun 2026 (EG header AI-credits balance pill)
- ✅ COMPLETED & TESTED (iter99 PASS): Added an "AI Credits" balance pill to the header (top-right,
  next to back button) of all 5 EG tool screens (eg-trap, eg-loop, eg-limitation, eg-aim, eg-session).
  Reuses existing `src/components/AiCreditsBadge.tsx` (compact + autoRefresh) backed by
  `useAiWalletStore` → GET /api/ai-wallet. Tapping opens /ai-wallet. Verified pill renders on every
  screen with live balance, autoRefresh hits /api/ai-wallet per screen, and the "~N cr" estimate
  badges still render (no regression). New header style `headerTop` (row, space-between) added to each.

## Fork session — 10 Jun 2026 (low-balance "Top up" nudge on EG credits pill)
- ✅ COMPLETED & TESTED (self-test via Playwright screenshots): Enhanced `AiCreditsBadge.tsx` with an
  optional `lowThreshold` prop. When the wallet balance drops below the cost of the next AI action on
  the screen, the pill turns amber (or red when empty), gets a subtle tinted background, and appends a
  "· Top up" nudge. Each EG screen passes its most-expensive action estimate as the threshold:
  eg-trap=trapEst(9), eg-loop=loopRefEst(10), eg-limitation=limRefEst(10), eg-aim=aimEst(14),
  eg-session=reportEst(20). Default (no threshold) preserves prior <3cr behaviour for other screens.
  - Verified: balance 921 → plain purple pill; balance 5 (< trap cost 9) → amber "5.0 · Top up".
  - NOTE: Metro runs in CI mode (reloads disabled) — restart `expo` supervisor to serve latest bundle.

## Fork session — 10 Jun 2026 (EG session-detail empty content + result scroll-to-top)
- ✅ BUG 1 FIXED & VERIFIED: Opening a completed EG session from the listing (eg-session.tsx) showed
  only the Generate-Report button + empty Commitments/Journal — the captured AI analysis was never
  rendered though the backend already returns trap_reflection.ai_summary / loop_reflection.ai_reframe_full
  / limitation_reflection.ai_summary / aim_reflection.ai_analysis. Added analysis render cards
  (AI Trap Awareness, Loop Reframe, Limitation Breakthrough, AIM Analysis) mirroring the in-flow result
  screens. Verified on admin-owned session EG-4B460C2111 — full Trap Awareness now displays.
- ✅ BUG 2 FIXED: Result/step screens (eg-trap/loop/limitation/aim) didn't reset scroll position, so the
  AI result rendered mid-page. Added a ScrollView ref + `useEffect(()=>scrollTo({y:0}),[step])` so every
  step change snaps to top. Smoke-verified screens load without errors.
- NOTE: did NOT run full-flow testing agent to avoid spending the user's AI credits; bug 1 verified by
  direct render screenshot, bug 2 is a deterministic scroll reset.

## Fork session — 10 Jun 2026 (ROOT CAUSE: empty draft sessions + generic reports)
Investigation findings (user on PROD jelcos.ai → EC2 + separate prod Mongo; dev DB can't see prod data):
- `POST /sessions` creates a session as **"draft"** the instant a tool opens; the CAPTURE step is what
  creates the reflection doc + flips status to "in_progress". So a **"draft" session = opened but never
  captured = genuinely empty** → detail page was blank. The user was clicking these empty drafts.
- The "completed" session's report was full of generic "not yet recorded" text because the
  **Breakthrough Report was generated on an EMPTY session**. Confirmed the report generator works:
  on a session with real capture ("Missed a deadline / career") it returned a personalized report.
Fixes (all verified in dev):
- BACKEND: generate_report now returns **400 no_reflection_data** when the session has no
  trap/loop/limitation/aim/outlet content → no more generic placeholder reports.
- BACKEND: trap-analyze, loop-reframe, limitation-reframe now set session **status="completed"**
  (previously only report-gen did) → analyzed flows now show "Completed" instead of draft/in_progress.
- FRONTEND eg-session.tsx: renders **"What You Shared"** captured inputs (trap/loop/limitation) +
  existing AI analysis cards; shows an **"incomplete session → Resume"** state (routes back into the
  correct tool) for empty sessions; **hides** the Generate Report button when there's no content.
- ⚠️ REQUIRES REDEPLOY to prod (Cloudflare frontend + EC2 backend). Existing old empty/generic prod
  sessions stay as-is; new sessions behave correctly. Old generic reports can be regenerated on a
  session that has real data.
- FOLLOW-UP (not yet done): empty draft sessions still clutter the listing — consider lazy session
  creation (create on first capture) or hiding empty drafts from the list.

## Fork session — 11 Jun 2026 ("Classify My Limitation nothing happens" → 503 + silent web alerts)
TWO distinct issues found:
1. ROOT of "nothing happens" on web (jelcos.ai): React Native `Alert.alert` is a NO-OP on
   react-native-web, so the 503 error (and all validations + the >15cr confirm) were swallowed
   silently. FIX: added `src/utils/crossAlert.ts` (window.alert/confirm on web, native Alert on
   mobile) and repointed `Alert` imports in eg-trap/loop/limitation/aim/session + aiErrors.ts +
   aiEstimates.ts. VERIFIED on web: clicking an AI button now fires a real browser dialog.
2. The underlying 503 itself is a PROD CONFIG issue, NOT a code bug. classify works in dev (200):
   the metered fallback chain Gemini→Groq→OpenAI→Emergent catches Gemini's 429 and advances to Groq.
   The chain is built ONLY from keys present in the backend `.env`. On prod EC2 the `.env` is almost
   certainly missing GROQ_API_KEY / OPENAI_API_KEY / EMERGENT_LLM_KEY (added this session in dev; .env
   is not in git), so when Gemini rate-limits there's no fallback → 503 ai_unavailable.
   ACTION FOR USER: add GEMINI_API_KEY, GROQ_API_KEY, OPENAI_API_KEY, EMERGENT_LLM_KEY to the EC2
   backend `.env` and restart the backend. Optional model overrides: METERED_GEMINI_MODEL /
   METERED_GROQ_MODEL / METERED_OPENAI_MODEL (defaults gemini-2.5-flash / llama-3.3-70b-versatile /
   gpt-4o-mini).
- Needs REDEPLOY of frontend (Cloudflare) for the alert fix + the EC2 .env keys for the 503 fix.
- FOLLOW-UP: other EG screens (eg-outlet, eg-advisor, eg-emotional-reception) may still use RN Alert
  directly — sweep them to crossAlert too if they show AI errors.

## Fork session — 11 Jun 2026 (back arrow + resume in-progress session)
- BACK ARROW: `router.back()` is a no-op on react-native-web when there's no in-app history (direct
  URL / resume). Added a `goBack()` helper to all EG screens: `router.canGoBack?.() ? router.back() :
  router.replace('/tools/emotional-gatekeeper')`. Verified on web: back now navigates to the dashboard.
- RESUME: eg-limitation always started at step 0 with empty fields (no mount-load). Added a mount
  useEffect that GETs the session, prefills capture inputs + classification + flow answers, and jumps
  to step 1 (explore) if ai_classification exists or step 2 if ai_summary (reframe) exists. Verified:
  resumes to "Classify & Explore" with the 90% classification + the user's data prefilled.
- CONTINUE BUTTON: eg-session detail now shows a "Continue Session" button for non-completed sessions
  with content (routes back into the correct tool via resumeRoutes[session_type]).
- Backend fields used: limitation_reflection.{limitation_statement,why_limited,origin,belief_duration,
  cost_of_limitation,ai_classification,limitation_category,flow_answers,ai_summary}.
- ⚠️ Needs frontend REDEPLOY (Cloudflare) to reach jelcos.ai.
- FOLLOW-UP: resume-to-step + prefill is implemented for eg-limitation only. eg-trap / eg-loop / eg-aim
  still start at step 0 on re-open — replicate the same mount-load pattern there next.

## Fork session — 11 Jun 2026 (PROACTIVE SWEEP: back + web-alert + resume across ALL EG screens)
Completed the full sweep the user asked for (both items):
1. BACK BUTTON + WEB-SAFE ALERTS on the 3 remaining screens (eg-advisor, eg-outlet,
   eg-emotional-reception): added `goBack()` (canGoBack?back:replace dashboard) + swapped RN `Alert`
   for the web-safe `crossAlert` shim. Now ALL 8 EG screens have both fixes (verified: no screen uses
   raw `() => router.back()`; goBack present in all 8).
2. RESUME-TO-STEP + PREFILL on eg-trap, eg-loop, eg-aim, eg-outlet (limitation already done): mount
   useEffect GETs the session, prefills saved inputs, and jumps to the furthest completed step.
   - Backend field names verified per tool (trap stores landscaping_pattern/linking_meaning/
     looping_thought/ai_summary, not the granular scanning_* fields — fixed trap step-detection to use
     real fields). loop: ai_recommended_method/selected_method/method_answers/ai_reframe_full. aim:
     addictions/irritations/ai_analysis. outlet: ai_analysis.
   - VERIFIED on web: limitation→"Classify & Explore", trap→"Looping"(step3), loop→inputs prefilled.
   - KNOWN BACKEND GAP (pre-existing): trap landscaping endpoint stores `landscaping_pattern`=None and
     drops the granular scanning_* inputs, so landscaping sub-answers aren't restorable on resume; step
     detection still routes correctly via linking_meaning. Not fixed (out of scope).
- ⚠️ Needs frontend REDEPLOY (Cloudflare) for all of the above to reach jelcos.ai.

## Fork session — 11 Jun 2026 (trap resume field-name correction — NO backend gap)
- CORRECTION to the earlier "trap landscaping persistence gap" note: there is NO backend gap. The
  landscaping endpoint DOES persist scanning_for / scanning_patterns / scanning_without_urgency /
  repeated_concern; `landscaping_pattern` is just an unused legacy field. The earlier issue was my
  resume code reading the wrong fields. Fixed eg-trap resume to read the REAL fields:
  scanning_*, trigger_type, trigger_description, linking_meaning, looping_thought, getting_new_solution,
  emotion_increasing, intensity_after_loop, ai_summary — and prefill all corresponding inputs.
- VERIFIED on web: a capture→landscaping→linking→looping session resumes to step 3 "Looping" with the
  looping thought prefilled ("They will laugh at me"), "No, just replaying" selected, Intensity After 9/10.
- Trap resume now fully restores all prior answers + jumps to the furthest completed step. No backend
  changes were needed.

## Fork session — 10 Jun 2026 (Emotional Outlet Analyzer REVAMP — DONE & tested)
User-approved spec ("1.a 2.b 3.b + same Outlet Group", + breakdown weighted by frequency).
Backend (constants.py / ai_engine.py / outlet_aim_routes.py):
- COPING_STRATEGIES expanded to 40 statements = 10 per Outlet Group (Physical 🔴 / Mental 🔵 /
  Emotional 🟠 / Energy 🟣), each a MIX of healthy (default_constructive=True) & unhealthy (False).
- Route now computes a deterministic frequency-weighted % breakdown (Often=7/Sometimes=4/Rarely=1/
  Not-at-all=0) per group + Top-2 modes (primary/secondary), stored in ai_analysis so resume renders them.
- `analyze_outlets` AI prompt rewritten to: interpret Top-2 modes (mode_insight) + return EXACTLY 5
  constructive replacement_activities that stay in the SAME Outlet Group as the replaced behavior
  (fills extra slots with primary-mode elevating activities), + overall_pattern + encouragement.
Frontend (app/tools/eg-outlet.tsx — full rewrite):
- Step 0: 40 statements shown MIXED (seeded shuffle, no category headers), color-coded left-border by
  nature + a legend. Tap reveals frequency chips + "feels compulsive". testIDs on all interactive els.
- Step 1 (surprise reveal): Primary + Secondary Mode chips, "Where Your Energy Goes" % bars (color-
  coded), mode_insight, "5 Healthier Swaps" cards (group pill + Replaces + why), overall_pattern,
  encouragement. Resume of completed session renders saved analysis.
VERIFIED: curl e2e (37/37/21/5 breakdown, physical/mental modes, 5 same-group swaps) + web screenshots
of both steps. NOTE: Metro runs in CI mode (reloads disabled) — must restart `expo` to rebundle FE edits.

## Fork session — 10 Jun 2026 (Outlet Analyzer refinements + P0 session regression fix)
P0 REGRESSION FIX: eg-session.tsx never rendered the OUTLET reflection (user saw an empty
completed Outlet session). Added a "What You Shared (Outlets)" input card + "Your Outlet Profile"
analysis card (modes, % breakdown, mode_insight, primary/secondary swaps, overall_pattern,
encouragement) + an "Open Full Report (PDF & Share)" button. Trap/loop/limitation/aim sections
untouched.
Refinements (all tested):
1. Color legend moved from the TOP of step 0 to just ABOVE the Reveal button (smaller font) so it
   no longer spoils the surprise.
2. "Feels Compulsive" is now the FIRST chip in each outlet's options row (before Often), not a
   separate checkbox.
3. AI suggestions split into 5 PRIMARY-group + 3 SECONDARY-group activities (no longer 5 mixed).
   ai_engine.analyze_outlets returns primary_activities[5] + secondary_activities[3], each strictly
   within that mode's Outlet Group. Frontend renders two grouped sections.
4. Branded PDF + Share: new backend module outlet_report_routes.py —
   GET /api/emotional-gatekeeper/outlet/{sid}/report.pdf (reuses decision_reports._build_pdf →
   same JELCOS header/footer as MyDezider) and POST .../outlet/{sid}/share {channel,email/phone}
   (email = branded HTML + PDF attachment via Resend; whatsapp = branded text via UltraMsg).
   No L1/L2 paywall (Outlet is AI-credit metered). eg-outlet results page now has Download PDF +
   Share buttons + a channel/recipient modal.
VERIFIED: curl (5 physical + 3 mental swaps; PDF 200/valid 5-page; email share sent:true) + web
screenshots (results grouped swaps, session-page inputs+analysis, compulsive-first chip).

## Fork session — 10 Jun 2026 (Outlet share: attach PDF on WhatsApp too)
WhatsApp share now ATTACHES the branded PDF (previously text-only). Added
_send_whatsapp_document() using UltraMsg POST /messages/document with the PDF as a base64
`document` + `filename` + `caption` (branded summary). Email already attached the PDF (Resend).
VERIFIED: curl email share sent:true (PDF attached) + WhatsApp share to owner's verified number
sent:true (PDF document delivered).

## Fork session — 11 Jun 2026 (P0: "AI Assess All" escalation — empty cells + step jump)
User escalation: after AI-Wallet top-up, "AI Assess All" consumed credits but left cells empty AND
auto-navigated back to Step 6 (Define Options). THREE root causes found & fixed:
1. BACKEND (core/ai_assess.py batch_score_cells): prompt was hard-truncated at 11K chars → LLM
   silently skipped cells while the call was still charged. Replaced with size-aware chunking
   (_chunk_work: ≤40 cells AND ≤9K-char items-JSON per call, never truncated) + ONE automatic
   retry pass (chunks of 12) for dropped/malformed/parse-failed cells.
2. FRONTEND (DecisionContext.tsx): the smart step auto-jump in fetchDecision() ran on EVERY
   refetch — added autoJumpDoneRef so it runs ONLY on first load; refetches after Assess All /
   saves / imports never move the user's step anymore.
3. FRONTEND RACE (Step7.tsx applyCellResult) — found by testing agent: bulk path fired one PUT
   /decisions/{id} per cell from stale React snapshots (last-write-wins → only 1/8 cells survived
   in MongoDB). Bulk path no longer PUTs at all (backend already persisted); local echo only +
   fetchDecision() repaint. Manual per-cell saves still PUT (regression-verified).
Plus: completion alert now offers "Retry failed cells" when some cells errored.
TESTS: /app/backend/tests/test_batch_assess.py (4 unit) + tests/test_ai_assess_all_batched_e2e.py
(live e2e, by testing agent) = 6/6 pass. Frontend e2e iteration_101: 8/8 cells persisted, 0 racing
PUTs, stays on Step 7, alert OK, manual-edit regression pass.
PENDING (user-deferred until he verifies this fix): EG dashboard "empty Draft sessions" cleanup.

## Fork session — 11 Jun 2026 (PostHog Analytics integration, EU cloud)
User requested PostHog analytics across all app flows. Choices: frontend + backend events,
identify by user_id ONLY (no PII), named business events. Project: eu.posthog.com #199570.
IMPLEMENTED (no-op safe — activates when keys land in env):
- Frontend: src/utils/analytics.ts (posthog-react-native v4.46, EU host). _layout.tsx
  AnalyticsListener → screen event on EVERY expo-router route change + auto tool_opened for
  /tools/*. identify(user_id) on auth (authStore success paths + _layout effect), reset() on
  logout. Named events: login{method}, signup, decision_created (prr/new), ai_assess_all_run
  (Step7 w/ cell count).
- Backend: core/posthog_client.py (lazy-init, no-op w/o POSTHOG_API_KEY, never raises).
  Server-truth events: signup (auth register), payment_success (payments verify + webhook),
  ai_credits_consumed (ai_wallet._ledger debits w/ feature+provider+balance_after),
  otp_sent (whatsapp_otp), eg_session_completed (outlet+aim completion).
- Env: POSTHOG_HOST / EXPO_PUBLIC_POSTHOG_HOST set to https://eu.i.posthog.com in dev .envs.
PENDING: user must supply Project API Key (phc_..., from eu.posthog.com/project/199570/settings/project
— they pasted a phx_ personal key by mistake, advised to revoke). PRODUCTION rollout:
Cloudflare Pages env (EXPO_PUBLIC_POSTHOG_KEY/HOST) + redeploy; EC2 /opt/dezider/backend/.env
(POSTHOG_API_KEY/POSTHOG_HOST) + docker compose up -d --build. Google-auth signups currently
fire frontend login{method:google} only (no backend signup event) — minor gap, note if needed.
VERIFIED: pytest 4/4, tsc clean for changed files, signup curl OK w/ clean no-op log, app loads.
LIVE event verification possible only after the phc_ key arrives.

### PostHog activation (same session, 11 Jun 2026)
phc_ key received, added to dev .envs (frontend EXPO_PUBLIC_POSTHOG_KEY, backend POSTHOG_API_KEY).
LIVE VERIFIED: (1) direct capture curl → {"status":"Ok"}; (2) core.posthog_client flush OK;
(3) real signup via API fired with "PostHog server-side analytics enabled" log; (4) frontend SDK
initialized — config fetch from eu-assets.i.posthog.com HTTP 200. User instructed to do the
production rollout (Cloudflare Pages env + redeploy; EC2 backend .env + compose rebuild).
