"""7x7 Organization Standard Structure Seed.

7 Divisions (Chakras of Organization) — each scored against 7 Drivers
grouped under 3 categories: Team / Systems / Strategy.

Reference: 'Advanced DoD Venture Dashboard - The 7/7 Matrix !' v3.25.
"""
from typing import List, Dict, Any

# ─────────────────────────────────────────────────────────
# 7 DIVISIONS (top-level chakras of an organization)
# ─────────────────────────────────────────────────────────
SEVEN_DIVISIONS: List[Dict[str, Any]] = [
    {
        "code": "solution_delivery", "order": 1,
        "name": "Solution Delivery Division",
        "department": "Production Department",
        "icon": "hammer",
        "color": "#DC2626",  # red — root chakra
        "sub_teams": [
            {"code": "sd_software",  "order": 1, "name": "Software Delivery Team", "children": [
                {"code": "sd_sw_core",   "order": 1, "name": "Core Solution Delivery Team"},
                {"code": "sd_sw_server", "order": 2, "name": "Server Administration Team"},
            ]},
            {"code": "sd_noncore",   "order": 2, "name": "Non-Core Solution Delivery Teams", "children": [
                {"code": "sd_nc_catalog", "order": 1, "name": "Central Catalog Management Team"},
                {"code": "sd_nc_master",  "order": 2, "name": "Master Solutions Management Team"},
                {"code": "sd_nc_ext",     "order": 3, "name": "External Operations Team"},
            ]},
        ],
    },
    {
        "code": "market_leadership", "order": 2,
        "name": "Market Leadership Division",
        "department": "R&D Department",
        "icon": "telescope",
        "color": "#EA580C",  # orange — sacral
        "sub_teams": [
            {"code": "ml_product",  "order": 1, "name": "Product Management"},
            {"code": "ml_research", "order": 2, "name": "Market Research"},
            {"code": "ml_chess",    "order": 3, "name": "CHESS - Customer & Sales Strategy"},
        ],
    },
    {
        "code": "profit_max", "order": 3,
        "name": "Profit Maximization Division",
        "department": "Sales / Marketing / PR",
        "icon": "trending-up",
        "color": "#CA8A04",  # yellow — solar plexus
        "sub_teams": [
            {"code": "pm_branding", "order": 1, "name": "PR & Branding"},
            {"code": "pm_marketing", "order": 2, "name": "Marketing"},
            {"code": "pm_sales",    "order": 3, "name": "Sales"},
            {"code": "pm_delivery", "order": 4, "name": "Service Delivery"},
        ],
    },
    {
        "code": "cost_ops", "order": 4,
        "name": "Cost Effective Operations Division",
        "department": "HR / Finance / Admin / Legal / Social",
        "icon": "wallet",
        "color": "#16A34A",  # green — heart
        "sub_teams": [
            {"code": "co_hr",      "order": 1, "name": "HR — Recruitment / People Dev / Work Culture"},
            {"code": "co_finance", "order": 2, "name": "Finance — Bill Payments / Compliance"},
            {"code": "co_admin",   "order": 3, "name": "Admin — Facilities / Infra"},
            {"code": "co_legal",   "order": 4, "name": "Legal — Company Law / IP"},
            {"code": "co_social",  "order": 5, "name": "Social — Policies / Contribution"},
        ],
    },
    {
        "code": "cashflows", "order": 5,
        "name": "Consistent CashFlows & Profitability Division",
        "department": "Finance Strategy",
        "icon": "cash",
        "color": "#0EA5E9",  # blue — throat
        "sub_teams": [
            {"code": "cf_profitability", "order": 1, "name": "Profitability Management"},
            {"code": "cf_cashflow",     "order": 2, "name": "CashFlow Management", "children": [
                {"code": "cf_reserves", "order": 1, "name": "Required Cash Reserves"},
                {"code": "cf_external", "order": 2, "name": "External Funding"},
                {"code": "cf_inhouse",  "order": 3, "name": "In-House Investments"},
            ]},
        ],
    },
    {
        "code": "governance", "order": 6,
        "name": "Corporate Governance Division",
        "department": "Board",
        "icon": "shield-checkmark",
        "color": "#6366F1",  # indigo — third eye
        "sub_teams": [
            {"code": "gv_bod",   "order": 1, "name": "BoD — Board of Directors"},
            {"code": "gv_boss",  "order": 2, "name": "BOSS — Board of Successful Strategies"},
            {"code": "gv_smo",   "order": 3, "name": "CSO — Strategic Management Office"},
            {"code": "gv_pmo",   "order": 4, "name": "CSO — Program Management Office"},
            {"code": "gv_vmo",   "order": 5, "name": "CSO — Vendor Management Office"},
            {"code": "gv_boc",   "order": 6, "name": "BoC — Board of Consultants"},
            {"code": "gv_boa",   "order": 7, "name": "BoA — Board of Advisors"},
        ],
    },
    {
        "code": "cga", "order": 7,
        "name": "Chief Growth Accelerator (CGA) Division",
        "department": "Chairman / Chairperson",
        "icon": "rocket",
        "color": "#8B5CF6",  # violet — crown
        "sub_teams": [
            {"code": "cga_self",    "order": 1, "name": "Self-Awareness"},
            {"code": "cga_health",  "order": 2, "name": "Health"},
            {"code": "cga_energy",  "order": 3, "name": "Energy"},
            {"code": "cga_state",   "order": 4, "name": "Joyful, Loving & Powerful State of Being"},
        ],
    },
]

# ─────────────────────────────────────────────────────────
# 7 DRIVERS grouped under 3 categories
# ─────────────────────────────────────────────────────────
SEVEN_DRIVERS: List[Dict[str, Any]] = [
    # A. TEAM
    {"code": "capability",     "order": 1, "category": "team",     "name": "Capability",     "hint": "Skill, knowledge, talent depth of the team"},
    {"code": "commitment",     "order": 2, "category": "team",     "name": "Commitment",     "hint": "Engagement, ownership, accountability levels"},
    {"code": "quantity",       "order": 3, "category": "team",     "name": "Quantity",       "hint": "Headcount adequacy for the scope"},
    # B. SYSTEMS
    {"code": "simple",         "order": 4, "category": "systems",  "name": "Simple",         "hint": "Processes are easy to follow"},
    {"code": "scalable",       "order": 5, "category": "systems",  "name": "Scalable",       "hint": "Systems scale with growth"},
    # C. STRATEGY
    {"code": "profitable",     "order": 6, "category": "strategy", "name": "Profitable",     "hint": "Strategy yields healthy ROI"},
    {"code": "irresistible",   "order": 7, "category": "strategy", "name": "Irresistible",   "hint": "Compelling to all stakeholders"},
]

SCORING_SCALE: List[Dict[str, Any]] = [
    {"code": "up_to_mark", "order": 3, "name": "Up-to-the-mark", "color": "#10B981"},
    {"code": "moderate",   "order": 2, "name": "Moderate",       "color": "#F59E0B"},
    {"code": "inadequate", "order": 1, "name": "Inadequate",     "color": "#EF4444"},
]
