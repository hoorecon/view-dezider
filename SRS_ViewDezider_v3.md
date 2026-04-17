# VIEW DEZIDER — Software Requirements Specification (SRS)
## Decision Intelligence Platform by Venture Buddha
### Version 3.0 | Last Updated: March 2026

---

## 1. EXECUTIVE SUMMARY

**View Dezider** is a comprehensive multi-user Decision Intelligence platform built on the **Proactive Risk Response (PRR) Framework** — a 10-step structured methodology for making rational, data-driven decisions. The platform extends beyond decision-making into goal execution, task tracking, lifestyle management, time optimization, and emotional self-awareness.

**Tech Stack:**
- **Frontend:** Expo (React Native) — Cross-platform (iOS, Android, Web)
- **Backend:** FastAPI (Python) with modular route architecture
- **Database:** MongoDB (via Motor async driver)
- **AI Integration:** OpenAI GPT-4.1-mini (via Emergent LLM Key)
- **Payments:** Razorpay (Live keys)
- **Calendar:** Google Calendar OAuth 2.0
- **OTP/Auth:** UltraMsg WhatsApp OTP, Google OAuth, Email/Password

---

## 2. SYSTEM ARCHITECTURE

### 2.1 Backend Architecture (Modular)
```
server.py (140 lines) — Entry point, CORS, router mounting
├── core/
│   ├── auth.py          — Session-based auth, role hierarchy, JWT utilities
│   ├── database.py      — MongoDB connection (Motor)
│   └── helpers.py       — Shared utilities (push notifications, notification creation)
├── routes/
│   ├── auth_routes.py         — Authentication (email, Google OAuth, sessions)
│   ├── organizations.py       — Multi-tenant SaaS org management
│   ├── decisions.py           — PRR CRUD, Templates, Test123, Journal, Sharing, MPPS
│   ├── notifications.py       — Push notifications, Experts management
│   ├── analytics.py           — Folder analytics, Decision meta
│   ├── ai_tools.py            — TEPFI auto-map, Factor data fetch, CLD analyze
│   ├── video_calls.py         — Expert video consultation (Jitsi)
│   ├── decision_templates.py  — Admin-curated decision templates
│   ├── tools.py               — Solution Finder, Solution Matrix
│   ├── admin.py               — Feature flags, call config
│   ├── ctt_gem.py             — CTT Task Tracker, GEM Goals, TEPFI entries, Calendar
│   ├── lifestyle.py           — Lifestyle routines, assessments, streaks, calendar sync
│   ├── decision_intake.py     — HOS guided decision creation wizard
│   ├── org_auth.py            — Organization-specific OTP login
│   ├── solutions_store.py     — Solutions catalog + ReviewNet
│   ├── google_calendar.py     — Google Calendar OAuth & event management
│   ├── deo.py                 — Decision Engine Optimization (scraper + API)
│   ├── cld.py                 — Causal Loop Diagram engine
│   ├── time_dezider.py        — AI time scheduling + Time Store
│   ├── payments.py            — Razorpay subscriptions, credits, wallets
│   ├── gem_flight.py          — GEM Flight Orchestrator + iGIS
│   └── consciousness_diary.py — Emotional wellness & self-awareness tracking
```

### 2.2 Frontend Architecture
```
app/                          — Expo Router (file-based routing)
├── (tabs)/                   — Bottom tab navigation
│   ├── index.tsx             — Home dashboard
│   ├── prr.tsx               — Decision Box (list)
│   ├── test123.tsx           — Quick Decision Test
│   ├── journal.tsx           — Decision Journal
│   └── profile.tsx           — Profile, Admin, Settings
├── auth/                     — Login, Register, Forgot Password
├── admin/                    — Admin screens (experts, templates, org members)
├── prr/                      — Decision detail & creation
├── tools/                    — All tool screens
│   ├── ctt.tsx, ctt-task.tsx         — Task Tracker
│   ├── gem.tsx, gem-goal.tsx         — Goal Execution Manager
│   ├── tepfi.tsx, tepfi-entry.tsx    — TEPFI Resource Matrix
│   ├── lifestyle.tsx                 — Lifestyle Dezider
│   ├── cld-engine.tsx                — Causal Loop Diagrams
│   ├── time-dezider.tsx              — AI Time Scheduler
│   ├── time-store.tsx                — Time Budget Store
│   ├── solutions-store.tsx           — Solutions Catalog
│   ├── deo.tsx                       — DEO Engine
│   ├── gem-flight.tsx                — GEM Flight Orchestrator
│   ├── consciousness-diary.tsx       — Consciousness Diary
│   ├── subscription.tsx              — Credits & Plans
│   └── google-calendar.tsx           — Calendar Integration
src/
├── components/               — Reusable UI components
│   ├── steps/Step2-10.tsx    — PRR 10-step form components
│   ├── CLDViewer.tsx         — CLD graph visualization
│   ├── ShareStepModal.tsx    — Collaborative step sharing
│   └── ExpertCallModal.tsx   — Video call interface
├── context/DecisionContext.tsx — PRR decision state management
├── store/authStore.ts        — Zustand auth store
└── utils/                    — API client, alerts, voice parsers
```

