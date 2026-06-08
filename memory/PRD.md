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

## Remaining backlog (post-fork)
- P1: CLD Engine Phase B & C (Rules Engine + AI Suggestions)
- P1: PRR Enhancement #4 & #5 (configurable timing fields + decision-linking bypass)
- P1: DigiLocker eKYC Integration (needs sandbox credentials or mock-first)
- P2: Webhook API Integration; Org-Type Master Migration
