"""
ReviewNet — default qualitative factor templates.

Each entry maps a SCOPE (life_area_id or sub_area_id or catalog_node_id)
to a set of qualitative factors that solutions falling under it inherit.

Factors are RESOLVED hierarchically: solution-specific > catalog L3/L2 >
sub_area (L1) > life_area (L0) > global. Closer scope wins; a child scope
appends to (does not replace) the ancestor's factors unless it explicitly
defines a factor with the same slug.
"""
from __future__ import annotations

from typing import Dict, List


# ---------------------------------------------------------------------------
# GLOBAL — apply to every solution if no closer scope overrides
# ---------------------------------------------------------------------------
GLOBAL_FACTORS: List[dict] = [
    {"slug": "value_for_money", "name": "Value for Money", "description": "Did the price feel justified by what you got?"},
    {"slug": "communication", "name": "Communication", "description": "How responsive and clear was the provider?"},
    {"slug": "reliability", "name": "Reliability", "description": "Did they deliver what they promised, on time?"},
    {"slug": "trustworthiness", "name": "Trustworthiness", "description": "How honest and transparent were they?"},
]


# ---------------------------------------------------------------------------
# Per LIFE-AREA defaults (L0)
# ---------------------------------------------------------------------------
LIFE_AREA_FACTORS: Dict[str, List[dict]] = {
    "la_finance": [
        {"slug": "fee_transparency", "name": "Fee Transparency", "description": "Hidden costs, unclear fees?"},
        {"slug": "advisor_competence", "name": "Advisor Competence", "description": "Did they explain risks clearly?"},
        {"slug": "ease_of_onboarding", "name": "Ease of Onboarding", "description": "How simple was getting started?"},
    ],
    "la_health": [
        {"slug": "wait_time", "name": "Wait Time"},
        {"slug": "facility_hygiene", "name": "Facility Hygiene"},
        {"slug": "doctor_empathy", "name": "Care-giver Empathy"},
        {"slug": "follow_up_care", "name": "Follow-up Care"},
    ],
    "la_career": [
        {"slug": "career_growth_support", "name": "Career Growth Support"},
        {"slug": "feedback_quality", "name": "Feedback Quality"},
        {"slug": "team_culture", "name": "Team Culture"},
    ],
    "la_knowledge": [
        {"slug": "teaching_quality", "name": "Teaching Quality"},
        {"slug": "curriculum_relevance", "name": "Curriculum Relevance"},
        {"slug": "mentor_support", "name": "Mentor Support"},
    ],
    "la_relationships": [
        {"slug": "honesty", "name": "Honesty"},
        {"slug": "compatibility", "name": "Compatibility"},
        {"slug": "family_compatibility", "name": "Family Compatibility"},
    ],
    "la_assets": [
        {"slug": "build_quality", "name": "Build Quality"},
        {"slug": "after_sales_service", "name": "After-Sales Service"},
        {"slug": "documentation", "name": "Documentation / Paperwork"},
    ],
}


# ---------------------------------------------------------------------------
# Per SUB-AREA refinements (L1) — override / extend life-area defaults
# ---------------------------------------------------------------------------
SUB_AREA_FACTORS: Dict[str, List[dict]] = {
    # ---- Finance ----
    "sa_fin_savings": [
        {"slug": "interest_consistency", "name": "Interest Pay-out Consistency"},
        {"slug": "premature_withdrawal_ease", "name": "Premature Withdrawal Ease"},
    ],
    "sa_fin_investments": [
        {"slug": "risk_clarity", "name": "Risk Clarity"},
        {"slug": "long_term_returns", "name": "Long-term Returns vs Promised"},
    ],
    "sa_fin_risk": [
        {"slug": "claim_settlement_speed", "name": "Claim Settlement Speed"},
        {"slug": "claim_rejection_clarity", "name": "Claim Rejection Clarity"},
        {"slug": "policy_documentation", "name": "Policy Documentation"},
    ],
    "sa_fin_debt": [
        {"slug": "interest_rate_fairness", "name": "Interest Rate Fairness"},
        {"slug": "loan_processing_speed", "name": "Loan Processing Speed"},
        {"slug": "prepayment_friendliness", "name": "Prepayment Friendliness"},
    ],
    "sa_fin_planning": [
        {"slug": "advisor_unbiasedness", "name": "Advisor Unbiasedness"},
        {"slug": "report_clarity", "name": "Report Clarity"},
    ],

    # ---- Career ----
    "sa_car_job": [
        {"slug": "interview_experience", "name": "Interview Experience"},
        {"slug": "compensation_fairness", "name": "Compensation Fairness"},
        {"slug": "work_life_balance", "name": "Work-life Balance"},
    ],
    "sa_car_business": [
        {"slug": "founder_responsiveness", "name": "Founder Responsiveness"},
        {"slug": "vision_clarity", "name": "Vision Clarity"},
    ],
    "sa_car_fundraise": [
        {"slug": "due_diligence_quality", "name": "Due-diligence Quality"},
        {"slug": "term_sheet_fairness", "name": "Term Sheet Fairness"},
        {"slug": "post_investment_support", "name": "Post-Investment Support"},
    ],
    "sa_car_growth": [
        {"slug": "session_punctuality", "name": "Session Punctuality"},
        {"slug": "actionability", "name": "Advice Actionability"},
    ],

    # ---- Knowledge ----
    "sa_kno_education": [
        {"slug": "infrastructure", "name": "Infrastructure"},
        {"slug": "placement_support", "name": "Placement Support"},
        {"slug": "alumni_network", "name": "Alumni Network"},
    ],
    "sa_kno_skills": [
        {"slug": "hands_on_practice", "name": "Hands-on Practice"},
        {"slug": "instructor_expertise", "name": "Instructor Expertise"},
    ],

    # ---- Health ----
    "sa_hlt_preventive": [
        {"slug": "report_turnaround", "name": "Report Turnaround"},
        {"slug": "test_accuracy", "name": "Test Accuracy"},
    ],
    "sa_hlt_lifestyle": [
        {"slug": "instructor_personalization", "name": "Instructor Personalisation"},
        {"slug": "session_consistency", "name": "Session Consistency"},
    ],
    "sa_hlt_physical": [
        {"slug": "diagnosis_accuracy", "name": "Diagnosis Accuracy"},
        {"slug": "treatment_explanation", "name": "Treatment Explanation"},
    ],
    "sa_hlt_mental": [
        {"slug": "session_safe_space", "name": "Sense of Safe Space"},
        {"slug": "tools_provided", "name": "Tools / Coping Strategies"},
    ],

    # ---- Assets ----
    "sa_ast_real_estate": [
        {"slug": "title_clarity", "name": "Title Clarity"},
        {"slug": "construction_quality", "name": "Construction Quality"},
        {"slug": "neighborhood", "name": "Neighborhood"},
        {"slug": "amenities", "name": "Amenities"},
    ],
    "sa_ast_home": [
        {"slug": "punctuality", "name": "Punctuality"},
        {"slug": "tidiness", "name": "Tidiness After Service"},
    ],
    "sa_ast_vehicles": [
        {"slug": "fuel_efficiency", "name": "Fuel / Power Efficiency"},
        {"slug": "ride_comfort", "name": "Ride Comfort"},
        {"slug": "service_network", "name": "Service Network Reach"},
    ],

    # ---- Relationships ----
    "sa_rel_marriage": [
        {"slug": "profile_authenticity", "name": "Profile Authenticity"},
        {"slug": "values_alignment", "name": "Values Alignment"},
    ],
    "sa_rel_parenting": [
        {"slug": "child_engagement", "name": "Child Engagement"},
    ],
}