### 2.3 Authentication & Authorization
| Method | Description |
|--------|-------------|
| Email/Password | Standard registration with bcrypt hashing |
| Google OAuth | Session-based via Emergent OAuth proxy |
| WhatsApp OTP | Organization-specific login via UltraMsg |
| Session Tokens | Stored in cookies (native) + AsyncStorage/localStorage (mobile/web) |

**Role Hierarchy (Global):**
```
super_admin (3) > co_admin (2) > admin (1) > user (0)
```

**Role Hierarchy (Organization):**
```
org_super_admin (3) > org_co_admin (2) > org_admin (1) > org_member (0)
```

---

## 3. FEATURE SPECIFICATIONS

---

### 3.1 PRR Decision Framework (Core)
**10-Step Proactive Risk Response Flow**

| Step | Name | Description |
|------|------|-------------|
| 1 | Context & Options | Define the decision context, life area, type (Problem/Need/Aspiration) |
| 2 | List Factors | Enumerate all factors affecting the decision |
| 3 | Classify Factors | Categorize as Primary/Secondary using CLD AI analysis |
| 4 | Prioritize Factors | Rank and rate factors by importance (1-10 scale) |
| 5 | Calculate Ratings | CLD-derived gap multipliers determine weighted ratings |
| 6 | Define Options | Add options manually or import from Solutions Store |
| 7 | Assess & Calculate | Per-option factor assessment (0-100%) with auto-calculated Worth % |
| 8 | Case-1 Results | View option ranking by Worth %, select best option |
| 9 | MPPS Analysis | Improvement plan for chosen option's weak factors |
| 10 | Final Decision | Reflection, notes, implementation review date |

**Key Features:**
- **Factor Assessment Modes:** Percentage slider, Unit-based input, AI auto-fetch
- **Worth Calculation:** `Worth = Σ (factor_rating / total_rating × assessment_percentage)`
- **MPPS (Multi-Point Performance Strategy):** Projects improvements with TEPFI resource allocation
- **MPPS Export:** CSV and PDF action plans with assignees, deadlines, TEPFI classification
- **Decision Cloning:** Clone at any level (factors, classification, prioritization, options, assessment)
- **Template System:** Save decisions as reusable templates (private, shared, public, authorized)

**API Endpoints:**
```
POST   /api/decisions                           — Create decision
GET    /api/decisions                           — List user's decisions
GET    /api/decisions/{id}                      — Get decision detail
PUT    /api/decisions/{id}                      — Update decision (factors, options, assessments)
DELETE /api/decisions/{id}                      — Delete decision
POST   /api/decisions/{id}/clone                — Clone decision at specified level
POST   /api/decisions/{id}/save-as-template     — Save as reusable template
GET    /api/decisions/{id}/mpps-action-plan      — Download MPPS CSV
GET    /api/decisions/{id}/mpps-action-plan-pdf  — Download MPPS PDF
```

**DB Schema — `decisions` collection:**
```json
{
  "id": "uuid",
  "user_id": "user_xxx",
  "title": "string",
  "context": "string",
  "folder": "holistic_health | career | finance | ...",
  "life_area": "string",
  "decision_type": "problem | need | aspiration",
  "factors": [
    {
      "id": "uuid", "name": "string", "category": "primary|secondary",
      "rating": 0-10, "order": int, "unit": "string",
      "expected_value": "any", "data_type": "string",
      "operator": "string", "gap_multiplier": float,
      "parent_id": "uuid|null", "weight": float
    }
  ],
  "options": [
    {
      "id": "uuid", "name": "string", "worth_percentage": 0.0-100.0,
      "assessments": [
        { "factor_id": "uuid", "percentage": 0-100, "unit_value": "string",
          "actual_value": float, "assessment_mode": "string" }
      ]
    }
  ],
  "chosen_option_id": "uuid|null",
  "decision_case": "string",
  "mpps_option_id": "uuid",
  "mpps_improvements": [
    {
      "factor_id": "uuid", "original_percentage": int, "projected_percentage": int,
      "delta_percentage": int, "improvement_plan": "string",
      "tepfi_elements": ["T","E","P","F","I"], "tepfi_layer": "self|micro|macro",
      "action_items": [
        { "assignee_name": "", "assignee_email": "", "task": "", "deadline": "" }
      ]
    }
  ],
  "mpps_projected_worth": float,
  "mpps_timeframe": "string",
  "implementation_review_date": "datetime",
  "status": "draft | in_progress | completed",
  "rating_gap_multiplier": 1.0
}
```

---

### 3.2 Test123 Quick Decision Module

A rapid 3-test emotional intelligence check for quick decisions.

**Tests:**
1. **Is it Emotional?** — Determine if the decision is emotion-driven
2. **What I Want** — Clarify desires, worst-case readiness, all needs vs important needs
3. **Action Plan** — Final decision and action plan

