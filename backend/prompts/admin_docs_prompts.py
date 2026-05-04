"""LLM prompts used by the Admin Documentation Hub.

Keeping these prompts in a dedicated config module:
- avoids 700-line route files,
- lets prompt engineers iterate without touching FastAPI handlers,
- makes A/B prompt testing easy (just swap a key).

Each entry is a callable that takes the API summary text and returns the
final prompt string. This indirection makes it trivial to inject extra
context (e.g., recent changelog, feature flags) later without rewriting
the route.
"""

from typing import Callable, Dict


def _prd_prompt(api_summary: str) -> str:
    return f"""You are a senior product manager. Generate a comprehensive Product Requirements Document (PRD) for "View Dezider" — a Decision Intelligence platform by Venture Buddha.

Based on the following API endpoints, reverse-engineer the full product requirements:

{api_summary}

The PRD must include:
1. Product Overview & Vision
2. Target Users (Individual, Business, Government/NonProfit)
3. Core Features covering ALL modules:
   - PRR Decision Engine (10-step), Test123 Quick Decisions, Pros & Cons, SWOT
   - Solutions Store with ReviewNet, DEO Engine (Inbound scraping + Outbound APIs)
   - CLD (Causal Loop Diagrams) — per-decision, per-module, and Master CLD (cross-module aggregation)
   - GEM Flight Model, CTT Task Tracker, GEM Goal Execution Manager
   - Lifestyle Dezider with routines, streaks, and LEE (Lifestyle Effectiveness Evaluation)
   - AALA (Accrued Assets & Liabilities Analysis) — Circle of Influence across 10 life areas
   - Goal Setter (SMART), Goal Manifestation (CAB-FAME 7 stages), KalphaVriksha Meditation
   - Unconditional Happiness Tracker, Meditation Settings (custom audio per user)
   - Emotional Gatekeeper sub-tools (Breaking the Trap, Breaking the Loop, Breaking Limitations, AIM, Outlet Analyzer, Effective Outlets Advisor, Emotional Reception)
   - Consciousness Diary, Time Dezider, Time Store, HOS Decision Intake
   - PNA Framework (Problems/Needs/Aspirations across 10 life areas with Convert-to-Decision/Goal)
   - Lifestyle Designer (plan ideal lifestyle allocations vs actuals with LEE comparison)
   - Conflict Breaker — 9-stage guided crucial conversation prep (Crucial Check, Motive Clarity, Learn to Look, Make It Safe, Story Map, Script Builder, Listening Plan, Action Plan, Closure) with AI script rewriting
   - AI Solution Assistant — personal AI chatbot with 6 languages (English, Tamil, Telugu, Kannada, Malayalam, Hindi), Text-to-Speech, cross-module context awareness, quick-ask one-shot queries
   - WOWO Access Control Matrix (role-based + subscription-plan feature gating with quotas)
   - Org Admin hierarchy (super_admin, admin, co_admin, user)
   - TEPFI Matrix (Time, Energy, People, Finance, Infrastructure resource analysis)
4. User Stories for each major feature
5. Non-functional Requirements (performance, security, scalability to 10k concurrent)
6. Integration Requirements (Google Calendar OAuth, Razorpay, WhatsApp OTP via UltraMsg, Emergent LLM/AI for doc generation / CLD / Conflict Breaker / AI Assistant, DigiLocker eKYC)
7. Platform Support (Web, Android, iOS, Chatbot, IVR)
8. AI-Powered Features Overview (CLD Generation, Conflict Script Rewriting, AI Assistant Conversations, Admin Doc Generation)

Format in clean Markdown with proper headings."""


