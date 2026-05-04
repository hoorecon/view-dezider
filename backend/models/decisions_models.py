"""Pydantic models + static reference data for /routes/decisions.py.

Covers: PRR (10-step) decisions, MPPS action plans, Test123, Mode
Assessment, Decision Journal, Step Sharing.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, Field, EmailStr


# ────────────────────────────────────────────
# PRR Decisions
# ────────────────────────────────────────────

class Factor(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    category: str = "primary"
    rating: int = 0
    order: int = 0
    unit: Optional[str] = None
    expected_value: Optional[Any] = None
    data_type: Optional[str] = None
    operator: Optional[str] = None
    gap_multiplier: Optional[float] = 1.0
    parent_id: Optional[str] = None
    weight: Optional[float] = None


class OptionAssessment(BaseModel):
    factor_id: str
    percentage: Optional[int] = None
    unit_value: Optional[str] = None
    actual_value: Optional[float] = None
    assessment_mode: Optional[str] = None


class MPPSActionItem(BaseModel):
    assignee_name: str = ""
    assignee_email: str = ""
    assignee_mobile: str = ""
    task: str = ""
    deadline: Optional[str] = None


class MPPSImprovement(BaseModel):
    factor_id: str
    original_percentage: Optional[int] = None
    projected_percentage: Optional[int] = None
    delta_percentage: Optional[int] = None
    expected_value: Optional[str] = None
    expected_unit: Optional[str] = None
    improvement_plan: str = ""
    tepfi_elements: List[str] = []
    tepfi_layer: Optional[str] = None
    action_items: List[MPPSActionItem] = []


class DecisionOption(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    assessments: List[OptionAssessment] = []
    worth_percentage: float = 0.0


class PRRDecision(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    title: str
    context: str
    factors: List[Factor] = []
    options: List[DecisionOption] = []
    chosen_option_id: Optional[str] = None
    decision_case: Optional[str] = None
    notes: str = ""
    reflection: str = ""
    final_notes: str = ""
    folder: str = ""
    life_area: Optional[str] = None
    decision_type: Optional[str] = None
    rating_gap_multiplier: float = 1.0
    mpps_option_id: Optional[str] = None
    mpps_improvements: List[MPPSImprovement] = []
    mpps_projected_worth: Optional[float] = None
    mpps_timeframe: Optional[str] = None
    implementation_review_date: Optional[datetime] = None
    status: str = "draft"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PRRDecisionCreate(BaseModel):
    title: str
    context: str
    folder: str = ""
    life_area: Optional[str] = None
    decision_type: Optional[str] = None
    implementation_review_date: Optional[datetime] = None


class PRRDecisionUpdate(BaseModel):
    title: Optional[str] = None
    context: Optional[str] = None
    factors: Optional[List[Factor]] = None
    options: Optional[List[DecisionOption]] = None
    chosen_option_id: Optional[str] = None
    decision_case: Optional[str] = None
    notes: Optional[str] = None
    reflection: Optional[str] = None
    final_notes: Optional[str] = None
    folder: Optional[str] = None
    rating_gap_multiplier: Optional[float] = None
    mpps_option_id: Optional[str] = None
    mpps_improvements: Optional[List[MPPSImprovement]] = None
    mpps_projected_worth: Optional[float] = None
    mpps_timeframe: Optional[str] = None
    life_area: Optional[str] = None
    decision_type: Optional[str] = None
    implementation_review_date: Optional[datetime] = None
    status: Optional[str] = None


class CloneDecisionRequest(BaseModel):
    title: str
    clone_level: str


# ────────────────────────────────────────────
# Decision Templates
# ────────────────────────────────────────────

class SaveTemplateRequest(BaseModel):
    name: str
    template_type: str = "options"
    visibility: str = "private"
    shared_with: List[str] = []


class UseTemplateRequest(BaseModel):
    title: str


# ────────────────────────────────────────────
# Admin (user role management)
# ────────────────────────────────────────────

class PromoteUserRequest(BaseModel):
    email: EmailStr
    role: str


class DemoteUserRequest(BaseModel):
    email: EmailStr


# ────────────────────────────────────────────
# Test123 (Quick decisions)
# ────────────────────────────────────────────

class Test123Session(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    situation: str
    is_emotional: Optional[bool] = None
    what_i_want: str = ""
    worst_case_scenario: str = ""
    ready_for_worst: Optional[bool] = None
    all_needs: List[str] = []
    important_needs: List[str] = []
    action_plan: str = ""
    final_decision: str = ""
    completed_test: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Test123Create(BaseModel):
    situation: str


class Test123Update(BaseModel):
    is_emotional: Optional[bool] = None
    what_i_want: Optional[str] = None
    worst_case_scenario: Optional[str] = None
    ready_for_worst: Optional[bool] = None
    all_needs: Optional[List[str]] = None
    important_needs: Optional[List[str]] = None
    action_plan: Optional[str] = None
    final_decision: Optional[str] = None
    completed_test: Optional[int] = None


# ────────────────────────────────────────────
# Decision Mode Assessment
# ────────────────────────────────────────────

class ModeAssessmentCreate(BaseModel):
    answers: Dict[str, int]


class ModeAssessmentResult(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    answers: Dict[str, int]
    dominant_mode: str
    mode_scores: Dict[str, float]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ────────────────────────────────────────────
# Decision Journal
# ────────────────────────────────────────────

VALID_LINKED_MODULES = ["decision", "solution_finder", "solution_matrix", "gem", "ctt", "lifestyle"]
VALID_ENTRY_TYPES = ["best_practice", "learning"]


class JournalEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    decision_title: str
    decision_description: str
    linked_module: Optional[str] = None
    linked_id: Optional[str] = None
    linked_title: Optional[str] = None
    entry_type: Optional[str] = None
    outcome: str = ""
    outcome_rating: int = 0
    lessons_learned: str = ""
    failure_reasons: List[str] = []
    status: str = "pending"
    decision_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    outcome_date: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JournalEntryCreate(BaseModel):
    decision_title: str
    decision_description: str
    linked_module: Optional[str] = None
    linked_id: Optional[str] = None
    linked_title: Optional[str] = None
    entry_type: Optional[str] = None
    decision_date: Optional[datetime] = None


class JournalEntryUpdate(BaseModel):
    decision_title: Optional[str] = None
    decision_description: Optional[str] = None
    linked_module: Optional[str] = None
    linked_id: Optional[str] = None
    linked_title: Optional[str] = None
    entry_type: Optional[str] = None
    outcome: Optional[str] = None
    outcome_rating: Optional[int] = None
    lessons_learned: Optional[str] = None
    failure_reasons: Optional[List[str]] = None
    status: Optional[str] = None
    outcome_date: Optional[datetime] = None


# ────────────────────────────────────────────
# Step Sharing
# ────────────────────────────────────────────

class ShareStepRequest(BaseModel):
    decision_id: str
    step_number: int
    recipient_emails: List[str]
    merge_mode: str = "equal"
    custom_weights: Optional[dict] = None
    message: str = ""


class ContributeStepRequest(BaseModel):
    factors: Optional[List[dict]] = None
    options: Optional[List[dict]] = None
    assessments: Optional[dict] = None
    note: str = ""


class MergeStepRequest(BaseModel):
    merge_mode: str = "equal"
    custom_weights: Optional[dict] = None


class NotificationCreate(BaseModel):
    user_id: str
    type: str
    title: str
    message: str
    data: Optional[dict] = None


# ────────────────────────────────────────────
# Reference data (static)
# ────────────────────────────────────────────

DECISION_FOLDERS = [
    {"id": "holistic_health", "name": "Holistic Health", "icon": "fitness", "color": "#10B981"},
    {"id": "knowledge_skills", "name": "Knowledge & Skills", "icon": "book", "color": "#3B82F6"},
    {"id": "relationships", "name": "Relationships", "icon": "heart", "color": "#EC4899"},
    {"id": "finance", "name": "Finance", "icon": "cash", "color": "#F59E0B"},
    {"id": "assets", "name": "Assets", "icon": "home", "color": "#8B5CF6"},
    {"id": "career", "name": "Career", "icon": "briefcase", "color": "#6366F1"},
    {"id": "hobbies_entertainment", "name": "Hobbies & Entertainment", "icon": "game-controller", "color": "#14B8A6"},
    {"id": "social_image", "name": "Social Image & Influence", "icon": "star", "color": "#F97316"},
    {"id": "social_contributions", "name": "Social Contributions", "icon": "people", "color": "#06B6D4"},
    {"id": "spirituality_religion", "name": "Spirituality & Religion", "icon": "leaf", "color": "#A855F7"},
]

ASSESSMENT_QUESTIONS = [
    {"id": "q1", "text": "When faced with a decision, I usually go with my gut feeling.", "mode": "intuitive"},
    {"id": "q2", "text": "I prefer to analyze all available data before deciding.", "mode": "logical"},
    {"id": "q3", "text": "My decisions are often influenced by how I feel at the moment.", "mode": "emotional"},
    {"id": "q4", "text": "I can detach myself from emotions when making important decisions.", "mode": "awareness"},
    {"id": "q5", "text": "I trust my instincts even when logic suggests otherwise.", "mode": "intuitive"},
    {"id": "q6", "text": "I create pros and cons lists for major decisions.", "mode": "logical"},
    {"id": "q7", "text": "I often regret decisions made when I was upset or excited.", "mode": "emotional"},
    {"id": "q8", "text": "I can observe my thoughts without being controlled by them.", "mode": "awareness"},
    {"id": "q9", "text": "I often know the right decision without knowing why.", "mode": "intuitive"},
    {"id": "q10", "text": "I need concrete evidence to make a decision.", "mode": "logical"},
    {"id": "q11", "text": "My mood significantly affects my decision-making.", "mode": "emotional"},
    {"id": "q12", "text": "I practice mindfulness or meditation regularly.", "mode": "awareness"},
]