**API Endpoints:**
```
POST /api/test123          — Create session
GET  /api/test123          — List sessions
GET  /api/test123/{id}     — Get session detail
PUT  /api/test123/{id}     — Update session progress
```

---

### 3.3 Decision-Making Mode Assessment

12-question psychological assessment identifying the user's dominant decision-making mode:
- **Emotional** — Decisions influenced by feelings
- **Logical** — Data-driven analytical approach
- **Intuitive** — Gut-feeling based decisions
- **Awareness** — Mindful, detached observation

**API Endpoints:**
```
GET  /api/assessment/questions    — Get 12 assessment questions
POST /api/assessment              — Submit answers, get dominant mode + scores
GET  /api/assessment/history      — View past assessments
```

---

### 3.4 Decision Journal

Track decision outcomes, lessons learned, and failure analysis.

**Features:**
- Link entries to any module (Decision, Solution Finder, Solution Matrix, GEM, CTT, Lifestyle)
- Entry types: Best Practice, Learning
- Outcome rating (1-5 scale)
- Failure reason tracking
- Implementation review reminders (auto-generated from decisions with review dates)

**API Endpoints:**
```
POST   /api/journal                   — Create entry
GET    /api/journal                   — List entries (filterable by module, type)
GET    /api/journal/reminders         — Get pending review reminders
GET    /api/journal/linkable-items    — Get all linkable items across modules
GET    /api/journal/{id}              — Get entry detail
PUT    /api/journal/{id}              — Update entry
DELETE /api/journal/{id}              — Delete entry
```

---

### 3.5 Collaborative Step Sharing

Enable multi-user decision-making by sharing specific PRR steps with collaborators.

**Merge Modes:**
- **Equal** — All contributors weighted equally
- **Self-Weighted** — Decision owner gets 50%, others split 50%
- **Custom** — Manual weight assignment per contributor

**Flow:**
1. Owner shares Step N with recipients (by email)
2. Recipients receive push notification
3. Each recipient submits their assessment
4. Owner merges contributions using selected merge mode
5. Merged data updates the original decision

**API Endpoints:**
```
POST /api/decisions/{id}/share-step        — Share step with users
GET  /api/shared-steps/received            — View received shares
GET  /api/shared-steps/sent                — View sent shares
GET  /api/shared-steps/{id}                — Get share detail
POST /api/shared-steps/{id}/contribute     — Submit contribution
POST /api/shared-steps/{id}/merge          — Merge all contributions
```

---

### 3.6 Causal Loop Diagram (CLD) Engine

AI-powered Systems Thinking analysis that identifies causal relationships between decision factors.

**Features:**
- **AI Analysis:** GPT-4.1-mini generates CLD nodes, links, loops, centrality scores
- **Visual Graph:** Interactive node-link diagram with circular/force-directed layout
- **Simulation:** What-if analysis — adjust one factor's value and see ripple effects
- **Auto-Classification:** AI classifies factors as Primary/Secondary based on centrality
- **Gap Multipliers:** CLD-derived weights for factor rating gaps
- **Manual Editing:** Add/update/delete nodes and links

**API Endpoints:**
```
POST /api/cld/analyze                      — AI-generate CLD from factors
GET  /api/cld/list                         — List saved CLDs
GET  /api/cld/{decision_id}                — Get CLD for decision
POST /api/cld/{decision_id}/save           — Save CLD diagram
PUT  /api/cld/{decision_id}/node/{id}      — Update node position/properties
PUT  /api/cld/{decision_id}/link           — Add/update link
POST /api/cld/{decision_id}/simulate       — Run what-if simulation
POST /api/cld/{decision_id}/generate       — AI-generate full CLD
POST /api/cld/{decision_id}/layout         — Auto-layout nodes
DELETE /api/cld/{decision_id}              — Delete CLD
```

---

### 3.7 Centralized Task Tracker (CTT)

Track action items generated from decisions, MPPS plans, and other modules.

**Features:**
- Tasks linked to decisions, life areas, priority levels (P0-P3)
- Status tracking: Not Started → In Progress → Completed → Cancelled
- Day-wise status tracking (for habit-like tasks)
- Google Calendar sync (individual tasks)
- Batch calendar export
- Upcoming deadlines view
- Aggregate reporting across life areas

**DB Schema — `ctt_tasks`:**
```json
{
  "id": "uuid", "user_id": "string",
  "task": "string", "description": "string",
  "priority": "P0|P1|P2|P3",
  "status": "not_started|in_progress|completed|cancelled",
  "life_area": "string",
  "linked_decision_id": "uuid|null",
  "deadline": "datetime",
  "day_status": { "2026-03-01": "completed", ... },
  "calendar_event_id": "string|null"
}
```

