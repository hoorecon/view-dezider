"""
core/branding.py — Multi-edition brand resolver.

ONE codebase, MANY brand editions. Selected via `PRODUCT_EDITION` env var
(default "jelcos"). Returns a `BrandConfig` consumed by the `/api/branding/*`
routes and surfaced to the frontend on app boot.

Editions registered today:
  • jelcos       — JELCOS AI (Business Leaders edition) — DEFAULT
  • geodezider   — GeoDezider AI (Govt Departments edition)
  • consumer     — Earth Dezider (future consumer edition)

Whitelabels are NOT separate editions — they sit *under* jelcos or geodezider
with their own primary_color / logo / display_name overrides at the org level
(handled by the existing pp_orgs / org_branding system).

Master roof brand: Earth Dezider (always shown as "by Earth Dezider"
imprint regardless of edition). Legal entity: VEALES Vedic Decisions Pvt Ltd
(never shown in consumer marketing copy).
"""
import os
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Optional


MASTER_BRAND_NAME = "Earth Dezider"
MASTER_BRAND_TAGLINE = "The Decision OS for People."
LEGAL_ENTITY = "VEALES Vedic Decisions Private Limited"


@dataclass
class BrandConfig:
    """The active edition's brand surface — sent to frontend on app boot."""
    edition: str                              # "jelcos" | "geodezider" | "consumer"
    display_name: str                         # "JELCOS AI"
    full_expansion: str                       # "Joyful Executive's Life Choices Operating System powered by Artificial Intelligence"
    tagline: str
    audience_identity: str                    # "The Joyful Executive"
    primary_color: str                        # "#7C3AED"
    secondary_color: str
    logo_uri: Optional[str] = None
    domain: Optional[str] = None
    audience_segments: List[str] = field(default_factory=list)
    enabled_features: List[str] = field(default_factory=list)   # ACM keys this edition unlocks by default
    # Master / parent imprint (always shown as "by ...")
    master_brand: str = MASTER_BRAND_NAME
    master_tagline: str = MASTER_BRAND_TAGLINE
    legal_entity: str = LEGAL_ENTITY

    def as_dict(self) -> Dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Edition registry
# ---------------------------------------------------------------------------
EDITIONS: Dict[str, BrandConfig] = {
    "jelcos": BrandConfig(
        edition="jelcos",
        display_name="JELCOS AI",
        full_expansion="Joyful Executive's Life Choices Operating System powered by Artificial Intelligence",
        tagline="The AI Decision OS for the Joyful Executive's life.",
        audience_identity="The Joyful Executive",
        primary_color="#7C3AED",       # current app default
        secondary_color="#1A237E",
        domain="jelcos.ai",
        audience_segments=[
            "Solopreneurs",
            "Startup Founders",
            "MSME Founders",
            "CXOs",
            "Corporate Managers",
        ],
        enabled_features=[
            "expert_net", "review_net", "solution_matrix",
            "accountability_trilogy", "public_pulse_org_portal",
            "decision_tools", "goal_setter", "conflict_breaker",
            "solutions_store", "ai_assistant", "lifestyle_routines",
        ],
    ),
    "geodezider": BrandConfig(
        edition="geodezider",
        display_name="GeoDezider AI",
        full_expansion="Geographic Decision OS powered by Artificial Intelligence",
        tagline="The AI Decision OS for civic governance.",
        audience_identity="The Public Servant",
        primary_color="#0E7490",       # govt-coded teal
        secondary_color="#134E4A",
        domain="geodezider.ai",
        audience_segments=[
            "Govt Departments",
            "Public Institutions",
            "City / District Officials",
            "Citizens engaging with Govt",
        ],
        enabled_features=[
            "public_pulse_govt_portal", "public_pulse_admin",
            "decision_tools", "solution_matrix",
            "review_net", "ai_assistant",
            # NB: expert_net excluded by default for govt edition
        ],
    ),
    "consumer": BrandConfig(
        edition="consumer",
        display_name="Earth Dezider",
        full_expansion="Earth Dezider — the Decision OS for People",
        tagline="Better life choices, every day.",
        audience_identity="The Conscious Decider",
        primary_color="#059669",
        secondary_color="#065F46",
        domain="earthdezider.com",
        audience_segments=["Every human"],
        enabled_features=[
            "decision_tools", "goal_setter", "conflict_breaker",
            "solutions_store", "lifestyle_routines",
            "review_net", "ai_assistant", "accountability_trilogy",
        ],
    ),
}


# ---------------------------------------------------------------------------
# Resolver
# ---------------------------------------------------------------------------
def get_active_edition() -> str:
    """Reads PRODUCT_EDITION env var. Falls back to 'jelcos'."""
    raw = (os.getenv("PRODUCT_EDITION") or "jelcos").strip().lower()
    return raw if raw in EDITIONS else "jelcos"


def get_brand_config(edition: Optional[str] = None) -> BrandConfig:
    """Return the BrandConfig for the requested edition (or active one)."""
    key = (edition or get_active_edition()).lower()
    return EDITIONS.get(key) or EDITIONS["jelcos"]


def list_editions() -> List[Dict]:
    """For super-admin UI — list all known editions."""
    return [b.as_dict() for b in EDITIONS.values()]


def is_feature_enabled_in_edition(feature_key: str, edition: Optional[str] = None) -> bool:
    """Cheap check (does NOT replace ACM — that's per-user/role gating)."""
    cfg = get_brand_config(edition)
    return feature_key in cfg.enabled_features