def _srs_prompt(api_summary: str) -> str:
    return f"""You are a systems architect. Generate a detailed System Requirements Specification (SRS) for "View Dezider" — a multi-platform Decision Intelligence system with 35+ modules.

Based on these API endpoints:

{api_summary}

The SRS must include:
1. System Overview & Architecture (FastAPI + MongoDB + Expo React Native + Emergent LLM Integration)
2. Functional Requirements per module (with endpoint mappings) covering:
   - Core Decision modules (PRR 10-step, Test123, Pros-Cons, SWOT, CLD with per-module + Master generation, HOS)
   - Execution modules (CTT, GEM, GEM Flight)
   - Evaluation modules (AALA, LEE, Lifestyle Designer, PNA Framework)
   - Growth modules (Goal Setter SMART, Goal Manifestation CAB-FAME, Unconditional Happiness, KalphaVriksha Meditation)
   - Self-Awareness (Emotional Gatekeeper with 10+ sub-tools, Consciousness Diary, Meditation Settings)
   - External Integration modules (Solutions Store, DEO Engine, Google Calendar OAuth)
   - Collaboration modules (Conflict Breaker 9-stage wizard with AI, Shared Steps, Expert Video Calls, Contacts)
   - AI Intelligence modules (AI Solution Assistant with 6-language TTS, CLD AI Generation, Conflict Script AI Rewriting)
   - Admin modules (WOWO ACM with role-based + subscription-plan gating, Org Auth, Feature Flags, Payments, Admin Doc Hub)
   - Resource modules (TEPFI Matrix, Time Dezider, Time Store)
3. Data Models / Schema Definitions (all 35+ collections including conflict_breaker_sessions, ai_assistant_conversations, pna_items, lifestyle_plans, acm_modules)
4. Authentication & Authorization (Session tokens, Role hierarchy super_admin → admin → co_admin → user, Org roles, WOWO ACM two-axis check: user_type × subscription_plan)
5. External Integrations (Google Calendar OAuth, Razorpay, UltraMsg WhatsApp OTP, Emergent LLM for AI features, DigiLocker, expo-speech for TTS)
6. API Design Patterns (RESTful, prefix /api, session token auth, channel tagging: internal/chatbot/ivr/partner)
7. Security & Privacy Requirements (bcrypt password hashing, session tokens, role-based access)
8. Performance Requirements (10k concurrent users target, in-memory ACM cache, MongoDB indices, connection pooling, rate limiting)
9. Deployment Architecture (Kubernetes, Expo Web/Mobile, FastAPI with uvicorn auto-reload)

Format in clean Markdown with proper headings."""


def _regression_tests_prompt(api_summary: str) -> str:
    return f"""You are a QA lead. Generate comprehensive regression test cases for "View Dezider" Decision Intelligence platform with 35+ modules and 500+ API endpoints.

Based on these API endpoints:

{api_summary}

Generate test cases covering ALL modules:
1. Authentication Flow (Register, Login, Session, Logout, Password Reset, WhatsApp OTP)
2. PRR Decision CRUD (Create, Read, Update, Delete, Clone, Share — 10 steps)
3. Factor & Option Management
4. Test123 Quick Decisions, Pros & Cons, SWOT Analysis
5. CTT Task Tracker, GEM Goals, GEM Flight
6. Solutions Store & ReviewNet
7. DEO Engine (Scraping import + API Keys)
8. CLD (Causal Loop Diagrams) CRUD + Simulation + Module-Specific Generation (PNA, Goal, Lifestyle, Master) + List Modules
9. AALA (Assets & Liabilities)
10. LEE (Lifestyle Effectiveness Evaluation)
11. Goal Setter (SMART) + Goal Manifestation (CAB-FAME)
12. Unconditional Happiness + Meditation Settings
13. PNA Framework (Problems/Needs/Aspirations) — CRUD + Dashboard + Area Detail + Convert to Decision/Goal
14. Lifestyle Designer — Plan CRUD + Activate + Comparison vs LEE + Manual Overrides
15. Conflict Breaker — Session CRUD, 9-stage data save (Crucial Check through Closure), AI Generate per stage, Full session retrieval, Dashboard
16. AI Solution Assistant — Meta (6 languages), Conversation CRUD, Send Message (LLM), Quick Ask (LLM), Delete Conversation
17. Emotional Gatekeeper — All 10 sub-tools (Breaking Trap/Loop/Limitations, AIM, Outlet Analyzer, Effective Outlets Advisor, Emotional Reception, AI Reports)
18. Payments & Credits (Razorpay integration)
19. Admin Operations + WOWO ACM (Seed, Matrix, Feature Update, User Type Management, Usage Stats)
20. Admin Doc Hub (API Catalog, Postman Collection Export, PRD/SRS/Regression/UAT Generate & Refresh)
21. TEPFI Matrix, Time Dezider, Time Store
22. Google Calendar OAuth (Auth URL, Callback, Sync)
23. Rate Limiting & Quota Enforcement (per-user, per-IP, AI-tier limits)
24. Edge Cases (empty data, unauthorized access, invalid IDs, role escalation, quota limits, expired sessions)

Format each test case as:
**TC-XXX: [Title]**
- Precondition: ...
- Steps: 1. ... 2. ... 3. ...
- Expected Result: ...
- Priority: P0/P1/P2

Format in clean Markdown."""