**API Endpoints:**
```
POST   /api/ctt/tasks                    — Create task
GET    /api/ctt/tasks                    — List tasks (filterable)
PUT    /api/ctt/tasks/{id}               — Update task
PUT    /api/ctt/tasks/{id}/day-status    — Update daily status
DELETE /api/ctt/tasks/{id}               — Delete task
POST   /api/ctt/aggregate                — AI-aggregate task report
GET    /api/ctt/tasks/{id}/calendar-url  — Get ICS calendar URL
GET    /api/ctt/stats                    — Get task statistics
POST   /api/calendar/batch-export        — Batch export to Google Calendar
GET    /api/calendar/upcoming            — Upcoming deadlines
```

---

### 3.8 Goal Execution Manager (GEM)

Track goals across 10 life areas with progress tracking and decision/task linking.

**10 Life Areas:** Holistic Health, Knowledge & Skills, Relationships, Finance, Assets, Career, Hobbies, Social Image, Social Contributions, Spirituality

**Goal Types:** Problem, Need, Aspiration

**Features:**
- Goal CRUD with life area and type classification
- Link goals to decisions, tasks, journal entries
- Dashboard with life area distribution and progress
- Goal-to-GEM-Flight project linking

**API Endpoints:**
```
POST   /api/gem/goals                    — Create goal
GET    /api/gem/goals                    — List goals
GET    /api/gem/goals/{id}               — Get goal detail
PUT    /api/gem/goals/{id}               — Update goal
DELETE /api/gem/goals/{id}               — Delete goal
POST   /api/gem/goals/{id}/link          — Link to decision/task
GET    /api/gem/dashboard                — Life area dashboard
```

---

### 3.9 TEPFI Resource Matrix

Track resource allocation across Time, Effort, People, Finance, and Infrastructure at Self, Micro (team), and Macro (systemic) levels.

**Features:**
- TEPFI entry management with 5 resource types × 3 scope layers
- Import from Solution Matrix entries
- Dashboard with resource distribution visualization
- AI auto-mapping of decision factors to TEPFI elements

**API Endpoints:**
```
POST /api/tepfi/entries                           — Create entry
GET  /api/tepfi/entries                           — List entries
PUT  /api/tepfi/entries/{id}                      — Update entry
DELETE /api/tepfi/entries/{id}                     — Delete entry
GET  /api/tepfi/dashboard                         — Resource distribution dashboard
GET  /api/tepfi/metadata                          — Get TEPFI categories/layers
POST /api/tepfi/import-from-matrix/{matrix_id}    — Import from Solution Matrix
POST /api/tepfi-auto-map                          — AI auto-classify factors to TEPFI
```

---

### 3.10 Solution Finder & Solution Matrix

**Solution Finder:** Quick brainstorming tool for generating solution ideas.

**Solution Matrix:** Structured evaluation comparing solutions against criteria with SMART goal linkage.

**API Endpoints:**
```
POST/GET/PUT/DELETE /api/solution-finders/{id}
POST/GET/PUT/DELETE /api/solution-matrices/{id}
```

---

### 3.11 Solutions Store & ReviewNet

Catalog of solutions (products, services, events, contacts) with quantitative factor assessments and qualitative reviews.

**Features:**
- Create/browse solutions with category, country, language filters
- Quantitative factor-value pairs per solution
- ReviewNet: User reviews with quality scores (1-5)
- Admin approval workflow for public solutions
- Integration with PRR Step 6 (import options from store)
- Integration with PRR Step 7 (auto-populate factor assessments from store data)
- User location/language preferences

**Admin Workflow:**
```
User submits public solution → Status: pending → Admin reviews → Approve/Reject
```

**API Endpoints:**
```
POST   /api/solutions-store/solutions              — Create solution
GET    /api/solutions-store/solutions              — List solutions (with filters)
GET    /api/solutions-store/browse                 — Browse by category
GET    /api/solutions-store/search                 — Full-text search
GET    /api/solutions-store/for-decision           — Get solutions matching decision context
POST   /api/solutions-store/apply-to-option        — Auto-populate option assessments
GET    /api/solutions-store/pending-approval       — Admin: pending solutions
PUT    /api/solutions-store/approve/{id}           — Admin: approve solution
PUT    /api/solutions-store/reject/{id}            — Admin: reject solution
POST   /api/reviewnet/reviews                      — Submit review
GET    /api/reviewnet/reviews                      — List reviews for solution
```

---

### 3.12 DEO (Decision Engine Optimization)

**Inbound DEO:** AI-powered web scraper that imports external product/service data into the Solutions Store.

**Outbound DEO:** API key system allowing external websites to use View Dezider's decision flow logic.

**Inbound Flow:**
1. User provides a URL
2. BeautifulSoup scrapes the page content
3. GPT-4.1-mini extracts factor-value combinations
4. Imported as a solution into the Solutions Store

**Outbound API:**
- Generate API keys with scopes
- Public endpoints for external decision flow consumption
- SDK info and widget embeddable endpoint

