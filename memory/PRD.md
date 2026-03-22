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
│       └── admin.py (Feature Flags + Call Config)
├── frontend/
│   ├── app/
│   │   ├── (tabs)/ (index, profile, prr)
│   │   ├── admin/ (experts, templates, settings)
│   │   ├── auth/ (login, register)
│   │   ├── tools/ (solution-finder, solution-finder-list, solution-matrix, solution-matrix-list)
│   │   └── prr/[id].tsx
│   └── src/
│       ├── components/ (steps/, CLDViewer, ExpertCallModal)
│       ├── context/ (DecisionContext)
│       └── store/ (authStore)
```

## API Endpoints (New)
- `GET/PUT /api/admin/feature-flags` - WOWO toggle
- `GET /api/feature-flags` - Get flags (auth)
- `GET /api/feature-flags/public` - Get flags (no auth)
- `POST/GET/PUT/DELETE /api/solution-finders` - Solution Finder CRUD
- `POST/GET/PUT/DELETE /api/solution-matrices` - Solution Matrix CRUD
- `GET/PUT /api/admin/call-config` - Video call settings
