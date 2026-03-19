# View Dezider - Product Requirements Document

## Overview
**View Dezider** is a decision intelligence mobile app based on Chapter 2 of "Be Your Best-mate" book by Venture Buddha. It helps users make better decisions through structured frameworks.

## Core Features

### 1. PRR (Priority Related Ratings) Decision System
- 10-step guided decision-making process
- Steps: Context → List Factors → Classify → Prioritize → Calculate Ratings → Define Options → Assess Options → Results → Reflection → Final Notes
- LMH (Low/Medium/High) quick assessment toggles
- Custom percentage input for precise ratings
- Voice command input support
- Auto-calculated worth percentages with weighted average formula
- Clone decisions at 5 levels (factors/classification/prioritization/options/assessment)
- Template system with visibility (private/shared/public)

### 2. Test123 - Quick Decision Tool
- 3-test instant decision framework
- Test 1: Am I emotional? (emotional check)
- Test 2: Worst case scenario analysis
- Test 3: Core needs identification

### 3. Decision Mode Assessment
- 12-question personality quiz
- 4 decision modes: Emotional, Logical, Intuitive, Awareness
- Score breakdown with visual charts

### 4. Decision Journal
- Track decisions and outcomes
- Status tracking (Pending Review, Reviewed, Archived)

### 5. Admin System
- 3-tier role hierarchy: super_admin > co_admin > admin > user
- Template authorization (approve/revoke)
- User role management (promote/demote)

## Tech Stack
- **Frontend**: Expo (React Native) with expo-router, TypeScript
- **Backend**: FastAPI (Python) with Motor (async MongoDB)
- **Database**: MongoDB
- **Auth**: Email/password + Google OAuth
- **Styling**: Venture Buddha branding with purple/magenta gradient theme

## API Endpoints (34 total)
All endpoints prefixed with `/api`

### Auth (6)
- POST /auth/register, /auth/login, /auth/forgot-password, /auth/reset-password, /auth/set-password
- GET /auth/me

### Decisions (5)
- POST /decisions, GET /decisions, GET /decisions/{id}, PUT /decisions/{id}, DELETE /decisions/{id}

### Clone & Templates (6)
- POST /decisions/{id}/clone, /templates, /templates/{id}/use, /templates/{id}/import
- GET /templates, DELETE /templates/{id}

### Test123 (4)
- POST /test123, GET /test123, GET /test123/{id}, PUT /test123/{id}

### Assessment (3)
- POST /assessment, GET /assessment, GET /assessment/questions

### Journal (4)
- POST /journal, GET /journal, PUT /journal/{id}, DELETE /journal/{id}

### Stats (1)
- GET /stats

### Admin (5)
- POST /admin/setup, /admin/promote/{id}, /admin/demote/{id}, /admin/templates/{id}/approve, /admin/templates/{id}/revoke
- GET /admin/users

## Status
- Backend: All 34 API endpoints tested and working ✅
- Frontend: All screens implemented and tested ✅
- Shadow deprecation warnings fixed ✅
- UI polish completed ✅