**API Endpoints:**
```
POST /api/deo/scrape-url                   — Scrape URL for factor-value data
POST /api/deo/import                       — Import scraped data as solution
GET  /api/deo/mappings                     — List field mappings
POST /api/deo/api-keys                     — Generate outbound API key
GET  /api/deo/api-keys                     — List API keys
DELETE /api/deo/api-keys/{id}              — Revoke API key
GET  /api/deo/public/solutions             — Public: Browse solutions (via API key)
POST /api/deo/public/decision-flow         — Public: Start decision flow
POST /api/deo/public/decision-logic        — Public: Execute decision logic
GET  /api/deo/public/widget                — Public: Embeddable widget HTML
GET  /api/deo/public/sdk-info              — Public: SDK integration docs
```

---

### 3.13 Time Dezider (AI Time Scheduler)

AI-powered daily time scheduling based on user preferences and task priorities.

**Features:**
- User preferences: wake time, sleep time, core hours, time blocks
- AI generates optimized daily schedule from CTT tasks
- Unplanned task insertion with auto-rescheduling
- Buffer time management
- Schedule approval workflow

**API Endpoints:**
```
GET  /api/time-dezider/preferences          — Get user time preferences
PUT  /api/time-dezider/preferences          — Update preferences
GET  /api/time-dezider/daily                — Generate AI daily schedule
POST /api/time-dezider/unplanned-task       — Add unplanned task
DELETE /api/time-dezider/unplanned-task/{id} — Remove unplanned task
POST /api/time-dezider/reschedule           — AI reschedule after changes
POST /api/time-dezider/approve              — Approve generated schedule
```

---

### 3.14 Time Store (Time Budget Analysis)

Analyze how time is allocated across life areas and optimize time distribution.

**Features:**
- Time budget computation from CTT tasks and schedule data
- AI analysis of time allocation patterns
- Recommendations for time rebalancing
- Apply recommended changes to schedule

**API Endpoints:**
```
GET  /api/time-store/budget                 — Get time budget breakdown
POST /api/time-store/analyze                — AI analyze time allocation
POST /api/time-store/apply                  — Apply AI recommendations
```

---

### 3.15 Lifestyle Dezider

Track daily routines, measure lifestyle effectiveness, and build healthy habits.

**Features:**
- Routine management (create, edit, schedule by frequency)
- Daily completion tracking with streak counting
- AI-powered lifestyle assessment (generates personalized routines)
- Import routines from CTT tasks
- Auto-detect routine patterns from CTT
- Google Calendar recurring event sync
- Lifestyle analytics with category distribution
- Dashboard with completion rates and streaks

**API Endpoints:**
```
POST   /api/lifestyle/routines                         — Create routine
GET    /api/lifestyle/routines                         — List routines
PUT    /api/lifestyle/routines/{id}                    — Update routine
DELETE /api/lifestyle/routines/{id}                    — Delete routine
POST   /api/lifestyle/routines/{id}/complete           — Mark daily completion
DELETE /api/lifestyle/routines/{id}/uncomplete         — Undo completion
GET    /api/lifestyle/routines/{id}/completions        — Get completion history
GET    /api/lifestyle/today-status                     — Today's dashboard
POST   /api/lifestyle/start-assessment                 — AI lifestyle assessment
GET    /api/lifestyle/assessments                      — Past assessments
GET    /api/lifestyle/analytics                        — Category analytics
GET    /api/lifestyle/dashboard                        — Full dashboard
POST   /api/lifestyle/routines/{id}/sync-calendar      — Sync to Google Calendar
DELETE /api/lifestyle/routines/{id}/unsync-calendar     — Remove calendar sync
POST   /api/lifestyle/auto-detect-from-ctt             — Auto-detect routines
POST   /api/lifestyle/bulk-import-from-ctt             — Bulk import from CTT
POST   /api/lifestyle/import-from-ctt                  — Import single CTT task
```

---

### 3.16 GEM Flight Orchestrator

A gamified airplane journey metaphor mapping project dynamics to actual project data.

**Metaphor Mapping:**
| Flight Phase | Project Phase | Data Source |
|-------------|---------------|-------------|
| Take-off | Project initiation | GEM goals created |
| Cruising Altitude | Progress level | CTT task completion % |
| Turbulence | Risk/Problems | Open issues, missed deadlines |
| Fuel Level | Resource health | TEPFI resource allocation |
| Landing | Goal completion | All tasks completed |

**Features:**
- Create flight projects linked to GEM goals
- 5-step flight progression (Boarding → Take-off → Cruising → Descent → Landing)
- 4-gear system (Planning, Execution, Monitoring, Course Correction)
- Real-time flight score calculation from linked CTT + Lifestyle data
- Flight dynamics visualization (speed, altitude, fuel, weather)
- Flight log with historical events
- **iGIS (Integrated Growth Intelligence System):** 5 layers of self-growth data
  - Emotional Wellness (from Consciousness Diary)
  - Self-Awareness Levels (from Consciousness Diary)
  - Astrology (stub)
  - Energy Healing (stub)
  - Manifestation (stub)

