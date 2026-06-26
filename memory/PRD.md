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
