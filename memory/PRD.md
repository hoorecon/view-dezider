# View Dezider - Product Requirements Document

> ⚠️ FORK AGENTS: read **/app/memory/FORK_KICKOFF.md** FIRST — it holds the
> standing operating procedure (deploy ritual, QA facts, last user intent).
>
> ## 🚀 Custom Deploy Ritual (DO NOT LOSE — prod = jelcos.ai, branch emergent-v3)
> 1. `python3 backend/scripts/bump_build_version.py --tag v3.<n>-<desc>`  (bumps README BUILD_VERSION=YYYY.MM.DD.NNN)
> 2. User clicks **Save to GitHub** (emergent-v3) — the agent CANNOT push; never claim a git push happened.
> 3. On EC2: `cd /opt/dezider && EXPECT_BUILD=<new BUILD_VERSION> ./deploy/sync.sh emergent-v3`
>    (sync.sh fail-fasts if remote BUILD_VERSION != EXPECT_BUILD → catches dropped pushes).
> Cloudflare Pages auto-builds the frontend on push to emergent-v3.

> ## 🚫 GLOBAL UI RULE (user-mandated — do not regress)
> Forms & modals must NEVER stretch to full viewport width on web. Always cap:
> `maxWidth ~480-520, width '100%', alignSelf 'center'` (bottom-sheet `modalBg`
> uses `alignItems: 'center'`). A full-desktop-width form is a BUG.

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


### 13. Generic Notification Engine (v3.18.0 — 12 Jun 2026)
- CRUD-able notification triggers bound to a registry of trigger-event keys
  (scheduled: import-analytics weekly digest · event: import-run-failed instant alert)
- Channels with independent toggles: Email (Resend, branded HTML) + WhatsApp (UltraMsg, short text + link)
- 60s scheduler (tz-aware daily/weekly/monthly), per-trigger event throttling, dispatch run log
- Admin screen /admin/notification-engine + home tile + sidebar nav
- Extensible: new trigger events = one backend builder function, UI auto-discovers via registry

### 14. Org-Type Master + Import Progress UX (v3.19.0 — 12 Jun 2026)
- "Acting As / This decision is for…" org types are DYNAMIC from `db.org_types_master`
  (single source of truth — also powers coupon org-filters & Solution targeting)
- 7 seed types incl. new **FAMILY** (pink, "Family / household"); admin CRUD under
  Admin → Masters → Org Types (default tab): label, key, description, searchable
  Ionicons picker, color presets, is_org/active, sort order; system rows soft-disable
- Intake validation (`/api/hos/decisions`) accepts any ACTIVE master key; login page
  org types intentionally static (user choice)
- URL-Import shows LIVE progress modal (real backend stages, % bar, elapsed seconds)
  via `GET /api/url-analyze/progress/{id}`; classification runs concurrent with
  rendered fetch (~5-15s faster); Set-Expectations returns changed/confirmed counts

### 15. Import Trust + Org-Type Templates + Deep Import (v3.20.0 — 12 Jun 2026)
- **Page-grounding contract**: every numeric value a URL import writes must trace to an
  explicit page number (Lakh/Crore/comma/range aware); unverified → blanked + reported;
  every verified value carries a source quote ("Source quotes" modal) — makes geo price
  variants (ex-showroom vs on-road) self-evident. Geo note for money values; ScraperAPI
  defaults to India region.
- **Org-type-aware intake content**: Admin → Intake Scenarios manager with org-type
  tagging; 5 FAMILY starter templates; intake scenario suggestions filtered by the
  selected "This decision is for…" card (untagged = generic).
- **Deep Import (opt-in)**: base URL + 1-2 line context → bounded multi-page crawl →
  factor-first review (include + H/M/L priority) → merge approved factors with values
  already captured (no second AI pass). Explicit mode by design (5-10x credit cost vs
  normal import).

---
## Memory file map (split 12 Jun 2026 — PRD.md exceeded 700 lines)
- **PRD.md** (this file): static product requirements & architecture
- **CHANGELOG.md**: chronological session build log (newest at bottom)
- **ROADMAP.md**: prioritized backlog P0/P1/P2
- test_credentials.md · pending_verifications.md · carry_forward.md unchanged

