"""
ACM Seed Data — Default Access Control Matrix
Defines all modules, features, quota units, and default access per user_type × subscription_plan.

Access Levels:
  "full"      → Full access (quota applies if set)
  "read"      → Read/View only (can browse but not create/modify)
  "locked"    → Visible but greyed out with upgrade prompt
  "hidden"    → Not shown in UI at all

Quota:
  -1  → Unlimited
   0  → No access (use with "locked" or "hidden")
   N  → Specific limit per quota_unit period

User Types: unit_tester, integration_tester, alpha, beta, free, trial, paid
Subscription Plans (for paid): starter, pro, enterprise, api
"""

# Release stages (ordered by visibility)
RELEASE_STAGES = [
    "unit_test",          # Only UT
    "integration_test",   # UT + IT
    "alpha",              # UT + IT + Alpha
    "beta",               # UT + IT + Alpha + Beta
    "ga_paid",            # All above + Paid users
    "ga_trial",           # All above + Trial users
    "ga_free",            # Everyone (general availability)
]

USER_TYPES = [
    {"id": "unit_tester", "name": "Unit Tester", "description": "Internal QA — tests individual modules in production", "order": 1},
    {"id": "integration_tester", "name": "Integration Tester", "description": "Internal QA — tests integrated features pre-release", "order": 2},
    {"id": "alpha", "name": "Alpha User", "description": "Closed group — non-technical internal/extended stakeholders", "order": 3},
    {"id": "beta", "name": "Beta User", "description": "Early adopters — unreleased features (like Google Labs)", "order": 4},
    {"id": "free", "name": "Free User", "description": "Public free tier with limited feature access", "order": 5},
    {"id": "trial", "name": "Free Trial User", "description": "Time-limited access to premium features", "order": 6},
    {"id": "paid", "name": "Paid User", "description": "Active subscription holder", "order": 7},
]

SUBSCRIPTION_PLANS = [
    {"id": "none", "name": "No Plan", "description": "Free tier — no subscription", "price": 0, "order": 0},
    {"id": "starter", "name": "Starter", "description": "Basic paid features with moderate limits", "price": 499, "order": 1},
    {"id": "pro", "name": "Professional", "description": "Full feature access with generous limits", "price": 1499, "order": 2},
    {"id": "enterprise", "name": "Enterprise", "description": "Multi-org, API access, white-label, unlimited", "price": 4999, "order": 3},
    {"id": "api", "name": "API / Developer", "description": "DEO outbound API access for external consumers", "price": 2999, "order": 4},
]


def _full(quota=-1):
    return {"level": "full", "quota": quota}

def _read(quota=-1):
    return {"level": "read", "quota": quota}

def _locked():
    return {"level": "locked", "quota": 0}

def _hidden():
    return {"level": "hidden", "quota": 0}


# ============================================================
# MASTER ACM MATRIX
# ============================================================
# Each module contains features. Each feature defines access
# per (user_type, subscription_plan) combination.
# For "paid" user_type, access varies by subscription plan.
# ============================================================

