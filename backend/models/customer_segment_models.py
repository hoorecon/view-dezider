"""
customer_segment_models.py — Customer Segment / Target-Group master.

A Customer Segment captures the NON-TECHNICAL profile of a target group
(demography, psychography, behaviour, firmography) and is then mapped to
one or more of the 7 Chakra subscription tiers with multi-currency
multi-country pricing. This is orthogonal to the tier_matrix (which only
controls feature/module access).
"""
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# ----------------------------------------------------------------------
# Predefined factor templates (admin can add custom factors freely)
# ----------------------------------------------------------------------
PREDEFINED_FACTORS: List[Dict[str, Any]] = [
    # Demography
    {"key": "age_range",        "label": "Age Range",          "category": "demographic", "ai_researchable": True},
    {"key": "gender",           "label": "Gender",             "category": "demographic", "ai_researchable": True},
    {"key": "income_range",     "label": "Income Range",       "category": "demographic", "ai_researchable": True},
    {"key": "education",        "label": "Education Level",    "category": "demographic", "ai_researchable": True},
    {"key": "occupation",       "label": "Occupation",         "category": "demographic", "ai_researchable": True},
    {"key": "location",         "label": "Location / Geo",     "category": "demographic", "ai_researchable": True},
    {"key": "family_status",    "label": "Family Status",      "category": "demographic", "ai_researchable": True},
    {"key": "urban_rural",      "label": "Urban / Rural",      "category": "demographic", "ai_researchable": True},
    # Psychography
    {"key": "values",           "label": "Core Values",        "category": "psychographic", "ai_researchable": True},
    {"key": "interests",        "label": "Interests / Hobbies","category": "psychographic", "ai_researchable": True},
    {"key": "lifestyle",        "label": "Lifestyle",          "category": "psychographic", "ai_researchable": True},
    {"key": "personality",      "label": "Personality Traits", "category": "psychographic", "ai_researchable": True},
    {"key": "attitudes",        "label": "Attitudes / Beliefs","category": "psychographic", "ai_researchable": True},
    {"key": "motivations",      "label": "Motivations",        "category": "psychographic", "ai_researchable": True},
    {"key": "pain_points",      "label": "Pain Points",        "category": "psychographic", "ai_researchable": True},
    # Behavioural
    {"key": "buying_behaviour", "label": "Buying Behaviour",   "category": "behavioural", "ai_researchable": True},
    {"key": "brand_loyalty",    "label": "Brand Loyalty",      "category": "behavioural", "ai_researchable": True},
    {"key": "decision_drivers", "label": "Decision Drivers",   "category": "behavioural", "ai_researchable": True},
    {"key": "tech_savviness",   "label": "Tech Savviness",     "category": "behavioural", "ai_researchable": True},
    # Firmography (B2B)
    {"key": "company_size",     "label": "Company Size",       "category": "firmographic", "ai_researchable": True},
    {"key": "industry",         "label": "Industry",           "category": "firmographic", "ai_researchable": True},
    {"key": "role",             "label": "Role / Title",       "category": "firmographic", "ai_researchable": True},
    {"key": "revenue_band",     "label": "Annual Revenue",     "category": "firmographic", "ai_researchable": True},
]

FACTOR_CATEGORIES = ["demographic", "psychographic", "behavioural", "firmographic", "custom"]


# ----------------------------------------------------------------------
# Pydantic input schemas
# ----------------------------------------------------------------------
class FactorValue(BaseModel):
    key: str
    label: Optional[str] = None
    category: str = "custom"
    value: Optional[str] = ""
    ai_researchable: bool = True
    is_custom: bool = False


class TierPricing(BaseModel):
    tier_key: str  # root | sacral | solar_plexus | heart | throat | third_eye | crown
    country_code: str = "IN"  # ISO 3166-1 alpha-2
    currency: str = "INR"     # ISO 4217
    monthly_price: float = 0.0
    annual_price: float = 0.0
    enabled: bool = True


class CustomerSegmentCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    chakra_tier_link: Optional[str] = None  # primary recommended tier
    factors: List[FactorValue] = Field(default_factory=list)
    market_research_module_ids: List[str] = Field(default_factory=list)
    tier_pricings: List[TierPricing] = Field(default_factory=list)


class CustomerSegmentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    chakra_tier_link: Optional[str] = None
    factors: Optional[List[FactorValue]] = None
    market_research_module_ids: Optional[List[str]] = None
    tier_pricings: Optional[List[TierPricing]] = None


class FactorAddRequest(BaseModel):
    key: str
    label: Optional[str] = None
    category: str = "custom"
    value: Optional[str] = ""


class AIResearchRequest(BaseModel):
    factor_key: str
    extra_context: Optional[str] = ""


class TierPricingUpsert(BaseModel):
    tier_pricings: List[TierPricing]
