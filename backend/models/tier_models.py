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
# Lower number = unlocks earlier (cheaper tier). Module ids MUST match the
# canonical ACM module ids (db.acm_modules.module_id). Modules NOT listed below
# default to DEFAULT_MIN_TIER. Last verified against ACM 2026-06-01.
SMART_SEED_MIN_TIER: Dict[str, int] = {
    # === Tier 1 — Root (Freelancer): basic decision + life-direction core ===
    "my_dezider": 1,                  # 10-step HOS engine
    "aala": 1,                        # Assets & Liabilities ledger
    "journal": 1,                     # Decision Journal
    "assessment": 1,                  # Decision-making self assessment
    "pna": 1,                         # Problems / Needs / Aspirations
    "security": 1,                    # Account security basics
    "subscription": 1,                # Billing / plan management

    # === Tier 2 — Sacral (Solopreneur): + AI assist + goal setting ===
    "ai_assistant": 2,                # AI Solution Assistant (limited)
    "goal_setter": 2,                 # SMART goals
    "decision_kickstarters": 2,       # Kickstarter checklists
    "conflict_breaker": 2,            # Conflict resolution
    "consciousness_diary": 2,         # Consciousness diary
    "emotional_gatekeeper": 2,        # Emotional gatekeeper

    # === Tier 3 — Solar Plexus (Early Founder): + execution + tools ===
    "ctt": 3,                         # Centralised Task Tracker
    "gem": 3,                         # Goal Execution Manager
    "time_intelligence": 3,           # Time Store / Time Dezider / Daily Time Log
    "solutions_store": 3,             # Solutions catalogue
    "solution_tools": 3,              # Solution Matrix etc.
    "google_calendar": 3,             # Calendar sync
    "lifestyle": 3,                   # Lifestyle Dezider basics
    "lifestyle_eval": 3,              # Lifestyle Effectiveness Eval
    "goal_manifestation": 3,          # CAB-FAME manifestation
    "unconditional_happiness": 3,     # Unconditional Happiness tools

    # === Tier 4 — Heart (Growth Founder): + customer/team + advanced ===
    "public_pulse": 4,                # Citizen + Org portals
    "collaboration": 4,               # Multi-user video/decision
    "cld_engine": 4,                  # Causal Loop Diagrams
    "lifestyle_designer": 4,          # Full Lifestyle Designer
    "tepfi": 4,                       # TEPFI Matrix
    "deo": 4,                         # DEO outbound engine

    # === Tier 5 — Throat (Successful Founder): + social + community ===
    "social_learning": 5,             # Social Learning Pipeline

    # === Tier 6 — Third Eye (Unicorn): + admin / multi-tenant ===
    "admin": 6,                       # Admin Panel — orgs unlock multi-admin here

    # === Tier 7 — Crown (Fortune Venture): + internal/test ===
    "test123": 7,                     # Test module — only visible to top tier
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