---
## Iter 173 — Per-step Review & Merge + AI Review & Auto-Merge (DONE, tested 11/11 BE + 5 FE flows)
- Owner-side per-step "Review & Merge" (manual) + "AI Review & Auto-Merge" for MyDezider, Pros&Cons, Solution Finder, surfaced in the in-flow share modal (ShareStepModal Sent tab) and via per-step CollabBar ("Share this step" + "Review & merge") for P&C/SF.
- Backend: GET /api/shared-steps/{id}/review, POST /ai-merge, POST /apply (owner-only). AI weights owner merge_mode + each contributor's SME/capability/resources (enriched from owner contacts). metered_chat (free→paid) metered per user / per flow (session_id={module}:{flow_id}) / per step (feature=collab_ai_merge:{module}:s{step}) via tp_collab_ai_merge.
- Owner can view own + per-contributor inputs even AFTER merge (contributions preserved). AI advisory: owner edits/overrides or applies as suggested (default).
- Admin → AI Wallet Config → AI touchpoints: new tp_collab_ai_merge toggle.
- PENDING (next): Email/WhatsApp OTP verification toggles in Step 6 (inviting).

---
## Iter 174–175 — Collab Hub redesign + deep-link/OTP/live (DONE, tested)
- Wizard Step 1 = Module→Flow→Step; Launch creates share-step invites (Email+WhatsApp via Resend/UltraMsg, real) and routes owner to the step's Sent tab. Wizard bugs fixed (scroll, checkbox visibility, presence-check live-only, auth instructions, async verify dead-end, de-branded "Jitsi").
- Deep-link /contribute?share=<id> → signup→auto-return → opens exact module/flow/step in contribution mode (login.tsx honors getPostAuthRoute for all; contribute.tsx waits on isLoading).
- OTP-on-access gate (email/WhatsApp, once/every-time) via /shared-steps/{id}/access,/send-otp,/verify-otp. Owner bypasses.
- Live Sync: auto room URL; ShareStepModal Sent tab shows meeting link + Copy + Invite-more (/shared-steps/{id}/add-recipients dispatches step+meeting links).
- All verified: backend scripts PASS + testing_agent iter174/175/176 PASS.


---

## ITER 176 — Life Goals, Import-from-File, Global Sub-types (June 2026) ✅ TESTED

### A) Life Goals (My 360° Life → "Life Goals" tab) — GEM-backed
- **Storage**: lives in `db.gem_goals` (GEM is the central connector across Goal Setter, Solution Finder, MyDezider, Pros & Cons, Action Tracker). A Life Goal is a GEM goal carrying `lg_mode`, `lg_level`, `parent_id`, `horizon`, `sub_type`; regular GEM goals have no `lg_mode`.
- **Backend**: `routes/life_goals.py` (prefix `/api/life-goals`): `GET /meta`, `POST ""`, `GET ""` (filters mode/level/parent_id/life_area), `GET /tree`, `GET/PUT/DELETE /{id}` (tree delete cascades descendants).
- **Two modes**:
  - *Timeline* ("By Life Area"): per Life Area, a goal with horizon ∈ {This Quarter, 1yr, 3yr, 5yr, 10yr} + optional sub-type.
  - *7-Level Tree* (strict nested): L1 Overall → L2 10yr → L3 5yr → L4 3yr → L5 1yr (requires Life Area) → L6 Quarterly (requires sub-type) → L7 Monthly. Child must reference a parent exactly one level up.
- **Frontend**: in-screen top-tab switch in `app/tools/pna.tsx` ("Life Map" | "Life Goals"); panel `src/components/lifegoals/LifeGoalsPanel.tsx`.