ACM_MODULES = [
    # ────────────────────────────────────────────────────
    # MODULE 1: My Dezider (10-Step Decision Engine)
    # ────────────────────────────────────────────────────
    {
        "module_id": "my_dezider",
        "module_name": "My Dezider",
        "module_icon": "bulb",
        "module_description": "10-step HOS Decision Engine with AI-powered factor analysis",
        "order": 1,
        "features": [
            {
                "feature_id": "my_dezider_create",
                "feature_name": "Create New Decision",
                "release_stage": "ga_free",
                "quota_unit": "decisions/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(3), "trial": _full(),
                    "paid_starter": _full(15), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "my_dezider_sl_import",
                "feature_name": "Import Factors from Social Learning",
                "release_stage": "ga_paid",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "my_dezider_store_import",
                "feature_name": "Import Options from Solutions Store",
                "release_stage": "ga_paid",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 2: Test123 (Instant Decision)
    # ────────────────────────────────────────────────────
    {
        "module_id": "test123",
        "module_name": "Test123",
        "module_icon": "flash",
        "module_description": "Quick instant decision sessions",
        "order": 2,
        "features": [
            {
                "feature_id": "test123_create",
                "feature_name": "Create Test123 Session",
                "release_stage": "ga_free",
                "quota_unit": "sessions/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 3: Decision Kickstarters
    # ────────────────────────────────────────────────────
    {
        "module_id": "decision_kickstarters",
        "module_name": "Decision Kickstarters",
        "module_icon": "rocket",
        "module_description": "Quick decision frameworks: Pros & Cons, SWOT",
        "order": 3,
        "features": [
            {
                "feature_id": "pros_cons",
                "feature_name": "Pros & Cons Analysis",
                "release_stage": "ga_free",
                "quota_unit": "analyses/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "swot_analysis",
                "feature_name": "SWOT Analysis",
                "release_stage": "ga_free",
                "quota_unit": "analyses/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(5), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 4: Solution Tools
    # ────────────────────────────────────────────────────
    {
        "module_id": "solution_tools",
        "module_name": "Solution Tools",
        "module_icon": "construct",
        "module_description": "Structured problem-solving: Solution Finder & Solution Matrix",
        "order": 4,
        "features": [
            {
                "feature_id": "solution_finder",
                "feature_name": "Solution Finder (5-Step)",
                "release_stage": "ga_trial",
                "quota_unit": "worksheets/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(),
                    "paid_starter": _full(10), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "solution_finder_sl_import",
                "feature_name": "Import Risks from Social Learning (Q4)",
                "release_stage": "ga_paid",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _hidden(), "trial": _full(),
                    "paid_starter": _locked(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "solution_matrix",
                "feature_name": "Solution Matrix (7-Step Advanced)",
                "release_stage": "ga_paid",
                "quota_unit": "worksheets/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(),
                    "paid_starter": _locked(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 5: CTT (Centralized Task Tracker)
    # ────────────────────────────────────────────────────
    {
        "module_id": "ctt",
        "module_name": "Centralized Task Tracker (CTT)",
        "module_icon": "checkmark-done",
        "module_description": "Full task management with day-wise status, routines, and calendar sync",
        "order": 5,
        "features": [
            {
                "feature_id": "ctt_tasks",
                "feature_name": "Task Management",
                "release_stage": "ga_free",
                "quota_unit": "active_tasks",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(20), "trial": _full(),
                    "paid_starter": _full(100), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "ctt_auto_aggregate",
                "feature_name": "Auto-Aggregate from Decisions & Solutions",
                "release_stage": "ga_paid",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _hidden(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "ctt_calendar_sync",
                "feature_name": "Google Calendar Sync",
                "release_stage": "ga_paid",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _hidden(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 6: GEM (Goal Execution Manager)
    # ────────────────────────────────────────────────────
    {
        "module_id": "gem",
        "module_name": "GEM — Goal Execution Manager",
        "module_icon": "trophy",
        "module_description": "Goal management across 10 Life Areas with progress tracking",
        "order": 6,
        "features": [
            {
                "feature_id": "gem_goals",
                "feature_name": "Goal Management",
                "release_stage": "ga_free",
                "quota_unit": "active_goals",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(3), "trial": _full(),
                    "paid_starter": _full(10), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "gem_flight",
                "feature_name": "GEM Flight Model (Orchestrator)",
                "release_stage": "ga_paid",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 7: Social Learning Pipeline
    # ────────────────────────────────────────────────────
    {
        "module_id": "social_learning",
        "module_name": "Social Learning Pipeline",
        "module_icon": "newspaper",
        "module_description": "News-to-Decision intelligence: Upload, classify, extract factors & risks",
        "order": 7,
        "features": [
            {
                "feature_id": "sl_upload",
                "feature_name": "News Upload (Text/URL/File/Audio/Video)",
                "release_stage": "ga_paid",
                "quota_unit": "uploads/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(),
                    "paid_starter": _full(5), "paid_pro": _full(50),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "sl_browse_authorized",
                "feature_name": "Browse Authorized Templates (Tier 2)",
                "release_stage": "ga_free",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _read(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "sl_tier3_premium",
                "feature_name": "AI Premium Templates (Tier 3)",
                "release_stage": "ga_paid",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(),
                    "paid_starter": _locked(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 8: Solutions Store
    # ────────────────────────────────────────────────────
    {
        "module_id": "solutions_store",
        "module_name": "Solutions Store",
        "module_icon": "storefront",
        "module_description": "Catalog of solutions with reviews, ratings, and location filtering",
        "order": 8,
        "features": [
            {
                "feature_id": "store_browse",
                "feature_name": "Browse Solutions Catalog",
                "release_stage": "ga_free",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _read(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _full(),
                },
            },
            {
                "feature_id": "store_submit",
                "feature_name": "Submit Solutions for Approval",
                "release_stage": "ga_paid",
                "quota_unit": "submissions/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(2),
                    "paid_starter": _full(5), "paid_pro": _full(20),
                    "paid_enterprise": _full(), "paid_api": _full(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 9: DEO Engine
    # ────────────────────────────────────────────────────
    {
        "module_id": "deo",
        "module_name": "DEO Engine",
        "module_icon": "code-slash",
        "module_description": "Decision Engine Optimization: Inbound scraping & Outbound API",
        "order": 9,
        "features": [
            {
                "feature_id": "deo_scrape",
                "feature_name": "Inbound: AI URL Scraping",
                "release_stage": "ga_paid",
                "quota_unit": "scrapes/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _hidden(), "beta": _full(),
                    "free": _hidden(), "trial": _hidden(),
                    "paid_starter": _hidden(), "paid_pro": _full(20),
                    "paid_enterprise": _full(), "paid_api": _full(50),
                },
            },
            {
                "feature_id": "deo_api_keys",
                "feature_name": "Outbound: API Key Generation",
                "release_stage": "ga_paid",
                "quota_unit": "active_keys",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _hidden(), "beta": _hidden(),
                    "free": _hidden(), "trial": _hidden(),
                    "paid_starter": _hidden(), "paid_pro": _hidden(),
                    "paid_enterprise": _full(5), "paid_api": _full(10),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 10: TEPFI Matrix
    # ────────────────────────────────────────────────────
    {
        "module_id": "tepfi",
        "module_name": "TEPFI Matrix",
        "module_icon": "grid",
        "module_description": "Time, Energy, People, Finance, Infrastructure resource analysis",
        "order": 10,
        "features": [
            {
                "feature_id": "tepfi_analysis",
                "feature_name": "TEPFI Resource Analysis",
                "release_stage": "ga_trial",
                "quota_unit": "analyses/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 11: CLD Engine
    # ────────────────────────────────────────────────────
    {
        "module_id": "cld_engine",
        "module_name": "CLD Engine",
        "module_icon": "git-network",
        "module_description": "Causal Loop Diagrams — AI-generated systemic analysis",
        "order": 11,
        "features": [
            {
                "feature_id": "cld_viewer",
                "feature_name": "CLD Viewer & Editor",
                "release_stage": "beta",
                "quota_unit": "diagrams/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _hidden(), "beta": _full(),
                    "free": _hidden(), "trial": _locked(),
                    "paid_starter": _locked(), "paid_pro": _full(10),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 12: Time Intelligence
    # ────────────────────────────────────────────────────
    {
        "module_id": "time_intelligence",
        "module_name": "Time Intelligence",
        "module_icon": "time",
        "module_description": "Time Dezider & Time Store for time-based decision analysis",
        "order": 12,
        "features": [
            {
                "feature_id": "time_dezider",
                "feature_name": "Time Dezider",
                "release_stage": "ga_paid",
                "quota_unit": "analyses/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "time_store",
                "feature_name": "Time Store (Allocation Tracking)",
                "release_stage": "ga_paid",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 13: Lifestyle Dezider
    # ────────────────────────────────────────────────────
    {
        "module_id": "lifestyle",
        "module_name": "Lifestyle Dezider",
        "module_icon": "leaf",
        "module_description": "Routine management with daily tracking, streaks, and analytics",
        "order": 13,
        "features": [
            {
                "feature_id": "lifestyle_routines",
                "feature_name": "Routine Management",
                "release_stage": "ga_free",
                "quota_unit": "active_routines",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(3), "trial": _full(),
                    "paid_starter": _full(15), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "lifestyle_streaks",
                "feature_name": "Streaks & Daily Completion",
                "release_stage": "ga_paid",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "lifestyle_analytics",
                "feature_name": "Lifestyle Analytics Dashboard",
                "release_stage": "ga_paid",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 14: Consciousness Diary
    # ────────────────────────────────────────────────────
    {
        "module_id": "consciousness_diary",
        "module_name": "Consciousness Diary",
        "module_icon": "eye",
        "module_description": "Self-awareness and inner wellness tracking",
        "order": 14,
        "features": [
            {
                "feature_id": "consciousness_diary",
                "feature_name": "Diary Entries",
                "release_stage": "ga_free",
                "quota_unit": "entries/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(30), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 15: Journal
    # ────────────────────────────────────────────────────
    {
        "module_id": "journal",
        "module_name": "Decision Journal",
        "module_icon": "book",
        "module_description": "Decision journaling with review reminders",
        "order": 15,
        "features": [
            {
                "feature_id": "journal_entries",
                "feature_name": "Journal Entries & Reviews",
                "release_stage": "ga_free",
                "quota_unit": "entries/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(15), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 16: Collaboration
    # ────────────────────────────────────────────────────
    {
        "module_id": "collaboration",
        "module_name": "Collaboration",
        "module_icon": "people",
        "module_description": "Contacts, group decisions, shared steps, expert video calls",
        "order": 16,
        "features": [
            {
                "feature_id": "contacts",
                "feature_name": "Contacts Management",
                "release_stage": "ga_paid",
                "quota_unit": "active_contacts",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(10),
                    "paid_starter": _full(25), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "group_decisions",
                "feature_name": "Group Decisions (Multi-User)",
                "release_stage": "ga_paid",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "expert_calls",
                "feature_name": "Expert Video Calls (Jitsi)",
                "release_stage": "ga_paid",
                "quota_unit": "calls/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _hidden(), "trial": _full(1),
                    "paid_starter": _full(3), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 17: Google Calendar
    # ────────────────────────────────────────────────────
    {
        "module_id": "google_calendar",
        "module_name": "Google Calendar Integration",
        "module_icon": "calendar",
        "module_description": "OAuth sync for tasks, routines, and deadlines",
        "order": 17,
        "features": [
            {
                "feature_id": "gcal_sync",
                "feature_name": "Calendar Sync & Export",
                "release_stage": "ga_paid",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _hidden(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 18: Decision Modes Assessment
    # ────────────────────────────────────────────────────
    {
        "module_id": "assessment",
        "module_name": "Decision Making Assessment",
        "module_icon": "analytics",
        "module_description": "Emotional/Logical/Intuitive mode identification quiz",
        "order": 18,
        "features": [
            {
                "feature_id": "decision_modes_quiz",
                "feature_name": "Decision Modes Quiz",
                "release_stage": "ga_free",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 19: Security
    # ────────────────────────────────────────────────────
    {
        "module_id": "security",
        "module_name": "Security Features",
        "module_icon": "shield-checkmark",
        "module_description": "Face authentication and document verification",
        "order": 19,
        "features": [
            {
                "feature_id": "face_auth",
                "feature_name": "Face Authentication (MediaPipe)",
                "release_stage": "ga_paid",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _hidden(), "beta": _full(),
                    "free": _hidden(), "trial": _hidden(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "digilocker",
                "feature_name": "DigiLocker Verification",
                "release_stage": "integration_test",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _hidden(), "beta": _hidden(),
                    "free": _hidden(), "trial": _hidden(),
                    "paid_starter": _hidden(), "paid_pro": _hidden(),
                    "paid_enterprise": _hidden(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 20: Emotional Gatekeeper
    # ────────────────────────────────────────────────────
    {
        "module_id": "emotional_gatekeeper",
        "module_name": "Emotional Gatekeeper",
        "module_icon": "heart-circle",
        "module_description": "Self-introspection engine: Break traps, loops & limitations with AI coaching",
        "order": 20,
        "features": [
            {
                "feature_id": "eg_dashboard",
                "feature_name": "Gatekeeper Dashboard & Streaks",
                "release_stage": "ga_trial",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _read(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "eg_breaking_trap",
                "feature_name": "Breaking the Trap (Landscaping → Linking → Looping)",
                "release_stage": "ga_trial",
                "quota_unit": "sessions/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(2), "trial": _full(),
                    "paid_starter": _full(10), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "eg_breaking_loop",
                "feature_name": "Breaking the Loop (4 Methods: IDK, All Is Well, Both, This Too Shall Pass)",
                "release_stage": "ga_trial",
                "quota_unit": "sessions/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(2), "trial": _full(),
                    "paid_starter": _full(10), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "eg_breaking_limitations",
                "feature_name": "Breaking Limitations (Past Self/Others, External, Fear of Unknown)",
                "release_stage": "ga_trial",
                "quota_unit": "sessions/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(2), "trial": _full(),
                    "paid_starter": _full(10), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "eg_outlet_analyzer",
                "feature_name": "Emotional Outlet Analyzer (Physical/Mental/Emotional/Energy)",
                "release_stage": "ga_paid",
                "quota_unit": "analyses/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(),
                    "paid_starter": _full(5), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "eg_aim_manager",
                "feature_name": "AIM — Addictions & Irritations Manager",
                "release_stage": "ga_paid",
                "quota_unit": "sessions/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(),
                    "paid_starter": _full(5), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "eg_voice_input",
                "feature_name": "Voice Recording Input (Audio Transcription)",
                "release_stage": "ga_paid",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "eg_ai_reports",
                "feature_name": "AI Breakthrough Reports & Commitments",
                "release_stage": "ga_paid",
                "quota_unit": "reports/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(3),
                    "paid_starter": _full(10), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 20b: Coming Soon (Unreleased)
    # ────────────────────────────────────────────────────
    {
        "module_id": "coming_soon",
        "module_name": "Coming Soon Modules",
        "module_icon": "sparkles",
        "module_description": "Modules under development — available to testers and beta users only",
        "order": 25,
        "features": [
            {
                "feature_id": "conflict_breaker",
                "feature_name": "The Conflict Breaker",
                "release_stage": "beta",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _hidden(), "beta": _full(),
                    "free": _hidden(), "trial": _hidden(),
                    "paid_starter": _hidden(), "paid_pro": _locked(),
                    "paid_enterprise": _locked(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 21: Credits & Subscription
    # ────────────────────────────────────────────────────
    {
        "module_id": "subscription",
        "module_name": "Credits & Subscription",
        "module_icon": "diamond",
        "module_description": "Plan management, credit purchase, and billing",
        "order": 21,
        "features": [
            {
                "feature_id": "subscription_manage",
                "feature_name": "Manage Subscription & Credits",
                "release_stage": "ga_free",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _full(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 22: Admin Panel
    # ────────────────────────────────────────────────────
    {
        "module_id": "admin",
        "module_name": "Admin Panel",
        "module_icon": "settings",
        "module_description": "Platform administration: WOWO, templates, users, audit, incidents",
        "order": 22,
        "features": [
            {
                "feature_id": "admin_wowo",
                "feature_name": "WOWO Feature Flags & ACM",
                "release_stage": "ga_paid",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _hidden(), "beta": _hidden(),
                    "free": _hidden(), "trial": _hidden(),
                    "paid_starter": _hidden(), "paid_pro": _hidden(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "admin_templates",
                "feature_name": "Template & Content Management",
                "release_stage": "ga_paid",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _hidden(), "beta": _hidden(),
                    "free": _hidden(), "trial": _hidden(),
                    "paid_starter": _hidden(), "paid_pro": _hidden(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "admin_audit",
                "feature_name": "Audit Trail & Incident Response",
                "release_stage": "ga_paid",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _hidden(), "beta": _hidden(),
                    "free": _hidden(), "trial": _hidden(),
                    "paid_starter": _hidden(), "paid_pro": _hidden(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },
]
