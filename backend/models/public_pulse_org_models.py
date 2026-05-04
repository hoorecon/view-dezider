"""Pydantic models + admin-configurable defaults for Public Pulse Phase 2.

Phase 2 adds: Org registration & verification, Admin moderation queue,
Org dashboard, Rectification workflow.

All of the following are admin-configurable at runtime via
`pp_admin_config` MongoDB collection (routes/public_pulse_org.py exposes
CRUD for admins):
  - Org application eligibility rules (per org-type)
  - Re-apply cooldown days (per org-type)
  - Feedback visibility within an org (per org-type)
  - Feedback auto-routing preferences (per org-type)
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ────────────────────────────────────────────
# Org types & statuses
# ────────────────────────────────────────────

ORG_TYPES = [
    {"code": "ngo", "label": "NGO / Non-Profit", "icon": "heart-circle"},
    {"code": "msme", "label": "MSME / Small Business", "icon": "business"},
    {"code": "industry_association", "label": "Industry Association", "icon": "people-circle"},
    {"code": "govt_dept", "label": "Government Department", "icon": "shield-checkmark"},
    {"code": "political_org", "label": "Political Organization", "icon": "flag"},
    {"code": "education_institute", "label": "Educational Institution", "icon": "school"},
    {"code": "media", "label": "Media / Press", "icon": "newspaper"},
    {"code": "other", "label": "Other", "icon": "ellipsis-horizontal-circle"},
]

ORG_STATUSES = ["pending", "approved", "rejected", "suspended"]
ORG_MEMBER_ROLES = ["org_admin", "org_member"]


# ────────────────────────────────────────────
# Admin-configurable defaults
# ────────────────────────────────────────────
#
# These are seeded once via POST /api/public-pulse/admin/config/init
# and can be updated via PUT /api/public-pulse/admin/config.
# Per-org-type overrides supported — lookup is: org_type -> key;
# if absent, fall back to the `default` block.

DEFAULT_ADMIN_CONFIG = {
    # Eligibility rules for who can submit an org application
    "application_eligibility": {
        "default": {
            "require_login": True,        # always True (forced)
            "require_tool_use": False,    # must have completed ≥1 Public Pulse tool session
            "require_email_verified": True,
        },
        "overrides": {
            # Govt depts should be verified more strictly; trial allowed looser for pilot
            "govt_dept": {"require_email_verified": True, "require_tool_use": False},
            "political_org": {"require_email_verified": True, "require_tool_use": True},
            "other": {"require_email_verified": True, "require_tool_use": True},
        },
    },

    # Re-apply cooldown days after a rejection
    "reapply_cooldown_days": {
        "default": 7,
        "overrides": {
            "govt_dept": 30,
            "political_org": 14,
            "industry_association": 10,
        },
    },

    # Within an approved org, who sees incoming feedback items?
    #   "all_members"  — every member of the org
    #   "admin_only"   — only org_admins
    #   "first_come"   — visible to all until one claims; then only to that person + org_admins
    "feedback_visibility": {
        "default": "all_members",
        "overrides": {
            "govt_dept": "admin_only",
            "political_org": "admin_only",
            "msme": "first_come",
        },
    },

    # Auto-routing preferences — controls whether citizen is asked to confirm
    # fuzzy / district-match routes.
    "feedback_routing": {
        "default": {
            "auto_route_exact_match": True,    # exact display_name match → auto
            "confirm_fuzzy_match": True,       # fuzzy → ask citizen to pick from top 3
            "confirm_district_match": True,    # district-match fallback also asks citizen
            "suggestion_count": 3,             # how many candidates to surface
        },
        "overrides": {},  # per-org-type overrides optional
    },
}


class AdminConfigUpdate(BaseModel):
    key: str    # e.g., "application_eligibility"
    value: Any  # replacement sub-document


# ────────────────────────────────────────────
# Org Application
# ────────────────────────────────────────────

class OrgApplicationSubmit(BaseModel):
    org_type: str
    display_name: str
    legal_name: Optional[str] = None
    about: Optional[str] = None  # short pitch / what they do
    website: Optional[str] = None
    email: str
    phone: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    categories: List[str] = []  # e.g., ["education", "skills", "employment"]
    # Documents — base64 encoded (max ~5MB each, enforced in route)
    verification_doc_b64: Optional[str] = None       # registration cert
    verification_doc_name: Optional[str] = None
    authorized_id_b64: Optional[str] = None          # applicant's ID
    authorized_id_name: Optional[str] = None
    # For white-label portal (used in Phase 3)
    brand_logo_b64: Optional[str] = None
    brand_color: Optional[str] = None


class OrgApplication(BaseModel):
    application_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: Optional[str] = None  # populated once approved
    user_id: str                  # the applicant
    org_type: str
    display_name: str
    legal_name: Optional[str] = None
    about: Optional[str] = None
    website: Optional[str] = None
    email: str
    phone: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    categories: List[str] = []
    verification_doc_b64: Optional[str] = None
    verification_doc_name: Optional[str] = None
    authorized_id_b64: Optional[str] = None
    authorized_id_name: Optional[str] = None
    brand_logo_b64: Optional[str] = None
    brand_color: Optional[str] = None
    status: str = "pending"       # pending | approved | rejected
    rejection_reason: Optional[str] = None
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    submitted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OrgApplicationReview(BaseModel):
    decision: str  # "approve" | "reject"
    reason: Optional[str] = None


# ────────────────────────────────────────────
# Approved Org (post-approval active record)
# ────────────────────────────────────────────

class PPOrg(BaseModel):
    org_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    application_id: str
    owner_user_id: str
    org_type: str
    display_name: str
    legal_name: Optional[str] = None
    about: Optional[str] = None
    website: Optional[str] = None
    email: str
    phone: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    categories: List[str] = []
    brand_logo_b64: Optional[str] = None
    brand_color: Optional[str] = None
    status: str = "approved"
    approved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Phase 2+
    slug: Optional[str] = None  # for white-label URLs in Phase 3
    # Analytics
    active_member_count: int = 1
    total_feedback_handled: int = 0


class PPOrgMember(BaseModel):
    member_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    org_id: str
    user_id: str
    role: str = "org_member"
    added_by: str
    added_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OrgInviteRequest(BaseModel):
    email: str
    role: str = "org_member"


# ────────────────────────────────────────────
# Feedback routing (Phase 2 additions)
# ────────────────────────────────────────────

# Extension fields on pp_feedback_items:
#   routing_status: "unrouted" | "auto_routed" | "awaiting_citizen_confirm" | "routed" | "escalated_to_admin"
#   suggested_orgs: [{org_id, display_name, reason, score}]  (when fuzzy match)
#   assigned_org_id, claimed_by_user_id, claimed_at
#   sla_target_days, sla_breach_at

class FeedbackRoutingConfirm(BaseModel):
    org_id: str  # citizen-picked from suggestions


class FeedbackOrgAction(BaseModel):
    action: str  # "acknowledge" | "respond" | "action_taken" | "close" | "reopen"
    response_text: Optional[str] = None
    action_taken_description: Optional[str] = None
    action_taken_date: Optional[datetime] = None


FEEDBACK_ACTION_TRANSITIONS = {
    "acknowledge": {"from": ["new", "auto_routed", "awaiting_citizen_confirm", "routed"], "to": "acknowledged"},
    "respond":   {"from": ["acknowledged", "action_pending"], "to": "responded"},
    "action_taken": {"from": ["acknowledged", "responded", "action_pending"], "to": "action_taken"},
    "close": {"from": ["responded", "action_taken", "resolution_review"], "to": "closed"},
    "reopen": {"from": ["closed"], "to": "reopened"},
}