**API Endpoints:**
```
GET    /api/gem-flight/config                              — Flight configuration
POST   /api/gem-flight/projects                            — Create flight project
GET    /api/gem-flight/projects                            — List projects
GET    /api/gem-flight/projects/{id}                       — Get project detail
PUT    /api/gem-flight/projects/{id}                       — Update project
DELETE /api/gem-flight/projects/{id}                       — Delete project
PUT    /api/gem-flight/projects/{id}/step/{n}              — Update flight step
PUT    /api/gem-flight/projects/{id}/gear/{n}              — Update gear status
GET    /api/gem-flight/projects/{id}/flight-score          — Calculate real-time score
GET    /api/gem-flight/projects/{id}/flight-dynamics       — Get speed/altitude/fuel/weather
GET    /api/gem-flight/projects/{id}/flight-log            — Get flight event log
POST   /api/gem-flight/projects/{id}/link-task             — Link CTT task
POST   /api/gem-flight/projects/{id}/link-routine          — Link lifestyle routine
GET    /api/gem-flight/projects/{id}/igis/emotional-wellness — iGIS: Emotional data
GET    /api/gem-flight/projects/{id}/igis/self-awareness    — iGIS: Self-awareness level
GET    /api/gem-flight/projects/{id}/dashboard             — Full project dashboard
```

---

### 3.17 Consciousness Diary

Daily tracking of 8 emotional wellness metrics feeding into progressive self-awareness levels (1-6).

**8 Core Metrics (tracked daily):**
1. Anger Level (1-10)
2. Sadness Level (1-10)
3. Fear Level (1-10)
4. Outlets Impact (1-10) — Effect of hobbies/outlets on mood
5. ADS Impact (1-10) — Addictions/Dependencies/Substances impact
6. Sitting Still (1-10) — Meditation/mindfulness practice
7. Peacefulness (1-10) — Inner peace and calm
8. Solution-Oriented Leadership (1-10) — Proactive problem-solving attitude

**Progressive Awareness Levels:**
| Level | Name | Score Range | Description |
|-------|------|-------------|-------------|
| 1 | Unconscious Reactivity | 0.0 - 2.0 | Reactive, emotionally driven |
| 2 | Emerging Awareness | 2.1 - 4.0 | Beginning self-observation |
| 3 | Developing Mindfulness | 4.1 - 5.5 | Consistent practice |
| 4 | Conscious Leadership | 5.6 - 7.0 | Applied awareness in decisions |
| 5 | Integrated Awareness | 7.1 - 8.5 | Holistic mind-body integration |
| 6 | Transcendent Clarity | 8.6 - 10.0 | Mastery of self-awareness |

**API Endpoints:**
```
GET  /api/consciousness-diary/config                   — Metric definitions
POST /api/consciousness-diary/entries                  — Log daily entry
GET  /api/consciousness-diary/entries                  — List entries (date range)
PUT  /api/consciousness-diary/entries/{id}             — Update entry
DELETE /api/consciousness-diary/entries/{id}            — Delete entry
GET  /api/consciousness-diary/history                  — Historical trends
GET  /api/consciousness-diary/self-awareness           — Current awareness level
PUT  /api/consciousness-diary/self-awareness           — Update custom levels
GET  /api/consciousness-diary/emotional-wellness       — Emotional wellness dashboard
GET  /api/consciousness-diary/daily-context            — Today's context
```

---

### 3.18 Google Calendar Integration

Full OAuth 2.0 integration for two-way calendar synchronization.

**Features:**
- OAuth consent flow (authorize → callback → token storage)
- Read calendar events
- Create/update/delete calendar events
- Sync CTT tasks to Google Calendar
- Sync Lifestyle routines as recurring events
- Batch export tasks to calendar

**API Endpoints:**
```
GET    /api/oauth/calendar/start             — Initiate OAuth flow
GET    /api/oauth/calendar/callback          — OAuth callback handler
GET    /api/oauth/calendar/status            — Check connection status
DELETE /api/oauth/calendar/disconnect        — Disconnect Google account
GET    /api/google-calendar/events           — List calendar events
POST   /api/google-calendar/events           — Create event
PUT    /api/google-calendar/events/{id}      — Update event
DELETE /api/google-calendar/events/{id}      — Delete event
POST   /api/google-calendar/sync-ctt-task    — Sync CTT task to calendar
```

---

### 3.19 Payments & Credits (Razorpay)

Freemium credit-based monetization system.

**Plans:**
| Plan | Monthly Cost | Credits |
|------|-------------|---------|
| Free | ₹0 | 100 initial credits |
| Starter | ₹149 | 500 credits/month |
| Pro | ₹299 | 1200 credits/month |
| Business | ₹599 | 3000 credits/month |
| Enterprise | ₹999 | 8000 credits/month |