def _uat_prompt(api_summary: str) -> str:
    return f"""You are a UAT coordinator. Generate User Acceptance Test scenarios for "View Dezider" — covering ALL critical user journeys across 35+ modules.

Based on these API endpoints:

{api_summary}

Generate UAT scenarios for:
1. New User Onboarding (Register → First Decision → Complete PRR flow)
2. Pros & Cons / SWOT → PRR Conversion Flow
3. Task Management (CTT) with Decision linkage + Google Calendar sync
4. Goal Setting → Manifestation (CAB-FAME 7 stages) + KalphaVriksha Meditation
5. Solutions Store browsing + Integration into PRR Step 6/7 (auto-populate factors)
6. AALA Assessment + LEE Daily Logging
7. PNA Framework — Add items across 10 life areas → Convert to Decision/Goal
8. Lifestyle Designer — Create plan, set weekday/weekend allocations, compare vs LEE actuals, manual overrides
9. Unconditional Happiness daily tracking + streaks
10. Emotional Gatekeeper — Breaking the Trap → Breaking the Loop → Breaking Limitations → AI Breakthrough Report
11. Conflict Breaker — Create session → Walk through 9 stages (Crucial Check → Motive Clarity → Learn to Look → Make It Safe → Story Map → Script Builder → Listening Plan → Action Plan → Closure) → AI Script Rewriting → View Full Session
12. AI Solution Assistant — Select language → Start conversation → Send messages (receive AI responses with cross-module context) → Use TTS to hear response → Quick Ask one-shot → Switch language
13. CLD Engine — Generate per-decision CLD → Generate module-specific CLD (PNA, Goal, Lifestyle) → Generate Master CLD → Run What-If Simulation
14. Payment & Credit purchase (Razorpay flow)
15. Admin operations (user management, WOWO ACM settings, seed matrix, update feature access, doc generation/refresh)
16. Multi-platform verification (Web + Mobile via Expo Go)
17. DEO Engine import from external URLs + API key generation for outbound
18. Org Admin hierarchy: super_admin creates org → admin manages members → co_admin limited access → user
19. TEPFI Matrix resource analysis
20. Google Calendar OAuth flow: Authorize → Sync tasks → Sync lifestyle routines

Each scenario should be:
**UAT-XXX: [Scenario Title]**
- Actor: [User type]
- Goal: [What they want to achieve]
- Steps: 1. ... 2. ... 3. ...
- Acceptance Criteria: ...
- Platform: Web/Mobile/Chatbot/IVR/All

Format in clean Markdown."""


# Prompt registry — maps doc_type to a (prompt_builder, system_message) tuple.
PROMPT_REGISTRY: Dict[str, Callable[[str], str]] = {
    "prd": _prd_prompt,
    "srs": _srs_prompt,
    "regression_tests": _regression_tests_prompt,
    "uat_cases": _uat_prompt,
}

DOC_SYSTEM_MESSAGE = (
    "You are an expert technical writer. Generate professional, "
    "comprehensive documentation in Markdown format."
)

DOC_TITLES = {
    "prd": "Product Requirements Document — View Dezider",
    "srs": "System Requirements Specification — View Dezider",
    "regression_tests": "Regression Test Cases — View Dezider",
    "uat_cases": "User Acceptance Test Cases — View Dezider",
}


def build_prompt(doc_type: str, api_summary: str) -> str:
    """Return the final LLM prompt string for the given doc_type.

    Falls back to a generic "Generate documentation." string if doc_type
    isn't registered (defensive — should be guarded upstream via DOC_TYPES).
    """
    builder = PROMPT_REGISTRY.get(doc_type)
    if not builder:
        return "Generate documentation."
    return builder(api_summary)