### B) Import from File (MyDezider Step 2)
- **Backend**: `routes/file_import.py` — `POST /api/file-import/decision/{decision_id}` {filename, file_b64, ai_tier, crawl_web, context}. Parses pdf/docx/txt/xlsx/xls/csv/image(OCR) → AI extracts factors+options (metered via same AI wallet as URL import) → optional DuckDuckGo + LLM web-enrichment of options (cap 8) → `merge_into_mydezider` (factors + option candidates with `unit_values`).
- **Frontend**: 4th "File" button in Step2 import row + modal (file pick, AI tier, "Also research the web (AI crawl)" toggle, context). After success, an alert offers an opt-in to run the existing plan-capped "Fetch My Best Factors" (`/ai/suggest-factors`, `tp_best_factors`) to add missed-out factors.
- `src/utils/filePick.ts` — cross-platform pick→base64 (web FileReader; native `new File(uri).base64()` from expo-file-system v19).

### C) 4 Sub-types consistency
- Canonical order **Present Problem · Need · Future Risk · Aspiration** (`src/constants/decisionTypes.ts`).
- "Type" chip selector now in the Initial-Info step of MyDezider (`prr/new.tsx`), Pros & Cons wizard Step-1 Basics (saved to `decision_type`), and Solution Finder Step-0 Goal (saved via `buildPayload.decision_type`). Backend `tools.py` now accepts `decision_type` for Solution Finder.

**Status**: Verified by testing_agent (27/27 backend pytest PASS; frontend flows PASS; no new bugs). Demo Life Goals exist for super@test.com.

---

## ITER 177 — Financial Model on L1 (Financial) of 6 LeGS (Phase 1) ✅ TESTED

**Where**: A "Financial Model" branch on L1 (Financial) of each Org's 6 LeGS tree (My Organizations → org-detail → "6 LeGs GOALS" tab). Entry points: a "Financial Model" button + a calculator icon on every L1 goal node.

**Phase 1 — on-screen modelling & valuation engine** (no external deps):
- Backend `core/fin_model.py` (pure engine) + `routes/financial_model.py` (`/api/financial-models/*`: meta, compute (stateless preview), CRUD with org ownership).
- From **revenue projections + assumptions** → 3-statement forecast (P&L, Balance Sheet that ties out, Cash Flow), **financial ratios** (current/quick/debt-equity/interest-coverage/**DSCR**/margins/ROCE/ROE/WC-days), and an **FCFF-DCF valuation** → **Enterprise Value, Equity Value, Per-Share Price** + headline indicators (revenue CAGR, avg/min DSCR).
- Screen `app/tools/financial-model.tsx`: Inputs | P&L | Balance Sheet | Cash Flow | Ratios | Valuation tabs; units selector (default **Absolute**; Thousands/Lakhs/Millions/Crores); Recalculate + Save.
- Stored in `db.financial_models` (owned by user + scoped to a `user_org_id`, optional `leg_goal_id`).

**Deferred**: Phase 2 = Investor-ready PDF + Bank-ready CMA workbook (Excel, multi-form incl DSCR stress scenarios, MPBF, WC cycle, break-even). Phase 3 = **Zoho Books** (then Analytics) 2-way sync (needs OAuth client + Books Org ID; integration via integration_expert; secrets in backend `.env` / EC2 prod `.env`).

**Status**: Verified by testing_agent (13/13 backend pytest PASS incl. BS-ties-out & DCF; all 5 frontend flows PASS; no new bugs).


---

## ITER 184 — Solution Finder UX finish + Pros & Cons Step 4/5/7/8 polish ✅ TESTED

**Solution Finder** (`app/tools/solution-finder.tsx`) — completed the 6-point feedback:
- Clickable breadcrumbs (jump fwd/back up to `reachableMax`; current step ringed).
- Visible AI-credits meter row above the AI auto-fill buttons in Q3 & Q4 (balance + per-action estimate + Top up).
- Hierarchy in UI: Step 4 Solution cards show Concern›RCA trail chips + collapse (Expand/Collapse all); Step 5 action items show full lineage (Concern›RCA›Solution›Risk), colour-coded by source (solution=indigo / mitigation=emerald / contingency=amber) with legend + per-item & all collapse.
- Report export (Step 5, when saved): Download PDF (`GET /api/reports/solution_finder/{id}.pdf`; 402 → store, paid L1 gate like dezider/pros_cons/swot) + Share report (ReportShareSheet, module=solution_finder).