**Top-up Packs:**
| Pack | Price | Credits |
|------|-------|---------|
| Micro | ₹29 | 50 |
| Mini | ₹49 | 100 |
| Standard | ₹99 | 250 |
| Mega | ₹199 | 600 |
| Ultra | ₹499 | 2000 |

**Credit Costs per Action:**
| Action | Credits |
|--------|---------|
| CLD Generate | 3 |
| CLD Simulate | 1 |
| Decision Analyze | 2 |
| Time Store Analyze | 5 |
| Lifestyle Assessment | 2 |
| Factor Data Fetch | 1 |
| DEO Scrape | 3 |

**Payment Flow:**
1. User selects plan/pack → Create Razorpay order
2. Frontend opens Razorpay checkout
3. On payment success → Verify HMAC signature → Add credits
4. Webhook backup for missed verifications

**API Endpoints:**
```
GET  /api/payments/plans                     — List plans and packs
GET  /api/payments/wallet                    — Get credit balance
GET  /api/payments/history                   — Transaction history
POST /api/payments/create-topup-order        — Create topup order
POST /api/payments/create-subscription       — Create subscription order
POST /api/payments/verify                    — Verify payment signature
POST /api/payments/webhook                   — Razorpay webhook handler
POST /api/payments/check-credits             — Check if user can afford action
PUT  /api/payments/admin/initial-credits     — Admin: set initial credit amount
GET  /api/payments/admin/initial-credits     — Admin: get initial credit amount
```

---

### 3.20 Multi-Tenant Organization System

White-label organization support with custom branding and role-based access.

**Features:**
- Organization creation with slug-based URL
- Custom branding (logo, colors, tagline)
- Organization-specific member management
- OTP-based login for org members (via WhatsApp)
- Org role hierarchy independent of global roles

**API Endpoints:**
```
POST   /api/organizations                              — Create org
GET    /api/organizations/{slug}                       — Get org by slug (public)
PUT    /api/organizations/{id}                         — Update branding
GET    /api/organizations/{id}/members                 — List members
PUT    /api/organizations/{id}/members/{uid}/role      — Change member role
DELETE /api/organizations/{id}/members/{uid}           — Remove member
POST   /api/org-auth/login                             — OTP login for org
POST   /api/org-auth/verify-otp                        — Verify OTP
POST   /api/org-auth/resend-otp                        — Resend OTP
```

---

### 3.21 HOS Decision Intake Wizard

Guided decision creation flow with categorized templates.

**Flow:**
1. Select Life Area → 2. Select Ask Type (Problem/Need/Aspiration) → 3. Select Sub-Area → 4. Browse suggested templates → 5. Create decision from template

**API Endpoints:**
```
GET  /api/hos/life-areas             — Life area categories
GET  /api/hos/ask-types              — Decision types
GET  /api/hos/sub-areas              — Sub-area categories
GET  /api/hos/categories             — Full category tree
GET  /api/hos/templates              — Browse templates (filterable)
GET  /api/hos/templates/suggest      — AI-suggest templates
GET  /api/hos/templates/{id}         — Template detail
POST /api/hos/decisions              — Create from template
POST /api/hos/seed                   — Seed default templates
```

---

### 3.22 Expert Video Consultations

Jitsi-based video call sessions for expert consultation during decision-making.

**Features:**
- Admin-managed expert directory
- Create video call sessions linked to specific decision steps
- Configurable call duration limits
- Call expiry management
- Expert notification on call creation

**API Endpoints:**
```
GET  /api/call-config                        — Get call settings
PUT  /api/call-config                        — Update call settings (admin)
POST /api/call-sessions                      — Create call session
GET  /api/call-sessions/{id}                 — Get session detail
PUT  /api/call-sessions/{id}/end             — End session
GET  /api/call-sessions                      — List user's sessions
GET  /api/experts                            — List authorized experts
POST /api/experts                            — Create expert (admin)
PUT  /api/experts/{id}                       — Update expert (admin)
DELETE /api/experts/{id}                     — Delete expert (admin)
```

---

### 3.23 Notifications & Push

Real-time notification system with Expo Push.

**Notification Types:**
- `share_invite` — Step sharing invitation
- `share_contributed` — Contribution received
- `share_merged` — Contributions merged
- `call_invitation` — Expert call request

**API Endpoints:**
```
GET    /api/notifications                    — List notifications
GET    /api/notifications/unread-count       — Unread count
POST   /api/notifications/{id}/read          — Mark as read
POST   /api/notifications/read-all           — Mark all read
DELETE /api/notifications/{id}               — Delete notification
POST   /api/auth/push-token                  — Register push token
```

---

### 3.24 Analytics & Reporting

**Folder Analytics:** Decision statistics broken down by the 10 life area folders.
- Total decisions, completion rate, average factors/options per folder
- Most active folder identification

**Decision Meta:** Life area and decision type reference data.

**API Endpoints:**
```
GET /api/analytics/folders                   — Full folder analytics
GET /api/analytics/folder/{id}               — Single folder deep-dive
GET /api/decision-meta                       — Life areas + decision types
GET /api/stats                               — User dashboard stats
GET /api/folders                             — Folder definitions
```

