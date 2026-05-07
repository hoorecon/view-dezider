"""
tier_models.py — 7-chakra subscription-tier matrix.

Layered on top of the existing ACM (32 modules, 89 features). ACM controls
fine-grained quota + access level per user_type / subscription_plan.
This chakra-tier matrix is the MARKETING-tier feature gate that maps each
ACM module + feature to one of 7 aspirational customer segments.

Tiers (chakra-named, ordered):
  1. Root (Muladhara)       — Freelancer
  2. Sacral (Svadhisthana)  — Solopreneur
  3. Solar Plexus (Manipura)— Early Stage Startup Founder
  4. Heart (Anahata)        — Growth Stage Startup Founder
  5. Throat (Vishuddha)     — Successful Startup Founder
  6. Third Eye (Ajna)       — Unicorn Venture
  7. Crown (Sahasrara)      — Fortune Venture

Toggle rules (per founder lock 2026-05-07):
  • Module=Y at tier T → cascades up to T+1..7; child features default to Y.
  • Module=N at tier T → all features forced N at T (module dominates).
  • Feature toggle requires parent module=Y at same tier.
  • Toggle ON cascades up; toggle OFF does not (preserves overrides).
"""
from typing import Dict, List, Any, Optional
from pydantic import BaseModel


CHAKRA_TIERS: List[Dict[str, Any]] = [
    {"key": "root",         "order": 1, "chakra_sanskrit": "Muladhara",     "label": "Root",         "aspiration": "Freelancer",                   "color": "#EF4444", "icon": "flame",        "monthly_price_inr": 0},
    {"key": "sacral",       "order": 2, "chakra_sanskrit": "Svadhisthana",  "label": "Sacral",       "aspiration": "Solopreneur",                  "color": "#F97316", "icon": "water",        "monthly_price_inr": 499},
    {"key": "solar_plexus", "order": 3, "chakra_sanskrit": "Manipura",      "label": "Solar Plexus", "aspiration": "Early Stage Startup Founder",  "color": "#EAB308", "icon": "sunny",        "monthly_price_inr": 1499},
    {"key": "heart",        "order": 4, "chakra_sanskrit": "Anahata",       "label": "Heart",        "aspiration": "Growth Stage Startup Founder", "color": "#10B981", "icon": "heart",        "monthly_price_inr": 2999},
    {"key": "throat",       "order": 5, "chakra_sanskrit": "Vishuddha",     "label": "Throat",       "aspiration": "Successful Startup Founder",   "color": "#3B82F6", "icon": "megaphone",    "monthly_price_inr": 5999},
    {"key": "third_eye",    "order": 6, "chakra_sanskrit": "Ajna",          "label": "Third Eye",    "aspiration": "Unicorn Venture",              "color": "#6366F1", "icon": "eye",          "monthly_price_inr": 14999},
    {"key": "crown",        "order": 7, "chakra_sanskrit": "Sahasrara",     "label": "Crown",        "aspiration": "Fortune Venture",              "color": "#A855F7", "icon": "diamond",      "monthly_price_inr": 49999},
]

TIER_KEYS = [t["key"] for t in CHAKRA_TIERS]


# Smart-seed mapping per module_id → minimum tier (inclusive) where it unlocks.
# Lower number = unlocks earlier (cheaper tier). Modules not listed default to
# tier 4 (Heart) so admin can pull them earlier or later as needed.
SMART_SEED_MIN_TIER: Dict[str, int] = {
    # === Tier 1 — Root (Freelancer): basic decision + life-direction core ===
    "my_dezider": 1,                  # 10-step HOS engine
    "ldc": 1,                         # Life Directions Compass (north star)
    "aala": 1,                        # Resource ledger (basics)
    "daily_tracker": 1,               # Daily log (text only)
    "lifestyle_routines": 1,          # Recurring habits
    "accountability_trilogy": 1,      # Time Store / Time Dezider / Daily Time Log
    "decision_journal": 1,            # Personal journal

    # === Tier 2 — Sacral (Solopreneur): + AI assist + goal setting ===
    "ai_assistant": 2,                # Limited AI chat
    "goal_setter": 2,                 # PNA goals
    "conflict_breaker": 2,
    "voice_browsing": 2,              # Voice input on PRR

    # === Tier 3 — Solar Plexus (Early Founder): + execution layer ===
    "ctt_gem": 3,                     # CTT tasks / GEM project mgmt
    "time_dezider": 3,                # Full Time Dezider features
    "solutions_store": 3,             # Browse Solution catalog
    "lee": 3,                         # Life Eval Engine
    "calendar_sync": 3,               # Google Calendar integration
    "review_net": 3,                  # Public reviews submit

    # === Tier 4 — Heart (Growth Stage Founder): + customer/team feedback ===
    "public_pulse": 4,                # Phase 1+2 (citizen + org portals)
    "solution_matrix": 4,             # 84-cell problem matrix
    "shared_steps": 4,                # Collaborative steps
    "collaboration": 4,               # Multi-user video/decision
    "central_catalog_management": 4,  # CCM browse

    # === Tier 5 — Throat (Successful Founder): + expert + advanced AI ===
    "expert_net": 5,                  # Discover/book experts + recommendations
    "cld": 5,                         # Causal Loop Diagrams
    "ai_chat_advanced": 5,            # Unlimited AI chat
    "admin_docs": 5,                  # Doc library
    "voice_global": 5,                # Voice across all modules

    # === Tier 6 — Third Eye (Unicorn): + host/broadcast + multi-org ===
    "expert_net_host": 6,             # Host webinars
    "public_pulse_admin": 6,          # Phase 3 admin features
    "org_surveys": 6,                 # Host org-scoped surveys
    "multi_org": 6,                   # Manage multiple orgs
    "api_access": 6,                  # DEO outbound API

    # === Tier 7 — Crown (Fortune Venture): + whitelabel + govt + unlimited ===
    "whitelabel": 7,                  # Per-org branded sub-portals
    "govt_portal": 7,                 # GeoDezider govt access
    "priority_support": 7,            # Dedicated CSM
    "tier_matrix_admin": 7,           # Manage own org's tier matrix
}

# Default tier for any module NOT in SMART_SEED_MIN_TIER (4 = Heart).
DEFAULT_MIN_TIER = 4


class TierMatrixCellSet(BaseModel):
    """Admin sets one cell."""
    module_id: str
    feature_id: Optional[str] = None         # None = module-level cell
    tier_key: str
    allowed: bool


class TierMatrixBulkSet(BaseModel):
    """Bulk save many cells in one round-trip."""
    cells: List[TierMatrixCellSet]


class UserTierAssign(BaseModel):
    user_id: str
    tier_key: str