**Pros & Cons** (`pros-cons-wizard.tsx` + `src/features/pros-cons/*`):
- Step 4: "+ Sub-factor" existing-factor chips now carry a web hover tooltip (WebTitle → real `<div title>`; RN-Web strips `title` from View/Text).
- Step 5: ALL operators (numeric symbols + Contains/Starts/Ends/Equals/Not-equals) now common to BOTH Quantitative & Qualitative factors (`ALL_OPERATORS`).
- Step 7: new "Show/Hide Realistic Gap" 3rd toggle hides/shows all gap connectors; per-factor "Realistic gap" reveal when hidden; option names wrap full-width (no truncation).
- Step 8 (Case-2/MPPS): per-option **Case-1 vs Case-2 comparison table** (Overall %, Score, Mandatory %, Optional % + Change delta); A%/B% relabeled to Mandatory %/Optional %. Factor card Type chips renamed Subjective/Objective → **Quantitative/Qualitative** (preselected from Step-5 type, writes data_type+factor_type), a `|` separator between Type & Improvability groups, and **multi-select improvability** (Not-improvable exclusive; Improvable + Improvable(self) combinable → stored `y_both`).

**Status**: Verified by testing_agent across 2 rounds — Solution Finder all 6 PASS; Pros & Cons Step 4/5/7/8 all PASS; no new bugs. Backend unchanged (report/PDF/estimate endpoints pre-existing). NOTE: Stripe key is still the pod placeholder (`sk_test_emergent`) — live checkout only works post-deploy.

---

## ITER 188 — The Decider Store (Phase 1) ✅ TESTED (13/13 BE + admin FE PASS)

**What**: A public storefront (App-Store/Play-Store style) for Admin-**Authorized Decision Templates**.
Browsable WITHOUT login; cloning requires login and auto-launches a **prefilled MyDezider decision**.

**Backend** (`routes/decider_store.py`, prefix `/api/decider-store`; parser `core/decider_import.py`):
- PUBLIC (no auth): `GET ""` (cards), `GET /meta`, `GET /{id}`, `GET /import-template.xlsx` (downloadable authoring template).
- ADMIN: `GET /admin/all`, `POST /import/excel {file_b64}`, `POST /import/gsheet {sheet_url}`, `POST ""` (create), `PUT /{id}`, `POST /{id}/authorize`, `POST /{id}/unpublish`, `DELETE /{id}`.
- CLONE (auth): `POST /{id}/clone {mode}` → inserts a MyDezider decision (`db.decisions`, source=decider_store) and returns `decision_id`.
  - `full` = factors + classification (category mandatory/optional) + priority + options + option-values.
  - `values_only` = factors + options + option-values; category='' & rating=0 (user classifies).
  - Option value carried as `assessment.unit_value` ("Solo, Startup (40%)") + `suitability_values`; `percentage`=None (suitability % is per-value info, NOT the scoring %).
  - Paid template clone → **402** with price (fulfillment = Phase 2).
- Collection `db.decider_store_templates`. Seeded "The 55 Business Model Patterns" (`bmp-55-patterns`, 10 factors × 54 options) via `scripts/seed_decider_store_bmp.py` (idempotent).

**Import layout** (XLSX/Google-Sheet; col-A row labels): Factor Name / Possible Values / Main Factor Data-Type / Select-Type / UI-Object / Sub Factor Data-Type / Select-Type / UI-Object / Factor Group / Classification / Priority, then an option header row (No · Product Model · Option Name · Affected Components · Exemplary Companies · Description · Remarks · <factor cols>) with one option per row. Factor cell = "Value (nn%), Value2" (no % ⇒ 100%).

**Frontend**: `app/admin/decider-store.tsx` (Download template · Import Excel/GSheet · Create · Classify factors mandatory/optional+priority · Authorize/Unpublish/Delete). Tile in `/admin` → Content group.

**DEFERRED — Phase 2**: public storefront screen (`/decider-store` + detail) browsable logged-out; login-gated "Use this template" that launches the prefilled MyDezider flow; paid-template payment fulfillment (Stripe/Razorpay) with platform/creator split.
