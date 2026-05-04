"""Pydantic models + static tool definitions for /routes/public_pulse.py.

The 3 self-discovery tools (Life Direction, Marriage Readiness, Govt Benefit
Finder) live here as declarative configs. Adding a 4th tool = adding a new
TOOL_DEFINITIONS entry, no route changes needed.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ────────────────────────────────────────────
# Consent
# ────────────────────────────────────────────

CONSENT_PURPOSES = [
    {
        "code": "personal_recommendations",
        "label": "Use my data for personal recommendations",
        "description": "Help me get better insights tailored to my situation.",
        "default": True,
    },
    {
        "code": "aggregate_research",
        "label": "Include my anonymized responses in public research",
        "description": "Help governments and orgs understand needs of people like me.",
        "default": True,
    },
    {
        "code": "verified_org_insights",
        "label": "Allow verified organizations to view anonymized group insights",
        "description": "NGOs, MSMEs, associations can see aggregated patterns (no individual data).",
        "default": False,
    },
    {
        "code": "follow_up_contact",
        "label": "Allow follow-up contact for support and services",
        "description": "Eligible for schemes / services? We'll let you know.",
        "default": False,
    },
]

CONSENT_VERSION = "v1.0-2026-05"


class ConsentSubmit(BaseModel):
    purposes: Dict[str, bool]  # code -> allowed
    data_categories_allowed: List[str] = []  # e.g., ["demographics", "tool_answers"]


class ConsentRecord(BaseModel):
    consent_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    consent_version: str = CONSENT_VERSION
    purposes: Dict[str, bool]
    data_categories_allowed: List[str] = []
    withdrawn: bool = False
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ────────────────────────────────────────────
# Demographic Profile
# ────────────────────────────────────────────

AGE_GROUPS = ["18-24", "25-34", "35-44", "45-60", "60+"]

PROFESSIONS = [
    "student", "salaried", "self_employed", "entrepreneur",
    "homemaker", "farmer", "freelancer", "unemployed", "retired", "other",
]

EDUCATION_LEVELS = [
    "below_10th", "10th_pass", "12th_pass", "diploma",
    "graduate", "post_graduate", "doctorate", "other",
]

INCOME_BRACKETS = [
    "below_2.5L", "2.5L-5L", "5L-10L", "10L-25L", "25L-50L", "above_50L", "prefer_not_to_say",
]


class DemographicProfile(BaseModel):
    profile_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    state: Optional[str] = None
    district: Optional[str] = None
    constituency: Optional[str] = None
    taluk: Optional[str] = None
    pincode: Optional[str] = None
    age_group: Optional[str] = None
    gender: Optional[str] = None  # "male" | "female" | "other" | "prefer_not_to_say"
    profession: Optional[str] = None
    income_bracket: Optional[str] = None  # consent-gated
    education: Optional[str] = None
    business_type: Optional[str] = None
    association_membership: Optional[str] = None
    # Sensitive — only captured if user explicitly opts in mid-tool
    religion: Optional[str] = None  # consent-gated, high-risk
    community: Optional[str] = None  # consent-gated, high-risk (caste-equivalent)
    org_brand_id: Optional[str] = None  # for white-label portals (Phase 2)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DemographicProfileUpdate(BaseModel):
    state: Optional[str] = None
    district: Optional[str] = None
    constituency: Optional[str] = None
    taluk: Optional[str] = None
    pincode: Optional[str] = None
    age_group: Optional[str] = None
    gender: Optional[str] = None
    profession: Optional[str] = None
    income_bracket: Optional[str] = None
    education: Optional[str] = None
    business_type: Optional[str] = None
    association_membership: Optional[str] = None
    religion: Optional[str] = None
    community: Optional[str] = None


# ────────────────────────────────────────────
# Self-Discovery Tool Sessions
# ────────────────────────────────────────────

class ToolStartRequest(BaseModel):
    org_brand_id: Optional[str] = None


class ToolAnswerRequest(BaseModel):
    step: int
    answers: Dict[str, Any]


class ToolSession(BaseModel):
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    tool_slug: str  # life_direction | marriage_readiness | govt_benefit_finder
    current_step: int = 1
    completed_steps: List[int] = []
    answers: Dict[str, Any] = {}
    score: Optional[int] = None  # 0-100
    score_band: Optional[str] = None  # "high" | "medium" | "low"
    insight: Optional[str] = None
    recommendations: List[Dict[str, Any]] = []
    hidden_value_hook: Optional[str] = None
    contributed_to_research: bool = False
    completed: bool = False
    org_brand_id: Optional[str] = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


# ────────────────────────────────────────────
# Feedback / Rectification
# ────────────────────────────────────────────

FEEDBACK_TYPES = ["service", "scheme", "local_problem", "department_experience", "policy_suggestion"]
FEEDBACK_STATES = ["new", "acknowledged", "responded", "action_pending", "action_taken", "resolution_review", "closed", "reopened"]


class FeedbackSubmit(BaseModel):
    feedback_text: str
    feedback_type: str
    related_entity: Optional[str] = None  # department / scheme / org name
    district: Optional[str] = None
    severity: int = 3  # 1-5 self-reported


class FeedbackItem(BaseModel):
    feedback_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    feedback_text: str
    feedback_type: str
    related_entity: Optional[str] = None
    district: Optional[str] = None
    severity: int = 3
    status: str = "new"
    response_text: Optional[str] = None
    response_org_id: Optional[str] = None
    action_taken_description: Optional[str] = None
    action_taken_date: Optional[datetime] = None
    citizen_satisfaction_score: Optional[int] = None  # 0-100, post-action
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ────────────────────────────────────────────
# Admin K-Anonymity Config
# ────────────────────────────────────────────

DEFAULT_K_THRESHOLDS = {
    "district_demand_heatmap": 30,
    "youth_job_priority": 30,
    "marriage_support_need": 30,
    "scheme_awareness": 30,
    "rectification_tracker": 10,  # lower because each issue is itself the unit
    "teaser": 20,                 # in-flow teasers can be looser
}


class KAnonymityUpdate(BaseModel):
    dashboard_key: str
    threshold: int


# ────────────────────────────────────────────
# 3 Self-Discovery Tool Definitions
# ────────────────────────────────────────────
# Each tool has:
#   - meta (slug, title, hook, hero_score_label)
#   - steps[] (each with questions[])
#   - scoring rules
#   - insight templates (keyed by score band)
#   - recommendation generators (function in routes file)
#
# Frontend reads /api/public-pulse/tools/{slug} to render the multi-step flow.

TOOL_DEFINITIONS = {
    "life_direction": {
        "slug": "life_direction",
        "title": "My Life Direction Score™",
        "tagline": "Career • Income • Stability • Growth",
        "hook": "Feeling stuck or unsure about your next move? Get your Life Direction Score in 60 seconds.",
        "hero_score_label": "Life Direction Score",
        "icon": "compass",
        "color": "#6366F1",
        "estimated_seconds": 60,
        "steps": [
            {
                "step": 1,
                "title": "Quick start",
                "subtitle": "Just to localise your insight",
                "questions": [
                    {"id": "age_group", "type": "single_select", "label": "Your age group",
                     "options": AGE_GROUPS, "required": True, "stores_in_profile": True},
                    {"id": "district", "type": "text", "label": "District / City",
                     "required": True, "stores_in_profile": True},
                ],
                "show_teaser": True,
                "teaser_dimension": "career_choice",
            },
            {
                "step": 2,
                "title": "Your current state",
                "subtitle": "Where you are right now",
                "questions": [
                    {"id": "current_status", "type": "single_select",
                     "label": "Your current status",
                     "options": ["studying", "working", "running_a_business", "searching"],
                     "required": True},
                    {"id": "satisfaction", "type": "slider",
                     "label": "How satisfied are you?", "min": 1, "max": 5, "default": 3,
                     "required": True},
                    {"id": "monthly_income_range", "type": "single_select",
                     "label": "Monthly income range (optional, helps with insights)",
                     "options": INCOME_BRACKETS, "required": False,
                     "soft_phrasing": "Helps match opportunities — your number stays anonymous."},
                ],
                "show_partial_result": True,
                "partial_result_logic": "transition_zone",
            },
            {
                "step": 3,
                "title": "Direction clarity",
                "subtitle": "Where you want to go",
                "questions": [
                    {"id": "want", "type": "single_select",
                     "label": "What do you WANT?",
                     "options": ["stable_job", "high_income", "freedom", "abroad", "government_job", "own_business"],
                     "required": True},
                    {"id": "biggest_blocker", "type": "single_select",
                     "label": "Biggest blocker",
                     "options": ["skills", "money", "fear", "family", "clarity", "network"],
                     "required": True},
                ],
            },
            {
                "step": 4,
                "title": "Precision layer",
                "subtitle": "Optional — but unlocks deeper matches",
                "questions": [
                    {"id": "profession", "type": "single_select",
                     "label": "Profession / field",
                     "options": PROFESSIONS, "required": False, "stores_in_profile": True},
                    {"id": "education", "type": "single_select",
                     "label": "Education level", "options": EDUCATION_LEVELS,
                     "required": False, "stores_in_profile": True,
                     "soft_phrasing": "Helps match scholarships, training, schemes."},
                    {"id": "income_refinement", "type": "single_select",
                     "label": "Income refinement (optional)",
                     "options": INCOME_BRACKETS, "required": False, "stores_in_profile": True},
                ],
                "is_final": True,
            },
        ],
    },

    "marriage_readiness": {
        "slug": "marriage_readiness",
        "title": "Marriage Readiness & Support Score™",
        "tagline": "Emotional • Financial • Practical readiness",
        "hook": "Are you truly ready for marriage — emotionally, financially, and practically? Get your Marriage Readiness Score + Support Eligibility.",
        "hero_score_label": "Marriage Readiness Score",
        "icon": "heart",
        "color": "#EC4899",
        "estimated_seconds": 75,
        "steps": [
            {
                "step": 1,
                "title": "Entry",
                "subtitle": "Just to localise your insight",
                "questions": [
                    {"id": "age_group", "type": "single_select", "label": "Your age range",
                     "options": AGE_GROUPS, "required": True, "stores_in_profile": True},
                    {"id": "gender", "type": "single_select", "label": "Gender (optional)",
                     "options": ["male", "female", "other", "prefer_not_to_say"],
                     "required": False, "stores_in_profile": True},
                    {"id": "district", "type": "text", "label": "District",
                     "required": True, "stores_in_profile": True},
                ],
                "show_teaser": True,
                "teaser_dimension": "marriage_finance_unprep",
            },
            {
                "step": 2,
                "title": "Readiness inputs",
                "questions": [
                    {"id": "current_status", "type": "single_select",
                     "label": "Current status",
                     "options": ["searching", "not_ready", "family_pressure", "engaged", "evaluating"],
                     "required": True},
                    {"id": "financial_readiness", "type": "single_select",
                     "label": "Financial readiness",
                     "options": ["ready", "partially", "not_ready"], "required": True},
                    {"id": "emotional_readiness", "type": "single_select",
                     "label": "Emotional readiness",
                     "options": ["confident", "confused", "not_ready"], "required": True},
                ],
            },
            {
                "step": 3,
                "title": "Practical constraints",
                "questions": [
                    {"id": "biggest_concern", "type": "single_select",
                     "label": "Biggest concern",
                     "options": ["money", "right_partner", "family", "career", "compatibility"],
                     "required": True},
                    {"id": "timeline", "type": "single_select",
                     "label": "Timeline expectation",
                     "options": ["within_6m", "within_1y", "1_to_3y", "after_3y", "not_sure"],
                     "required": True},
                ],
            },
            {
                "step": 4,
                "title": "Support layer",
                "subtitle": "Would the right help change things?",
                "questions": [
                    {"id": "wants_financial_support", "type": "boolean",
                     "label": "Would financial support help?", "required": True},
                    {"id": "wants_guidance", "type": "boolean",
                     "label": "Would guidance / counselling help?", "required": True},
                    {"id": "wants_matchmaking", "type": "boolean",
                     "label": "Would matchmaking help?", "required": True},
                ],
            },
            {
                "step": 5,
                "title": "Optional precision",
                "subtitle": "Skip any field. Helps match support programs better.",
                "questions": [
                    {"id": "income_bracket", "type": "single_select",
                     "label": "Income range (optional)", "options": INCOME_BRACKETS,
                     "required": False, "stores_in_profile": True},
                    {"id": "education", "type": "single_select",
                     "label": "Education", "options": EDUCATION_LEVELS,
                     "required": False, "stores_in_profile": True},
                    {"id": "community", "type": "text",
                     "label": "Community (optional, clearly marked)",
                     "required": False, "stores_in_profile": True,
                     "sensitive": True,
                     "soft_phrasing": "Some support programs are community-specific. Always optional."},
                ],
                "is_final": True,
            },
        ],
    },

    "govt_benefit_finder": {
        "slug": "govt_benefit_finder",
        "title": "My Government Benefit & Support Finder™",
        "tagline": "Schemes • Eligibility • Civic Support",
        "hook": "Most people miss benefits they are eligible for. Check what YOU can actually get in under 60 seconds.",
        "hero_score_label": "Eligibility Match Count",
        "icon": "ribbon",
        "color": "#10B981",
        "estimated_seconds": 60,
        "steps": [
            {
                "step": 1,
                "title": "Start",
                "questions": [
                    {"id": "district", "type": "text", "label": "District",
                     "required": True, "stores_in_profile": True},
                    {"id": "age_group", "type": "single_select", "label": "Age group",
                     "options": AGE_GROUPS, "required": True, "stores_in_profile": True},
                ],
                "show_teaser": True,
                "teaser_dimension": "missing_benefits",
            },
            {
                "step": 2,
                "title": "Life category",
                "questions": [
                    {"id": "life_category", "type": "single_select",
                     "label": "Which fits you best?",
                     "options": ["student", "job_seeker", "married", "business_owner", "farmer", "homemaker", "senior_citizen"],
                     "required": True},
                ],
            },
            {
                "step": 3,
                "title": "Need-based inputs",
                "questions": [
                    {"id": "biggest_need", "type": "single_select",
                     "label": "What do you need most?",
                     "options": ["job", "money_support", "education", "marriage", "business", "healthcare", "housing"],
                     "required": True},
                    {"id": "difficulty", "type": "slider",
                     "label": "Current difficulty level", "min": 1, "max": 5, "default": 3,
                     "required": True},
                ],
            },
            {
                "step": 4,
                "title": "Eligibility refinement",
                "questions": [
                    {"id": "income_bracket", "type": "single_select",
                     "label": "Income bracket (optional)",
                     "options": INCOME_BRACKETS, "required": False, "stores_in_profile": True},
                    {"id": "education", "type": "single_select",
                     "label": "Education", "options": EDUCATION_LEVELS,
                     "required": False, "stores_in_profile": True},
                    {"id": "employment_type", "type": "single_select",
                     "label": "Employment type",
                     "options": ["salaried", "self_employed", "unemployed", "informal", "student", "retired"],
                     "required": False, "stores_in_profile": True},
                ],
            },
            {
                "step": 5,
                "title": "Optional deeper layer",
                "subtitle": "Answer a few more for exact matches",
                "questions": [
                    {"id": "has_disability", "type": "boolean",
                     "label": "Person with disability?", "required": False,
                     "soft_phrasing": "Some schemes have priority access."},
                    {"id": "family_size", "type": "number", "label": "Family size", "required": False},
                    {"id": "land_owner", "type": "boolean", "label": "Own agricultural land?", "required": False},
                ],
                "is_final": True,
            },
        ],
    },
}
