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

# Bump this version whenever ACM_MODULES / USER_TYPES / SUBSCRIPTION_PLANS change.
# Boot-time auto-seed (core/acm_engine.py) reseeds DB iff stored version < this one.
# Format: "YYYY-MM-DD-N" — human-readable, monotonically sortable.
ACM_SEED_VERSION = "2026-06-16-02"  # +swot under decision_kickstarters; non-destructive reseed

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
            # ── Per-OrgType column gating (Accurate mode) ──
            {
                "feature_id": "solution_matrix_orgtype_individual",
                "feature_name": "Matrix — Individual OrgType column",
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
            {
                "feature_id": "solution_matrix_orgtype_org",
                "feature_name": "Matrix — Org OrgType column",
                "release_stage": "ga_paid",
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
            {
                "feature_id": "solution_matrix_orgtype_govt",
                "feature_name": "Matrix — Govt OrgType column",
                "release_stage": "ga_paid",
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
            {
                "feature_id": "solution_matrix_orgtype_nature",
                "feature_name": "Matrix — Nature OrgType column",
                "release_stage": "ga_paid",
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
            {
                "feature_id": "solution_matrix_pdf_export",
                "feature_name": "Matrix — PDF Export",
                "release_stage": "ga_paid",
                "quota_unit": "exports/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(5),
                    "paid_starter": _full(10), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _full(),
                },
            },
            {
                "feature_id": "solution_matrix_templates",
                "feature_name": "Matrix — Starter Templates",
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
        "module_description": "Causal Loop Diagrams — AI-generated systemic analysis with per-decision, per-module, and master CLDs",
        "order": 11,
        "features": [
            {
                "feature_id": "cld_viewer",
                "feature_name": "CLD Viewer & Editor",
                "release_stage": "ga_trial",
                "quota_unit": "diagrams/month",
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
                "feature_id": "cld_module_generate",
                "feature_name": "Module-Specific CLD Generation (PNA, Goal, Lifestyle, etc.)",
                "release_stage": "ga_paid",
                "quota_unit": "generations/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(5),
                    "paid_starter": _full(10), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "cld_master_generate",
                "feature_name": "Master CLD (Cross-Module Aggregation)",
                "release_stage": "ga_paid",
                "quota_unit": "generations/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(2),
                    "paid_starter": _full(5), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "cld_simulation",
                "feature_name": "What-If Simulation & Propagation",
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
            {
                "feature_id": "eg_effective_outlets_advisor",
                "feature_name": "Effective Outlets Advisor (9 Constructive Techniques)",
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
                "feature_id": "eg_emotional_reception",
                "feature_name": "Emotional Reception — 5-min 'Just BE' Guided Practice",
                "release_stage": "ga_trial",
                "quota_unit": "sessions/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(3), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 20b: Conflict Breaker (Crucial Conversations)
    # ────────────────────────────────────────────────────
    {
        "module_id": "conflict_breaker",
        "module_name": "The Conflict Breaker",
        "module_icon": "shield-half",
        "module_description": "9-stage guided preparation for crucial conversations — based on Start with Heart, Learn to Look, Make It Safe principles",
        "order": 30,
        "features": [
            {
                "feature_id": "cb_sessions",
                "feature_name": "Conflict Breaker Sessions",
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
                "feature_id": "cb_9_stage_wizard",
                "feature_name": "9-Stage Conversation Wizard (Crucial Check → Closure)",
                "release_stage": "ga_trial",
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
            {
                "feature_id": "cb_ai_script_rewrite",
                "feature_name": "AI Script Rewriting (Blame → Respectful Dialogue)",
                "release_stage": "ga_paid",
                "quota_unit": "rewrites/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(5),
                    "paid_starter": _full(20), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "cb_dashboard",
                "feature_name": "Conflict Resolution Dashboard & Analytics",
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
    # MODULE 31: AI Solution Assistant
    # ────────────────────────────────────────────────────
    {
        "module_id": "ai_assistant",
        "module_name": "AI Solution Assistant",
        "module_icon": "chatbubbles",
        "module_description": "Personal AI advisor chatbot with 6 languages, Text-to-Speech, and cross-module context awareness",
        "order": 31,
        "features": [
            {
                "feature_id": "ai_assistant_conversations",
                "feature_name": "AI Conversations (Text Chat)",
                "release_stage": "ga_trial",
                "quota_unit": "messages/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(10), "trial": _full(100),
                    "paid_starter": _full(200), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _full(),
                },
            },
            {
                "feature_id": "ai_assistant_quick_ask",
                "feature_name": "Quick Ask (One-Shot Questions)",
                "release_stage": "ga_free",
                "quota_unit": "queries/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(5), "trial": _full(50),
                    "paid_starter": _full(100), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _full(),
                },
            },
            {
                "feature_id": "ai_assistant_tts",
                "feature_name": "Text-to-Speech Voice Output (6 Languages)",
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
                "feature_id": "ai_assistant_cross_module",
                "feature_name": "Cross-Module Context Awareness",
                "release_stage": "ga_paid",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _locked(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _full(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 23: AALA (Accrued Assets & Liabilities Analysis)
    # ────────────────────────────────────────────────────
    {
        "module_id": "aala",
        "module_name": "AALA — Assets & Liabilities Analysis",
        "module_icon": "wallet",
        "module_description": "Circle of Influence assessment: track assets & liabilities across 10 life areas",
        "order": 23,
        "features": [
            {
                "feature_id": "aala_assessment",
                "feature_name": "AALA Baseline Assessment",
                "release_stage": "ga_trial",
                "quota_unit": "assessments/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(1), "trial": _full(),
                    "paid_starter": _full(5), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "aala_tracking",
                "feature_name": "Periodic Snapshot Tracking",
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
                "feature_id": "aala_solution_matrix_sync",
                "feature_name": "Auto-Populate Solution Matrix",
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
    # MODULE 24: LEE (Lifestyle Effectiveness Evaluation)
    # ────────────────────────────────────────────────────
    {
        "module_id": "lifestyle_eval",
        "module_name": "Lifestyle Effectiveness Evaluation",
        "module_icon": "analytics",
        "module_description": "Track actual daily lifestyle vs planned — time allocation across life areas",
        "order": 24,
        "features": [
            {
                "feature_id": "lee_daily_log",
                "feature_name": "Daily Activity Logging",
                "release_stage": "ga_trial",
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
            {
                "feature_id": "lee_planned_vs_actual",
                "feature_name": "Planned vs Actual Comparison",
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
                "feature_id": "lee_summary",
                "feature_name": "Summary & Analytics Dashboard",
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

    # ────────────────────────────────────────────────────
    # MODULE 28: PNA (Problems / Needs / Aspirations)
    # ────────────────────────────────────────────────────
    {
        "module_id": "pna",
        "module_name": "PNA — Problems / Needs / Aspirations",
        "module_icon": "layers",
        "module_description": "Track and manage Problems, Needs, and Aspirations across 10 life areas",
        "order": 28,
        "features": [
            {
                "feature_id": "pna_items",
                "feature_name": "PNA Item Management",
                "release_stage": "ga_trial",
                "quota_unit": "items",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(10), "trial": _full(),
                    "paid_starter": _full(50), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "pna_convert",
                "feature_name": "Convert PNA to Decision/Goal",
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
    # MODULE 29: Lifestyle Designer
    # ────────────────────────────────────────────────────
    {
        "module_id": "lifestyle_designer",
        "module_name": "Lifestyle Designer",
        "module_icon": "color-palette",
        "module_description": "Plan ideal lifestyle allocations and compare planned vs actual",
        "order": 29,
        "features": [
            {
                "feature_id": "ld_plans",
                "feature_name": "Lifestyle Plan Management",
                "release_stage": "ga_trial",
                "quota_unit": "plans",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(1), "trial": _full(),
                    "paid_starter": _full(5), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "ld_comparison",
                "feature_name": "Planned vs Actual Comparison",
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
                "feature_id": "ld_overrides",
                "feature_name": "Manual Override Actuals",
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
    # MODULE 25: Goal Setter (SMART)
    # ────────────────────────────────────────────────────
    {
        "module_id": "goal_setter",
        "module_name": "Goal Setter — SMART Framework",
        "module_icon": "flag",
        "module_description": "Define best possible SMART goals: Specific, Measurable, Achievable, Realistic, Time-bound",
        "order": 25,
        "features": [
            {
                "feature_id": "smart_goals",
                "feature_name": "SMART Goal Creation",
                "release_stage": "ga_trial",
                "quota_unit": "goals/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(3), "trial": _full(),
                    "paid_starter": _full(20), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE 26: Goal Manifestation (CAB-FAME)
    # ────────────────────────────────────────────────────
    {
        "module_id": "goal_manifestation",
        "module_name": "Goal Manifestation — CAB-FAME",
        "module_icon": "sparkles",
        "module_description": "7-stage Wish Fulfillment: Cosmic Consciousness → Awakening → Believing → Feeling → Actions → Manifestation → Effect",
        "order": 26,
        "features": [
            {
                "feature_id": "cabfame_journeys",
                "feature_name": "CAB-FAME Journeys",
                "release_stage": "ga_trial",
                "quota_unit": "journeys/month",
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
                "feature_id": "kalphavriksha_meditation",
                "feature_name": "KalphaVriksha Meditation Audio",
                "release_stage": "ga_trial",
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
    # MODULE 27: Unconditional Happiness
    # ────────────────────────────────────────────────────
    {
        "module_id": "unconditional_happiness",
        "module_name": "Unconditional Happiness",
        "module_icon": "happy",
        "module_description": "Shift from conditional to unconditional happiness through guided reflection and celebration",
        "order": 27,
        "features": [
            {
                "feature_id": "uh_sessions",
                "feature_name": "Happiness Practice Sessions",
                "release_stage": "ga_trial",
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
            {
                "feature_id": "uh_streaks",
                "feature_name": "Happiness Streak Tracking",
                "release_stage": "ga_trial",
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
    # MODULE 32: Public Pulse — Public Decision Intelligence
    # ────────────────────────────────────────────────────
    {
        "module_id": "public_pulse",
        "module_name": "Public Pulse",
        "module_icon": "pulse",
        "module_description": "Consent-based decision intelligence + market research. 3 self-discovery Score™ tools, k-anonymized public dashboards, feedback & rectification flow.",
        "order": 32,
        "features": [
            {
                "feature_id": "pp_self_discovery_tools",
                "feature_name": "Self-Discovery Score™ Tools (3 templates)",
                "release_stage": "beta",
                "quota_unit": "sessions/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": {"enabled": True, "quota": 5},
                    "trial": _full(), "paid_starter": _full(),
                    "paid_pro": _full(), "paid_enterprise": _full(),
                    "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "pp_consent_management",
                "feature_name": "Consent Management (granular, withdrawable)",
                "release_stage": "ga_trial",
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
            {
                "feature_id": "pp_public_dashboards",
                "feature_name": "Public Insights Dashboards (k-anonymized)",
                "release_stage": "beta",
                "quota_unit": "views",
                "quota_resets": "daily",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "pp_feedback_rectification",
                "feature_name": "Feedback & Rectification Flow",
                "release_stage": "beta",
                "quota_unit": "submissions/month",
                "quota_resets": "monthly",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": {"enabled": True, "quota": 3},
                    "trial": _full(), "paid_starter": _full(),
                    "paid_pro": _full(), "paid_enterprise": _full(),
                    "paid_api": _hidden(),
                },
            },
            {
                "feature_id": "pp_org_portal",
                "feature_name": "Org / Gov Portal — Registration, Dashboard, Rectification Workflow",
                "release_stage": "beta",
                "quota_unit": "toggle",
                "quota_resets": "none",
                "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": {"enabled": True, "quota": 0},
                    "trial": _full(), "paid_starter": _full(),
                    "paid_pro": _full(), "paid_enterprise": _full(),
                    "paid_api": _hidden(),
                },
            },
        ],
    },

    # ────────────────────────────────────────────────────
    # MODULE: Dashboard Tiles — controls visibility of each
    # tile on the Home / Dashboard screen (the "direct entry"
    # point only). Wiring off a tile here HIDES it from Home
    # but does NOT block the same module from being reached
    # via inter-module navigation (e.g. Goal Setter can still
    # be opened from GEM even if dash_goal_setter is locked).
    # Each feature is a single-tile toggle. Default = full
    # (all tiles ON); admin can lock individual tiles in
    # /admin/acm without touching the underlying module
    # features.
    # ────────────────────────────────────────────────────
    {
        "module_id": "dashboard_tiles",
        "module_name": "Dashboard Tiles (Home Screen)",
        "module_icon": "grid",
        "module_description": "Per-tile visibility toggles for the Home dashboard. Tiles are grouped under their parent SECTION; setting the section to Hidden cascades to all child tiles (unless a tile already has a per-audience override). Setting any tile to Full/Read while the section is Hidden auto-flips the section back to Full for that audience.",
        "order": 99,
        "features": (
            # ── 9 SECTION FEATURES (parents) ────────────────────────────────
            [
                {"feature_id": f"dash_section_{sid}", "feature_name": f"§{order} · {sname}",
                 "release_stage": "ga_free", "quota_unit": "section_toggle", "quota_resets": "none",
                 "is_section": True, "section_order": order,
                 "access": {k: _full() for k in [
                    "unit_tester", "integration_tester", "alpha", "beta",
                    "free", "trial", "paid_starter", "paid_pro",
                    "paid_enterprise", "paid_api",
                 ]}}
                for order, sid, sname in [
                    (1, "self_discovery",          "Self Discovery"),
                    (2, "decision_kickstarters",   "Decision Kickstarters"),
                    (3, "inner_wellbeing",         "Inner Wellbeing"),
                    (4, "goals_manifestation",     "Goals & Manifestation"),
                    (5, "execute_track",           "Execute & Track"),
                    (6, "reflection_awareness",    "Reflection & Awareness"),
                    (7, "collaboration_mgmt",      "Collaboration & Management"),
                    (8, "solution_space",          "Solution Space"),
                    (9, "more_tools",              "More Tools"),
                ]
            ]
            +
            # ── INDIVIDUAL TILES (children) ─────────────────────────────────
            [
                {"feature_id": f"dash_{tile_id}", "feature_name": f"Dashboard tile · {tile_label}",
                 "release_stage": "ga_free", "quota_unit": "toggle", "quota_resets": "none",
                 "parent_feature_id": f"dash_section_{parent_section}",
                 "access": {
                    "unit_tester": _full(), "integration_tester": _full(),
                    "alpha": _full(), "beta": _full(),
                    "free": _full(), "trial": _full(),
                    "paid_starter": _full(), "paid_pro": _full(),
                    "paid_enterprise": _full(), "paid_api": _full(),
                 }}
                for tile_id, tile_label, parent_section in [
                    # §1 Self Discovery
                    ("pna",                   "My 360° Life",                   "self_discovery"),
                    ("gem",                   "GEM",                            "self_discovery"),
                    # §2 Decision Kickstarters
                    ("my_dezider",            "My Dezider",                     "decision_kickstarters"),
                    ("instant_dezider",       "Instant Dezider (Test123)",      "decision_kickstarters"),
                    ("pros_cons",             "Pros & Cons",                    "decision_kickstarters"),
                    ("swot",                  "SWOT Analysis",                  "decision_kickstarters"),
                    ("solution_finder",       "Solution Finder",                "decision_kickstarters"),
                    # §3 Inner Wellbeing
                    ("emotional_gatekeeper",  "Emotional Gatekeeper",           "inner_wellbeing"),
                    ("conflict_breaker",      "Conflict Breaker",               "inner_wellbeing"),
                    # §4 Goals & Manifestation
                    ("goal_setter",           "Goal Setter",                    "goals_manifestation"),
                    ("goal_manifestation",    "Manifestation",                  "goals_manifestation"),
                    # §5 Execute & Track
                    ("action_tracker",        "Action Tracker",                 "execute_track"),
                    ("ctt",                   "Centralized Task Tracker (CTT)", "execute_track"),
                    ("lifestyle_dezider",     "Lifestyle Dezider",              "execute_track"),
                    # §6 Reflection & Awareness
                    ("public_pulse",          "Life Mirror (Public Pulse)",     "reflection_awareness"),
                    ("outlet_analyzer",       "Outlet Analyzer",                "reflection_awareness"),
                    ("aim_manager",           "AIM Manager",                    "reflection_awareness"),
                    ("capabilities_index",    "Capabilities & Resources Index", "reflection_awareness"),
                    ("lifestyle_designer",    "Lifestyle Designer",             "reflection_awareness"),
                    ("lifestyle_analyzer",    "Lifestyle Analyzer",             "reflection_awareness"),
                    ("consciousness_diary",   "Consciousness Diary",            "reflection_awareness"),
                    ("unconditional_happiness", "Unconditional Happiness",      "reflection_awareness"),
                    # §7 Collaboration & Management
                    ("collaboration_hub",     "Collaboration Hub",              "collaboration_mgmt"),
                    ("aala",                  "AALA",                           "collaboration_mgmt"),
                    ("time_dezider",          "Time Intelligence",              "collaboration_mgmt"),
                    ("gem_flight",            "GEM Flight Model",               "collaboration_mgmt"),
                    # §8 Solution Space
                    ("solution_store",        "Solution Store",                 "solution_space"),
                    ("review_net",            "Review Net",                     "solution_space"),
                    ("deo",                   "DEO",                            "solution_space"),
                    ("time_store",            "Time Store",                     "solution_space"),
                    # §9 More Tools
                    ("ai_assistant",          "AI Assistant",                   "more_tools"),
                    ("social_learning",       "Social Learning",                "more_tools"),
                    ("swot",                  "SWOT Analysis",                  "more_tools"),
                    ("contacts",              "Contacts",                       "more_tools"),
                    ("calendar",              "Calendar",                       "more_tools"),
                    ("subscription",          "Subscription",                   "more_tools"),
                    ("cld_engine",            "CLD Engine",                     "more_tools"),
                ]
            ]
        ),
    },
]
