"""
ReviewNet — domain models.

Public reviews on the QUALITATIVE / SUBJECTIVE factors of every Solution Store
item (products, services, events, projects, people). Quantitative factors stay
out of scope here — they are objectively comparable in the Solution Store.

Reviewer segmentation: 3 top-level segments × 1 sub-level each
  - INDIVIDUAL    → customer | observer | expert
  - ORGANIZATION  → business_corporate | educational_institution | ngo_nonprofit
  - GOVERNMENT    → regulator | local_body | central_state_dept

Eligibility policy (per solution, configurable by publisher, admin can override):
  - ALL_AUTHENTICATED   (default)
  - VERIFIED_BUYERS_ONLY
  - INVITED_ONLY
  - EMPLOYEES_ONLY
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, conint, field_validator


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SEGMENTS = ("individual", "organization", "government")

SUBSEGMENTS_BY_SEGMENT: Dict[str, tuple[str, ...]] = {
    "individual": ("customer", "observer", "expert"),
    "organization": ("business_corporate", "educational_institution", "ngo_nonprofit"),
    "government": ("regulator", "local_body", "central_state_dept"),
}
ALL_SUBSEGMENTS = tuple(s for v in SUBSEGMENTS_BY_SEGMENT.values() for s in v)

ELIGIBILITY_POLICIES = (
    "ALL_AUTHENTICATED",
    "VERIFIED_BUYERS_ONLY",
    "INVITED_ONLY",
    "EMPLOYEES_ONLY",
)

REVIEW_STATUSES = ("pending", "approved", "rejected", "auto_approved")
RULE_ACTIONS = ("AUTO_APPROVE", "HOLD_FOR_ADMIN", "AUTO_REJECT")


# ---------------------------------------------------------------------------
# Qualitative factor templates
# ---------------------------------------------------------------------------
class QualitativeFactor(BaseModel):
    factor_id: str
    name: str
    slug: str
    description: Optional[str] = None
    scope_type: Literal["global", "catalog_node", "solution"] = "catalog_node"
    scope_id: Optional[str] = None    # life_area_id / sub_area_id / catalog_node_id / solution_id
    sort_order: int = 0
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class QualitativeFactorCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    slug: Optional[str] = Field(None, max_length=60)
    description: Optional[str] = Field(None, max_length=300)
    scope_type: Literal["global", "catalog_node", "solution"] = "catalog_node"
    scope_id: Optional[str] = None
    sort_order: int = 0


class QualitativeFactorUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=80)
    description: Optional[str] = Field(None, max_length=300)
    sort_order: Optional[int] = None
    is_active: Optional[bool] = None


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------
StarRating = conint(ge=1, le=5)


class ReviewSubmit(BaseModel):
    solution_id: str
    reviewer_segment: Literal["individual", "organization", "government"] = "individual"
    reviewer_subsegment: Optional[str] = None     # validated server-side against segment
    factor_ratings: Dict[str, int]                 # { factor_id: 1..5 }
    comment: Optional[str] = Field(None, max_length=2000)
    title: Optional[str] = Field(None, max_length=120)

    @field_validator("factor_ratings")
    @classmethod
    def _ratings_in_range(cls, v: Dict[str, int]) -> Dict[str, int]:
        for fid, rating in v.items():
            if not isinstance(rating, int) or rating < 1 or rating > 5:
                raise ValueError(f"rating for {fid} must be int 1..5")
        if not v:
            raise ValueError("at least one factor rating required")
        return v


class ReviewModerate(BaseModel):
    decision: Literal["approve", "reject"]
    note: Optional[str] = Field(None, max_length=500)


class HelpfulVote(BaseModel):
    helpful: bool


class OwnerReply(BaseModel):
    content: str = Field(..., min_length=1, max_length=1000)


# ---------------------------------------------------------------------------
# Eligibility policy
# ---------------------------------------------------------------------------
class EligibilityPolicy(BaseModel):
    policy: Literal["ALL_AUTHENTICATED", "VERIFIED_BUYERS_ONLY", "INVITED_ONLY", "EMPLOYEES_ONLY"] = "ALL_AUTHENTICATED"
    allowed_segments: List[str] = Field(default_factory=lambda: list(SEGMENTS))
    invited_user_ids: Optional[List[str]] = None
    employee_org_ids: Optional[List[str]] = None
    admin_overridden: bool = False


# ---------------------------------------------------------------------------
# Moderation auto-rules
# ---------------------------------------------------------------------------
class ModerationRuleCondition(BaseModel):
    """One rule = AND of conditions; first-matching rule wins."""
    field: Literal[
        "rating_min",            # all factor ratings >= value
        "rating_max",            # all factor ratings <= value
        "overall_min",           # average rating >= value (computed)
        "overall_max",           # average rating <= value
        "comment_max_length",    # len(comment) <= value
        "is_verified_buyer",     # equals bool
        "reviewer_min_prior_approved",   # reviewer has >= N approved past reviews
        "comment_contains_blocklist",    # comment lowercase contains any of value (list)
    ]
    op: Literal["eq", "gte", "lte", "in"] = "eq"
    value: Any


class ModerationRule(BaseModel):
    rule_id: Optional[str] = None
    name: str
    description: Optional[str] = None
    conditions: List[ModerationRuleCondition]
    action: Literal["AUTO_APPROVE", "HOLD_FOR_ADMIN", "AUTO_REJECT"]
    priority: int = 100   # lower = higher priority
    is_active: bool = True


class ModerationRuleCreate(BaseModel):
    name: str
    description: Optional[str] = None
    conditions: List[ModerationRuleCondition]
    action: Literal["AUTO_APPROVE", "HOLD_FOR_ADMIN", "AUTO_REJECT"]
    priority: int = 100


class ModerationRuleUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    conditions: Optional[List[ModerationRuleCondition]] = None
    action: Optional[Literal["AUTO_APPROVE", "HOLD_FOR_ADMIN", "AUTO_REJECT"]] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