---

### 3.25 Admin & Feature Flags

**Feature Flags:** Toggle features on/off globally.

**Admin Settings:**
- Promote/demote users between roles
- Manage decision templates (approve, revoke authorization)
- Expert management
- Call configuration
- Initial credit configuration
- Pending solution approvals

**API Endpoints:**
```
GET  /api/feature-flags                      — Get flags
GET  /api/feature-flags/public               — Public flags
PUT  /api/admin/feature-flags                — Update flags
POST /api/admin/setup                        — First-time super admin setup
POST /api/admin/promote                      — Promote user
POST /api/admin/demote                       — Demote user
GET  /api/admin/users                        — List admin users
POST /api/admin/templates/{id}/approve       — Authorize template
POST /api/admin/templates/{id}/revoke        — Revoke authorization
```

---

## 4. 3RD PARTY INTEGRATIONS

| Service | Purpose | Key Type |
|---------|---------|----------|
| OpenAI GPT-4.1-mini | CLD analysis, TEPFI mapping, Lifestyle assessment, DEO scraping, Time scheduling | Emergent LLM Key |
| Razorpay | Payment processing (subscriptions + top-ups) | Live API Key + Secret |
| Google Calendar API | OAuth 2.0 calendar sync | Client ID + Secret |
| UltraMsg | WhatsApp OTP for org login | Instance ID + Token |
| DuckDuckGo Search | Web surfing for factor data source | No key required |
| Jitsi Meet | Video call hosting | No key required |
| Expo Push | Mobile push notifications | Built-in |

---

## 5. DATABASE COLLECTIONS

| Collection | Purpose |
|-----------|---------|
| `users` | User accounts (email, Google, org auth) |
| `user_sessions` | Active session tokens |
| `organizations` | Multi-tenant org definitions |
| `decisions` | PRR decision data (10-step) |
| `templates` | User-created decision templates |
| `decision_templates` | Admin-curated template library |
| `test123_sessions` | Quick decision test sessions |
| `assessments` | Decision-making mode assessments |
| `journal` | Decision journal entries |
| `shared_steps` | Collaborative step sharing |
| `notifications` | User notifications |
| `experts` | Authorized expert directory |
| `call_sessions` | Video call sessions |
| `ctt_tasks` | Centralized task tracker |
| `gem_goals` | Goal execution manager |
| `tepfi_entries` | TEPFI resource matrix entries |
| `solution_finders` | Solution brainstorming entries |
| `solution_matrices` | Solution comparison matrices |
| `solutions_store` | Solutions catalog |
| `solution_reviews` | ReviewNet reviews |
| `user_location_preferences` | Location/language prefs |
| `cld_diagrams` | Saved CLD diagrams |
| `lifestyle_routines` | Lifestyle routines |
| `lifestyle_assessments` | AI lifestyle assessments |
| `lifestyle_completions` | Daily routine completions |
| `time_preferences` | Time Dezider preferences |
| `time_schedules` | Generated daily schedules |
| `time_budgets` | Time Store budget data |
| `consciousness_diary` | Daily emotional wellness entries |
| `consciousness_self_awareness` | Self-awareness level tracking |
| `deo_api_keys` | DEO outbound API keys |
| `deo_scrape_logs` | DEO scraping history |
| `deo_field_mappings` | DEO field mapping configs |
| `gem_flight_projects` | GEM Flight orchestrator projects |
| `password_resets` | Password reset OTPs |
| `user_wallets` | Credit wallets |
| `payment_orders` | Razorpay order records |
| `credit_transactions` | Credit ledger |
| `app_config` | App-wide config (feature flags, call settings, etc.) |
| `google_tokens` | Google OAuth refresh tokens |

---

## 6. CROSS-PLATFORM CONSIDERATIONS

| Concern | Implementation |
|---------|---------------|
| Navigation | Expo Router (file-based), 5-tab bottom navigation |
| Safe Area | `react-native-safe-area-context` with dynamic insets |
| Alerts/Dialogs | Custom `showAlert()` utility (window.confirm on web, Alert.alert on native) |
| Auth Storage | AsyncStorage (localStorage on web, device storage on native) |
| Push Notifications | Expo Push (native only) |
| Keyboard Handling | KeyboardAvoidingView on input screens |
| Tab Bar | Dynamic height with safe area insets (56px + bottom inset on native, 64px on web) |

---

## 7. STUB FEATURES (Future Development)

| Feature | Status | Location |
|---------|--------|----------|
| Astrology (iGIS Layer) | Stub endpoint returning mock data | `gem_flight.py` |
| Energy Healing (iGIS Layer) | Stub endpoint returning mock data | `gem_flight.py` |
| Manifestation (iGIS Layer) | Stub endpoint returning mock data | `gem_flight.py` |

---

*Document generated from codebase analysis — View Dezider v3.0*
*© Venture Buddha | Decision Intelligence Platform*
